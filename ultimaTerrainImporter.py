bl_info = {
    "name": "Import Ultima 9 terrain",
    "author": "Chev",
    "version": (0,1),
    "blender": (3, 2, 2),
    "location": "File > Import > Ultima 9 terrain (terrain.*)",
    "description": 'Import terrains from Ultima Ascension',
    "warning": "",
    "wiki_url": "https://github.com/Chevluh/Ultima-9-Blender-Importer",
    "category": "Import-Export"
}

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from mathutils import *
import re #regex
import time
import os # for path stuff
import ntpath
import math 

from bpy.props import CollectionProperty #for multiple files
from bpy.types import OperatorFileListElement

try: 
    import struct
except: 
    struct = None

###
# https://docs.python.org/3/library/struct.html
# < little endian, i integer. B would be unsigned char (ie ubyte in c#), ? would be C99 1-byte bool

def readInt32(file_object):
    return struct.unpack("<i", file_object.read(4))[0] 

def readUInt32(file_object):
    return struct.unpack("<I", file_object.read(4))[0]

def readUByte(file_object):
    return struct.unpack("<B", file_object.read(1))[0]

def readFloat(file_object):
    return struct.unpack("<f", file_object.read(4))[0]
    
def readUInt16(file_object):
    return struct.unpack("<H", file_object.read(2))[0]

def readBool(file_object):
    return struct.unpack("<?", file_object.read(1))[0]

def readUInt64(file_object):
    return struct.unpack("<Q", file_object.read(8))[0]

def readUBytes(file_object, count):
    xs = bytearray()
    for i in range(count):
        xs.append(readUByte(file_object))
    return xs

#complex types

def readColor32(file_object):
    B= readUByte(file_object)/255
    G= readUByte(file_object)/255
    R= readUByte(file_object)/255
    A= readUByte(file_object)/255
    return [R,G,B,A]

def readColor16_5551(file_object):
    rawColor = readUInt16(file_object);
    b = ((rawColor) & 0b11111) / 31 # Shift 0, mask 31.
    g = ((rawColor >> 5) & 0b11111) / 31 # Shift 5, mask 0x3E0.
    r = ((rawColor >> 10) & 0b11111) / 31 # Shift 10, mask 0x7C00.

    a = (rawColor >> 15) & 1 # Shift 15, mask 0x8000.
    return [r,g,b,a]

def readColor16_565(file_object):
    rawColor = readUInt16(file_object);
    b = ((rawColor) & 0b11111) / 31 # Shift 0, mask 31.
    g = ((rawColor >> 5) & 0b111111) / 63 # Shift 5, mask 0x3E0.
    r = ((rawColor >> 11) & 0b11111) / 31 # Shift 10, mask 0x7C00.

    a = 1.0
    return [r,g,b,a]

###FLX archive

def readArchiveHeader(file_object):
    header = dict()
    
    header["unused1"] = readUBytes(file_object, 0x4C)  # = 0x20
    header["unused2"] = readUInt32(file_object)  # = 0x00
    header["count"] = readUInt32(file_object)  # The number of records.
    header["unused3"] = readUInt32(file_object)  # Perhaps it's a version number.
    header["size"] = readUInt32(file_object)  # Size in bytes of the archive file.
    header["size2"] = readUInt32(file_object)  # Also the size in bytes of the archive file.
    header["unused4"] = readUInt32(file_object)
    header["unused4_2"] = readUInt32(file_object)
    header["unused5"] = readUInt32(file_object)  # = 0x01
    header["unused5_2"] = readUInt32(file_object)  # an extra to reach 0x80 length

    header["unused6"] = readUBytes(file_object, 0x10)  # = 0x00
    return header # Total size is 0x80 bytes.

def readArchiveRecord(file_object):
    record = dict()
    record["offset"] = readUInt32(file_object)  # Byte offset from the beginning of the file to the record data.
    record["size"] = readUInt32(file_object)  # Size in bytes of the record.
    return record # Total size is 0x08 bytes.

#bitmap records

