import os
import struct

#define T_DIR  1   // Directory
#define T_FILE 2   // File
#define T_DEV  3   // Device

NDIRECT = 12  # number of direct block pointers
dirsiz = 14   # bytes per directory entry
BSIZE = 512
BPB = BSIZE * 8   # bits per bitmap block (4096)
INODE_SIZE = struct.calcsize("hhhhI" + "I" * (NDIRECT + 1))

class SuperBlock(object):
    # xv6 filesystem layout (see fs.h)
    #  uint size;         // Size of file system image (blocks)
    #  uint nblocks;      // Number of data blocks
    #  uint ninodes;      // Number of inodes
    #  uint nlog;         // Number of log blocks
    #  uint logstart;     // Block number of first log block
    #  uint inodestart;   // Block number of first inode block
    #  uint bmapstart;    // Block number of first free map block
    def __init__(self, block):
        self.size, self.nblocks, self.ninodes, self.nlog, self.logstart, self.inodestart, self.bmapstart = struct.unpack_from('I'*7, block)
        self.ninodeblocks = (self.ninodes * INODE_SIZE + BSIZE - 1) // BSIZE
        self.bitmap_blocks = (self.nblocks + BPB - 1) // BPB
        self.first_data_block = self.bmapstart + self.bitmap_blocks

class Inode(object):
    #struct dinode {
    #  short type;           // File type
    #  short major;          // Major device number (T_DEV only)
    #  short minor;          // Minor device number (T_DEV only)
    #  short nlink;          // Number of links to inode in file system
    #  uint size;            // Size of file (bytes)
    def __init__(self, number, raw_inode, disc):
        
        self.number = number
        self.tipo, self.major, self.minor, self.nlink, self.size, *self.addrs = struct.unpack_from("hhhhI"+"I"*(NDIRECT + 1), raw_inode)
        self.disc = disc
    
    def is_dir(self):
        return self.tipo == 1
    
    def is_file(self):
        return self.tipo == 2
    
    def is_device(self):
        return self.tipo == 3
    
    def get_indirect_addrs(self):
        if self.addrs[NDIRECT] == 0:
            return []
        data = self.disc.block(self.addrs[NDIRECT])
        indirect_addrs = [int.from_bytes(data[i:i+4], 'little') 
                          for i in range(0, 512, 4)]
        return indirect_addrs

    def _all_addrs(self):
        """List of block numbers (direct + indirect) up to the first 0."""
        addrs = list(self.addrs[:NDIRECT])
        if self.addrs[NDIRECT] != 0:
            addrs.extend(self.get_indirect_addrs())
        return addrs

    def data(self):
        result = b""
        for data_block in self._all_addrs():
            if data_block != 0:
                result += self.disc.block(data_block)
            else:
                break
        return result[:self.size]

    def write_back(self):
        """Write the current inode back to disk."""
        raw = struct.pack("hhhhI", self.tipo, self.major, self.minor, self.nlink, self.size)
        raw += struct.pack("I" * (NDIRECT + 1), *self.addrs)
        assert len(raw) == INODE_SIZE
        block_idx = self.disc.superblock.inodestart + (self.number * INODE_SIZE) // BSIZE
        offset_in_block = (self.number * INODE_SIZE) % BSIZE
        base = block_idx * BSIZE + offset_in_block
        self.disc.rawdata[base:base + INODE_SIZE] = raw

    def __repr__(self):
        return "Inode(number=%s)" % self.number
        
    def to_file(self,name):
        if self.is_dir():
            return Directory(name,self,self.disc.inodes)
        elif self.is_file():
            return File(name, self)
        elif self.is_device():
            return Device(name, self)
        else:
            print(name)
            print(self)
            assert False

class InodesBlocks(object):
    def __init__(self,rawblocks,disc):
        self.rawblocks = rawblocks
        self.disc = disc

        i=0
        self.root_inode = self.inode(i)
        while not self.root_inode.is_dir():
            i+=1
            self.root_inode = self.inode(i)
            
    def raw_inode(self,index):
        return self.rawblocks[index*INODE_SIZE:(index+1)*INODE_SIZE]
    def inode(self,index):
        return Inode(index, self.raw_inode(index), self.disc)

