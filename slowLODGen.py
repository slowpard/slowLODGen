import os
import time
time.clock = time.time #hack as time.clock is not available since python 3.8, open-source and backward compatibility... :cry:
import pyffi.spells.nif.modify
import pyffi.formats.nif
import math
import numpy as np
from pyffi.utils.withref import ref
import traceback
import logging
import csv
import yaml
import winreg

start_time = time.time()

#PATHS

logging.basicConfig(
    level=logging.INFO,  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(levelname)s - %(message)s',  
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output.log')),  # Log to a file
        logging.StreamHandler()             # Log to console
    ]
)


with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LODGen_config.yaml'), "r") as file:
    config = yaml.safe_load(file)

try:
    folder = config["game_folder"]
except:
    folder = ""

if folder == "":
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Bethesda Softworks\Oblivion", 0, winreg.KEY_READ)
        oblivion_path, _ = winreg.QueryValueEx(registry_key, "Installed Path")
        winreg.CloseKey(registry_key)
    except:
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Bethesda Softworks\Oblivion", 0, winreg.KEY_READ)
            oblivion_path, _ = winreg.QueryValueEx(registry_key, "Installed Path")
            winreg.CloseKey(registry_key)
        except:
            logging.critical("Oblivion folder not found, exiting...")
            exit()
    folder = os.path.join(oblivion_path, "data")

try:
    plugins_txt = config["plugins_txt_path"]
except:
    plugins_txt = ""

try:
    skip_nif_generation = config["skip_mesh_generation"]
except:
    skip_nif_generation = False

if plugins_txt == "":
    oblivion_plugins_path = os.path.join(os.getenv("USERPROFILE"), "AppData\\Local\\Oblivion", "plugins.txt")
    if os.path.exists(oblivion_plugins_path):
        plugins_txt = oblivion_plugins_path
    else:
        logging.critical("Plugins.txt not found, exiting...")
        exit()

logging.info("Oblivion path: " + folder)
logging.info("plugins.txt path: " + plugins_txt)
try:
    worldspaces_to_skip = config["worldspaces_to_skip"]
except:
    worldspaces_to_skip = []

try:
    meshes_to_skip = config["meshes_to_skip"]
except:
    meshes_to_skip = []

empty_nif_template = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'empty_ninode.nif')

#pyffi has extremly abstract struct classes defined from xmls
#this is a hack to make them *much* faster to work with 

if True: 
    def Vector3_fast_init(self, template = None, argument = None, parent = None):
        float_object1 = pyffi.object_models.common.Float()
        float_object2 = pyffi.object_models.common.Float()
        float_object3 = pyffi.object_models.common.Float()
        self._x_value_ = float_object1
        self._y_value_ = float_object2
        self._z_value_ = float_object3
        self._items = [float_object1, float_object2, float_object3]
    pyffi.formats.nif.NifFormat.Vector3.__init__ = Vector3_fast_init

    def Triangle_fast_init(self, template = None, argument = None, parent = None):
        short_object1 = pyffi.object_models.common.UShort()
        short_object2 = pyffi.object_models.common.UShort()
        short_object3 = pyffi.object_models.common.UShort()
        self._v_1_value_ = short_object1
        self._v_2_value_ = short_object2
        self._v_3_value_ = short_object3
        self._items = [short_object1, short_object2, short_object3]
    pyffi.formats.nif.NifFormat.Triangle.__init__ = Triangle_fast_init
if True: 
    def Color3_fast_init(self, template = None, argument = None, parent = None):
        float_object1 = pyffi.object_models.common.Float()
        float_object2 = pyffi.object_models.common.Float()
        float_object3 = pyffi.object_models.common.Float()
        self._r_value_ = float_object1
        self._g_value_ = float_object2
        self._b_value_ = float_object3
        self._items = [float_object1, float_object2, float_object3]
    pyffi.formats.nif.NifFormat.Color3.__init__ = Color3_fast_init
if True:     
    def Color4_fast_init(self, template = None, argument = None, parent = None):
        float_object1 = pyffi.object_models.common.Float()
        float_object2 = pyffi.object_models.common.Float()
        float_object3 = pyffi.object_models.common.Float()
        float_object4 = pyffi.object_models.common.Float()
        self._r_value_ = float_object1
        self._g_value_ = float_object2
        self._b_value_ = float_object3
        self._a_value_ = float_object4
        self._items = [float_object1, float_object2, float_object3, float_object4]
    pyffi.formats.nif.NifFormat.Color4.__init__ = Color4_fast_init

if False: #slow on pypy, fast on cpython
    def TexCoord_fast_init(self, template = None, argument = None, parent = None):
        float_object1 = pyffi.object_models.common.Float()
        float_object2 = pyffi.object_models.common.Float()
        self._u_value_ = float_object1
        self._v_value_ = float_object2
        self._items = [float_object1, float_object2]
    pyffi.formats.nif.NifFormat.TexCoord.__init__ = TexCoord_fast_init

if True:
    def Vector3_fast_write(self, stream, data):
        self._x_value_.write(stream, data)
        self._y_value_.write(stream, data)
        self._z_value_.write(stream, data)
    pyffi.formats.nif.NifFormat.Vector3.write = Vector3_fast_write
    def Triangle_fast_write(self, stream, data):
        self._v_1_value_.write(stream, data)
        self._v_2_value_.write(stream, data)
        self._v_3_value_.write(stream, data)
        #self._log_struct(stream, attr)
    pyffi.formats.nif.NifFormat.Triangle.write = Triangle_fast_write
    def Color3_fast_write(self, stream, data):
        self._r_value_.write(stream, data)
        self._g_value_.write(stream, data)
        self._b_value_.write(stream, data)  
    pyffi.formats.nif.NifFormat.Color3.write = Color3_fast_write
    def Color4_fast_write(self, stream, data):
        self._r_value_.write(stream, data)
        self._g_value_.write(stream, data)
        self._b_value_.write(stream, data)
        self._a_value_.write(stream, data)
    pyffi.formats.nif.NifFormat.Color4.write = Color4_fast_write
    def TexCoord_fast_write(self, stream, data):
        self._u_value_.write(stream, data)
        self._v_value_.write(stream, data)
    pyffi.formats.nif.NifFormat.TexCoord.write = TexCoord_fast_write 

    def Vector3_get_size(self, data):
        return 12
    def Triangle_get_size(self, data):
        return 6    
    def TexCoord_get_size(self, data):
        return 8
    def Color4_get_size(self, data):
        return 16
    def Color3_get_size(self, data):
        return 12
    pyffi.formats.nif.NifFormat.Vector3.get_size = Vector3_get_size
    pyffi.formats.nif.NifFormat.Triangle.get_size = Triangle_get_size
    pyffi.formats.nif.NifFormat.Color4.get_size = Color4_get_size
    pyffi.formats.nif.NifFormat.Color3.get_size = Color3_get_size
    pyffi.formats.nif.NifFormat.TexCoord.get_size = TexCoord_get_size

 
    def Vector3_get_x_value(self):
        return self._x_value_._value
    def Vector3_set_x_value(self, value):
        self._x_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Vector3, 'x', property(Vector3_get_x_value, Vector3_set_x_value))

    def Vector3_get_y_value(self):
        return self._y_value_._value
    def Vector3_set_y_value(self, value):
        self._y_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Vector3, 'y', property(Vector3_get_y_value, Vector3_set_y_value))


    def Vector3_get_z_value(self):
        return self._z_value_._value
    def Vector3_set_z_value(self, value):
        self._z_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Vector3, 'z', property(Vector3_get_z_value, Vector3_set_z_value))


    def Triangle_get_v_1_value(self):
        return self._v_1_value_._value
    def Triangle_set_v_1_value(self, value):
        self._v_1_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Triangle, 'v_1', property(Triangle_get_v_1_value, Triangle_set_v_1_value))

    def Triangle_get_v_2_value(self):
        return self._v_2_value_._value
    def Triangle_set_v_2_value(self, value):
        self._v_2_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Triangle, 'v_2', property(Triangle_get_v_2_value, Triangle_set_v_2_value))

    def Triangle_get_v_3_value(self):
        return self._v_3_value_._value
    def Triangle_set_v_3_value(self, value):
        self._v_3_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Triangle, 'v_3', property(Triangle_get_v_3_value, Triangle_set_v_3_value))

    def Color3_get_r_value(self):
        return self._r_value_._value
    def Color3_set_r_value(self, value):
        self._r_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Color3, 'r', property(Color3_get_r_value, Color3_set_r_value))
  
    def Color3_get_g_value(self):
        return self._g_value_._value
    def Color3_set_g_value(self, value):
        self._g_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Color3, 'g', property(Color3_get_g_value, Color3_set_g_value))

    def Color3_get_b_value(self):
        return self._b_value_._value
    def Color3_set_b_value(self, value):
        self._b_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Color3, 'b', property(Color3_get_b_value, Color3_set_b_value))

    def Color4_get_r_value(self):
        return self._r_value_._value
    def Color4_set_r_value(self, value):
        self._r_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Color4, 'r', property(Color4_get_r_value, Color4_set_r_value))

    def Color4_get_g_value(self):
        return self._g_value_._value
    def Color4_set_g_value(self, value):
        self._g_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Color4, 'g', property(Color4_get_g_value, Color4_set_g_value))

    def Color4_get_b_value(self):
        return self._b_value_._value
    def Color4_set_b_value(self, value):
        self._b_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Color4, 'b', property(Color4_get_b_value, Color4_set_b_value))

    def Color4_get_a_value(self):
        return self._a_value_._value
    def Color4_set_a_value(self, value):
        self._a_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.Color4, 'a', property(Color4_get_a_value, Color4_set_a_value))


    def TexCoord_get_u_value(self):
        return self._u_value_._value
    def TexCoord_set_u_value(self, value):
        self._u_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.TexCoord, 'u', property(TexCoord_get_u_value, TexCoord_set_u_value))

    def TexCoord_get_v_value(self):
        return self._v_value_._value
    def TexCoord_set_v_value(self, value):
        self._v_value_._value = value
    setattr(pyffi.formats.nif.NifFormat.TexCoord, 'v', property(TexCoord_get_v_value, TexCoord_set_v_value))


    def Vector3_fast_read(self, stream, data):
        self.x = self._x_value_
        self.y = self._y_value_
        self.z = self._z_value_
        self.x.arg = self.y.arg = self.z.arg = None
        self.x.read(stream, data)
        self.y.read(stream, data)
        self.z.read(stream, data)
    pyffi.formats.nif.NifFormat.Vector3.read = Vector3_fast_read

    def Triangle_fast_read(self, stream, data):
        self.v_1 = self._v_1_value_
        self.v_2 = self._v_2_value_
        self.v_3 = self._v_3_value_
        self.v_1.arg = self.v_2.arg = self.v_3.arg = None
        self.v_1.read(stream, data)
        self.v_2.read(stream, data)
        self.v_3.read(stream, data)
    pyffi.formats.nif.NifFormat.Triangle.read = Triangle_fast_read



    def Color3_fast_read(self, stream, data):
        self.r = self._r_value_
        self.g = self._g_value_
        self.b = self._b_value_
        self.r.arg = self.g.arg = self.b.arg = None
        self.r.read(stream, data)
        self.g.read(stream, data)
        self.b.read(stream, data)
    pyffi.formats.nif.NifFormat.Color3.read = Color3_fast_read

    def Color4_fast_read(self, stream, data):
        self.r = self._r_value_
        self.g = self._g_value_
        self.b = self._b_value_
        self.a = self._a_value_
        self.r.arg = self.g.arg = self.b.arg = self.a.arg = None
        self.r.read(stream, data)
        self.g.read(stream, data)
        self.b.read(stream, data)
        self.a.read(stream, data)
    pyffi.formats.nif.NifFormat.Color4.read = Color4_fast_read

if False:  
    def TexCoord_fast_read(self, stream, data):
        self.u = self._u_value_
        self.v = self._v_value_
        self.u.arg = self.v.arg = None
        self.u.read(stream, data)
        self.v.read(stream, data)
    pyffi.formats.nif.NifFormat.TexCoord.read = TexCoord_fast_read

if True:

    #makes perf MUCH worse on pypy but much faster on cpython ¯\_(ツ)_/¯ 
    def log_struct_fast(self, stream, attr):
        pass
    
    #this still does something but less than the original function
    #commenting out stuff actually makes it run worse idk
    #OpTiMiZaTiOn
    def log_struct_fast(self, stream, attr):
        val = getattr(self, "_%s_value_" % attr.name)  # debug

        try:
            pass
            out = val.get_value()  # debug
        except Exception:
            pass
        else:
            pass
            #offset = stream.tell()
            #hex_ver = "0x%08X" % offset
            #self.logger.debug("* {0}.{1} = {2} : type {3} at {4} offset {5} - ".format(self.__class__.__name__, attr.name, str(out), attr.type_, hex_ver, offset ))  # debug

    pyffi.object_models.xml.struct_.StructBase._log_struct = log_struct_fast


