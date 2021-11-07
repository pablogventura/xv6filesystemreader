#!/usr/bin/env python

import struct
import os
import sys
import errno

from fuse import FUSE, FuseOSError, Operations, fuse_get_context




#define T_DIR  1   // Directory
#define T_FILE 2   // File
#define T_DEV  3   // Device

NDIRECT = 12 # cantidad de bloques directos
dirsiz = 14 # bytes de una entrada de directorio

def leer(offset, size=None):
    if not size:
        return rawdata[offset:]
    else:
        return rawdata[offset:offset+size]


class SuperBlock(object):
    #dado por la especificacion del filesystem
    #  uint size;         // Size of file system image (blocks)
    #  uint nblocks;      // Number of data blocks
    #  uint ninodes;      // Number of inodes.
    #  uint nlog;         // Number of log blocks
    #  uint logstart;     // Block number of first log block
    #  uint inodestart;   // Block number of first inode block
    #  uint bmapstart;    // Block number of first free map block
    def __init__(self):
        self.size, self.nblocks, self.ninodes, self.nlog, self.logstart, self.inodestart, self.bmapstart = struct.unpack_from('I'*7, leer(512,4*7))



class Inode(object):
    #struct dinode {
    #  short type;           // File type
    #  short major;          // Major device number (T_DEV only)
    #  short minor;          // Minor device number (T_DEV only)
    #  short nlink;          // Number of links to inode in file system
    #  uint size;            // Size of file (bytes)
    def __init__(self, number):
        self.number = number
        inodo_size = struct.calcsize("hhhhI"+"I"*(NDIRECT + 1))
        self.tipo, self.major, self.minor, self.nlink, self.size, *self.addrs = struct.unpack_from("hhhhI"+"I"*(NDIRECT + 1), leer(sblock.inodestart*512+number*inodo_size))
    
    def is_dir(self):
        return self.tipo == 1
    
    def is_file(self):
        return self.tipo == 2
    
    def is_device(self):
        return self.tipo == 3
    
    def get_indirect_addrs(self):
        data = leer(512*self.addrs[NDIRECT], 512)
        indirect_addrs = [int.from_bytes(data[i:i+4], 'little') 
                          for i in range(0, 512, 4)]
        return indirect_addrs

    def data(self):
        result = b""
        addrs = self.addrs[:NDIRECT] + self.get_indirect_addrs()
        for data_block in addrs:
            if data_block == 0:
                continue
            else:
                result += leer(512*data_block, 512)
        return result[:self.size]
    def __repr__(self):
        return "Inode(number=%s)" % self.number







    
def path_inodo(name, inodo):
    if inodo.is_dir():
        return Directory(name,inodo)
    elif inodo.is_file():
        return File(name, inodo)
    elif inodo.is_device():
        return Device(name, inodo)
    else:
        print(name)
        print(inodo)
        assert False

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
    def __repr__(self):
        return "File(\'%s\', %s)" % (self.name, self.inode)

class Directory(object):
    def __init__(self, name, inode):
        assert inode.is_dir()
        self.name = name
        dirents = inode.data()
        archivos = dict()
        dirents = dirents[16*2:] # tiro . y ..
        while dirents:
            dirent, dirents = dirents[0:16], dirents[16:]
            inum, *namedata = struct.unpack_from("H"+ str(dirsiz) + "c", dirent)
            if inum != 0:
                name = ""
                for c in namedata:
                    if c != b"\x00":
                        name += c.decode("ascii")
                    else:
                        break
                archivos[name] = path_inodo(name,Inode(inum))
        self.archivos = archivos

    def deref_dir(self,path):
        if path == "/":
            return list(self.archivos.keys()) + [".",".."]
        else:
            d, path = path.split("/",1)
            if d in self.archivos:
                return self.archivos[d].deref_dir(path)
            else:
                print("no existe: %s, %s" % (d,path))

        
        
    def __repr__(self):
        return "Directory(\'%s\', %s)" % (self.name, self.inode)
        
        


rawfile = open("fs.img","rb")
rawdata = rawfile.read()