def readTextureSetHeader(file_object):
    header=dict()
    header["frameWidth"] = readUInt16(file_object)  # Maximum width in pixels of all the frames.
    header["format"]= readUInt16(file_object) # enum TextureFormat
    header["frameHeight"] = readUInt16(file_object)  # Maximum height in pixels of all the frames.
    header["compression"] = readUInt16(file_object)  # Uncompressed = 0x00, Unknown = 0x01 (Used with some 8-bit textures)
    header["count"] = readUInt32(file_object)  # The number of frames.; u9tools thinks count is 4 bytes, othes specs say 2
    header["unknown"] = readUInt32(file_object)  #
    return header # Total size is 0x10 bytes.

def readFrameRecord(file_object):
    record = dict()
    record["offset"] = readUInt32(file_object) # Offset of the frame relative to the start of the resource.
    record["length"] = readUInt32(file_object) # Size in bytes of the frame data.
    return record

def readFrameHeader(file_object):
    header=dict()
    header["unknown1"] = readUInt16(file_object)  #
    header["unknown2"] = readUInt16(file_object)  #Usually 0x6000
    header["width"] = readUInt32(file_object) # Width in pixels of the frame
    header["height"] = readUInt32(file_object) # Height in pixels of the frame
    header["unknown3"] = readUInt32(file_object) # Almost always 0
    header["unknown4"] = readUInt32(file_object) # Almost always 0
    header["offsets"] =[]
    for i in range(header["height"]):
        header["offsets"].append(readUInt32(file_object)) # Offset to the data for each row relative to the start of the resource
    return header # Basic size is 0x14 bytes.

def chunkTextureName(textureIndex, frameIndex):
    return "bitmap16_{0}_{1}".format(textureIndex, frameIndex)

def makeTexture(archiveRecords, textureIndex, frameIndex, textureFile_object):
    textureFile_object.seek(archiveRecords[textureIndex]["offset"], 0)
    textureSetHeader = readTextureSetHeader(textureFile_object)
    frameRecords = []
    for i in range(textureSetHeader["count"]):
        frameRecords.append(readFrameRecord(textureFile_object))
    #go to specific frame
    textureFile_object.seek(archiveRecords[textureIndex]["offset"] + frameRecords[frameIndex]["offset"], 0)
    frameHeader = readFrameHeader(textureFile_object)
    imageData =[]
    for i in range(frameHeader["width"]*frameHeader["height"]):
        color=readColor16_565(textureFile_object)
        imageData.extend(color)
        
    image = bpy.data.images.new(chunkTextureName(textureIndex, frameIndex), 
        frameHeader["width"], frameHeader["height"], alpha = True)
    image.pixels = imageData
    image.file_format = 'PNG'
    image.pack()

    return image

### terrain

def readHeader(file_object):
    header = dict()

    header["width"] = readUInt32(file_object)  #width in points
    header["height"] = readUInt32(file_object) #height in points
    rawName = readUBytes(file_object, int(0x80))
    header["name"] = rawName[:rawName.index(b'\0')].decode("cp1252") # zero-terminated string
    header["waterLevel"] = readUInt32(file_object)
    header["waveAmplitude"] = readUInt32(file_object)
    header["flags"] = readUInt32(file_object)
    header["chunkCount"] = readUInt32(file_object)
    
    return header

def readPoint(file_object):
    tile = dict()
    rawTile = readUInt32(file_object)
    tile["height"] = rawTile & 0xFFF # (bits 0-11) Height of the point, from 0 to 4095.
    tile["isHole"] = rawTile & 0x1000 !=0 # (bit 12) If true, then this is a hole in the scenery, such as for a cave or a building.
    tile["swapUV"] = rawTile & 0x2000 !=0 # (bit 13) Swap the X and Y axes for the texture coordinates
    tile["mirrorUV"] = rawTile & 0x4000 !=0 # (bit 14) Mirror the X and Y axes for the texture coordinates.
    tile["flipDiagonal"] = rawTile & 0x8000 !=0 # (bit 15) diagonal maybe?
    tile["frame"] = (rawTile >>16) & 0x3F # (bits 16-21) Frame index in the texture.
    tile["texture"] = (rawTile >>22) & 0x3FF # (bits 22-31) Texture index.
    return tile