class NifProcessor:


    #paths
    ATLAS_CSV_PATH = r'S:\IC LOD Project\atlas.csv'
    EMPTY_NIF_PATH = r'S:\IC LOD Project\resources\empty_ninode.nif'

    #suppressing annoying spam of havok credits but don't want to suppress errors, so only hijacking the moppper credit function
    #since can't avoid making a new line, let's at least have this message
    pyffi.utils.mopp.getMopperCredits = lambda: 'Running havok mopper executable...'  


    #PARAMETERS
    #scale of the coordinates for havok objects
    #some sources use 6.996 (i.e. Blender niftools) some 7
    HAVOK_SCALE = 6.996

    #used for converting convex collision shapes to nitrishapes
    #the script checks if vertices belong to a normal plane, if they do, they form a triangle
    #this is the maximum distance from the plane for a vertex to be considered part of the plane
    #(basically, an allowance for float rounding errors)
    CONVEX_PLANE_MAX_DISTANCE = 0.0001

    #used for merging shapes with similar materials
    MATERIAL_COLOR_MERGING_DISTANCE = 10

    #when processing a meshlist ignore meshes below z<-30k (usually disabled objects that were accidentially exported)
    IGNORE_LOW_Z_FOR_MERGING = True

    #ignore certain material parameters for shape merging
    #they don't seem to be do anything in the game
    #maybe in some edge cases only
    IGNORE_AMBIENT_COLOR = True
    IGNORE_DIFFUSE_COLOR = True
    IGNORE_SPECULAR_COLOR = True

    #AWLS
    AWLS_ANIM_GROUP_LIST = ['AttackLeft', 'AttackLeftPower', 'Death', 'CastSelf', 'Stagger', 'Unequip', 'Recoil']


    IGNORE_COLLISIONS = True
    SKIP_TANGENT_SPACE_GENERATION = True
    IGNORE_AWLS = True #skips animation processing

    #used for LOD generator - merges only shapes that are listed in atlassed textures list
    #assumed thatt IGNORE_COLLISIONS = True SKIP_TANGENT_SPACE_GENERATION = True IGNORE_AWLS = True
    MERGE_ATLASSED_SHAPES_ONLY = False

    #uv coordinates for atlas are supposed to be in 0-1 range
    #this is the maximum allowed deviation from this range
    #if the deviation is higher, the shape is not to the atlassed shape
    ATLAS_UV_COORDINATES_LIMIT = 0.1

    def __init__(self):
        self.master_nif = pyffi.formats.nif.NifFormat.Data()
        self.anim_list = []
        self.nif_template = None
        self.merged_data = []
        self.shapes_merged = 0
        self.atlas_data = {}


    def MatrixfromEulerAngles(self, x, y, z):
        #xyz
        x = math.radians(x)
        y = math.radians(y)
        z = math.radians(z)
        

        sinX = math.sin(x)
        cosX = math.cos(x)
        sinY = math.sin(y)
        cosY = math.cos(y)
        sinZ = math.sin(z)
        cosZ = math.cos(z)

        m = [[0, 0, 0],
            [0, 0, 0],
            [0, 0, 0]]

        m[0][0] = cosY * cosZ
        m[0][1] = -cosY * sinZ
        m[0][2] = sinY
        m[1][0] = sinX * sinY * cosZ + sinZ * cosX
        m[1][1] = cosX * cosZ - sinX * sinY * sinZ
        m[1][2] = -sinX * cosY
        m[2][0] = sinX * sinZ - cosX * sinY * cosZ
        m[2][1] = cosX * sinY * sinZ + sinX * cosZ
        m[2][2] = cosX * cosY

        return np.array(m)


    def MatrixfromEulerAngles_zyx(self, x, y, z):
        
        #for future reference
        #{{cosz, -sinz, 0},{sinz, cosz, 0},{0, 0, 1}} 
        # * {{cosy, 0, siny},{0,1,0},{-siny,0,cosy}} 
        # * {{1, 0, 0},{0,cosx,-sinx},{0,sinx,cosx}} 

        x = math.radians(x)
        y = math.radians(y)
        z = math.radians(z)
        

        sinX = math.sin(x)
        cosX = math.cos(x)
        sinY = math.sin(y)
        cosY = math.cos(y)
        sinZ = math.sin(z)
        cosZ = math.cos(z)

        m = [[0, 0, 0],
            [0, 0, 0],
            [0, 0, 0]]

        m[0][0] = cosY * cosZ
        m[0][1] = sinX*sinY*cosZ - cosX*sinZ
        m[0][2] = cosX*sinY*cosZ + sinX*sinZ
        m[1][0] = cosY*sinZ
        m[1][1] = sinX*sinY*sinZ + cosX*cosZ
        m[1][2] = cosX*sinY*sinZ - sinX*cosZ
        m[2][0] = -sinY
        m[2][1] = sinX*cosY
        m[2][2] = cosX * cosY

        return np.array(m)




    def MatrixToEulerAngles(self, m):
        if m[0][2] < 1:
            if m[0][2] > -1:
                y = math.asin(m[0][2])
                x = math.atan2(-m[1][2], m[2][2])
                z = math.atan2(-m[0][1], m[0][0])
            else:
                y = -math.pi / 2
                x = -math.atan2(m[1][0], m[1][1])
                z = 0
        else:
            y = math.pi / 2
            x = math.atan2(m[1][0], m[1][1])
            z = 0

        return [math.degrees(x), math.degrees(y), math.degrees(z)]


    def ArraytoMatrix33(self, arr):
        m = pyffi.formats.nif.NifFormat.Matrix33()
        m.m_11 = arr[0][0]
        m.m_12 = arr[0][1]
        m.m_13 = arr[0][2]
        m.m_21 = arr[1][0]
        m.m_22 = arr[1][1]
        m.m_23 = arr[1][2]
        m.m_31 = arr[2][0]
        m.m_32 = arr[2][1]
        m.m_33 = arr[2][2]
        return m


    def Matrix33toArray(self, m):
        return np.array([[m.m_11, m.m_12, m.m_13], [m.m_21, m.m_22, m.m_23], [m.m_31, m.m_32, m.m_33]])


    def QuaternionToMatrix(self, q):

        m = [[0.0, 0.0, 0.0],[0.0, 0.0, 0.0],[0.0, 0.0, 0.0]]

        m[0][0] = 1.0 - 2 * (q.y * q.y + q.z * q.z)
        m[0][1] = 2 * (q.y * q.x - q.z * q.w)
        m[0][2] = 2 * (q.z * q.x + q.y * q.w)
        m[1][0] = 2 * (q.y * q.x + q.z * q.w)
        m[1][1] = 1.0 - 2 * (q.x * q.x + q.z * q.z)
        m[1][2] = 2 * (q.z * q.y - q.x * q.w)
        m[2][0] = 2 * (q.z * q.x - q.y * q.w)
        m[2][1] = 2 * (q.z * q.y + q.x * q.w)
        m[2][2] = 1.0 - 2 * (q.x * q.x + q.y * q.y)

        return np.array(m)

    def EulerAnglestoQuaternion(self, m):

        x = math.radians(m[0])
        y = math.radians(m[1])
        z = math.radians(m[2])

        c1 = math.cos(x / 2)
        s1 = math.sin(x / 2)
        c2 = math.cos(y / 2)
        s2 = math.sin(y / 2)
        c3 = math.cos(z / 2)
        s3 = math.sin(z / 2)

        q = pyffi.formats.nif.NifFormat.Quaternion()
        q.w = c1 * c2 * c3 - s1 * s2 * s3
        q.x = s1 * c2 * c3 + c1 * s2 * s3
        q.y = c1 * s2 * c3 - s1 * c2 * s3
        q.z = c1 * c2 * s3 + s1 * s2 * c3

        return q

    def ColorComparer(self, c1, c2, distance):
        return pow(c1.r - c2.r, 2) + pow(c1.g - c2.g, 2) + pow(c1.b - c2.b, 2) <= pow(distance, 2)


    def ReadAtlasData(self):
        self.atlas_data = {}
        with open(self.ATLAS_CSV_PATH, newline='', encoding='utf-8') as csvfile:
            csv_file = csv.DictReader(csvfile)
            for row in csv_file:
                name = row['name']
                self.atlas_data[name.lower()] = row

    def ReturnAtlasData(self, shape):
        tex_path = None
        for property in shape.properties:
            if isinstance(property, pyffi.formats.nif.NifFormat.NiTexturingProperty):
                tex_path = property.base_texture.source.file_name



        if not tex_path:
            return None
        else:
            if str(tex_path.decode('UTF-8')).lower() in self.atlas_data:
                    
                    logging.debug(f'Atlas found for shape {str(shape.name.decode("UTF-8"))}')
                    for uv in shape.data.uv_sets[0]:
                        limit = self.ATLAS_UV_COORDINATES_LIMIT
                        if ((uv.u > 1 + limit) or 
                            (uv.v > 1 + limit) or
                            (uv.u < -limit) or
                            (uv.v < -limit)):
                            logging.warning(f'Shape {str(shape.name.decode("UTF-8"))} not atlassed - UVs out of bounds')
                            return None


                    return self.atlas_data[tex_path.decode('UTF-8').lower()]
            else:
                return None


    #COLLISIONS
    def create_lizardbox_object(self, material, layer):
        self.master_nif.roots[0].add_child(pyffi.formats.nif.NifFormat.NiNode())
        self.master_nif.roots[0].children[-1].collision_object = pyffi.formats.nif.NifFormat.bhkCollisionObject()
        obj = self.master_nif.roots[0].children[-1].collision_object
        obj.target = self.master_nif.roots[0].children[-1]
        obj.body = pyffi.formats.nif.NifFormat.bhkRigidBody()
        obj.body.collision_response = 1 #RESPONSE_SIMPLE_CONTACT
        obj.body.motion_system = 7 #MO_SYS_FIXED
        obj.body.deactivator_type = 1 #DEACTIVATOR_NEVER
        obj.body.solver_deactivation = 1 #SOLVER_DEACTIVATION_OFF
        obj.body.quality_type = 1 #MO_QUAL_FIXED
        obj.body.havok_col_filter.layer = layer
        obj.body.shape = pyffi.formats.nif.NifFormat.bhkMoppBvTreeShape()
        obj.body.shape.shape = pyffi.formats.nif.NifFormat.bhkPackedNiTriStripsShape()
        obj.body.shape.shape.scale.x = 1.0
        obj.body.shape.shape.scale.y = 1.0
        obj.body.shape.shape.scale.z = 1.0
        obj.body.shape.shape.scale_copy.x = 1.0
        obj.body.shape.shape.scale_copy.y = 1.0
        obj.body.shape.shape.scale_copy.z = 1.0
        obj.body.shape.shape.sub_shapes.append(pyffi.formats.nif.NifFormat.OblivionSubShape())
        obj.body.shape.shape.sub_shapes[0].material = material
        obj.body.shape.shape.sub_shapes[0].havok_col_filter.layer = layer
        obj.body.shape.shape.num_sub_shapes = 1
        obj.body.shape.shape.data = pyffi.formats.nif.NifFormat.hkPackedNiTriStripsData()
        return obj

    def create_convex_lizardbox_object(self, material, layer):
        #not used anymore
        self.master_nif.roots[0].add_child(pyffi.formats.nif.NifFormat.NiNode())
        self.master_nif.roots[0].children[-1].collision_object = pyffi.formats.nif.NifFormat.bhkCollisionObject()
        obj = self.master_nif.roots[0].children[-1].collision_object
        obj.target = self.master_nif.roots[0].children[-1]
        obj.body = pyffi.formats.nif.NifFormat.bhkRigidBodyT()
        obj.body.collision_response = 1 #RESPONSE_SIMPLE_CONTACT
        obj.body.motion_system = 7 #MO_SYS_FIXED
        obj.body.deactivator_type = 1 #DEACTIVATOR_NEVER
        obj.body.solver_deactivation = 1 #SOLVER_DEACTIVATION_OFF
        obj.body.quality_type = 1 #MO_QUAL_FIXED
        obj.body.havok_col_filter.layer = layer
        obj.body.shape = pyffi.formats.nif.NifFormat.bhkConvexVerticesShape()
        obj.body.shape.material = material
        return obj

    def box_shape_extractor(self, shape):
        x = shape.dimensions.x  
        y = shape.dimensions.y 
        z = shape.dimensions.z 
        return {'vertices': [[[x, y, z, 1]], [[-x, y, z, 1]], [[-x, -y, z, 1]], 
                            [[x, -y, z, 1]], [[x, y, -z, 1]], [[-x, y, -z, 1]], 
                            [[-x, -y, -z, 1]], [[x, -y, -z, 1]]],
                'triangles':[[[0, 1, 2], [0, 0, 1, 1]],
                            [[2, 3, 0], [0, 0, 1, 1]], 
                            [[0, 4, 5], [0, 1, 0, 1]],
                            [[5, 1, 0], [0, 1, 0, 1]],
                            [[1, 5, 6], [-1, 0, 0, 1]],
                            [[6, 2, 1], [-1, 0, 0, 1]],
                            [[2, 6, 7], [0, -1, 0, 1]],
                            [[7, 3, 2], [0, -1, 0, 1]],
                            [[3, 7, 4], [1, 0, 0, 1]],
                            [[4, 0, 3], [1, 0, 0, 1]],
                            [[4, 7, 6], [0, 0, -1, 1]],
                            [[6, 5, 4], [0, 0, -1, 1]]]}

    def collisions_process_box_object(self, node, translation, rotation, scale, material, layer, transform_matrix):
        #node is NiNode.collision_object.body.shape.shape
        #lizardboxbox

        target_collision = None

        shape_data = self.box_shape_extractor(node)
        for vertice in shape_data['vertices']:
            vertice[0] = np.matmul(np.array(transform_matrix), vertice[0])
            
        for triangle in shape_data['triangles']:
            triangle[1] = np.matmul(np.array(transform_matrix), triangle[1])
            triangle[1] = triangle[1] / np.linalg.norm(triangle[1][:3])
            

        for n in self.master_nif.roots[0].children:
            if isinstance(n, pyffi.formats.nif.NifFormat.NiNode):
                if n.collision_object:
                    if isinstance(n.collision_object.body.shape, pyffi.formats.nif.NifFormat.bhkMoppBvTreeShape):
                        if isinstance(n.collision_object.body.shape.shape, pyffi.formats.nif.NifFormat.bhkPackedNiTriStripsShape):
                            if n.collision_object.body.havok_col_filter.layer == layer:
                                if n.collision_object.body.shape.shape.sub_shapes[0].material.material == material.material:
                                    if n.collision_object.body.shape.shape.data.num_vertices < 65000:
                                        target_collision = n.collision_object

        if not target_collision:
            logging.debug(f"creating new collision object with material {material.material} and layer {layer}")
            target_collision = self.create_lizardbox_object(material, layer=layer)

        target_packedtrishape = target_collision.body.shape.shape
        triangles_offset = target_packedtrishape.data.num_vertices
        
        for vertice in shape_data['vertices']:
            temp_Vector3 = pyffi.formats.nif.NifFormat.Vector3()
            adjusted_vector = np.matmul(scale * np.array(vertice[0][0:3]), rotation)
            temp_Vector3.x = adjusted_vector[0] + translation[0] / self.HAVOK_SCALE
            temp_Vector3.y = adjusted_vector[1] + translation[1] / self.HAVOK_SCALE
            temp_Vector3.z = adjusted_vector[2] + translation[2] / self.HAVOK_SCALE
            target_packedtrishape.data.vertices.append(temp_Vector3)

        for triangle in shape_data['triangles']:
            temp_hkTriangle = pyffi.formats.nif.NifFormat.hkTriangle()
            temp_hkTriangle.triangle.v_1 = triangle[0][0] + triangles_offset
            temp_hkTriangle.triangle.v_2 = triangle[0][1] + triangles_offset
            temp_hkTriangle.triangle.v_3 = triangle[0][2] + triangles_offset
            temp_hkTriangle.welding_info = 0
            temp_hkTriangle.normal  = pyffi.formats.nif.NifFormat.Vector3()
            normal_vector = np.matmul(rotation, np.array(triangle[1][:3]))
            temp_hkTriangle.normal.x = normal_vector[0]
            temp_hkTriangle.normal.y = normal_vector[1]
            temp_hkTriangle.normal.z = normal_vector[2]
            target_packedtrishape.data.triangles.append(temp_hkTriangle)

        target_packedtrishape.data.num_vertices = len(target_packedtrishape.data.vertices)
        target_packedtrishape.data.num_triangles = len(target_packedtrishape.data.triangles)
        target_packedtrishape.sub_shapes[0].num_vertices += 8

    def collisions_process_bhkConvexTransformShape(self, node, translation, rotation, scale, layer):
        #node is NiNode.collision_object.body.shape 
            
        material = node.material
        transform_matrix = node.transform.as_list()
        if isinstance(node.shape, pyffi.formats.nif.NifFormat.bhkBoxShape):
            self.collisions_process_box_object(node.shape, translation, rotation, scale, material, layer, transform_matrix)
        else:
            logging.warning(f"Unsupported collision geometry format in ConvextTransformShape: {type(node.shape)}")
            

    def process_collision_object(self, node, translation, rotation, scale):
        if self.IGNORE_COLLISIONS:
            return
        
        if node.collision_object:
            
            collision = node.collision_object
            f_scale = 1 * scale #collision doesn't have scale?

            m_translation = translation
            m_rotation = rotation

            if isinstance(collision.body, pyffi.formats.nif.NifFormat.bhkRigidBodyT):
                #rotation = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
                m_translation = (translation + np.matmul(scale * self.HAVOK_SCALE * np.array([collision.body.translation.x, collision.body.translation.y, collision.body.translation.z]), rotation))
                m_rotation = np.matmul(np.linalg.inv(self.QuaternionToMatrix(collision.body.rotation)), rotation)
                
            target_collision = None      
            layer = collision.body.havok_col_filter.layer

            if isinstance(node.collision_object.body.shape, pyffi.formats.nif.NifFormat.bhkConvexTransformShape):
                self.collisions_process_bhkConvexTransformShape(node.collision_object.body.shape, m_translation, m_rotation, f_scale, layer)

            elif isinstance(node.collision_object.body.shape, pyffi.formats.nif.NifFormat.bhkListShape):
                
                for obj in node.collision_object.body.shape.sub_shapes:
                    if isinstance(obj, pyffi.formats.nif.NifFormat.bhkConvexTransformShape):
                        self.collisions_process_bhkConvexTransformShape(obj, m_translation, m_rotation, f_scale, layer)
                    else:
                        logging.warning(f"Unsupported collision node format in ListShape: {type(obj)}")

            elif isinstance(node.collision_object.body.shape, pyffi.formats.nif.NifFormat.bhkConvexVerticesShape):
                target_collision = None 
                material = collision.body.shape.material
                vertex_counter = 0
                
                for n in self.master_nif.roots[0].children:
                    if isinstance(n, pyffi.formats.nif.NifFormat.NiNode):
                        if n.collision_object:
                            if isinstance(n.collision_object.body.shape, pyffi.formats.nif.NifFormat.bhkMoppBvTreeShape):
                                if isinstance(n.collision_object.body.shape.shape, pyffi.formats.nif.NifFormat.bhkPackedNiTriStripsShape):
                                    if n.collision_object.body.havok_col_filter.layer == collision.body.havok_col_filter.layer:
                                        if n.collision_object.body.shape.shape.sub_shapes[0].material.material == material.material:
                                            if n.collision_object.body.shape.shape.data.num_vertices + collision.body.shape.num_vertices < 65000:
                                                target_collision = n.collision_object
                                                #print(subshape.material)
                                                #print(material)
                                                #print('Found matching collision object')
                    
                if not target_collision:
                    #print("creating new collision object with material ", material.material, " and layer ", collision.body.havok_col_filter.layer)
                    #target_collision = create_convex_lizardbox_object(material, layer=collision.body.havok_col_filter.layer)
                    target_collision = self.create_lizardbox_object(material, layer=collision.body.havok_col_filter.layer)            
                
                shape_data = node.collision_object.body.shape
                target_packedtrishape = target_collision.body.shape.shape
                num_vertices = shape_data.num_vertices 
                triangles_offset = target_packedtrishape.data.num_vertices

                for vertice in shape_data.vertices:
                        temp_Vector3 = pyffi.formats.nif.NifFormat.Vector3()
                        adjusted_vector = np.matmul(scale * np.array([vertice.x, vertice.y, vertice.z]), m_rotation)
                        temp_Vector3.x = adjusted_vector[0] + m_translation[0] / self.HAVOK_SCALE
                        temp_Vector3.y = adjusted_vector[1] + m_translation[1] / self.HAVOK_SCALE
                        temp_Vector3.z = adjusted_vector[2] + m_translation[2] / self.HAVOK_SCALE
                        target_packedtrishape.data.vertices.append(temp_Vector3)

                for normal in shape_data.normals:
                    vertices_in_triangle = []
                    PlaneVector = [normal.x, normal.y, normal.z, normal.w]
                    for j, vertice in enumerate(shape_data.vertices):
                        vertice_vector = [vertice.x, vertice.y, vertice.z, 1]
                        distance = np.dot(vertice_vector, PlaneVector)
                        #print(PlaneVector)
                        #print(vertice.x, vertice.y, vertice.z, distance)
                        if abs(distance) < self.CONVEX_PLANE_MAX_DISTANCE:
                            vertices_in_triangle.append(j)
                    #print(vertices_in_triangle)
                    if len(vertices_in_triangle) < 3:
                        logging.warning("Skipping normal - less than 3 vertices in triangle. Try increasing self.CONVEX_PLANE_MAX_DISTANCE")
                    elif len(vertices_in_triangle) > 4:
                        logging.warning("Skipping normal - more than 4 vertices in triangle. Try decreasing self.CONVEX_PLANE_MAX_DISTANCE")
                    else:
                        temp_hkTriangle = pyffi.formats.nif.NifFormat.hkTriangle()
                        temp_hkTriangle.triangle.v_1 = vertices_in_triangle[0] + triangles_offset
                        temp_hkTriangle.triangle.v_2 = vertices_in_triangle[1] + triangles_offset
                        temp_hkTriangle.triangle.v_3 = vertices_in_triangle[2] + triangles_offset
                        temp_hkTriangle.welding_info = 0
                        temp_hkTriangle.normal  = pyffi.formats.nif.NifFormat.Vector3()
                        normal_vector = np.matmul(m_rotation, np.array([normal.x, normal.y, normal.z]))
                        temp_hkTriangle.normal.x = normal_vector[0]
                        temp_hkTriangle.normal.y = normal_vector[1]
                        temp_hkTriangle.normal.z = normal_vector[2]
                        target_packedtrishape.data.triangles.append(temp_hkTriangle)
                        if len(vertices_in_triangle) == 4:
                            temp_hkTriangle = pyffi.formats.nif.NifFormat.hkTriangle()
                            temp_hkTriangle.triangle.v_1 = vertices_in_triangle[3] + triangles_offset

                            vertex_3 = shape_data.vertices[vertices_in_triangle[3]]

                            distances = []
                            for vertex_index in vertices_in_triangle[:3]:
                                vertex = shape_data.vertices[vertex_index]
                                distance = np.linalg.norm(np.array([vertex.x, vertex.y, vertex.z]) - np.array([vertex_3.x, vertex_3.y, vertex_3.z]))
                                distances.append(distance)

                            closest_indices = np.argsort(distances)[:2]

                            temp_hkTriangle.triangle.v_2 = vertices_in_triangle[closest_indices[0]] + triangles_offset
                            temp_hkTriangle.triangle.v_3 = vertices_in_triangle[closest_indices[1]] + triangles_offset                        


                            temp_hkTriangle.welding_info = 0
                            temp_hkTriangle.normal  = pyffi.formats.nif.NifFormat.Vector3()
                            normal_vector = np.matmul(m_rotation, np.array([normal.x, normal.y, normal.z]))
                            temp_hkTriangle.normal.x = normal_vector[0]
                            temp_hkTriangle.normal.y = normal_vector[1]
                            temp_hkTriangle.normal.z = normal_vector[2]
                            target_packedtrishape.data.triangles.append(temp_hkTriangle)          
            
                target_packedtrishape.data.num_vertices = len(target_packedtrishape.data.vertices)
                target_packedtrishape.data.num_triangles = len(target_packedtrishape.data.triangles)
                target_packedtrishape.sub_shapes[0].num_vertices += num_vertices
            
                if False: #old code just copying the collision

                    shape_data = node.collision_object.body.shape
                    target_packedtrishape = target_collision.body.shape
                    for vertice in shape_data.vertices:
                        temp_Vector4 = pyffi.formats.nif.NifFormat.Vector4()
                        adjusted_vector = np.matmul(scale * np.array([vertice.x, vertice.y, vertice.z]), m_rotation)
                        temp_Vector4.x = adjusted_vector[0] + m_translation[0] / self.HAVOK_SCALE
                        temp_Vector4.y = adjusted_vector[1] + m_translation[1] / self.HAVOK_SCALE
                        temp_Vector4.z = adjusted_vector[2] + m_translation[2] / self.HAVOK_SCALE
                        target_packedtrishape.vertices.append(temp_Vector4)
                    
                    target_packedtrishape.num_vertices = len(target_packedtrishape.vertices)

                    for normal in shape_data.normals:
                        temp_Vector4 = pyffi.formats.nif.NifFormat.Vector4()
                        normal_vector = np.matmul(np.array([normal.x, normal.y, normal.z]), m_rotation)
                        temp_Vector4.x = normal_vector[0]
                        temp_Vector4.y = normal_vector[1]
                        temp_Vector4.z = normal_vector[2]
                        temp_Vector4.w = normal.w * scale
                        target_packedtrishape.normals.append(temp_Vector4)
                        
                    target_packedtrishape.num_normals = len(target_packedtrishape.normals)
            
            elif (isinstance(node.collision_object.body.shape.shape, pyffi.formats.nif.NifFormat.bhkPackedNiTriStripsShape) 
                or isinstance(node.collision_object.body.shape.shape, pyffi.formats.nif.NifFormat.bhkNiTriStripsShape)):

                if isinstance(node.collision_object.body.shape.shape, pyffi.formats.nif.NifFormat.bhkNiTriStripsShape):
                    node.collision_object.body.shape.shape = node.collision_object.body.shape.shape.get_interchangeable_packed_shape()

                vertex_counter = 0
                for subshape in node.collision_object.body.shape.shape.sub_shapes:
                    target_collision = None 
                    material = subshape.material
                    for n in self.master_nif.roots[0].children:
                        if isinstance(n, pyffi.formats.nif.NifFormat.NiNode):
                            if n.collision_object:
                                if isinstance(n.collision_object.body.shape, pyffi.formats.nif.NifFormat.bhkMoppBvTreeShape):
                                    if isinstance(n.collision_object.body.shape.shape, pyffi.formats.nif.NifFormat.bhkPackedNiTriStripsShape):
                                        if n.collision_object.body.havok_col_filter.layer == collision.body.havok_col_filter.layer:
                                            #print('Found collision object')
                                            #print(material)
                                            #print(n.collision_object.body.shape.shape.sub_shapes[0].material)
                                            #print(n.collision_object.body.shape.shape.sub_shapes[0].material == material)
                                            if n.collision_object.body.shape.shape.sub_shapes[0].material.material == material.material:
                                                if n.collision_object.body.shape.shape.data.num_vertices + collision.body.shape.shape.data.num_vertices < 65000:
                                                    target_collision = n.collision_object
                                                    #print(subshape.material)
                                                    #print(material)
                                                    #print('Found matching collision object')
                    
                    if not target_collision:
                        logging.debug(f"creating new collision object with material {material.material} and layer {collision.body.havok_col_filter.layer}")
                        target_collision = self.create_lizardbox_object(material, layer=collision.body.havok_col_filter.layer)
                    
                    shape_data = node.collision_object.body.shape.shape.data
                    target_packedtrishape = target_collision.body.shape.shape
                    num_vertices = subshape.num_vertices 
                    vertex_range_start = vertex_counter
                    vertex_range_high = vertex_counter + num_vertices
                    triangles_offset = target_packedtrishape.data.num_vertices
                    for triangle in shape_data.triangles:
                        if min(triangle.triangle.v_1, triangle.triangle.v_2, triangle.triangle.v_3) >= vertex_range_start and max(triangle.triangle.v_1, triangle.triangle.v_2, triangle.triangle.v_3) < vertex_range_high:                    
                            temp_hkTriangle = pyffi.formats.nif.NifFormat.hkTriangle()
                            temp_hkTriangle.triangle.v_1 = triangle.triangle.v_1 + triangles_offset - vertex_range_start
                            temp_hkTriangle.triangle.v_2 = triangle.triangle.v_2 + triangles_offset - vertex_range_start
                            temp_hkTriangle.triangle.v_3 = triangle.triangle.v_3 + triangles_offset - vertex_range_start
                            temp_hkTriangle.welding_info = triangle.welding_info
                            temp_hkTriangle.normal  = pyffi.formats.nif.NifFormat.Vector3()
                            normal_vector = np.matmul(m_rotation, np.array([triangle.normal.x, triangle.normal.y, triangle.normal.z]))
                            temp_hkTriangle.normal.x = normal_vector[0]
                            temp_hkTriangle.normal.y = normal_vector[1]
                            temp_hkTriangle.normal.z = normal_vector[2]
                            target_packedtrishape.data.triangles.append(temp_hkTriangle)

                    for vertice in shape_data.vertices[vertex_range_start:vertex_range_high]:
                        temp_Vector3 = pyffi.formats.nif.NifFormat.Vector3()
                        adjusted_vector = np.matmul(scale * np.array([vertice.x, vertice.y, vertice.z]), m_rotation)
                        temp_Vector3.x = adjusted_vector[0] + m_translation[0] / self.HAVOK_SCALE
                        temp_Vector3.y = adjusted_vector[1] + m_translation[1] / self.HAVOK_SCALE
                        temp_Vector3.z = adjusted_vector[2] + m_translation[2] / self.HAVOK_SCALE
                        target_packedtrishape.data.vertices.append(temp_Vector3)
                    


                    target_packedtrishape.data.num_vertices += num_vertices
                    target_packedtrishape.sub_shapes[0].num_vertices += num_vertices
                    target_packedtrishape.data.num_triangles = len(target_packedtrishape.data.triangles)
                    vertex_counter += num_vertices

            else:
                logging.warning('Unsupported collision geometry format, only bhkPackedNiTriStripsShape or bhkConvexVerticesShape is supported')


    def process_animations(self, controller):
        if not self.IGNORE_AWLS:
            for k in controller.controller_sequences:

                target_sequence = None

                if str(k.name.decode('UTF-8')) in self.AWLS_ANIM_GROUP_LIST:
                    for s in self.master_nif.roots[0].controller.controller_sequences:
                        if s.name == k.name:
                                target_sequence = s
                
                if target_sequence:
                    for block in k.controlled_blocks:
                        '''if (isinstance(block, pyffi.formats.nif.NifFormat.NiBoolInterpolator) or
                            isinstance(block, pyffi.formats.nif.NifFormat.NiVisController) or
                            isinstance(block, pyffi.formats.nif.NifFormat.NiPoint3Interpolator) or
                            isinstance(block, pyffi.formats.nif.NifFormat.NiMaterialColorController)):'''
                        target_sequence.controlled_blocks.append(block)
                        self.anim_list.append([block.controller.target, target_sequence.controlled_blocks[-1]])
                        #print(id(target_sequence.controlled_blocks[-1]))
                    target_sequence.num_controlled_blocks = len(target_sequence.controlled_blocks)

    def process_nif_node(self, node, translation, rotation, scale):

        try:
            f_scale = node.scale * scale
            
            m_translation = translation +  np.matmul(scale * np.array([node.translation.x, node.translation.y, node.translation.z]), rotation)
            
            m_rotation = np.matmul(self.Matrix33toArray(node.rotation), rotation)
            
            if (not self.IGNORE_AWLS) and (node.name == 'Smoke'): #AWLS smoke
                if len(node.children) > 0:
                    if node.children[0].name == 'Smoke Particles (Large)-Emitter' or node.children[0].name == 'Smoke Particles (Small)-Emitter':
                        node.translation.x = m_translation[0]
                        node.translation.y = m_translation[1]
                        node.translation.z = m_translation[2]
                        node.scale = f_scale
                        node.rotation = self.ArraytoMatrix33(m_rotation)
                        self.master_nif.roots[0].add_child(node)
                        return

            self.process_collision_object(node, m_translation, m_rotation, f_scale)
            for child in node.children:
                if isinstance(child, pyffi.formats.nif.NifFormat.NiNode):
                    self.process_nif_node(child, m_translation, m_rotation, f_scale)
                elif isinstance(child, pyffi.formats.nif.NifFormat.NiTriShape):
                    self.process_nif_trigeometry(child, m_translation, m_rotation, f_scale)
                elif isinstance(child, pyffi.formats.nif.NifFormat.NiTriStrips):
                    self.process_nif_trigeometry(child, m_translation, m_rotation, f_scale)
                else:
                    logging.warning("Unexpected type in NiNode: " + type(child))
                    
        except Exception as e:
            logging.error(traceback.format_exc())

  
    def process_nif_trigeometry(self, trishape, translation, rotation, scale):

        
        f_scale = trishape.scale * scale
        m_translation = translation + np.matmul(scale * np.array([trishape.translation.x, trishape.translation.y, trishape.translation.z]), rotation)
        m_rotation = np.matmul(self.Matrix33toArray(trishape.rotation), rotation)
        #print(trishape.name, "processing collision object")
        self.process_collision_object(trishape, m_translation, m_rotation, f_scale)
        texture_path = ''
        material_name = ''
        material_glossiness = 10
        material_alpha = 1
        target_shape = None
        texture_property = None
        stencil_property = None
        material_property = None
        alpha_found = False
        atlas_obj = None
        for property in trishape.properties:
            if isinstance(property, pyffi.formats.nif.NifFormat.NiTexturingProperty):
                texture_path = str(property.base_texture.source.file_name.decode('UTF-8'))
                texture_path_raw = property.base_texture.source.file_name
                texture_apply_mode = property.apply_mode
                texture_property = property
            elif isinstance(property, pyffi.formats.nif.NifFormat.NiMaterialProperty):
                material_name = str(property.name.decode('UTF-8'))
                material_name_raw = property.name
                material_glossiness = property.glossiness
                material_alpha = property.alpha
                material_property = property
            elif isinstance(property, pyffi.formats.nif.NifFormat.NiVertexColorProperty):
                if (property.flags != 40 and property.flags != 0) or property.vertex_mode != 2 or property.lighting_mode != 1:
                    #non-default values for vertex color -- not supported yet
                    # flags : 0x28
                    # vertex_mode : VERT_MODE_SRC_AMB_DIF
                    # lighting_mode : LIGHT_MODE_EMI_AMB_DIF
                    logging.warning("NiVertexColorProperty with non-standard parameters found, these parameters will be ignored! Given that the effect is likely very specialized, not something which should be merged automatically to begin with.")
            elif isinstance(property, pyffi.formats.nif.NifFormat.NiSpecularProperty):
                if property.flags == 0:
                    logging.warningrint("NiSpecularProperty with specularity flag disabled, will be ignored (likely doesn't do anything in Oblivion to begin with)")
            elif isinstance(property, pyffi.formats.nif.NifFormat.NiStencilProperty):
                stencil_property = property
                #if property.stencil_enabled == 1:
                #logging.warning("NiStencilProperty, not supported yet, will be merged without applying stencil.")
            elif isinstance(property, pyffi.formats.nif.NifFormat.NiAlphaProperty):
                alpha_found = True
                alpha_flags = property.flags
                alpha_threshold = property.threshold
            else:
                logging.warning(f"Unknown/unsupported property in trishape: {type(property)}")
        #try:
        atlas_obj = self.ReturnAtlasData(trishape)
        #except:
        #   pass
        #print(atlas_obj)
        if atlas_obj:
            texture_path = atlas_obj['bin']
        elif self.MERGE_ATLASSED_SHAPES_ONLY:
            return
        
        if (not texture_property) and (texture_path == ''):
            logging.error(f"Skipping shape: No texture found for trishape {trishape.name}")
        elif not material_property:
            logging.error(f"Skipping shape: No material found for trishape {trishape.name}")
        else:        
            
            for shape in self.master_nif.roots[0].children:

                texture_check = False #using the same texture
                material_g_check = False #glossiness
                material_a_check = False #alpha
                tr_points_check = False #cannot exceed 65k vertices
                triag_check = False
                poly_check = False
                apply_mode_check = False #texture apply mode, important for parallax vs not parallax etc
                ambient_c_check = False #coloring checks
                diffuse_c_check = False
                specular_c_check = False
                emissive_c_check = False
                alpha_check = False

                if alpha_found:
                    alpha_check = False
                else:
                    alpha_check = True

                if stencil_property:
                    stencil_check = False
                else:
                    stencil_check = True

                if isinstance(shape, pyffi.formats.nif.NifFormat.NiTriShape):
                    poly_check = ((shape.data.num_vertices + trishape.data.num_vertices) < 65000)
                    triag_check = ((shape.data.num_triangles + trishape.data.num_triangles) < 65000)
                    tr_points_check = True
                    #tr_points_check = ((shape.data.num_triangle_points + trishape.data.num_triangle_points) < 65000)
                    for k in shape.properties:
                        if isinstance(k, pyffi.formats.nif.NifFormat.NiTexturingProperty):
                            texture_check = (texture_path.lower() == str(k.base_texture.source.file_name.decode('UTF-8')).lower())
                            apply_mode_check = (texture_apply_mode == k.apply_mode)
                        elif isinstance(k, pyffi.formats.nif.NifFormat.NiMaterialProperty):
                            material_g_check = (material_glossiness == k.glossiness)
                            material_a_check = (material_alpha == k.alpha)

                            if self.IGNORE_AMBIENT_COLOR:
                                ambient_c_check = True
                            else:
                                ambient_c_check = self.ColorComparer(material_property.ambient_color, k.ambient_color, self.MATERIAL_COLOR_MERGING_DISTANCE)

                            if self.IGNORE_DIFFUSE_COLOR:
                                diffuse_c_check = True
                            else:
                                diffuse_c_check = self.ColorComparer(material_property.diffuse_color, k.diffuse_color, self.MATERIAL_COLOR_MERGING_DISTANCE)

                            if self.IGNORE_SPECULAR_COLOR:
                                specular_c_check = True
                            else:
                                specular_c_check = self.ColorComparer(material_property.specular_color, k.specular_color, self.MATERIAL_COLOR_MERGING_DISTANCE) 

                            emissive_c_check = self.ColorComparer(material_property.emissive_color, k.emissive_color, self.MATERIAL_COLOR_MERGING_DISTANCE) 
                        elif isinstance(k, pyffi.formats.nif.NifFormat.NiStencilProperty):
                            if not stencil_property:
                                stencil_check = False
                            else:
                                if (stencil_property.stencil_enabled == k.stencil_enabled and stencil_property.stencil_mask == k.stencil_mask 
                                    and stencil_property.stencil_function == k.stencil_function and stencil_property.draw_mode == k.draw_mode and
                                    stencil_property.pass_action == k.pass_action and stencil_property.fail_action == k.fail_action):
                                    stencil_check = True
                        elif isinstance(k, pyffi.formats.nif.NifFormat.NiAlphaProperty):
                            if not alpha_found:
                                alpha_check = False
                            else:
                                if alpha_flags == k.flags and alpha_threshold == k.threshold:
                                    alpha_check = True
                
                    if texture_check and material_g_check and material_a_check and tr_points_check and triag_check and poly_check and apply_mode_check \
                        and ambient_c_check and diffuse_c_check and specular_c_check and emissive_c_check and stencil_check and alpha_check:
                        target_shape = shape
                        break

            if not target_shape:

                #self.material_list.loc[material_name] = [str(trishape.name.decode('UTF-8')), material_glossiness, material_alpha, str(texture_path)]
                self.master_nif.roots[0].add_child(pyffi.formats.nif.NifFormat.NiTriShape())
                trishape_t = self.master_nif.roots[0].children[-1]
                trishape_t.name = str(trishape.name.decode('UTF-8'))
                trishape_t.flags = trishape.flags

                for k in trishape.properties:
                    trishape_t.num_properties += 1
                    trishape_t.properties.update_size()
                    trishape_t.properties[-1] = type(k)().deepcopy(k)                    
                    if atlas_obj and isinstance(k, pyffi.formats.nif.NifFormat.NiTexturingProperty):
                        trishape_t.properties[-1].base_texture.source.file_name = texture_path


                trishape_t.data = pyffi.formats.nif.NifFormat.NiTriShapeData()
                trishape_t.data.has_vertices = True
                trishape_t.data.has_normals = True
                trishape_t.data.has_vertex_colors = True
                trishape_t.data.has_triangles = True       

                target_shape = trishape_t
            else:
                self.shapes_merged += 1


            if target_shape:

                vertices_offset = target_shape.data.num_vertices

                
                if not trishape.data.has_vertex_colors:
                    trishape.data.has_vertex_colors = True
                    trishape.data.vertex_colors.update_size()
                    for k in trishape.data.vertex_colors:
                        k.r = 1.0
                        k.g = 1.0
                        k.b = 1.0
                        k.a = 1.0


                vertice_list = []    
                for vertice in trishape.data.vertices:
                    temp_vertice = pyffi.formats.nif.NifFormat.Vector3()
                    adjusted_vector = np.matmul(f_scale * np.array([vertice.x, vertice.y, vertice.z]), m_rotation)
                    temp_vertice.x = adjusted_vector[0] + m_translation[0]
                    temp_vertice.y = adjusted_vector[1] + m_translation[1]
                    temp_vertice.z = adjusted_vector[2] + m_translation[2]
                    vertice_list.append(np.add(adjusted_vector, m_translation))                          
                    target_shape.data.vertices.append(temp_vertice)

                average_point = np.mean(vertice_list, axis=0)
                distance = np.max(np.linalg.norm(vertice_list - average_point, axis=1))
                target_shape.data.center.x = average_point[0]
                target_shape.data.center.y = average_point[1]
                target_shape.data.center.z = average_point[2]
                target_shape.data.radius = distance
                

                for normal in trishape.data.normals:
                    normal_vector = np.matmul(np.array([normal.x, normal.y, normal.z]), m_rotation)
                    temp_normal = pyffi.formats.nif.NifFormat.Vector3()
                    temp_normal.x = normal_vector[0]
                    temp_normal.y = normal_vector[1]
                    temp_normal.z = normal_vector[2]
                    target_shape.data.normals.append(temp_normal)
                for vertex in trishape.data.vertex_colors:
                    target_shape.data.vertex_colors.append(vertex)

                for uv in trishape.data.uv_sets[0]:
                    if len(target_shape.data.uv_sets) == 0:
                        target_shape.data.num_uv_sets = 1
                        #target_shape.data.uv_sets.update_size()
                        target_shape.data.uv_sets.append(pyffi.object_models.xml.array._ListWrap(pyffi.formats.nif.NifFormat.TexCoord))

                    if atlas_obj:
                        uv_new = pyffi.formats.nif.NifFormat.TexCoord()
                        uv_new.u = (uv.u * atlas_obj['width'] + atlas_obj['x']) / atlas_obj['atlas_x']
                        uv_new.v = (uv.v * atlas_obj['height'] + atlas_obj['y']) / atlas_obj['atlas_y']
                        target_shape.data.uv_sets[0].append(uv_new)
                    else:
                        target_shape.data.uv_sets[0].append(uv)


                if isinstance(trishape, pyffi.formats.nif.NifFormat.NiTriShape):
                    for triangle in trishape.data.triangles:
                        temp_triangle = pyffi.formats.nif.NifFormat.Triangle()
                        temp_triangle.v_1 = triangle.v_1 + vertices_offset
                        temp_triangle.v_2 = triangle.v_2 + vertices_offset
                        temp_triangle.v_3 = triangle.v_3 + vertices_offset
                        target_shape.data.triangles.append(temp_triangle)
                        #if str(trishape.name.decode('UTF-8')) == r'CheydinhalHouseMiddle04:15':
                        #    print("Adding triangle ", temp_triangle.v_1, temp_triangle.v_2, temp_triangle.v_3)
                        #    print("Offset:", vertices_offset)
                        #    print(triangle)

                elif isinstance(trishape, pyffi.formats.nif.NifFormat.NiTriStrips):
                    triangles = []
                    triangles = pyffi.utils.tristrip.triangulate(trishape.data.points)
                    for triangle in triangles:
                        temp_triangle = pyffi.formats.nif.NifFormat.Triangle()
                        temp_triangle.v_1 = triangle[0] + vertices_offset
                        temp_triangle.v_2 = triangle[1] + vertices_offset
                        temp_triangle.v_3 = triangle[2] + vertices_offset
                        target_shape.data.triangles.append(temp_triangle)
                                    
                target_shape.data.num_vertices = len(target_shape.data.vertices)
                target_shape.data.num_triangles = len(target_shape.data.triangles) #+= trishape.data.num_triangles
                target_shape.data.num_triangle_points = target_shape.data.num_triangles * 3


                if len(target_shape.data.normals) < len(target_shape.data.vertices):
                    logging.warning(f"WARNING: shape {trishape.name} doesn't have normals, dummy normals will be added. This will cause visual artifacts.")
                #just a workaround for missing normals crashing the saving routine
                #shouldn't merge meshes like this to begin with, fix them with Blender first
                while len(target_shape.data.normals) < len(target_shape.data.vertices):
                    temp_normal = pyffi.formats.nif.NifFormat.Vector3()
                    temp_normal.x = 0
                    temp_normal.y = 0
                    temp_normal.z = 1
                    target_shape.data.normals.append(temp_normal)

                if not self.IGNORE_AWLS:
                
                    for shape, anim_block in self.anim_list:
                        if shape == trishape:
                            anim_block.controller.target = target_shape
                            target_shape.controller = anim_block.controller
                            obj_found = None
                            for obj in self.master_nif.roots[0].controller.object_palette.objs:
                                if obj.av_object == target_shape:
                                    obj_found = obj
                                    break
                            if not obj_found:
                                self.master_nif.roots[0].controller.object_palette.objs.append(pyffi.formats.nif.NifFormat.AVObject())
                                self.master_nif.roots[0].controller.object_palette.objs[-1].name = target_shape.name
                                self.master_nif.roots[0].controller.object_palette.objs[-1].av_object = target_shape
                                self.master_nif.roots[0].controller.object_palette.num_objs += 1


    def process_nif_root(self, data, translation=[0, 0, 0], rotation=[0, 0, 0], scale=1.0):
        m_translation = np.array(translation) 
        m_rotation = self.MatrixfromEulerAngles_zyx(rotation[0], rotation[1], rotation[2])
        f_scale = scale #1.0
        for root in data.roots:

            if root.controller:
                self.process_animations(root.controller)
            
            if isinstance(root, pyffi.formats.nif.NifFormat.NiNode):
                self.process_nif_node(root, m_translation, m_rotation, f_scale)
            elif isinstance(root, pyffi.formats.nif.NifFormat.NiTriShape):
                self.process_nif_trigeometry(root, m_translation, m_rotation, f_scale)
            elif isinstance(root, pyffi.formats.nif.NifFormat.NiTriStrips):
                self.process_nif_trigeometry(root, m_translation, m_rotation, f_scale)
            else:
                logging.error(f"Unknown type in root node: {type(root)}")

    def GenerateMoppObjects(self):
        if self.IGNORE_COLLISIONS:
            return
        logging.info('Creating mopp collision objects')
        for n in self.master_nif.roots[0].children:
            if isinstance(n, pyffi.formats.nif.NifFormat.NiNode):
                if n.collision_object:
                    if isinstance(n.collision_object.body.shape, pyffi.formats.nif.NifFormat.bhkMoppBvTreeShape):
                        if True: #with HiddenPrints():
                            n.collision_object.body.shape.update_mopp_welding()

    def UpdateTangentSpaces(self):
        if self.SKIP_TANGENT_SPACE_GENERATION:
            return
        logging.info('Updating tangent spaces')

        for n in self.master_nif.roots[0].children:

            if isinstance(n, pyffi.formats.nif.NifFormat.NiTriShape):
                NiBinaryExtraData =  pyffi.formats.nif.NifFormat.NiBinaryExtraData()
                n.num_extra_data_list = 1
                n.extra_data_list.update_size()
                n.extra_data_list[0] = NiBinaryExtraData
                with ref(NiBinaryExtraData) as n_nibinaryextradata:
                    #if you don't initialize it like that, you can't use any method on the extradtatlist array
                    n_nibinaryextradata.name = b'Tangent space (binormal & tangent vectors)'
                    n_nibinaryextradata.binary_data = b'\xfb\x05\xd1>\xdc\x05\xd1>\xec\x05Q?\xaf\xd2H?\xf6\x9d\x16?\xe2\xd2H>\xb7\xa4O?\x15,\xf9\xbeY\x1d\xa6\xbe\xec\x05Q?\xda\x05\xd1>\xfd\x05\xd1\xbe\x89\xfe\xa6>\xc6f\xf8>\xa8\xb2O\xbf\xf2YC?\x00"\x05>q\x11"?\xb3\xb3O?\x90\x0f\xa7\xbe\xd5W\xf8>\x98L\x0f?\xfcnK?\x90\x89p>\x89\xfe\xa6>\xc6f\xf8>\xa8\xb2O\xbf\x98L\x0f?\xfcnK?\x90\x89p>\xaf\xd2H?\xf6\x9d\x16?\xe2\xd2H>\xaf\xd2H?\xf6\x9d\x16?\xe2\xd2H>\x98L\x0f?\xfcnK?\x90\x89p>\xb7\xa4O?\x15,\xf9\xbeY\x1d\xa6\xbe\xb7\xa4O?\x15,\xf9\xbeY\x1d\xa6\xbe\xb3\xb3O?\x90\x0f\xa7\xbe\xd5W\xf8>\xf2YC?\x00"\x05>q\x11"?\xfb\x05\xd1>\xdc\x05\xd1>\xec\x05Q?\xec\x05Q?\xda\x05\xd1>\xfd\x05\xd1\xbe\xf2YC?\x00"\x05>q\x11"?\xef\x045?\xf8\x045\xbf\xeec\x11\xb5\xb7\xe3g>~\xee\x10\xbfl\xe7J?.\xd0\xbf\xbd\x0e\xd6\'\xbf\x13\xd0??\xbc+\x1d\xb5\xf8\x045\xbf\xee\x045\xbf+\x9f?\xbf\x1c\x1f(?x\x00\xbc=B\xb5\x94\xbe2[N\xbf\x91\x00\x04?\xa4\xb6\xbb\xbdu\x9b??\xa0$(?\xc5+\x18\xbf\x9e\x0f@>\xad/H?+\x9f?\xbf\x1c\x1f(?x\x00\xbc=\xc5+\x18\xbf\x9e\x0f@>\xad/H?\xb7\xe3g>~\xee\x10\xbfl\xe7J?\xb7\xe3g>~\xee\x10\xbfl\xe7J?\xc5+\x18\xbf\x9e\x0f@>\xad/H?.\xd0\xbf\xbd\x0e\xd6\'\xbf\x13\xd0??.\xd0\xbf\xbd\x0e\xd6\'\xbf\x13\xd0??\xa4\xb6\xbb\xbdu\x9b??\xa0$(?B\xb5\x94\xbe2[N\xbf\x91\x00\x04?\xef\x045?\xf8\x045\xbf\xeec\x11\xb5\xbc+\x1d\xb5\xf8\x045\xbf\xee\x045\xbfB\xb5\x94\xbe2[N\xbf\x91\x00\x04?'
                n.update_tangent_space()

    def CleanAnimationController(self):

        #AWLS cleanup
        
        useful_sequences = []

        for s in self.master_nif.roots[0].controller.controller_sequences:
            if s.num_controlled_blocks > 0:
                s.append(useful_sequences)
        
        if len(useful_sequences) > 0:
            self.master_nif.roots[0].controller.num_controller_sequences = len(useful_sequences)
            self.master_nif.roots[0].controller.controller_sequences.update_size()

            for i, s in enumerate(useful_sequences):
                self.master_nif.roots[0].controller.controller_sequences[i] = s
        else:
            self.master_nif.roots[0].controller = None
            self.master_nif.roots[0].extra_data_list[0].integer_data = 2
        
            
        
        
    def ProcessNif(self, nif_path, translation, rotation, scale):
        logging.debug(f'Processing {nif_path} at position {translation}')
        if nif_path.endswith('.nif'):
            self.shapes_merged = 0
            try:
                try:
                    stream = open(nif_path, 'rb')
                    data = pyffi.formats.nif.NifFormat.Data()
                    data.read(stream)
                    self.process_nif_root(data, translation, rotation, scale)
                    #print('Shapes merged: ', str(self.shapes_merged))
                    self.merged_data.append([nif_path, self.shapes_merged])
                    stream.close()
                except FileNotFoundError:
                    logging.error(f'File not found: {nif_path}')
            except Exception as e:
                logging.info(f'Error processing {nif_path}')
                logging.error(traceback.format_exc())
        else:
            logging.error(f'Not a NIF file! {nif_path}')

    
    def SaveNif(self, nif_path):

        logging.debug(f'Saving {nif_path}')
        
        directory = os.path.dirname(nif_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
            
        new_stream = open((nif_path), 'wb')
        self.master_nif.write(new_stream)
        new_stream.close()
        self.nif_template.close()

    def CleanTemplates(self):
        
        self.nif_template = open(self.EMPTY_NIF_PATH, 'rb')

        self.master_nif = pyffi.formats.nif.NifFormat.Data()
        self.master_nif.read(self.nif_template)

        self.anim_list = []

    def MiddleOfCellCalc(self, cell_x, cell_y):
        
        #returns coordinates of the cell center, useful for large cell-size merges
        x_offset = (cell_x + 0.5) * 4096
        y_offset = (cell_y + 0.5) * 4096
        z_offset = 0

        return [x_offset, y_offset, z_offset]

    def GenerateCombinedNif(self, txt_path, x_offset, y_offset, z_offset, nif_path, mesh_repo):
        '''
        Generates a combined NIF file from a text with exported esp data
        txt data is structured in blocks of 8 lines, with the following structure:
        [0-2] - x, y, z coordinates
        [3-5] - rotation angles
        [6] - scale
        [7] - mesh path

        x-z_offset is the coordinate where the merged object will be placed in CS, 
        try to put it in the middle of the geometry 
        (if you need coords for the cell center, use MiddleOfCellCalc(x, y) helper function)

        nif_path is the path where the merged NIF will be saved

        mesh_repo is the folder where the meshes are stored 
        '''
        blocks = []

        block_size = 8
        with open(txt_path, 'r') as file:
            lines = file.readlines()
            num_blocks = len(lines) // block_size
            for i in range(num_blocks):
                block = []
                for j in range(i * block_size, (i + 1) * block_size):
                    try:
                        value = float(lines[j].strip())
                    except ValueError:
                        value = lines[j].strip()
                    block.append(value)
                if block[6] == 0.0: block[6] = 1.0
                blocks.append(block)
        
        self.CleanTemplates()
        self.ReadAtlasData()

        for obj in blocks:
            if obj[2] > -25000 or (not self.IGNORE_LOW_Z_FOR_MERGING):
                self.ProcessNif(os.path.join(mesh_repo, obj[7]), [obj[0] - x_offset, obj[1] - y_offset, obj[2] - z_offset], [obj[3], obj[4], obj[5]], obj[6])
            else:
                logging.warning(f'Skipping {obj[7]} due to low Z value')

        self.GenerateMoppObjects()
        self.UpdateTangentSpaces()
        self.CleanAnimationController()
        self.SaveNif(nif_path)


    def GenerateCombinedNifFromArray(self, mesh_data, x_offset, y_offset, z_offset, nif_path):
        
        self.CleanTemplates()
        self.ReadAtlasData()

        for obj in mesh_data:
            if obj[2] > -25000 or (not self.IGNORE_LOW_Z_FOR_MERGING):
                self.ProcessNif(obj[0], [obj[1] - x_offset, obj[2] - y_offset, obj[3] - z_offset], [obj[4], obj[5], obj[6]], obj[7])
            else:
                logging.warning(f'Skipping {obj[0]} due to low Z value')

        self.GenerateMoppObjects()
        self.UpdateTangentSpaces()
        self.CleanAnimationController()
        self.SaveNif(nif_path)
                    

    def ProcessSingleMesh(self, input_path, output_path):
        '''
        Simple mesh processor, useful for shape merging or atlassing
        '''
        self.CleanTemplates()
        self.ReadAtlasData()
        self.ProcessNif(input_path, [0, 0, 0], [0, 0, 0], 1.0)
        self.GenerateMoppObjects()
        self.UpdateTangentSpaces()
        self.CleanAnimationController()
        self.SaveNif(output_path)

    def ProcessAllMeshesInAFolder(self, folder, output_folder):
        '''
        A wrapper for ProcessSingleMesh() called for all meshes in a folder/subfolders
        '''
        self.ReadAtlasData()
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.endswith('.nif'):
                    self.CleanTemplates()
                    file_name = os.path.join(root, file)
                    self.ProcessNif(file_name, [0, 0, 0], [0, 0, 0], 1.0)
                    self.GenerateMoppObjects()
                    self.UpdateTangentSpaces()
                    self.CleanAnimationController()
                    self.SaveNif(os.path.join(output_folder, os.path.relpath(file_name, folder)))





import struct
import os 
import zlib
import os
import math
import shutil
class Subrecord:
    def __init__(self, sig, size, data, has_size=True, **kwargs):
        self.sig = sig   # str 4 bytes
        self.size = size # uint16
        self.data = data # raw bytes
        self.has_size = has_size

    def serialize(self):
        if self.has_size:
            header = struct.pack('<4sH', self.sig.encode('ascii'), self.size)
            return header + self.data
        else:  
            return self.sig.encode('ascii') + self.data

class Record:

    FLAG_ESM = 0x00000001
    FLAG_DELETED = 0x00000020
    FLAG_CASTS_SHADOWS = 0x00000200
    FLAG_PERSISTENT = 0x00000400
    FLAG_DISABLED = 0x00000800
    FLAG_IGNORED = 0x00001000
    FLAG_VISIBLE_WHEN_DISTANT = 0x00008000
    FLAG_DANGEROUS = 0x00020000
    FLAG_COMPRESSED = 0x00040000
    FLAG_CANT_WAIT = 0x00080000 

    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        #logging.debug('Creating a record')
        self.sig = sig  # str 4 bytes
        self.data_size = data_size      # uint32
        self.flags = flags              # uint32
        self.form_id = form_id          # uint32
        self.vc_info = vc_info          # uint32
        self.data = data                # raw bytes
        self.subrecords = []



        if not self.is_compressed():                 
            self.parse_subrecords(data)

    def is_compressed(self):
        return (self.flags & self.FLAG_COMPRESSED) != 0
    


    def parse_subrecords(self, data):
        offset = 0

        if self.sig == 'BOOK': #a quick bandaid for broken bashed patch subrecords
            return
        
        while offset < len(data):
            sig = data[offset:offset+4].decode('ascii')
            if sig == 'OFST':
                # OFST subrecord: no size field, consumes remaining data
                sub_data = data[offset+4:]
                subrecord = Subrecord(sig, len(sub_data), sub_data, has_size=False)
                self.subrecords.append(subrecord)
                offset = len(data) 
                break
            
            size = struct.unpack_from('<H', data, offset+4)[0]
            sub_data = data[offset+6:offset+6+size]
            subrecord = Subrecord(sig, size, sub_data)
            self.subrecords.append(subrecord)
            offset += 6 + size  # 6 bytes header + data



    def serialize(self):
        if self.is_compressed():
            header = struct.pack('<4sIIII', self.sig.encode('ascii'),
                                self.data_size, self.flags, self.form_id,
                                self.vc_info)
            return header + self.data
        else:
            subrecords_data = b''.join(sub.serialize() for sub in self.subrecords)
            self.data_size = len(subrecords_data)
            header = struct.pack('<4sIIII', self.sig.encode('ascii'),
                                 self.data_size, self.flags, self.form_id,
                                 self.vc_info)
            return header + subrecords_data
        
    def renumber_formids(self, formid_chg_map, formid_map):
        formid_bytes = bytearray(self.form_id.to_bytes(4, 'big'))
        mod_id = formid_bytes[0]
        if formid_chg_map[mod_id] != mod_id:
            old_formid = self.form_id
            formid_bytes[0] = formid_chg_map[mod_id]
            self.form_id = int.from_bytes(formid_bytes, 'big')
            formid_map.pop(old_formid)
            formid_map[self.form_id] = self
    
class RecordTES4(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        self.master_files = []
        super().__init__(sig, data_size, flags, form_id, vc_info, data, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        self.master_files = []
        for subrecord in self.subrecords:
            if subrecord.sig == 'MAST':
                self.master_files.append(subrecord.data.decode('ascii').rstrip('\x00'))
                #print('masterfile:', self.master_files[-1])
        #print(self.master_files)

class RecordREFR(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_worldspace, **kwargs):
        self.position = None
        self.rotation = None
        self.scale = None
        self.parentformid = None
        self.stateoppositeofparent_flag = None
        self.baserecordformid = None
        self.parent_worldspace = None
        super().__init__(sig, data_size, flags, form_id, vc_info, data, **kwargs)
        self.parent_worldspace = parent_worldspace

        
    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'NAME':
                self.baserecordformid = struct.unpack_from('<I', subrecord.data)[0]
            if subrecord.sig == 'DATA':
                pos_x, pos_y, pos_z, rot_x, rot_y, rot_z = struct.unpack('<6f', subrecord.data[:24])
                self.position = (pos_x, pos_y, pos_z)
                self.rotation = (rot_x, rot_y, rot_z)
            if subrecord.sig == 'XSCL':    
                self.scale = struct.unpack_from('<f', subrecord.data)
                #print(self.scale)
            if subrecord.sig == 'XESP':
                self.parentformid, self.stateoppositeofparent_flag = struct.unpack_from('<II', subrecord.data)

    def renumber_formids(self, formid_chg_map, formid_map):
        super().renumber_formids(formid_chg_map, formid_map)
        #note that the original XESP bytes are not modified
        if self.parentformid:
            formid_bytes = bytearray(self.parentformid.to_bytes(4, 'big'))
            mod_id = formid_bytes[0]
            if formid_chg_map[mod_id] != mod_id:
                formid_bytes[0] = formid_chg_map[mod_id]
                self.parentformid = int.from_bytes(formid_bytes, 'big')
        if self.baserecordformid:
            formid_bytes = bytearray(self.baserecordformid.to_bytes(4, 'big'))
            mod_id = formid_bytes[0]
            if formid_chg_map[mod_id] != mod_id:
                formid_bytes[0] = formid_chg_map[mod_id]
                self.baserecordformid = int.from_bytes(formid_bytes, 'big')

    def is_disabled(self):
        return (((self.flags & (Record.FLAG_DISABLED | Record.FLAG_IGNORED | Record.FLAG_DELETED)) != 0) \
            or (self.stateoppositeofparent_flag == 1 and self.parentformid == 20)) #20 = 14h is the formid of the player
    

    def get_parent_formid(self):
        for subrecord in self.subrecords:
            if subrecord.sig == 'XESP':
                return subrecord.parentformid, subrecord.stateoppositeofparent_flag
        return None, False

class RecordSTAT(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        self.model_filename = None
        super().__init__(sig, data_size, flags, form_id, vc_info, data, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'MODL':
                self.model_filename = subrecord.data.decode('ascii').rstrip('\x00')

class RecordTREE(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        self.model_filename = None
        
        super().__init__(sig, data_size, flags, form_id, vc_info, data, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'MODL':
                self.model_filename = subrecord.data.decode('ascii').rstrip('\x00')

class RecordWRLD(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        self.editor_id = None
        super().__init__(sig, data_size, flags, form_id, vc_info, data, **kwargs)
        
        
    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'EDID':
                self.editor_id = subrecord.data.decode('ascii').rstrip('\x00')
                

class RecordUseless(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        #print('Creating a record')
        self.sig = sig  # str 4 bytes
        self.data_size = data_size      # uint32
        self.flags = flags              # uint32
        self.form_id = form_id          # uint32
        self.vc_info = vc_info          # uint32
        self.data = None                # raw bytes
        self.subrecords = []

        
    def parse_subrecords(self, data):
        pass



class Group:
    def __init__(self, sig, group_size, label, typeid, version, records, parent_worldspace,**kwargs):
        self.sig = sig                  # 4 bytes
        self.size = group_size          # uint32
        self.label = label              # uint32
        self.typeid = typeid            # uint32
        self.version = version          # uint32
        self.records = records          # list
        self.parent_worldspace = parent_worldspace          # list of worldspace records

    def serialize(self):
        content = b''.join(r.serialize() for r in self.records)
        group_size = len(content) + 20  # 24 bytes for the group header
        header = struct.pack('<4sIIII', b'GRUP', group_size, self.label,
                             self.typeid, self.version)
        return header + content
    
    def renumber_formids(self, formid_chg_map, formid_map):
        for record in self.records:
            record.renumber_formids(formid_chg_map, formid_map)

class ESPParser:
    def __init__(self):
        self.records = []               # Top-level records and groups
        self.formid_map = {}            # FormID to Record mapping
        self.load_order = []

    def parse(self, filename):
        with open(filename, 'rb') as f:
            data = f.read()
        self._parse_data(data)       

    def _parse_data(self, data, offset=0, end=None):
        if end is None:
            end = len(data)
        while offset < end:
            record_type = data[offset:offset+4].decode('ascii')
            if record_type == 'GRUP':
                group_size = struct.unpack_from('<I', data, offset+4)[0]
                group_end = offset + group_size
                label, group_type, vc_info = struct.unpack_from('<III', data, offset+8)
                group = Group(record_type, group_size, label, group_type, vc_info, [], None)
                offset += 20  
                self._parse_group(data, offset, group_end, group)
                self.records.append(group)
                offset = group_end
            else:
                record = self._parse_record(data, offset, self)
                self.records.append(record)
                self.formid_map[record.form_id] = record
                offset += 20 + record.data_size  # 20 bytes header + data

    def _parse_group(self, data, offset, end, group):
        while offset < end:
            record_type = data[offset:offset+4].decode('ascii')
            if record_type == 'GRUP':
                group_size = struct.unpack_from('<I', data, offset+4)[0]
                group_end = offset + group_size
                label, group_type, vc_info = struct.unpack_from('<III', data, offset+8)
                subgroup = Group(record_type, group_size, label, group_type, vc_info, [], group.parent_worldspace)
                offset += 20  
                self._parse_group(data, offset, group_end, subgroup)
                group.records.append(subgroup)
                offset = group_end
            else:
                record = self._parse_record(data, offset, group)
                if record.sig == 'WRLD':
                    group.parent_worldspace = record
                group.records.append(record)
                self.formid_map[record.form_id] = record
                offset += 20 + record.data_size

    def _parse_record(self, data, offset, parent_group):
        header = struct.unpack_from('<4sIIII', data, offset)
        record_type = header[0].decode('ascii')
        data_size = header[1]
        flags = header[2]
        form_id = header[3]
        vc_info = header[4]
        record_data = data[offset+20:offset+20+data_size]
        if record_type == 'REFR':
            return RecordREFR(record_type, data_size, flags, form_id, vc_info, record_data, parent_group.parent_worldspace)
        elif record_type == 'STAT':
            return RecordSTAT(record_type, data_size, flags, form_id, vc_info, record_data)
        elif record_type == 'TREE':
            return RecordTREE(record_type, data_size, flags, form_id, vc_info, record_data)
        elif record_type == 'WRLD':
            return RecordWRLD(record_type, data_size, flags, form_id, vc_info, record_data)
        elif record_type == 'TES4':
            TES4Record = RecordTES4(record_type, data_size, flags, form_id, vc_info, record_data)
            for i, master in enumerate(TES4Record.master_files):
                self.load_order.append([i, master])
            return TES4Record
        elif record_type == 'ACHR' or record_type == 'ACRE' or record_type == 'CELL':
            return Record(record_type, data_size, flags, form_id, vc_info, record_data)
        else:
            return RecordUseless(record_type, data_size, flags, form_id, vc_info, None)
        #everything else not needed for LOD
            

    def find_record_by_formid(self, formid):
        return self.formid_map.get(formid)
    
    def reconstruct(self, filename):
        with open(filename, 'wb') as f:
            for item in self.records:
                f.write(item.serialize())

    def renumber_formids(self, formid_chg_map):
        for record in self.records:
            record.renumber_formids(formid_chg_map, self.formid_map)


class BSAParser(): 

    FLAG_COMPRESSED = 0x00000004
    FLAG_FULL_PATH_IN_BLOCK = 0x00000100

    def __init__(self):
        self.files = {}
        self.flags = None
        self.folder_count = None
        self.files_count = None
        self.compressed = None
        self.filename = None
        self.full_path_in_block = None

    def parse(self, filename):
        self.filename = filename
        with open(filename, 'rb') as f:
            data = f.read(3000000) #around first 3MB, an overkill for all but some theoretical bsas
        self._parse_data(data)



    def CalculateHash(self, fileName):
        """Returns tes4's two hash values for filename.
        Based on TimeSlips code with cleanup and pythonization."""
        """Source: https://en.uesp.net/wiki/Oblivion_Mod:Hash_Calculation#Python"""
        root,ext = os.path.splitext(fileName.lower()) #--"bob.dds" >> root = "bob", ext = ".dds"
        #--Hash1
        chars = [ord(x) for x in root] #map(ord,root) #--'bob' >> chars = [98,111,98]

        if len(chars) > 1:
            hash1 = chars[-1] | (0,chars[-2])[len(chars)>2]<<8 | len(chars)<<16 | chars[0]<<24
        else:
            hash1 = chars[-1] | (0,chars[-1])[len(chars)>2]<<8 | len(chars)<<16 | chars[0]<<24
        
        #--(a,b)[test] is similar to test?a:b in C. (Except that evaluation is not shortcut.)
        if   ext == '.kf':  hash1 |= 0x80
        elif ext == '.nif': hash1 |= 0x8000
        elif ext == '.dds': hash1 |= 0x8080
        elif ext == '.wav': hash1 |= 0x80000000
        #--Hash2
        #--Python integers have no upper limit. Use uintMask to restrict these to 32 bits.
        uintMask, hash2, hash3 = 0xFFFFFFFF, 0, 0 
        for char in chars[1:-2]: #--Slice of the chars array
            hash2 = ((hash2 * 0x1003f) + char ) & uintMask
        for char in (ord(x) for x in ext): #--map(ord,ext)
            hash3 = ((hash3 * 0x1003F) + char ) & uintMask
        hash2 = (hash2 + hash3) & uintMask
        #--Done
        return (hash2<<32) + hash1 #--Return as uint64
    

    def _parse_data(self, data):
        #36 bytes
        magic_number, bsa_version, folder_offset, flags, \
        n_folders, n_files, l_foldernames, \
        l_filenames, content_flags = struct.unpack_from('<4sIIIIIIII', data[:36], 0)
        
        if magic_number != b'BSA\x00':
            logging.error('Error: Not a BSA')
            return
        self.flags = flags
        #print(self.flags)
        self.folder_count = n_folders
        self.files_count = n_files
        self.compressed = (self.flags & self.FLAG_COMPRESSED)
        #print(self.compressed)
        self.full_path_in_block = (self.flags & self.FLAG_FULL_PATH_IN_BLOCK)
        

        #filenames
        offset = 36 + n_folders*16 + (l_foldernames + n_folders + 16 * n_files)
        files = {}
        for filename in data[offset:offset+l_filenames].split(b'\x00'):
            try:
                if filename != b'':
                    files[self.CalculateHash(filename.decode('ascii'))] = filename.decode('ascii')
            except:
                logging.error(f'Error: filename decoding error for {filename}')

        #folders
        for folder_index in range(n_folders):
            folder_hash, n_files, offset = struct.unpack_from('<QII', data, 36 + folder_index*16)
            offset -= l_filenames 
            string_length = data[offset]
            #string_length = int.from_bytes(data[offset], signed=False, byteorder='little')
            folder_path = data[offset + 1:offset + 1 + string_length].decode('ascii').rstrip('\x00')
            folder_files = []
            for i in range(n_files):
                try:
                    file_hash, file_size, file_pointer = struct.unpack_from('<QII', data, offset + string_length + 1 + i*16)
                    real_size = file_size & 0x3FFFFFFF  # Mask: 0011 1111 ....
                    compression_flag = (file_size >> 30) & 0x1  # Shift right by 30, and mask with 0x1 (bit 30)
                    file_name = files[file_hash]
                    full_path = os.path.join(folder_path, file_name)
                    self.files[full_path] = (file_pointer, real_size, compression_flag)
                except:
                    logging.error('Error: hashed file not found')


    def get_list_of_files(self):
        return self.files.keys()

    def extract(self, files, output_folder):
        with open(self.filename, 'rb') as f:
            for file in files:
                file = os.path.join(file)
                if file in self.files:
                    offset, size, compression_flag = self.files[file]
                    #if self.full_path_in_block: #apparenly wrong info in uesp
                    #    offset += data[offset] + 1
                    if self.compressed:
                        offset += 4
                        f.seek(offset)
                        data = f.read(size)
                        decompressed_file = zlib.decompress(data)
                    else:
                        f.seek(offset)
                        data = f.read(size)
                        decompressed_file = data
                    os.makedirs(os.path.dirname(os.path.join(output_folder, file)), exist_ok=True)
                    output_file = open(os.path.join(output_folder, file), 'wb')
                    output_file.write(decompressed_file)
                    output_file.close()
                else:
                    logging.error(f'Error: file {file} not found')
        





def sort_esp_list(filepath, folder):
    file_list = []
    with open(filepath, 'r') as file:
        filenames = [line.strip() for line in file if line.strip()]
        
    for filename in filenames:
        full_filename = os.path.join(folder, filename)
        _, extension = os.path.splitext(filename)
        extension = extension.lower()
        modified_time = os.path.getmtime(full_filename)   
        file_list.append((filename, extension, modified_time))

    def sorter(item):
        filename, extension, modified_time = item
        is_esp = extension != '.esm'
        return(is_esp, modified_time)
    
    sorted_list = sorted(file_list, key=sorter)

    return [n[0] for n in sorted_list]

load_order = sort_esp_list(plugins_txt, folder)

logging.info(f'{load_order}')

signatures = ['REFR', 'STAT', 'TREE']
object_dict = {}

try:
    mergedLOD_index = load_order.index('MergedLOD.esm')
except:
    logging.critical('Error: MergedLOD.esm not found in load order')
    exit()

load_order_lowercase = [x.lower() for x in load_order]

for plugin in load_order:
    parser = ESPParser()
    logging.info('Reading: ' + plugin)
    parser.parse(os.path.join(folder, plugin))
    plugin_lo = parser.load_order
    master_map = {}
    try:
        for entry in plugin_lo:
            index = load_order_lowercase.index(entry[1].lower())
            master_map[entry[0]] = index
        master_map[len(master_map)] = load_order_lowercase.index(plugin.lower())
    except ValueError:
        logging.critical(f'Error: masters missing for plugin: {plugin}')
        logging.critical(f'Expected masters: {plugin_lo}')
        exit()

    if len(master_map) > 0:
        if not all(key == value for key, value in master_map.items()):
            parser.renumber_formids(master_map)

    for record in parser.formid_map:
        if parser.formid_map[record].sig in signatures:
            object_dict[record] = parser.formid_map[record]

logging.info('Processing LOD files')

bsa_files = [f for f in os.listdir(folder) if f.endswith('.bsa')]

bsa_loadorder = ['Oblivion - Meshes.bsa', 'Oblivion - Misc.bsa', 'Oblivion - Textures - Compressed.bsa']
#TODO: skipper for some bsas like OUT

far_mesh_list = []
tree_billboard_textures = []

for plugin in load_order:
    for file in bsa_files:
        if file.lower().startswith(plugin.lower().replace('.esp', '')):
            bsa_loadorder.append(file)
            
for bsa in bsa_loadorder:
    bsa_obj = BSAParser()
    logging.info(f'Reading BSA: {bsa}')
    bsa_obj.parse(os.path.join(folder, bsa))
    list_to_extract = []
    for file in bsa_obj.get_list_of_files():
        if file.lower().endswith("_far.nif"):
            list_to_extract.append(file)

        if file.lower().startswith("textures\\trees\\billboards"):
            tree_billboard_textures.append(file)

    if len(list_to_extract) > 0:
        try:
            bsa_obj.extract(list_to_extract, os.path.join(folder, 'LODMerger'))
            far_mesh_list += list_to_extract
        except:
            logging.error(f'Failed to extract LOD files from {bsa}')


far_statics = []
far_trees = []

logging.info('Processing base objects...')

#going through every STAT and TREE and understanding if it can be VWD
for obj in object_dict:
    
    if object_dict[obj].sig == 'STAT':
        mesh_found = False
        try:
            if os.path.exists(os.path.join(folder, 'meshes', object_dict[obj].model_filename.lower().replace('.nif', '_far.nif'))):
                    far_statics.append(obj)
                    mesh_found = True
        except AttributeError:
            pass

        if not mesh_found:
            try:
                if 'meshes\\' + object_dict[obj].model_filename.lower().replace('.nif', '_far.nif') in far_mesh_list:
                    far_statics.append(obj)
            except AttributeError:
                pass


    elif object_dict[obj].sig == 'TREE':
        billboard_found = False
        try:
            if 'textures\\trees\\billboards' + object_dict[obj].model_filename.lower().replace('.spt', '.dds') in tree_billboard_textures:
                billboard_found = True
                far_trees.append(obj)
        except AttributeError:
            pass
        if not billboard_found:
            try:
                if os.path.exists(os.path.join(folder, 'textures\\trees\\billboards', object_dict[obj].model_filename.lower().replace('.spt', '.dds'))):
                    far_trees.append(obj)
            except AttributeError:
                pass


LODGen = {}

logging.info('Generating list of LOD objects..')

for obj_id in dict(sorted(object_dict.items())):
    obj = object_dict[obj_id]
    if obj.sig == 'REFR':
        if obj.parent_worldspace:
            if obj.baserecordformid in far_statics or obj.baserecordformid in far_trees:
                if not obj.is_disabled(): #TODO: parent checks
                    worldspace = obj.parent_worldspace.editor_id
                    if worldspace in worldspaces_to_skip:
                        continue
                    if not worldspace in LODGen:
                        LODGen[worldspace] = {}
                    
                    x_cell = math.floor(obj.position[0] / 4096)
                    y_cell = math.floor(obj.position[1] / 4096)
                    if not x_cell in LODGen[worldspace]:
                        LODGen[worldspace][x_cell] = {}
                    if not y_cell in LODGen[worldspace][x_cell]:
                        LODGen[worldspace][x_cell][y_cell] = []
                    LODGen[worldspace][x_cell][y_cell].append([obj.baserecordformid, obj.position, obj.rotation, obj.scale])

merger = NifProcessor()
merger.EMPTY_NIF_PATH = empty_nif_template

def MiddleOfCellCalc(cell_x, cell_y):
    
    #returns coordinates of the cell center, useful for large cell-size merges
    x_offset = (cell_x + 0.5) * 4096
    y_offset = (cell_y + 0.5) * 4096
    z_offset = 0

    return [x_offset, y_offset, z_offset]


record_offset = 2048 #first formid of the file

MODB_Template = Subrecord('MODB', 4, struct.pack('f', 2048.0))
STAT_Group = Group('GRUP', 0, 1413567571, 0, 0, [], None) #1347768903 = 'STAT'

end_time = time.time()                    
elapsed_time = end_time - start_time



logging.info(f"Mesh generation started: {elapsed_time:.6f} seconds")

for worldspace in LODGen:
    for i in sorted(LODGen[worldspace]):
        logging.info(f'Processing {worldspace} [{i},*]')
        for j in sorted(LODGen[worldspace][i]):
            logging.debug(f'Processing {worldspace} [{i},{j}]')
            mergeable_count = 0
            z_buffer = 0
            obj_to_merge = []
            for obj in LODGen[worldspace][i][j]:
                if object_dict[obj[0]].sig == 'STAT':
                    if object_dict[obj[0]].model_filename.lower() in meshes_to_skip:
                        continue
                    if skip_nif_generation:
                        if not os.path.exists(os.path.join(folder, 'meshes\\MergedLOD\\', worldspace + '_' + str(i) + '_' + str(j) + '.nif')) and \
                            not os.path.exists(os.path.join(folder, 'LODMerger\\meshes\\MergedLOD\\', worldspace + '_' + str(i) + '_' + str(j) + '_far.nif')):
                                continue
                    obj_to_merge.append(obj)
                    z_buffer += obj[1][2]
                    mergeable_count += 1
                    

            if mergeable_count > 1:
                
                average_z = z_buffer / mergeable_count
                middle_of_cell = MiddleOfCellCalc(i, j)

                if not skip_nif_generation:
                    merger.CleanTemplates()
                    for obj in obj_to_merge:
                    
                        mesh_file = object_dict[obj[0]].model_filename
                        path = os.path.join(folder, 'meshes', mesh_file.lower().replace('.nif', '_far.nif'))
                        if not os.path.exists(path):
                            path = os.path.join(folder, 'LODMerger', 'meshes', mesh_file.lower().replace('.nif', '_far.nif'))
                        position = [obj[1][0] - middle_of_cell[0], obj[1][1] - middle_of_cell[1], obj[1][2] - middle_of_cell[2] - average_z]
                        #radians to degrees
                        rotations = [obj[2][0] * 57.295779513, obj[2][1] * 57.295779513 , obj[2][2] * 57.295779513 ]
                        scale = obj[3]
                        if scale is None:
                            scale = 1.0
                        else:
                            scale = scale[0]
                        merger.ProcessNif(path, position, rotations, scale)
                    #merger.CleanAnimationController()
                    merger.SaveNif(os.path.join(folder, 'meshes\\MergedLOD', worldspace + '_' + str(i) + '_' + str(j) + '_far.nif'))
                    shutil.copyfile(empty_nif_template, \
                                    os.path.join(folder, 'meshes\\MergedLOD', worldspace + '_' + str(i) + '_' + str(j) + '.nif'))
                    
                    record_edid = 'LOD' + worldspace + ('n' if i < 0 else '') \
                                            + str(abs(i)) + ('n' if j < 0 else '')  + str(abs(j)) + '\x00'
                    STATRecord = RecordSTAT('STAT', 0, 0, record_offset, 0, b'')
                    EDID_Template = Subrecord('EDID', len(record_edid), \
                                            record_edid.encode('ascii'))
                    MODL_Template = Subrecord('MODL', len('MergedLOD\\' + worldspace + '_' + str(i) + '_' + str(j) + '.nif\x00'), \
                                            ('MergedLOD\\' + worldspace + '_' + str(i) + '_' + str(j) + '.nif').encode('ascii') + b'\x00')
                    STATRecord.subrecords.append(EDID_Template)
                    STATRecord.subrecords.append(MODL_Template)
                    STATRecord.subrecords.append(MODB_Template)
                    STAT_Group.records.append(STATRecord)
                

                LODGen[worldspace][i][j] = [obj for obj in LODGen[worldspace][i][j] if obj not in obj_to_merge]
                LODGen[worldspace][i][j].append([record_offset + mergedLOD_index * 16777216, [middle_of_cell[0], middle_of_cell[1], middle_of_cell[2] + average_z], [0, 0, 0], [1.0]])

                record_offset += 1

end_time = time.time()                    
elapsed_time = end_time - start_time
logging.info(f"Meshes generated: {elapsed_time:.6f} seconds")

new_esp = ESPParser()

HEDRTemplate = Subrecord('HEDR', 12, struct.pack('fII', 1.0, record_offset - 2048, record_offset))
CNAMTemplate = Subrecord('CNAM', 7, b'LODGen\x00')
SNAMTemplate = Subrecord('SNAM', 7, b'LODGen\x00')
TES4Record = RecordTES4('TES4', 0, 0, 0, 0, b'', master_files=[])
TES4Record.subrecords.append(HEDRTemplate)
TES4Record.subrecords.append(CNAMTemplate)
TES4Record.subrecords.append(SNAMTemplate)
new_esp.records.append(TES4Record)
new_esp.records.append(STAT_Group)
modified_time = os.path.getmtime(os.path.join(folder, 'MergedLOD.esm'))
new_esp.reconstruct(os.path.join(folder, 'MergedLOD.esm'))
os.utime(os.path.join(folder, 'MergedLOD.esm'), (modified_time, modified_time))

logging.info('Removing temp _far nif files...')

if os.path.exists(os.path.join(folder, 'LODMerger')):
    shutil.rmtree(os.path.join(folder, 'LODMerger'))

logging.info('Removing old LOD files...')

if os.path.exists(os.path.join(folder, 'distantlod')):
    shutil.rmtree(os.path.join(folder, 'distantlod'))

os.makedirs(os.path.join(folder, 'distantlod'))


for worldspace in LODGen:
    logging.info('Writing LOD for ' + worldspace)
    with open(os.path.join(folder, 'distantlod', worldspace + ".cmp"), 'wb') as cmp:

        for i in LODGen[worldspace]:
            for j in LODGen[worldspace][i]:
                
                cell_refs = LODGen[worldspace][i][j]
                unique_refs = sorted(set(ref[0] for ref in cell_refs))

                filename = os.path.join(folder, 'distantlod', f"{worldspace}_{i}_{j}.lod")

                with open(filename, 'wb') as lod_file:

                    lod_file.write(len(unique_refs).to_bytes(4, byteorder='little', signed=False))

                    for ref in unique_refs:
                        #formid
                        lod_file.write(ref.to_bytes(4, byteorder='little', signed=False))

                        count = 0
                        temp_refs = []
                        for r in cell_refs:
                            if r[0] == ref:
                                temp_refs.append(r)
                                count += 1
                                
                        lod_file.write(count.to_bytes(4, byteorder='little', signed=False))

                        #some of the edits there might not be needed,
                        # were done trying to eradicate black tree issues

                        for r in temp_refs:
                            lod_file.write(struct.pack('<fff', round(r[1][0]) + 0.5, round(r[1][1]) + 0.5, round(r[1][2]) + 0.970703125)) 
                            #xedit magic numbers, help trees not to look black (Oblivion doesn't like integer-like floats?)
                        
                        #rotation in radians
                        for r in temp_refs:
                            r[2] = [angle % 6.28318530718 for angle in r[2]]                            
                            lod_file.write(struct.pack('<fff', r[2][0], r[2][1], r[2][2]))

                        for r in temp_refs:
                            scale = r[3]
                            #print(scale)
                            if scale is None:
                                scale = 1.0
                            else:
                                scale = scale[0]
                            if abs(scale - 0) < 0.01:
                                scale = 1.0
                            scale *= 100
                            
                            scale += 0.970001220703 #xedit

                            lod_file.write(struct.pack('<f', scale))

                
                cmp.write((j).to_bytes(2, byteorder='little', signed=True))
                cmp.write((i).to_bytes(2, byteorder='little', signed=True))

    
        cmp.write((7).to_bytes(4, byteorder='little', signed=False))



end_time = time.time()
elapsed_time = end_time - start_time
logging.info(f"Finished in {elapsed_time:.6f} seconds")