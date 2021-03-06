import os
import struct

from . import modmath as BIN

# https://github.com/ByteHazard/BfMeshView/blob/master/source/modStdMesh.bas


def LoadBF2Mesh(
        filepath,
        loadTextures=False,
        loadSamples=False,
        loadCon=False):
    with open(filepath, 'rb') as meshfile:
        file_extension = os.path.splitext(filepath)[1].lower()

        isSkinnedMesh = (file_extension == '.skinnedmesh')
        isBundledMesh = (file_extension == '.bundledmesh')
        isStaticMesh = (file_extension == '.staticmesh')

        vmesh = StdMesh(isSkinnedMesh, isBundledMesh, isStaticMesh)
        vmesh.open(meshfile)

        if loadSamples:
            dir = os.path.dirname(filepath)
            for filename in os.listdir(dir):
                filepath = os.path.join(dir, filename)
                name = os.path.splitext(filename)[0]
                ext = os.path.splitext(filename)[1]
                if ext[:5] == '.samp':
                    if ext == '.samples':
                        vmesh.geoms[
                            0].lods[
                            0].sample = LoadBF2Sample(filepath)
                    else:
                        geom = int(ext.split('_')[1][0])
                        lod = int(ext.split('_')[1][1])
                        vmesh.geoms[
                            geom].lods[
                            lod].sample = LoadBF2Sample(filepath)
    return vmesh


def LoadBF2Sample(filepath):
    with open(filepath, 'rb') as samplefile:
        sample = StdSample()
        sample.open(samplefile)
    return sample


class bf2lod:

    def __init__(self):
        self.version = None

        self.min = None
        self.max = None
        self.pivot = None
        self.nodenum = None

        self.nodes = []
        self.polycount = 0
        self.matnum = None
        self.materials = []

        self.sample = None


class bf2mat:

    def __init__(self):
        self.alphamode = None
        self.fxfile = None
        self.technique = None
        self.mapnum = None
        self.maps = None
        self.vstart = None
        self.istart = None
        self.inum = None
        self.vnum = None
        self.u4 = None
        self.u5 = None
        self.nmin = None
        self.nmax = None

    def __get_string(self, fo):
        string_len = BIN.long(fo)
        return BIN.string(fo, string_len)

    def __get_maps(self, fo):
        mapnames = []
        for i in range(self.mapnum):
            mapname = self.__get_string(fo)
            mapnames.append(mapname)
        return mapnames
    
    def read(self, fo, isSkinnedMesh, version):
        #print('>> starting reading material at {}'.format(fo.tell()))
        self.alphamode = BIN.long(fo)
        self.fxfile = self.__get_string(fo)
        self.technique = self.__get_string(fo)
        self.mapnum = BIN.long(fo)
        self.maps = self.__get_maps(fo)
        self.vstart = BIN.long(fo)
        self.istart = BIN.long(fo)
        self.inum = BIN.long(fo)
        self.vnum = BIN.long(fo)
        self.u4 = BIN.long(fo)
        self.u5 = BIN.long(fo)
        if not isSkinnedMesh and version == 11:
            self.nmin = BIN.float3(fo)
            self.nmax = BIN.float3(fo)


class bf2head:

    def __init__(self):
        #some internals
        self.fmt = '5l'
        self.size = struct.calcsize(self.fmt)

        # reading bin
        data = None
        self.u1 = None
        self.version = None
        self.u3 = None
        self.u4 = None
        self.u5 = None

    def read(self, fo):
        self.u1 = BIN.long(fo)
        self.version = BIN.long(fo)
        self.u3 = BIN.long(fo)
        self.u4 = BIN.long(fo)
        self.u5 = BIN.long(fo)

    def __eq__(self, other):
        if self.u1 != other.u1:
            return False
        if self.version != other.version:
            return False
        if self.u3 != other.u3:
            return False
        if self.u4 != other.u4:
            return False
        if self.u5 != other.u5:
            return False
        return True


class bf2geom:

    def __init__(self):
        self.lodnum = None
        self.lods = []
    
    def read_lodnum(self, fo):
        self.lodnum = BIN.long(fo)


