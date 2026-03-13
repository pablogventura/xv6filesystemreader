#!/usr/bin/env python3
"""
Mount an xv6 disk image as a FUSE file system on Linux.
Usage: python3 fusereader.py <image> <mount_point> [--write]
"""

import errno
import os
import stat
import sys

from fuse import FUSE, FuseOSError, Operations

from reader import DiscImage, Directory, File

# Constants for st_mode (file types)
S_IFDIR = 0o040000
S_IFREG = 0o100000
S_IFCHR = 0o020000


class XV6Fuse(Operations):
    def __init__(self, image_path, writable=False):
        self.image_path = image_path
        self.writable = writable
        self.disc = DiscImage(image_path, writable=writable)
        self._written_paths = set()  # paths modified for sync on release

    def _resolve(self, path):
        """Resolve a FUSE path (e.g. /init, /etc/hostname) to the corresponding node."""
        path = path or "/"
        if path == "/":
            return self.disc.inodes.root_inode.to_file("/")
        return self.disc.resolve_path(path)

    def getattr(self, path, fh=None):
        path = path or "/"
        node = self._resolve(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        ino = node.inode.number
        nlink = node.inode.nlink
        size = getattr(node, "size", node.inode.size)
        now = 1636280338  # xv6 does not store timestamps
        if node.inode.is_dir():
            return {
                "st_atime": now,
                "st_ctime": now,
                "st_mtime": now,
                "st_gid": 0,
                "st_mode": S_IFDIR | 0o755,
                "st_nlink": max(nlink, 2),
                "st_size": 0,
                "st_uid": 0,
                "st_ino": ino,
            }
        if node.inode.is_file():
            return {
                "st_atime": now,
                "st_ctime": now,
                "st_mtime": now,
                "st_gid": 0,
                "st_mode": S_IFREG | 0o644,
                "st_nlink": nlink,
                "st_size": size,
                "st_uid": 0,
                "st_ino": ino,
            }
        # Device (T_DEV)
        return {
            "st_atime": now,
            "st_ctime": now,
            "st_mtime": now,
            "st_gid": 0,
            "st_mode": S_IFCHR | 0o666,
            "st_nlink": nlink,
            "st_size": 0,
            "st_uid": 0,
            "st_ino": ino,
            "st_rdev": (node.inode.major << 8) | node.inode.minor,
        }

    def readdir(self, path, fh=None):
        path = path or "/"
        node = self._resolve(path)
        if node is None or not node.inode.is_dir():
            raise FuseOSError(errno.ENOENT)
        yield "."
        yield ".."
        for f in node.files:
            yield f.name

    def open(self, path, flags):
        path = path or "/"
        node = self._resolve(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        if node.inode.is_dir():
            # FUSE opens dirs for readdir; we don't need fh
            return 0
        # For files/devices we use the path as fh for read/write
        return path

    def read(self, path, length, offset, fh):
        path = path or "/"
        node = self._resolve(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        if node.inode.is_dir():
            raise FuseOSError(errno.EISDIR)
        data = node.read()
        if offset >= len(data):
            return b""
        return data[offset : offset + length]

    def write(self, path, buf, offset, fh):
        if not self.writable:
            raise FuseOSError(errno.EROFS)
        path = path or "/"
        node = self._resolve(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        if not node.inode.is_file():
            raise FuseOSError(errno.EISDIR if node.inode.is_dir() else errno.EPERM)
        # Write at offset: read full content, splice in buf, write back
        content = node.read()
        end = offset + len(buf)
        if end > len(content):
            content = content.ljust(end, b"\x00")
        content = content[:offset] + buf + content[end:]
        node.write(content)
        self._written_paths.add(path)
        return len(buf)

    def release(self, path, fh):
        if path and path in self._written_paths:
            self._written_paths.discard(path)
            self.disc.sync()

    def destroy(self, path=None):
        """On unmount, flush the image if there were writes."""
        if self._written_paths:
            self.disc.sync()
            self._written_paths.clear()

    def statfs(self, path):
        sb = self.disc.superblock
        return {
            "f_bavail": sb.nblocks,  # approximate
            "f_bfree": sb.nblocks,
            "f_blocks": sb.size,
            "f_bsize": 512,
            "f_favail": sb.ninodes,
            "f_ffree": sb.ninodes,
            "f_files": sb.ninodes,
            "f_flag": 0,
            "f_frsize": 512,
            "f_namemax": 255,
        }


def main():
    if len(sys.argv) < 3:
        print("Usage: %s <xv6_image> <mount_point> [--write]" % sys.argv[0], file=sys.stderr)
        print("  --write  allow modifying files (writes are saved to the image)", file=sys.stderr)
        sys.exit(1)
    image_path = sys.argv[1]
    mount_point = sys.argv[2]
    writable = "--write" in sys.argv or "-w" in sys.argv
    if not os.path.isfile(image_path):
        print("Image file not found: %s" % image_path, file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(mount_point):
        print("Mount point does not exist or is not a directory: %s" % mount_point, file=sys.stderr)
        sys.exit(1)
    FUSE(
        XV6Fuse(image_path, writable=writable),
        mount_point,
        nothreads=True,
        foreground=True,
        allow_other=False,
    )


if __name__ == "__main__":
    main()