class DiscImage(object):
    def __init__(self, path, writable=False):
        self.path = path
        with open(path, "rb") as f:
            self.rawdata = bytearray(f.read())
        self.writable = writable
        self.superblock = SuperBlock(self.block(1))
        self.inodes = InodesBlocks(self.blocks(self.superblock.inodestart, self.superblock.ninodeblocks), self)

    def block(self, index):
        return bytes(self.rawdata[index * BSIZE:(index + 1) * BSIZE])

    def blocks(self, index, quantity):
        return bytes(self.rawdata[index * BSIZE:index * BSIZE + BSIZE * quantity])

    def write_block(self, index, data):
        """Write exactly BSIZE bytes to the block at index."""
        if not self.writable:
            raise RuntimeError("Image opened read-only")
        data = bytes(data)[:BSIZE].ljust(BSIZE, b"\x00")
        self.rawdata[index * BSIZE:index * BSIZE + BSIZE] = data

    def balloc(self):
        """Allocate a data block; return the block number."""
        if not self.writable:
            raise RuntimeError("Image opened read-only")
        sb = self.superblock
        for bi in range(sb.nblocks):
            bm_block = sb.bmapstart + bi // BPB
            bit = bi % BPB
            off = bm_block * BSIZE + bit // 8
            byte_val = self.rawdata[off]
            if (byte_val & (1 << (bit % 8))) == 0:
                self.rawdata[off] = byte_val | (1 << (bit % 8))
                return sb.first_data_block + bi
        raise RuntimeError("No free blocks in bitmap")

    def bfree(self, block_num):
        """Free a data block."""
        if not self.writable:
            raise RuntimeError("Image opened read-only")
        sb = self.superblock
        bi = block_num - sb.first_data_block
        if bi < 0 or bi >= sb.nblocks:
            return
        bm_block = sb.bmapstart + bi // BPB
        bit = bi % BPB
        off = bm_block * BSIZE + bit // 8
        self.rawdata[off] = self.rawdata[off] & ~(1 << (bit % 8))

    def sync(self):
        """Flush the modified image to the file."""
        if not self.writable:
            return
        with open(self.path, "wb") as f:
            f.write(self.rawdata)

    def inode(self, index):
        return self.inodes.inode(index)

    def open_file(self, path):
        """Open a file by absolute path (e.g. '/init'). Returns File or None."""
        node = self.resolve_path(path)
        return node if node is not None and node.inode.is_file() else None

    def resolve_path(self, path):
        """Resolve an absolute path to a node (Directory, File or Device). '/' = root."""
        parts = [p for p in path.split("/") if p]
        root = self.inodes.root_inode.to_file("/")
        if not isinstance(root, Directory):
            return None
        if not parts:
            return root
        current = root
        for p in parts[:-1]:
            current = current.get(p)
            if current is None or not current.inode.is_dir():
                return None
        return current.get(parts[-1])

    def read(self, offset, size=None):
        if size is None:
            return bytes(self.rawdata[offset:])
        return bytes(self.rawdata[offset:offset + size])


class Device(object):
    def __init__(self, name, inode):
        assert inode.is_device()
        self.name = name
        self.inode = inode
        self.size = inode.size
    def read(self):
        return self.inode.data()
    def __repr__(self):
        return "Device(\'%s\', %s)" % (self.name, self.inode)