class vertattrib:

    def __init__(self):
        self.flag = None
        self.offset = None
        self.vartype = None
        self.usage = None
    
    def read_vertattrib(self, fo):
        self.flag = BIN.short(fo) # some bool, never used
        self.offset = BIN.short(fo) # offset from vertex data start in bytes
        self.vartype = BIN.short(fo) # DX SDK 'Include/d3d9types.h' enum _D3DDECLTYPE
        self.usage = BIN.short(fo) # DX SDK 'Include/d3d9types.h' enum _D3DDECLUSAGE

    def __str__(self):
        return str((self.flag, self.offset, self.vartype, self.usage))

    def __eq__(self, other_tuple):
        if (self.flag, self.offset, self.vartype, self.usage) == other_tuple:
            return True
        else:
            return False


class StdMesh:

    def __init__(
            self,
            isSkinnedMesh=False,
            isBundledMesh=False,
            isStaticMesh=False):
        # setting some flags
        # perhaps should at least one by default?
        self.isSkinnedMesh = isSkinnedMesh
        self.isBundledMesh = isBundledMesh
        self.isStaticMesh = isStaticMesh

        # mesh data
        self.head = None  # header contains version and some bfp4f data
        self.u1 = None  # version flag for bfp4f
        self.geomnum = None  # amount of geoms
        self.geoms = None  # geometry struct, hold materials info etc
        self.vertattribnum = None  # amount of vertex attributes
        self.vertattrib = None  # vertex attributes table, struct info
        self.vertformat = None  # bytes lenght? seems to be always 4
        self.vertstride = None  # bytes len for vertex data chunk
        self.vertnum = None  # number of vertices
        self.vertices = None  # geom data, parse using attrib table
        self.indexnum = None  # number of indices
        self.index = None  # indices array
        self.u2 = None  # some another bfp4f garbage..

    # just a wrapper for better name
    def open(self, fo):
        # materials read will read everything inb4
        self._read_filedata(fo)

    def save(self, fo):
        # materials read will read everything inb4
        self._write_materials(fo)

    #-----------------------------
    # READING FILEDATA
    #-----------------------------
    def _read_head(self, fo):
        header = bf2head()
        header.read(fo)
        self.head = header
        #print('head ends at {}'.format(fo.tell()))

    def _read_u1_bfp4f_version(self, fo):
        self._read_head(fo)

        self.u1 = BIN.byte(fo)

    def _read_geomnum(self, fo):
        self._read_u1_bfp4f_version(fo)

        self.geomnum = BIN.long(fo)
    
    def _read_geom_table(self, fo):
        self._read_geomnum(fo)
        
        self.geoms = [bf2geom() for i in range(self.geomnum)]
        for i in range(self.geomnum):
            self.geoms[i].read_lodnum(fo)

    def _read_vertattribnum(self, fo):
        self._read_geom_table(fo)

        self.vertattribnum = BIN.long(fo)
        #print('.vertattribnum = {}'.format(self.vertattribnum))

    def _read_vertattrib_table(self, fo):
        self._read_vertattribnum(fo)

        self.vertattrib = [vertattrib() for i in range(self.vertattribnum)]
        for i in range(self.vertattribnum):
            self.vertattrib[i].read_vertattrib(fo)
            #print('>> [{}]{}'.format(i, fo.tell()))

    def _read_vertformat(self, fo):
        self._read_vertattrib_table(fo)

        self.vertformat = BIN.long(fo)

    def _read_vertstride(self, fo):
        self._read_vertformat(fo)
        #print('>> {}'.format(fo.tell()))

        self.vertstride = BIN.long(fo)

    def _read_vertnum(self, fo):
        self._read_vertstride(fo)
        #print('>> {}'.format(fo.tell()))

        self.vertnum = BIN.long(fo)

    def _read_vertex_block(self, fo):
        self._read_vertnum(fo)
        #print('>> {}'.format(fo.tell()))
        #print('self.vertnum = {}'.format(self.vertnum))

        vertices_num = int(self.vertstride / self.vertformat * self.vertnum)
        #print('vertices_num = {}'.format(vertices_num))
        # TODO: refactor
        fmt = '{}f'.format(vertices_num)
        size = struct.calcsize(fmt)

        self.vertices = struct.Struct(fmt).unpack(fo.read(size))
        #print('>> {}'.format(fo.tell()))

    def _read_indexnum(self, fo):
        self._read_vertex_block(fo)
        #print('>> vertex block end at {}'.format(fo.tell()))

        self.indexnum = BIN.long(fo)
        #print('self.indexnum = {}'.format(self.indexnum))

    def _read_index_block(self, fo):
        self._read_indexnum(fo)

        # TODO: refactor
        fmt = '{}h'.format(self.indexnum)
        size = struct.calcsize(fmt)

        self.index = struct.Struct(fmt).unpack(fo.read(size))

    def _read_u2(self, fo):
        self._read_index_block(fo)

        if not self.isSkinnedMesh:
            self.u2 = BIN.long(fo)

    def _read_nodes(self, fo):
        self._read_u2(fo)

        for geom in self.geoms:
            geom.lods = [bf2lod() for i in range(geom.lodnum)]
            for lod in geom.lods:
                lod.version = self.head.version
                lod.min = BIN.float3(fo)
                lod.max = BIN.float3(fo)
                if lod.version <= 6:
                    lod.pivot = BIN.float3(fo)
                lod.nodenum = BIN.long(fo)
                # reading nodes matrix
                if not self.isBundledMesh:
                    for i in range(lod.nodenum):
                        for j in range(16):
                            lod.nodes.append(BIN.float(fo))

    def _read_materials(self, fo):
        self._read_nodes(fo)

        for geom in self.geoms:
            for lod in geom.lods:
                lod.matnum = BIN.long(fo)
                lod.materials = [bf2mat() for i in range(lod.matnum)]
                for material in lod.materials:
                    material.read(fo, self.isSkinnedMesh, self.head.version)
                lod.polycount = lod.polycount + material.inum / 3

    def _read_filedata(self, fo):
        self._read_materials(fo)

    #-----------------------------
    # WRITING FILEDATA
    #-----------------------------
    def _write_header(self, filepath):
        directory = os.path.dirname(filepath)
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(filepath, 'wb+') as fo:
            dataset = (self.head.u1,
                       self.head.version,
                       self.head.u3,
                       self.head.u4,
                       self.head.u5)
            fo.write(struct.Struct(self.head.fmt).pack(*dataset))

    def _write_u1_bfp4f_version(self, filepath):
        self._write_header(filepath)
        
        with open(filepath, 'ab+') as fo:
            fmt = 'b'
            fo.write(struct.Struct(fmt).pack(self.u1))

    def _write_geomnum(self, filepath):
        self._write_u1_bfp4f_version(filepath)
        
        with open(filepath, 'ab+') as fo:
            fmt = 'l'
            fo.write(struct.Struct(fmt).pack(self.geomnum))

    def _write_geom_table(self, filepath):
        self._write_geomnum(filepath)
        
        with open(filepath, 'ab+') as fo:
            for geomnum in range(self.geomnum):
                fmt = 'l'
                fo.write(struct.Struct(fmt).pack(self.geoms[geomnum].lodnum))

    def _write_vertattribnum(self, filepath):
        self._write_geom_table(filepath)
        
        with open(filepath, 'ab+') as fo:
            fmt = 'l'
            fo.write(struct.Struct(fmt).pack(self.vertattribnum))

    def _write_vertattrib_table(self, filepath):
        self._write_vertattribnum(filepath)
        
        with open(filepath, 'ab+') as fo:
            for vertattribnum in range(self.vertattribnum):
                fmt = '4h'
                data = (self.vertattrib[vertattribnum].flag,
                        self.vertattrib[vertattribnum].offset,
                        self.vertattrib[vertattribnum].vartype,
                        self.vertattrib[vertattribnum].usage)
                fo.write(struct.Struct(fmt).pack(*data))

    def _write_vertformat(self, filepath):
        self._write_vertattrib_table(filepath)
        
        with open(filepath, 'ab+') as fo:
            fmt = 'l'
            fo.write(struct.Struct(fmt).pack(self.vertformat))

    def _write_vertstride(self, filepath):
        self._write_vertformat(filepath)
        
        with open(filepath, 'ab+') as fo:
            fmt = 'l'
            fo.write(struct.Struct(fmt).pack(self.vertstride))

    def _write_vertnum(self, filepath):
        self._write_vertstride(filepath)
        
        with open(filepath, 'ab+') as fo:
            fmt = 'l'
            fo.write(struct.Struct(fmt).pack(self.vertnum))

    def _write_vertex_block(self, filepath):
        self._write_vertnum(filepath)
        
        #print('writing {} vertices'.format(len(self.vertices)))
        with open(filepath, 'ab+') as fo:
            fmt = '{}f'.format(len(self.vertices))
            fo.write(struct.Struct(fmt).pack(*self.vertices))

    def _write_indexnum(self, filepath):
        self._write_vertex_block(filepath)
        
        with open(filepath, 'ab+') as fo:
            fmt = 'l'
            fo.write(struct.Struct(fmt).pack(self.indexnum))

    def _write_index_block(self, filepath):
        self._write_indexnum(filepath)
        
        with open(filepath, 'ab+') as fo:
            fmt = '{}h'.format(len(self.index))
            fo.write(struct.Struct(fmt).pack(*self.index))

    def _write_u2(self, filepath):
        self._write_index_block(filepath)
        
        if not self.isSkinnedMesh:
            with open(filepath, 'ab+') as fo:
                fmt = 'l'
                fo.write(struct.Struct(fmt).pack(self.u2))

    def _write_nodes(self, filepath):
        self._write_u2(filepath)
        
        with open(filepath, 'ab+') as fo:
            for geom in self.geoms:
                for lod in geom.lods:
                    fo.write(struct.Struct('3f').pack(*lod.min))
                    fo.write(struct.Struct('3f').pack(*lod.max))
                    if lod.version <= 6:
                        fo.write(struct.Struct('3f').pack(*lod.pivot))
                    fo.write(struct.Struct('l').pack(lod.nodenum))
                    # writing nodes matrix
                    if not self.isBundledMesh:
                        for i in range(lod.nodenum):
                            for j in range(16):
                                fo.write(struct.Struct('f').pack(lod.nodes[j]))

    def _write_materials(self, filepath):
        self._write_nodes(filepath)
        
        def write_bin_string(fo, bstring):
            fo.write(struct.Struct('l').pack(len(bstring)))
            fo.write(struct.Struct('{}s'.format(len(bstring))).pack(bstring))
        
        with open(filepath, 'ab+') as fo:
            for geom in self.geoms:
                for lod in geom.lods:
                    fo.write(struct.Struct('l').pack(lod.matnum))
                    for material in lod.materials:
                        fo.write(struct.Struct('l').pack(material.alphamode))
                        write_bin_string(fo, material.fxfile)
                        write_bin_string(fo, material.technique)
                        fo.write(struct.Struct('l').pack(material.mapnum))
                        for map in material.maps:
                            write_bin_string(fo, map)
                        fo.write(struct.Struct('l').pack(material.vstart))
                        fo.write(struct.Struct('l').pack(material.istart))
                        fo.write(struct.Struct('l').pack(material.inum))
                        fo.write(struct.Struct('l').pack(material.vnum))
                        fo.write(struct.Struct('l').pack(material.u4))
                        fo.write(struct.Struct('l').pack(material.u5))
                        if not self.isSkinnedMesh and self.head.version == 11:
                            fo.write(struct.Struct('3f').pack(*material.nmin))
                            fo.write(struct.Struct('3f').pack(*material.nmax))
    

