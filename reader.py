import struct

NDIRECT = 12

f = open("fs.img","rb")


bloques = []
b = f.read(512)
while b:
    if b:
        bloques.append(b)
        b = f.read(512)
bloqueboot = bloques[0] # no se usa
superbloque = bloques[1]

size, nblocks, ninodes, nlog, logstart, inodestart, bmapstart = struct.unpack('I'*7, superbloque[0:4*7] )

#  uint size;         // Size of file system image (blocks)
#  uint nblocks;      // Number of data blocks
#  uint ninodes;      // Number of inodes.
#  uint nlog;         // Number of log blocks
#  uint logstart;     // Block number of first log block
#  uint inodestart;   // Block number of first inode block
#  uint bmapstart;    // Block number of first free map block

bloques[inodestart]
def inodo(bloque, numero):
    inodo_size = struct.calcsize("hhhhI"+"I"*(NDIRECT + 1))
    tipo, major, minor, nlink, size, *addrs = struct.unpack_from("hhhhI"+"I"*(NDIRECT + 1), bloque[numero*inodo_size:])
    return (tipo,major,minor,nlink,size,addrs)

for i in range(8):
    print(inodo(bloques[inodestart],i))
for i in range(8):
    print(inodo(bloques[inodestart+1],i))
for i in range(8):
    print(inodo(bloques[inodestart+2],i))
#struct dinode {
#  short type;           // File type
#  short major;          // Major device number (T_DEV only)
#  short minor;          // Minor device number (T_DEV only)
#  short nlink;          // Number of links to inode in file system
#  uint size;            // Size of file (bytes)
#  uint addrs[NDIRECT+1];   // Data block addresses
#};