class File(object):
    def __init__(self, name, inode):
        assert inode.is_file()
        self.name = name
        self.inode = inode
        self.size = inode.size

    def read(self):
        return self.inode.data()

    def write(self, data):
        """Write data to the file and persist to the image. Requires disc.writable=True."""
        data = bytes(data)
        new_size = len(data)
        disc = self.inode.disc
        if not disc.writable:
            raise RuntimeError("Open the image with writable=True to write")
        sb = disc.superblock
        addrs = self.inode._all_addrs()
        blocks_needed = (new_size + BSIZE - 1) // BSIZE if new_size else 0
        NINDIRECT = BSIZE // 4  # 128 blocks in indirect block

        # Truncate: free excess blocks (already in addrs, do not double-free)
        if blocks_needed < len(addrs):
            for i in range(blocks_needed, len(addrs)):
                if addrs[i] != 0:
                    disc.bfree(addrs[i])
            for i in range(blocks_needed, NDIRECT):
                self.inode.addrs[i] = 0
            if blocks_needed <= NDIRECT:
                if self.inode.addrs[NDIRECT] != 0:
                    disc.bfree(self.inode.addrs[NDIRECT])
                    self.inode.addrs[NDIRECT] = 0
            else:
                ind = self.inode.get_indirect_addrs()
                for j in range(blocks_needed - NDIRECT, len(ind)):
                    ind[j] = 0
                disc.write_block(self.inode.addrs[NDIRECT], struct.pack("I" * 128, *ind))

        # Extend: allocate blocks if needed
        while len(addrs) < blocks_needed:
            if len(addrs) < NDIRECT:
                b = disc.balloc()
                addrs.append(b)
                self.inode.addrs[len(addrs) - 1] = b
            else:
                if self.inode.addrs[NDIRECT] == 0:
                    self.inode.addrs[NDIRECT] = disc.balloc()
                    ind = [0] * 128
                else:
                    ind = self.inode.get_indirect_addrs()
                b = disc.balloc()
                ind[len(addrs) - NDIRECT] = b
                addrs.append(b)
                disc.write_block(self.inode.addrs[NDIRECT], struct.pack("I" * 128, *ind))

        # Write data block by block
        for i in range(blocks_needed):
            start = i * BSIZE
            chunk = data[start:start + BSIZE]
            if len(chunk) < BSIZE:
                chunk = chunk.ljust(BSIZE, b"\x00")
            disc.write_block(addrs[i], chunk)

        self.inode.size = new_size
        self.inode.write_back()
        self.size = new_size

    def __repr__(self):
        return "File(\'%s\', %s)" % (self.name, self.inode)

class Directory(object):
    def __init__(self, name, inode, inodesblock):
        assert inode.is_dir()
        self.inodesblock = inodesblock
        self.name = name
        self.inode = inode
        dirents = inode.data()
        files = []
        dirents = dirents[16*2:]  # skip . and ..
        while dirents:
            dirent, dirents = dirents[0:16], dirents[16:]
            inum, *namedata = struct.unpack_from("H" + str(dirsiz) + "c", dirent)
            if inum != 0:
                ent_name = ""
                for c in namedata:
                    if c != b"\x00":
                        ent_name += c.decode("ascii")
                    else:
                        break
                files.append(self.inodesblock.inode(inum).to_file(ent_name))
        self.files = files

    def get(self, path):
        """Get a file or directory by name (single path component)."""
        for f in self.files:
            if f.name == path:
                return f
        return None

    def open_path(self, path):
        """Open a file by absolute path, e.g. '/init' or '/etc/hostname'. Returns File or None."""
        parts = [p for p in path.split("/") if p]
        if not parts:
            return self
        current = self
        for p in parts[:-1]:
            current = current.get(p)
            if current is None or not current.inode.is_dir():
                return None
        last = current.get(parts[-1])
        if last is not None and last.inode.is_file():
            return last
        return None

    def __repr__(self):
        return "Directory(\'%s\', %s)" % (self.name, self.inode)
        

def main():
    """Extract the xv6 image contents to the current directory (./root/...)."""
    import sys
    img_path = sys.argv[1] if len(sys.argv) > 1 else "fs.img"
    writable = "--write" in sys.argv or "-w" in sys.argv
    disc = DiscImage(img_path, writable=writable)
    root_dir = disc.inodes.root_inode.to_file("root")  # name used for extraction

    path = ["."]

    def extract(dir):
        os.mkdir("/".join(path) + "/" + dir.name)
        path.append(dir.name)
        for f in dir.files:
            if f.inode.is_dir():
                extract(f)
                path.pop()
            elif f.inode.is_file():
                with open("/".join(path) + "/" + f.name, "wb") as output_file:
                    output_file.write(f.read())
            else:
                with open("/".join(path) + "/" + f.name, "wb") as output_file:
                    output_file.write(b"Device file in xv6")
        path.pop()

    extract(root_dir)
    if writable:
        disc.sync()
        print("Image saved.")


if __name__ == "__main__":
    main()