sblock = SuperBlock()

i=0
root_inode = Inode(i)
while not root_inode.is_dir():
    i+=1
    root_inode = Inode(i)

directorio_raiz = Directory("root",root_inode)


path = ["xv6fs"]
def creador(directorio):
    os.mkdir("/".join(path) + "/" + directorio.name)
    path.append(directorio.name)
    for archivo in directorio.archivos:
        if archivo.inode.is_dir():
            creador(archivo)
        elif archivo.inode.is_file():
            f = open("/".join(path) + "/" + archivo.name, "bw")
            f.write(archivo.read())
            f.close()
        else:
            f = open("/".join(path) + "/" + archivo.name, "bw")
            f.write(b"Device file in xv6")
            f.close()

def lspath(path):
    dirs = path.split("/")
    



class Passthrough(Operations):
    def __init__(self, root = None):
        self.root = root

    # Helpers
    # =======



    # Filesystem methods
    # ==================

#    def access(self, path, mode):
#        full_path = self._full_path(path)
#        if not os.access(full_path, mode):
#            raise FuseOSError(errno.EACCES)

#    def chmod(self, path, mode):
#        full_path = self._full_path(path)
#        return os.chmod(full_path, mode)

#    def chown(self, path, uid, gid):
#        full_path = self._full_path(path)
#        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):

#void
#stati(struct inode *ip, struct stat *st)
#{
#  st->dev = ip->dev;
#  st->ino = ip->inum;
#  st->type = ip->type;
#  st->nlink = ip->nlink;
#  st->size = ip->size;
#}

##define T_DIR  1   // Directory
##define T_FILE 2   // File
##define T_DEV  3   // Device

#struct stat {
#  short type;  // Type of file
#  int dev;     // File system's disk device
#  uint ino;    // Inode number
#  short nlink; // Number of links to file
#  uint size;   // Size of file in bytes
#};

        print("getattr(%s,%s)" % (path,fh))
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        print("readdir(%s,%s)" % (path,fh))
        for r in directorio_raiz.deref_dir(path):
            yield r

#    def readlink(self, path):
#        pathname = os.readlink(self._full_path(path))
#        if pathname.startswith("/"):
#            # Path name is absolute, sanitize it.
#            return os.path.relpath(pathname, self.root)
#        else:
#            return pathname

#    def mknod(self, path, mode, dev):
#        return os.mknod(self._full_path(path), mode, dev)

#    def rmdir(self, path):
#        full_path = self._full_path(path)
#        return os.rmdir(full_path)

#    def mkdir(self, path, mode):
#        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        print("statfs de %s" % path)
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

#    def unlink(self, path):
#        return os.unlink(self._full_path(path))

#    def symlink(self, name, target):
#        return os.symlink(target, self._full_path(name))

#    def rename(self, old, new):
#        return os.rename(self._full_path(old), self._full_path(new))

#    def link(self, target, name):
#        return os.link(self._full_path(name), self._full_path(target))

#    def utimens(self, path, times=None):
#        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        full_path = self._full_path(path)
        return os.open(full_path, flags)

#    def create(self, path, mode, fi=None):
#        uid, gid, pid = fuse_get_context()
#        full_path = self._full_path(path)
#        fd = os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)
#        os.chown(full_path,uid,gid) #chown to context uid & gid
#        return fd

    def read(self, path, length, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

#    def write(self, path, buf, offset, fh):
#        os.lseek(fh, offset, os.SEEK_SET)
#        return os.write(fh, buf)

#    def truncate(self, path, length, fh=None):
#        full_path = self._full_path(path)
#        with open(full_path, 'r+') as f:
#            f.truncate(length)

#    def flush(self, path, fh):
#        return os.fsync(fh)

    def release(self, path, fh):
        return os.close(fh)

#    def fsync(self, path, fdatasync, fh):
#        return self.flush(path, fh)


def main():
    FUSE(Passthrough(), "mnt", nothreads=True, foreground=True, allow_other=True, debug=False)


if __name__ == '__main__':
    main()

