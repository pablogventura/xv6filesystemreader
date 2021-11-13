import os
import struct

#define T_DIR  1   // Directory
#define T_FILE 2   // File
#define T_DEV  3   // Device

NDIRECT = 12 # cantidad de bloques directos
dirsiz = 14 # bytes de una entrada de directorio
INODE_SIZE = struct.calcsize("hhhhI"+"I"*(NDIRECT + 1))

class SuperBlock(object):
    #dado por la especificacion del filesystem
    #  uint size;         // Size of file system image (blocks)
    #  uint nblocks;      // Number of data blocks
    #  uint ninodes;      // Number of inodes.
    #  uint nlog;         // Number of log blocks
    #  uint logstart;     // Block number of first log block
    #  uint inodestart;   // Block number of first inode block
    #  uint bmapstart;    // Block number of first free map block
    def __init__(self,block):
        self.size, self.nblocks, self.ninodes, self.nlog, self.logstart, self.inodestart, self.bmapstart = struct.unpack_from('I'*7, block)
        self.ninodeblocks = int((self.ninodes * INODE_SIZE)/512)

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
        data = self.disc.block(self.addrs[NDIRECT])
        indirect_addrs = [int.from_bytes(data[i:i+4], 'little') 
                          for i in range(0, 512, 4)]
        return indirect_addrs

    def data(self):
        result = b""
        addrs = self.addrs[:NDIRECT] + self.get_indirect_addrs()
        for data_block in addrs:
            if data_block != 0:
                result += self.disc.block(data_block)
            else:
                break
        return result[:self.size]
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
    def __init__(self, path):
        with open(path,"rb") as rawfile:
            self.rawdata = rawfile.read()
        self.superblock = SuperBlock(self.block(1))
        self.inodes = InodesBlocks(self.blocks(self.superblock.inodestart, self.superblock.ninodeblocks), self)
        
    def block(self, index):
        return self.blocks(index,1)

    def blocks(self, index, quantity):
        return self.rawdata[index*512:index*512+512*quantity]
    
    def inode(self, index):
        return self.inodes.inode(index)
    
    def read(ofset, size=None):
        if not size:
            return self.rawdata[offset:]
        else:
            return self.rawdata[offset:offset+size]


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
    def __init__(self, name, inode, inodesblock):
        assert inode.is_dir()
        self.inodesblock = inodesblock
        self.name = name
        dirents = inode.data()
        files = []
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
                files.append(self.inodesblock.inode(inum).to_file(name))
        self.files = files
    def __repr__(self):
        return "Directory(\'%s\', %s)" % (self.name, self.inode)
        

disc = DiscImage("fs.img")

root_dir = disc.inodes.root_inode.to_file("root")


path = ["."]
def extract(dir):
    os.mkdir("/".join(path) + "/" + dir.name)
    path.append(dir.name)
    for f in dir.files:
        if f.inode.is_dir():
            extract(f)
        elif f.inode.is_file():
            output_file = open("/".join(path) + "/" + f.name, "bw")
            output_file.write(f.read())
            output_file.close()
        else:
            
            output_file = open("/".join(path) + "/" + f.name, "bw")
            output_file.write(b"Device file in xv6")
            output_file.close()

extract(root_dir)