ChunkSize = 16
squareLength = 3.2 # 8.0 * 0.4
heightUnit = 0.1 # 0.25 * 0.4

def makeMaterial(texture): #specifically for terrain, with "extend"
    mat = bpy.data.materials.new(texture.name)
    mat.use_nodes = True
    mat.use_backface_culling = True
    nodes = mat.node_tree.nodes
    mainNode = nodes["Principled BSDF"]
    mainNode.inputs["Specular"].default_value = 0.01
    textureNode=nodes.new("ShaderNodeTexImage")
    textureNode.image = texture
    textureNode.extension = 'EXTEND'
    mat.node_tree.links.new(mainNode.inputs["Base Color"], textureNode.outputs["Color"])
    return mat

def ImportModel(modelFilePath, textureFilePath):
    file_object = open(modelFilePath, "rb")

    header = readHeader(file_object)
    print(header)

    chunkWidth = header["width"] // ChunkSize # Width of the terrain in chunks.
    chunkHeight = header["height"] // ChunkSize # Height of the terrain in chunks.
    chunkCount = chunkWidth * chunkHeight # Number of chunks in the terrain.
    print("chunkWidth : {0}, chunkHeight : {1}, chunkCount: {2}".format(chunkWidth, chunkHeight, chunkCount))

    indices = [] # Chunk template index to use for each tile in [x + y * header.chunkWidth] order
    for i in range(chunkCount):
        indices.append(readUInt16(file_object)) 

    chunkTemplates = []
    for i in range(header["chunkCount"]):
        points=[] #List of points in [x + y * ChunkSize] order.
        for j in range(ChunkSize * ChunkSize):
            points.append(readPoint(file_object))
        chunkTemplates.append(points)

    file_object.close()
    vertices = []
    heightMap = [0.0] * header["width"] * header["height"]
    for i in range(chunkWidth):
        for j in range(chunkHeight):
            tile_offset_x = ChunkSize * i
            tile_offset_y = ChunkSize * j
            for x in range(ChunkSize):
                for y in range(ChunkSize):
                    heightMap[tile_offset_x+x +(tile_offset_y+y) * header["width"]] = chunkTemplates[
                    indices[i + j* chunkWidth]][x+y*ChunkSize]["height"]* heightUnit

    for y in range(header["height"]+1):
        for x in range(header["width"]+1):
            vertices.append((squareLength * x, 
                            squareLength * y, 
                            heightMap[x % header["width"] + (y % header["height"] ) * header["width"]]))
    
    textureFile_object = open(textureFilePath, "rb")
    flxHeader = readArchiveHeader(textureFile_object)

    archiveRecords = []
    for i in range(flxHeader["count"]):
        archiveRecords.append(readArchiveRecord(textureFile_object))


    faces = []
    textures = dict()
    materialSlots = []
    materialIDs = []
    UVs = []

    stride = header["width"] + 1
    for y in range(header["height"]):
        for x in range(header["width"]):
            v1 = x + y * stride
            v2 = x + 1 + y * stride
            v3 = x + (y+1) * stride
            v4 = x + 1 + (y+1) * stride

            chunk_offset_x = x//ChunkSize
            chunk_offset_y = y//ChunkSize
            inside_coord_x = x%ChunkSize
            inside_coord_y = y%ChunkSize
            chunk = chunkTemplates[indices[chunk_offset_x+chunkWidth*chunk_offset_y]][inside_coord_x+ ChunkSize * inside_coord_y]

            if chunk["isHole"] == False:
                if chunk["flipDiagonal"] == True:
                    faces.append((v1, v2, v3))
                    faces.append((v2, v4, v3))
                else:
                    faces.append((v1, v2, v4))
                    faces.append((v1, v4, v3))

                textureIndex = chunk["texture"]
                frameIndex = chunk["frame"]
                key = chunkTextureName(textureIndex, frameIndex)
                if key not in textures:
                    image = makeTexture(archiveRecords, textureIndex, frameIndex, textureFile_object)
                    textures[key]=len(materialSlots)
                    materialSlots.append(makeMaterial(image))
                    #create basic material, link texture to diffuse through image node with "extend"
                    #also need to have generated UVs
                materialIDs.append(textures[key]) #add the material slot number
                materialIDs.append(textures[key])

                #UV
                
                uv3 = (0, 0)
                uv4 = (1, 0)
                uv2 = (1, 1)
                uv1 = (0, 1)
                
                # if chunk["swapUV"] == True:
                #     uv3 = (0, 0)
                #     uv4 = (0, 1)
                #     uv2 = (1, 1)
                #     uv1 = (1, 0)
                # if chunk["mirrorUV"] == True: 
                #     uv3 = (0, 1)
                #     uv4 = (1, 1)
                #     uv2 = (1, 0)
                #     uv1 = (0, 0)
                    
                #     if chunk["swapUV"] == True:
                #         uv3 = (1, 0)
                #         uv4 = (1, 1)
                #         uv2 = (0, 1)
                #         uv1 = (0, 0)

                #swap and mirror actually quarter turns?
                rotate = 0
                if chunk["swapUV"] == True:
                    rotate +=1
                if chunk["mirrorUV"] == True: 
                    rotate +=2

                if rotate == 3:
                    uv1 = (0, 0)
                    uv3 = (1, 0)
                    uv4 = (1, 1) #three quarter turn
                    uv2 = (0, 1)
                if rotate == 2:
                    uv2 = (0, 0)
                    uv1 = (1, 0)
                    uv3 = (1, 1) #one half turn
                    uv4 = (0, 1)

                if rotate == 1: #swapuv, actually quarter turn
                    uv4 = (0, 0)
                    uv2 = (1, 0)
                    uv1 = (1, 1)
                    uv3 = (0, 1)

                if chunk["flipDiagonal"] == True: #diagonal test
                    UVs.extend((uv1, uv2, uv3))
                    UVs.extend((uv2, uv4, uv3))
                else:
                    UVs.extend((uv1, uv2, uv4))
                    UVs.extend((uv1, uv4, uv3))
    
    #build the blender mesh
    objectName = header["name"]
    mesh = bpy.data.meshes.new(objectName)
    mesh.from_pydata(vertices, [], faces) #(x y z) vertices, (1 2) edges, (variable index count) faces 

    #add to scene
    object = bpy.data.objects.new(objectName, mesh)
    scene = bpy.context.scene
    scene.collection.objects.link(object)

    #mesh UVs
    new_uv = mesh.uv_layers.new(name = 'DefaultUV')
    
    for loop in mesh.loops:
        new_uv.data[loop.index].uv = UVs[loop.index]

    for faceIndex, face in enumerate(mesh.polygons):
        face.material_index = materialIDs[faceIndex]
    for material in materialSlots:
        mesh.materials.append(material)
    textureFile_object.close()

    #generate auto normals for terrain
    mesh.use_auto_smooth = True
    mesh.normals_split_custom_set_from_vertices([(0,0,0)] * len(vertices))

###

class ImportUltimaTerrain(bpy.types.Operator, ImportHelper):  #map 9 is all of britannia, 14 is avatar house
    bl_idname       = "import_ultima_terrain.chev";
    bl_label        = "import terrain";
    bl_options      = {'PRESET'};
    
    filename_ext    = ".xxx";

    filter_glob: StringProperty(
        default="*",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    
    def execute(self, context):
        print("importer start")
        then = time.time()

        modelFilePath = self.filepath
        textureFilePath = os.path.join(os.path.dirname(modelFilePath), "bitmap16.flx")

        print("importing {0}".format(modelFilePath))
        print ("textureFilePath : ", textureFilePath)

        ImportModel(modelFilePath, textureFilePath) #ntpath.basename(modelFilePath[:-4]))

        now = time.time()
        print("It took: {0} seconds".format(now-then))
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(ImportUltimaTerrain.bl_idname, text="Ultima 9 terrain (terrain.*)");

def register():
    from bpy.utils import register_class
    register_class(ImportUltimaTerrain)
    bpy.types.TOPBAR_MT_file_import.append(menu_func)
    
def unregister():
    from bpy.utils import unregister_class
    unregister_class(ImportUltimaTerrain)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func);

if __name__ == "__main__":
    register()