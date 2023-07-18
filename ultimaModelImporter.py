bl_info = {
    "name": "Import Ultima 9 models",
    "author": "Chev",
    "version": (0,1),
    "blender": (3, 2, 2),
    "location": "File > Import > Ultima 9 models (fixed.*, nonfixed.*, sappear.flx)",
    "description": 'Import models from Ultima Ascension',
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

def readInt16(file_object):
    return struct.unpack("<h", file_object.read(2))[0]

def readBool(file_object):
    return struct.unpack("<?", file_object.read(1))[0]

def readUInt64(file_object):
    return struct.unpack("<Q", file_object.read(8))[0]

def readUBytes(file_object, count):
    xs = bytearray()
    for i in range(count):
        xs.append(readUByte(file_object))
    return xs

# complex types

def readVector3(file_object):
    return (readFloat(file_object), readFloat(file_object), readFloat(file_object))

def readVector2(file_object):  #made for ultima UV
    x = readFloat(file_object)
    y = readFloat(file_object)
    return Vector([x,y])

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
    
    header["unused1"] = readUBytes(file_object, 0x4C)  # = 0x20; // 0x00
    header["unused2"] = readUInt32(file_object)  # = 0x00; // 0x4C
    header["count"] = readUInt32(file_object)  #; // 0x50 - The number of records.
    header["unused3"] = readUInt32(file_object)  # = 0x02; // 0x54 - Perhaps it's a version number.
    header["size"] = readUInt32(file_object)  #; // 0x58 - Size in bytes of the archive file.
    header["size2"] = readUInt32(file_object)  #; // 0x5C - Also the size in bytes of the archive file.
    
    header["unused4"] = readUInt32(file_object)
    header["unused4_2"] = readUInt32(file_object)
    header["unused5"] = readUInt32(file_object)  # = 0x01; // 0x68
    header["unused5_2"] = readUInt32(file_object)  # an extra to reach 0x80 length

    header["unused6"] = readUBytes(file_object, 0x10)  # = 0x00; // 0x6C
    return header # Total size is 0x80 bytes.

def readArchiveRecord(file_object):
    record = dict()
    record["offset"] = readUInt32(file_object)  #; // Byte offset from the beginning of the file to the record data.
    record["size"] = readUInt32(file_object)  #; // Size in bytes of the record.
    return record # Total size is 0x08 bytes.

###bitmap records

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
    header["unknown2"] = readUInt16(file_object)  # Usually 0x6000.
    header["width"] = readUInt32(file_object) # Width in pixels of the frame.
    header["height"] = readUInt32(file_object) # Height in pixels of the frame.
    header["unknown3"] = readUInt32(file_object) # Almost always 0.
    header["unknown4"] = readUInt32(file_object) # Almost always 0.
    header["offsets"] =[]
    for i in range(header["height"]):
        header["offsets"].append(readUInt32(file_object)) # Offset to the data for each row relative to the start of the resource.
    return header # Basic size is 0x14 bytes.

def modelTextureName(textureIndex, frameIndex):
    return "bitmap16_{0}_{1}".format(textureIndex, frameIndex)

def makeTexture(archiveRecords, textureIndex, frameIndex, textureFile_object):
    #print("texture record ({0}_{1}) : ".format(textureIndex, frameIndex), archiveRecords[textureIndex])
    textureFile_object.seek(archiveRecords[textureIndex]["offset"], 0)
    textureSetHeader = readTextureSetHeader(textureFile_object)
    #print(textureSetHeader)
    frameRecords = []
    for i in range(textureSetHeader["count"]):
        frameRecords.append(readFrameRecord(textureFile_object))
    #print(frameRecords)
    #go to specific frame
    textureFile_object.seek(archiveRecords[textureIndex]["offset"] + frameRecords[frameIndex]["offset"], 0)
    frameHeader = readFrameHeader(textureFile_object)
    #print(frameHeader)
    #print("unk1: {0:16b} unk2: {1:16b}".format(frameHeader["unknown1"], frameHeader["unknown2"]))
    isTransparent = frameHeader["unknown1"] >> 8 & 1 ==1 #unknown1 bit 13 or unknown2 bit 3 are also possible candidates
    imageData =[]
    for i in range(frameHeader["width"]*frameHeader["height"]):
        if isTransparent == False:
            color=readColor16_565(textureFile_object)
        else:
            color=readColor16_5551(textureFile_object)
        imageData.extend(color)
        
    image = bpy.data.images.new(modelTextureName(textureIndex, frameIndex), 
        frameHeader["width"], frameHeader["height"], alpha = True)
    image.pixels = imageData
    image.file_format = 'PNG'
    image.pack()

    return isTransparent

###types.dat file

def readType(file_object):
    description = dict()

    description["unknown1"] = readUInt32(file_object)  # ??  Either 0 or CDCDCDCDh, with no apparent reason.

    description["UsecodeID"] = readUInt16(file_object)  # Refers to an entry in the usecode list, which is within the game engine.
    description["DefaultModelID"] = readUInt16(file_object)  # Refers to a model entry in the "static/sappear.flx". 
    # This model ID is used by default but the model ID used per instance in the nonfixed map file takes priority.
    description["Type Flags"] = readUInt16(file_object)  # Each bit of this word is a separate type flag: 
    # Never Hidden(0x01), NPC Only Collision(0x02), Partial Collision(0x04), Non Camera Block (see Spaces FLX)(0x08),
    # Portal Block (see Spaces FLX)(0x10), Unique Model (Final Art I'm guessing for the modelers)(0x20), ??(0x40), Not used, 
    # Vestigial(0x80), Mesh Collision(0x0100)

    description["Weight"] = readUByte(file_object)  # Weight used for Physics gravity, FF are not player movable, FE appears to be the same
    description["Volume"] = readUByte(file_object)  # Probably used for collision cylinder
    description["BookNumber"] = readUByte(file_object)  # Vestigial parameter, may not even be recognized by the engine.
    description["Hitpoints"] = readUByte(file_object)  # Vestigial parameter, handled with NPC.flx or type's instance nonfixed property.
    description["unknown2"] = readUInt16(file_object)  # ??  Always 0.
    return description

def readTypeModels(file_object):
    i = 0
    modelIDs = []
    while True:
        try:
            typeEntry = readType(file_object)
            #print(typeEntry)
            i+=1
            modelIDs.append(typeEntry["DefaultModelID"])
        except:
            print("stopped at type entry ", i)
            break
    return modelIDs

### Models

#region file header
def readHeader(file_object):
    header = dict()

    header["unknown1"] = readUInt32(file_object)  # ??  
    header["unknown2"] = readUInt32(file_object)  # ??  
    header["pagesSize"] = readUInt32(file_object)  # The size in bytes of all the pages.
    header["unknown3"] = readUInt32(file_object)  # ??  
    header["width"] = readUInt32(file_object)  # The number of tiles the region is wide. This is the same as the terrain height map's width divided by two.
    header["height"] = readUInt32(file_object)  # The number of tiles the region is tall. This is the same as the terrain height map's height divided by two.
    header["unknown4"] = readUInt32(file_object)  #??
    header["unknown5"] = readUInt32(file_object)  #
    return header

def readPageHeader(file_object):
    header = dict()

    header["unknown1"] = (readUInt32(file_object), readUInt32(file_object),readUInt32(file_object))  #??  
    header["baseX"] = readUInt32(file_object)  # The base X coordinate to add to the X coordinate of all objects in the page.
    header["baseY"] = readUInt32(file_object)  # The base Y coordinate to add to the Y coordinate of all objects in the page.
    header["unknown2"] = readUBytes(file_object, 4 * 0x13)  # ??  

    return header

def readFixedObject(file_object):
    description = dict()
    description["reference"] = readUInt32(file_object) # A byte offset from the start of the file to another object, or 0. 
    # Some objects have invalid references, and some are circular.
    description["position"] = (readUInt16(file_object), readUInt16(file_object), readUInt16(file_object)) # The location of the object within the tile, 
    # between 0 and 4095. This means that for each terrain quad there are 128 discrete positions.
    description["type"] = readUInt16(file_object) # The type index.
    description["angle"] = (readInt16(file_object), readInt16(file_object), readInt16(file_object), readInt16(file_object)) 
    # Angle of the fixed stored in 0.16 fixed point as a normalized quaternion. 
    # compute the angle as Quaternion(x / 32767.0, y / 32767.0, z / 32767.0, w / 32767.0).
    description["Flags"] = readInt16(file_object) # Flags for the object. 16 bit further than the specs, that were missing W component of quaternion
    description["unknown"] = readUInt16(file_object) # ? 
    return description 

######## nonfixed objects

#region file header
def readNonfixedHeader(file_object):
    header = dict()

    header["unknown1"] = readUInt32(file_object)  # ??  
    header["unknown2"] = readUInt32(file_object)  # ??
    header["unknown3"] = readUInt32(file_object)  # ?? 
    header["unknown4"] = readUInt32(file_object)  # ?? 
    header["unknown5"] = readUInt32(file_object)  # ?? 
    header["width"] = readUInt32(file_object)  # Width of the region in chunks
    header["height"] = readUInt32(file_object)  # height of the region in chunks.
    header["unknown4"] = readUInt32(file_object)  # ??
    header["pageOffsets"] = [] # Byte offset of the first page in the chunk, relative to the end of the header.
    for i in range(header["width"] * header["height"]):
        header["pageOffsets"].append(readUInt32(file_object))
    header["unknown6"] = readUInt32(file_object)  #??
    return header

def readNonfixedPageHeader(file_object):
    #print("page offset : ", file_object.tell())
    header = dict()

    header["nextPage"] = readUInt32(file_object)  # Offset of the next page in this chunk, relative to the end of the header minus 1, or 0 for none.
    header["endEntityOffset"] = readUInt32(file_object)  # 
    header["endTriggerOffset"] = readUInt32(file_object)  #    
    header["baseX"] = readUInt32(file_object)  # Base X coordinate of the chunk.
    header["baseY"] = readUInt32(file_object)  # Base Y coordinate of the chunk.
    header["entityCount"] = readUInt32(file_object)  # Number of entities in the chunk.
    header["triggerCount"] = readUInt32(file_object)  # Number of triggers in the chunk.
    header["unknown"] = [] # Further offsets to either entities or extra data. (It's not currently clear how to distinguish them.)   
    for i in range(17):
        header["unknown"].append(readUInt32(file_object))
    return header

def readNonfixedObject(file_object):
    description = dict()

    description["nextEntity"] = readUInt16(file_object) # Offset to the next entity in a linked list.
    description["unknown"] = readUInt16(file_object) #

    description["position"] = (readUInt16(file_object), readUInt16(file_object), readUInt16(file_object)) #The location of the object within the tile
    # X offset of the entity relative to the chunk's baseX value.
    # Y offset of the entity relative to the chunk's baseY value.
    # description["z"] = readUInt16(file_object) # Z position of the entity; the elevation.

    description["type"] = readUInt16(file_object) # Type index.
    description["rotation"] = (readInt16(file_object), readInt16(file_object), readInt16(file_object), readInt16(file_object)) 
    # Rotation of the entity expressed as an 0.16 quaternion (divide integer values by 32767).
    description["flags"] = readUInt32(file_object) # Entity flags.
    description["meshIndex"] = readUInt16(file_object) # The mesh index to render for this entity.
    description["triggerId"] = readUInt16(file_object) #
    description["extraDataOffset"] = readUInt32(file_object) # Offset of the extra data, relative to the end of the file header.
    
    return description 

########

def readModelHeader(file_object):
    header = dict()
    header["Submesh Count"] = readUInt32(file_object)  # Number of submeshes.
    header["LOD Count"] = readUInt32(file_object)  # Number of level-of-detail stages.
    header["Cylinder Base Centre"] = readVector3(file_object)  # Centre of the Cylinder Base.
    header["Cylinder Base Height"] = readFloat(file_object)  # The height of the Cylinder
    header["Cylinder Base Radius"] = readFloat(file_object)  # The radius of the Cylinder.
    header["Sphere Center"] = readVector3(file_object)  #C enter of Sphere
    header["Sphere Radius"] = readFloat(file_object)  # Radius of the Sphere
    header["unknown1"] = readFloat(file_object)  # ??
    header["Minimum Bounds"] = readVector3(file_object)  # Minimum bounds of a bounding box for the mesh.
    header["Maximum bounds"] = readVector3(file_object)  # Maximum bounds of a bounding box for the mesh.
    header["LOD Threshold 0"] = readUInt32(file_object)  # Thresholds 0
    header["LOD Threshold 1"] = readUInt32(file_object)  # Thresholds 1
    header["LOD Threshold 2"] = readUInt32(file_object)  # Thresholds 2
    header["LOD Threshold 3"] = readUInt32(file_object)  # Thresholds 3
    header["Center of Mass"] = readVector3(file_object)  #  Center of Mass
    header["Mass or Volume"] = readFloat(file_object)  # Mass or Volume? ??
    header["Inertia Matrix"] = readUBytes(file_object, 36) # readMatrix(file_object)  #9x9 Matrix for the inertia for the model
    header["Inertia related"] = readFloat(file_object)  # Inertia related?    Usually 1 or close to zero.

    return header

def readSubmeshBoneHeader(file_object): # technically a bone
    header = dict()

    header["Limb ID"] = readUInt32(file_object)  # The ID of this submesh
    header["Parent ID"] = readUInt32(file_object)  # The ID of the parent mesh
    header["Scale X"] = readFloat(file_object)  # Scale of the submesh in the X direction
    header["Scale Y"] = readFloat(file_object)  # Scale of the submesh in the Y direction
    header["Scale Z"] = readFloat(file_object)  # Scale of the submesh in the Z direction
    header["Position"] = readVector3(file_object)  # Position/Offset coordinates to parent mesh
    header["Orientation W"] = readFloat(file_object)  # Rotation Scalar
    header["Orientation X"] = readFloat(file_object)  # Rotation X
    header["Orientation Y"] = readFloat(file_object)  # Rotation Y
    header["Orientation Z"] = readFloat(file_object)  # Rotation Z  

    return header

scaleFactor = 40 #39.3701 #meters to inches

def readSubmesh(file_object, objectName):
    if objectName in bpy.data.meshes:
        object = bpy.data.objects.new(objectName, bpy.data.meshes[objectName])
        scene = bpy.context.scene
        scene.collection.objects.link(object)
        object.scale = (1/scaleFactor, 1/scaleFactor, 1/scaleFactor)
        return object
    start = file_object.tell()
    #print("model submesh start is : ", start)
    header = dict()
    header["Mesh Size"] = readUInt32(file_object)  # The size of the submesh in bytes, excluding this value, 
    # or 0 if there is no such submesh at this LOD level.
    if header["Mesh Size"] == 0:
        return None
    header["Flags"] = readUInt32(file_object)  # Appears to be a bitmask, with 4 and 8 being most common.
    header["unknown1"] = readUInt32(file_object)  # Unused? 
    header["Sphere Center"] = readVector3(file_object)  # LOD level's sphere center
    header["Sphere Radius"] = readFloat(file_object)  # LOD level's sphere radius
    header["Minimum Bounds"] = readVector3(file_object)  # Minimum bounding box.
    header["Maximum Bounds"] = readVector3(file_object)  # Maximum bounding box.
    header["unknown2"] = readUInt32(file_object)  # ignorable   
    header["unknown3"] = readUInt32(file_object)  # ignorable   
    header["Face Count"] = readUInt32(file_object)  # Number of faces in the submesh.
    header["Mount Face Count"] = readUInt32(file_object)  #    
    header["Vertex Count"] = readUInt32(file_object)  # Number of vertices in the submesh.
    header["Mount Vertex Count"] = readUInt32(file_object)  # 
    header["Max Face Count"] = readUInt32(file_object)  #  
    header["Material Count"] = readUInt32(file_object)  # Number of materials.
    header["Face Offset"] = readUInt32(file_object)  # Offset of the faces relative to the start of the detail level plus 4.
    header["Mount Face Offset"] = readUInt32(file_object)  # Mount Face Offset   
    header["Vertex Offset"] = readUInt32(file_object)  # Offset of the vertices relative to the start of the detail level plus 4.
    header["Mount Vertex Count"] = readUInt32(file_object)  #  
    header["Material Offset"] = readUInt32(file_object)  # Offset of the materials relative to the start of the detail level plus 4.
    header["Sorted Faces Offset"] = (readUInt32(file_object),readUInt32(file_object),readUInt32(file_object),readUInt32(file_object)) #Sorted Faces Offset 
    header["unknown4"] = readUInt32(file_object)  # probably unused

    print(header)
    
    
    rawFaces = []
    vertices = []
    materials = []
    
    file_object.seek(start + header["Face Offset"] + 4)
    for i in range(header["Face Count"]):
        rawFaces.append(readFace(file_object))

    file_object.seek(start + header["Vertex Offset"] + 4)
    for i in range(header["Vertex Count"]):
        vertices.append((readFloat(file_object), readFloat(file_object), readFloat(file_object)))

    file_object.seek(start + header["Material Offset"] + 4)
    for i in range(header["Material Count"]):
        materials.append(readMaterial(file_object))

    faces = []
    UVs = []
    colors =[]
    normals = []
    for face in rawFaces:
         faces.append((int(face["Points"][0]["index"]),
             int(face["Points"][2]["index"]),
             int(face["Points"][1]["index"])))
         UVs.extend((face["Points"][0]["texCoord"],face["Points"][2]["texCoord"],face["Points"][1]["texCoord"]))
         colors.extend((face["color"],face["color"],face["color"]))
         normals.extend((face["Points"][0]["normal"],face["Points"][2]["normal"],face["Points"][1]["normal"]))

    # build the blender mesh
    mesh = bpy.data.meshes.new(objectName)
    # print(vertices)
    mesh.from_pydata(vertices, [], faces) # (x y z) vertices, (1 2) edges, (variable index count) faces 

    new_uv = mesh.uv_layers.new(name = 'DefaultUV')
    new_colors = mesh.vertex_colors.new(name = 'DefaultColors')
    loop_normals = [None] * len(mesh.loops)

    isInvisible = True
    materialIDs = [0] * len(faces)
    for ID, material in enumerate(materials):
        # print(material)
        # create material. the texture will be filled later
        # special case: if material number is 65535, then ignore curframe, it's an invisible material
        frame = material["CurFrame"]
        if material["Texture ID"] == 65535:
            key = "invisible"
        else:
            key = modelTextureName(material["Texture ID"], material["CurFrame"])
            isInvisible = False
        if key not in bpy.data.materials:
            if material["Texture ID"] == 65535:
                makeInvisibleMaterial(key)
            else:
                neededTextures.append((material["Texture ID"], material["CurFrame"]))
                makeMaterial(key)
        mesh.materials.append(bpy.data.materials[key])
        # assign material to faces
        for face in range(material["Face Count"]):
            materialIDs[material["First Face ID"] + face] = ID

    for loop in mesh.loops:
        new_uv.data[loop.index].uv = UVs[loop.index]
    for loop in mesh.loops:
        loop_normals[loop.index] = Vector(normals[loop.index]).normalized()
    for loop in mesh.loops:
        new_colors.data[loop.index].color = colors[loop.index]

    mesh.use_auto_smooth = True #needed for custom normals
    mesh.normals_split_custom_set(loop_normals)

    for faceIndex, face in enumerate(mesh.polygons):
        face.material_index = materialIDs[faceIndex]
    # #add to scene
    object = bpy.data.objects.new(objectName, mesh)
    scene = bpy.context.scene
    scene.collection.objects.link(object)
    object.scale = (1/scaleFactor, 1/scaleFactor, 1/scaleFactor)
    if isInvisible == True:
        # if mesh has only invisible material, display it in wireframe
        object.display_type = 'WIRE'

    return object

def readFace(file_object):
    start = file_object.tell()
    face = dict()
    face["Points"] = (readPoint(file_object), readPoint(file_object), readPoint(file_object)) # Points in the face
    face["Flags"] = readUInt32(file_object) # only first 12 bits appear to be used
    face["Flags2"] = readUInt32(file_object) # unused?
    face["Normal"] = readVector3(file_object) # Normal Vector   
    face["Vector W"] = readFloat(file_object) # Vector W?   
    face["Material"] = readUInt32(file_object) # Material    
    # Sometimes a zero-based index into the bitmap16.flx/bitmapC.flx/bitmapsh.flx file (whichever is the active option) 
    # for the texture to use. In other cases this has a pattern but no strict correlation to the material. 
    # Use the material list instead to select textures.
    face["color"] = readColor32(file_object) # Color of the face in RGBA order, each element being between 0 (black/transparent) and 255 (bright/opaque).
    face["Collision"] = readUBytes(file_object, 8) # Collision Related, for collision system (index list [so only values from 0, 1, or 2] 
    # that contains the index of the vertex that is closest to each of the faces [order is: left,right,front,back,bottom,top]
    return face

def readPoint(file_object):
    point = dict()
    point["index"] = readUInt32(file_object) # Point index
    point["offset"] = readUInt32(file_object) # Offset to the point in bytes
    point["normal"] = readVector3(file_object) # Normal  Not always a unit vector
    point["texCoord"] = readVector2(file_object) # UV coordinates

    return point

def buildVColors(faces):
    colors =[]
    for face in faces:
        faceColors = []
        for index in range(3):
            faceColors.append(face["color"])
        colors.extend(faceColors)

    return colors

def buildNormals(vertices, faces):
    normals =[]
    for face in faces:
        faceNormals = []
        for index in face:
            faceNormals.append(vertices[index]["normal"])
        normals.extend(faceNormals)

    return normals

def readMaterial(file_object):
    material=dict()
    material["Texture ID"] = readUInt16(file_object) # Zero-based index of the texture to use from the 
    # bitmap16.flx/bitmapC.flx/bitmapsh.flx file (whichever is the active option).
    material["Flags"] = readUInt16(file_object) #
    material["Subtexture Count"] = readUInt16(file_object) #
    material["Flags2"] = readUInt16(file_object) #
    material["First Face ID"] = readUInt16(file_object) # Zero-based index of the first face with this material.
    material["Face Count"] = readUInt16(file_object) # The number of faces with this material.
    material["Default Alpha"] = readUByte(file_object) #
    material["Modified Alpha"] = readUByte(file_object) #
    material["Animation Start"] = readUByte(file_object) # Starting Frame for animation
    material["Animation End"] = readUByte(file_object) # Ending Frame for animation
    material["CurFrame"] = readUByte(file_object) # CurFrame    
    material["Animation Speed"] = readUByte(file_object) # Animation Speed Speed of animation in frames per second
    material["Animation type"] = readUByte(file_object) #
    material["Playback direction"] = readUByte(file_object) # 0 - forward, 1 - backward
    material["Animation Timer related"] = readUInt32(file_object) # Animation timer value

    return material

def boneName(instanceID, modelID, boneID):
    return "instance {0} mesh {1} bone {2}".format(instanceID, modelID, boneID)

def getMesh(file_object, modelID, archiveRecords, instanceID, only_LOD_0 = False):
    # TODO: first check if mesh already in blender meshes
    print("model offset is : ", archiveRecords[modelID]["offset"])
    file_object.seek(archiveRecords[modelID]["offset"])
    header = readModelHeader(file_object)
    print(header)

    try:
        # Offsets from the start of the record for each bone followed by (lodcount) submeshes
        submeshOffsets = []
        for i in range(header["Submesh Count"]):
            offsetDescription = dict()
            offsetDescription["header"] = readUInt32(file_object)
            submeshLods = []
            for j in range(header["LOD Count"]):
                submeshLods.append(readUInt32(file_object)) 
            offsetDescription["lods"] = submeshLods
            submeshOffsets.append(offsetDescription)


        root = None
        for offsetDescription in submeshOffsets:
            file_object.seek(archiveRecords[modelID]["offset"] + offsetDescription["header"], 0)
            subMeshHeader = readSubmeshBoneHeader(file_object)
            print(subMeshHeader)

            #if header["Submesh Count"] > 1 or header["LOD Count"] > 1: #use empties to organize objects if there's lods or a skeleton
            name = boneName(instanceID, modelID, subMeshHeader["Limb ID"]);
            bone = bpy.data.objects.new( name, None )
            bpy.context.scene.collection.objects.link(bone)
            bone.empty_display_size = 0.1
            bone.empty_display_type = 'ARROWS' #'PLAIN_AXES'
            parentName = boneName(instanceID, modelID, subMeshHeader["Parent ID"])
            if parentName != name and parentName in bpy.context.scene.collection.objects:
                bone.parent = bpy.context.scene.collection.objects[parentName]
            bone.location = (subMeshHeader["Position"][0]/scaleFactor,subMeshHeader["Position"][1]/scaleFactor,subMeshHeader["Position"][2]/scaleFactor)
            bone.rotation_mode = 'QUATERNION'
            bone.rotation_quaternion = Quaternion((subMeshHeader["Orientation W"], subMeshHeader["Orientation X"], 
                subMeshHeader["Orientation Y"],subMeshHeader["Orientation Z"],))
            bone.scale = (subMeshHeader["Scale X"], subMeshHeader["Scale Y"], subMeshHeader["Scale Z"])
            if root == None:
                root = bone
            # else:
            #     bone = None
            for j, LODoffset in enumerate(offsetDescription["lods"]):
                file_object.seek(archiveRecords[modelID]["offset"] + LODoffset, 0)
                meshName = "mesh_{0}_{1}_lod_{2}".format(modelID, subMeshHeader["Limb ID"], j)
                meshObject = readSubmesh(file_object, meshName)
                if meshObject is not None and bone is not None:
                    meshObject.parent = bone 
                if root == None:
                    root = meshObject
                # if j > 0: #lod sublevel, hide object
    except:
        print("mesh", modelID, "import failed")
        print(header)
        return None
    return root

########

neededTextures = []
def makeMaterial(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = True
    nodes = mat.node_tree.nodes
    mainNode = nodes["Principled BSDF"]
    mainNode.inputs["Specular"].default_value = 0.01
    textureNode=nodes.new("ShaderNodeTexImage")
    mat.node_tree.links.new(mainNode.inputs["Base Color"], textureNode.outputs["Color"])
    return mat

def toTransparentMaterial(material):  # mix with transparent before output
    nodes = material.node_tree.nodes
    mainNode = nodes["Principled BSDF"]
    outputNode = nodes["Material Output"]
    textureNode = nodes["Image Texture"]

    transparentNode =nodes.new("ShaderNodeBsdfTransparent")
    mixNode =nodes.new("ShaderNodeMixShader")
    
    material.node_tree.links.new(mixNode.inputs[0], textureNode.outputs[1]) # texture alpha as factor
    material.node_tree.links.new(mixNode.inputs[1], transparentNode.outputs[0])
    material.node_tree.links.new(mixNode.inputs[2], mainNode.outputs[0])
    material.node_tree.links.new(nodes['Material Output'].inputs[0], mixNode.outputs[0])
    material.blend_method = 'CLIP'
    material.alpha_threshold = 0.999
    material.shadow_method = 'CLIP'
    material.use_backface_culling = False

def makeInvisibleMaterial(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = True
    nodes = mat.node_tree.nodes
    nodes.remove(nodes["Principled BSDF"])
    transparentNode =nodes.new("ShaderNodeBsdfTransparent")
    outputNode = nodes["Material Output"]
    mat.node_tree.links.new(outputNode.inputs[0], transparentNode.outputs[0])
    mat.blend_method = 'CLIP'
    mat.alpha_threshold = 0.5
    mat.shadow_method = 'NONE'
    return mat

def GetNonfixedObjectList(file_object):
    header = readNonfixedHeader(file_object)
    print(header)
    pageCount = header["width"] * header["height"]


    # fixed objects
    nonfixedObjects = []
    headerEnd = file_object.tell()
    for i in range(pageCount):
        # pageStart = file_object.tell()
        try:
            file_object.seek(headerEnd+ 4096 * i)
            pageHeader = readNonfixedPageHeader(file_object)
            print("page ", i)
            print(pageHeader)
            for j in range(pageHeader["entityCount"]): # always 166 entries
                # read object ref
                nonfixedObject = readNonfixedObject(file_object)
                print("offset : ", file_object.tell())
                print(nonfixedObject)
                if nonfixedObject["type"] !=0: #type 0 entries are just empty
                    nonfixedObject["worldPosition"] = (pageHeader["baseX"]/scaleFactor +nonfixedObject["position"][0]/scaleFactor, 
                        pageHeader["baseY"]/scaleFactor +nonfixedObject["position"][1]/scaleFactor, nonfixedObject["position"][2]/scaleFactor)
                    nonfixedObject["orientation"] = (nonfixedObject["rotation"][0]/32767,nonfixedObject["rotation"][1]/32767,
                        nonfixedObject["rotation"][2]/32767,nonfixedObject["rotation"][3]/32767)
                    nonfixedObjects.append(nonfixedObject)

            # padding = readUBytes(file_object, 0x10) #Padding to a 1000h (4096)-byte boundary.
        except:
            print("stopped at page ", i)
            break
    
    # to scan the file for page candidates
    # while True:
    #     pageCandidateStart = file_object.tell()
    #     pageHeader = readNonfixedPageHeader(file_object)
    #     if pageHeader["baseX"] % 4096 == 0 and pageHeader["baseY"] % 4096 == 0 and (pageHeader["entityCount"] > 0 or pageHeader["triggerCount"] > 0) 
    #     and pageHeader["entityCount"] < 2000 and pageHeader["triggerCount"] < 2000:
    #         print("page header candidate at ", pageCandidateStart, " (", pageCandidateStart - headerEnd, " )")
    #         print(pageHeader)
    #     file_object.seek(pageCandidateStart + 4)

    return nonfixedObjects

def GetFixedObjectList(file_object):
    header = readHeader(file_object)
    print(header)
    pageCount = header["width"] * header["height"]
    print("pageCount : ", pageCount)
    indices = [] # These are either 0 or a number in the form nnnn001h, where nnnn is a number that may be a page index
    for i in range(pageCount):
        indices.append(readUInt32(file_object)) 

    fixedObjects = []
    for i in range(pageCount):
        try:
            pageHeader = readPageHeader(file_object)
            print("page ", i)
            print(pageHeader)
            for j in range(166): #always 166 entries
                #read object ref
                fixedObject = readFixedObject(file_object)
                print(fixedObject)
                if fixedObject["type"] !=0: # type 0 entries are just empty
                    fixedObject["worldPosition"] = (pageHeader["baseX"]/scaleFactor +fixedObject["position"][0]/scaleFactor, 
                        pageHeader["baseY"]/scaleFactor +fixedObject["position"][1]/scaleFactor, fixedObject["position"][2]/scaleFactor)
                    fixedObject["orientation"] = (fixedObject["angle"][0]/32767,fixedObject["angle"][1]/32767,
                        fixedObject["angle"][2]/32767,fixedObject["angle"][3]/32767)
                    fixedObjects.append(fixedObject)
                    #print(fixedObject)
            padding = readUBytes(file_object, 0x10) # Padding to a 1000h (4096)-byte boundary.
        except:
            print("stopped at page ", i)
            break
    return fixedObjects

def ImportMapModels(mapObjectFilePath, textureFilePath, typesFilePath, modelsFilePath):
    file_object = open(mapObjectFilePath, "rb")
    if "runtime" in mapObjectFilePath:
        mapObjects = GetNonfixedObjectList(file_object)
    #
    else:
        mapObjects = GetFixedObjectList(file_object)
    file_object.close()

    typesFile_object = open(typesFilePath, "rb")
    # types actually begin at 8h
    typesFile_object.seek(0x8)
    modelIDs = readTypeModels(typesFile_object)

    typesFile_object.close()


    modelsFile_object = open(modelsFilePath, "rb")
    # get flx header
    flxHeader = readArchiveHeader(modelsFile_object)
    print(flxHeader)
    archiveRecords = []
    for i in range(flxHeader["count"]):
        archiveRecords.append(readArchiveRecord(modelsFile_object))
    # print("3d model count in sappear : ", flxHeader["count"]) #gives 8000 but actually only 3765 are used?

    print("-----")

    for i, instance in enumerate(mapObjects):
        # print(instance["type"])
        # print(modelIDs[instance["type"]])
        try:
            # if "meshIndex" in instance and instance["meshIndex"] < len(modelIDs):
            #     modelID = modelIDs[instance["meshIndex"]]
            # else:
            modelID = modelIDs[instance["type"]]
        except:
            modelID = 0
        if modelID != 0: #ID 0 is also debug cube
            print("modelID : ", modelID)
            meshObject = getMesh(modelsFile_object, modelID, archiveRecords, i)
            if meshObject is not None:
                meshObject.location = instance["worldPosition"]
                
                meshObject.rotation_mode = 'QUATERNION'
                
                meshObject.rotation_quaternion = Quaternion((instance["orientation"][3], instance["orientation"][0], 
                    instance["orientation"][1],instance["orientation"][2]))
    modelsFile_object.close()

    textureFile_object = open(textureFilePath, "rb")
    flxHeader = readArchiveHeader(textureFile_object)
    # print(flxHeader)
    archiveRecords = []
    for i in range(flxHeader["count"]):
        archiveRecords.append(readArchiveRecord(textureFile_object))
    # print(archiveRecords)

    for (textureIndex, frameIndex ) in neededTextures:
        try:
            materialName = modelTextureName(textureIndex, frameIndex)
            isTransparent = False
            if materialName not in bpy.data.textures:
                isTransparent = makeTexture(archiveRecords, textureIndex, frameIndex, textureFile_object)
            bpy.data.materials[materialName].node_tree.nodes["Image Texture"].image = bpy.data.images[materialName]
            if isTransparent == True:
                toTransparentMaterial(bpy.data.materials[materialName])
        except:
          print("An exception occurred with texture ", (textureIndex, frameIndex ))

def ImportSingleModel(modelID, textureFilePath, modelsFilePath, modelCount):
    modelsFile_object = open(modelsFilePath, "rb")
    # get flx header
    flxHeader = readArchiveHeader(modelsFile_object)
    print(flxHeader)
    archiveRecords = []
    for i in range(flxHeader["count"]):
        archiveRecords.append(readArchiveRecord(modelsFile_object))
    # print("3d model count in sappear : ", flxHeader["count"]) #gives 8000 but actually only 3765 are used?

    rowCount = math.ceil(math.sqrt(modelCount))
    for i in range(modelCount):
        if modelID + modelCount -1 <= 3764: #mesh 536 crashes
            meshObject = getMesh(modelsFile_object, modelID + i, archiveRecords, i, only_LOD_0 = True)
            if meshObject is not None:
                meshObject.location = meshObject.location + Vector(((i % rowCount) * 3, (i // rowCount) * 3, 0))

    modelsFile_object.close()

    textureFile_object = open(textureFilePath, "rb")
    flxHeader = readArchiveHeader(textureFile_object)
    # print(flxHeader)
    archiveRecords = []
    for i in range(flxHeader["count"]):
        archiveRecords.append(readArchiveRecord(textureFile_object))
    # print(archiveRecords)

    for (textureIndex, frameIndex ) in neededTextures:
        try:
            materialName = modelTextureName(textureIndex, frameIndex)
            isTransparent = False
            if materialName not in bpy.data.textures:
                isTransparent = makeTexture(archiveRecords, textureIndex, frameIndex, textureFile_object)
            bpy.data.materials[materialName].node_tree.nodes["Image Texture"].image = bpy.data.images[materialName]
            if isTransparent == True:
                toTransparentMaterial(bpy.data.materials[materialName])
        except:
          print("An exception occurred with texture ", (textureIndex, frameIndex ))
        
###

class MyDialog(bpy.types.Operator):

    bl_idname = "tools.mydialog"
    bl_label = "My Dialog"

    modelFilePath: bpy.props.StringProperty(name="modelFilePath", options={'HIDDEN'})
    textureFilePath: bpy.props.StringProperty(name="textureFilePath", options={'HIDDEN'})
    typesFilePath: bpy.props.StringProperty(name="typesFilePath", options={'HIDDEN'})
    meshFilePath: bpy.props.StringProperty(name="meshFilePath", options={'HIDDEN'})

    modelID: bpy.props.IntProperty(name="Model ID", max=3764, min=0)
    modelCount: bpy.props.IntProperty(name="Range", max=3765, min=1, default = 1)

    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        ImportSingleModel(self.modelID, self.textureFilePath, self.meshFilePath, self.modelCount)
        return {'FINISHED'}

    # def draw(self, context):
    #     row = self.layout
    #     row.prop(self, "modelID", text="model ID")

class ImportUltimaFixed(bpy.types.Operator, ImportHelper):
    bl_idname       = "import_ultima_fixed.chev";
    bl_label        = "import fixed";
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
        textureFilePath = os.path.join(os.path.dirname(modelFilePath), "..\\static\\bitmap16.flx")
        typesFilePath = os.path.join(os.path.dirname(modelFilePath), "..\\static\\types.dat")
        meshFilePath = os.path.join(os.path.dirname(modelFilePath), "..\\static\\sappear.flx")

        print("importing {0}".format(modelFilePath))
        print ("textureFilePath : ", textureFilePath)
        print ("typesFilePath : ", typesFilePath)
        print ("meshFilePath : ", meshFilePath)

        if os.path.basename(modelFilePath) == "sappear.flx":
            bpy.ops.tools.mydialog('INVOKE_DEFAULT', 
                textureFilePath = textureFilePath, typesFilePath = typesFilePath, meshFilePath = meshFilePath)
        else:
            ImportMapModels(modelFilePath, textureFilePath, typesFilePath, meshFilePath) #ntpath.basename(modelFilePath[:-4]))

        now = time.time()
        print("It took: {0} seconds".format(now-then))
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(ImportUltimaFixed.bl_idname, text="Ultima 9 models (fixed.*, nonfixed.*, sappear.flx)");

def register():
    from bpy.utils import register_class
    register_class(ImportUltimaFixed)
    bpy.utils.register_class(MyDialog)
    bpy.types.TOPBAR_MT_file_import.append(menu_func)
    
def unregister():
    from bpy.utils import unregister_class
    unregister_class(ImportUltimaFixed)
    bpy.utils.unregister_class(MyDialog)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func);

if __name__ == "__main__":
    register()