class smp_sample:

    def __init__(self):
        self.position = None
        self.rotation = None
        self.face = None

    def read(self, fo):
        self.position = BIN.float3(fo)
        self.rotation = BIN.float3(fo)
        self.face = BIN.long(fo)


class smp_face:

    def __init__(self):
        '''
            v1 As float3
            n1 As float3

            v2 As float3
            n2 As float3

            v3 As float3
            n3 As float3
        '''
        self.v1 = None
        self.n1 = None

        self.v2 = None
        self.n2 = None

        self.v3 = None
        self.n3 = None

    def read(self, fo):
        self.v1 = BIN.float3(fo)
        self.n1 = BIN.float3(fo)

        self.v2 = BIN.float3(fo)
        self.n2 = BIN.float3(fo)

        self.v3 = BIN.float3(fo)
        self.n3 = BIN.float3(fo)


class StdSample:

    def __init__(self):
        # header
        self.fourcc = None
        self.width = None
        self.height = None

        self.datanum = None
        self.data = []

        self.facenum = None
        self.faces = []

    def open(self, fo):
        self._read_faces(fo)

    def _read_head(self, fo):
        self.fourcc = BIN.string(fo, lenght=4)
        self.width = BIN.long(fo)
        self.height = BIN.long(fo)

    def _read_data(self, fo):
        self._read_head(fo)

        self.datanum = self.width * self.height
        for i in range(self.datanum):
            sample = smp_sample()
            sample.read(fo)
            self.data.append(sample)

    def _read_faces(self, fo):
        self._read_data(fo)

        self.facenum = BIN.long(fo)
        for i in range(self.facenum):
            face = smp_face()
            face.read(fo)
            self.faces.append(face)



