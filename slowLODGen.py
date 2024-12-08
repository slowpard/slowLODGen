import os
import time
time.clock = time.time #hack as time.clock is not available since python 3.8, open-source and backward compatibility... :cry:
import math
import logging
import yaml
import winreg
import struct
import zlib
import math
import shutil
from NifMerger.NifProcessor import NifProcessor
import gc
import csv


start_time = time.time()

#PATHS
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LODGen_config.yaml'), "r") as file:
        config = yaml.safe_load(file)
except:
    logging.critical("LODGen_config.yaml not found, using default values...")
    
counter = 0

try:
    debug_level = config["debug_level"]
except:
    debug_level = "INFO"


logging.basicConfig(
    level=logging._nameToLevel[debug_level.upper()],  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(lineno)s - %(levelname)s - %(message)s',  
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output.log'), mode='w'),  # Log to a file
        logging.StreamHandler()             # Log to console
    ],
    datefmt='%H:%M:%S'
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
    bsa_name = config["custom_bsa_name"]
except:
    bsa_name = ""

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
else:
    if not os.path.exists(plugins_txt):
        logging.critical(f"Plugins.txt not found at the defined path {plugins_txt}, exiting...")
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

for i, mesh in enumerate(meshes_to_skip):
    meshes_to_skip[i] = mesh.lower()

try:
    hardcoded_bsas = config["hardcoded_bsas"]
except:
    hardcoded_bsas = ['Oblivion - Meshes.bsa', 'Oblivion - Misc.bsa', 'Oblivion - Textures - Compressed.bsa',
                    'N - Meshes.bsa', 'N - Textures1.bsa', 'N - Textures2.bsa', 'N - Misc.bsa']

empty_nif_template = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'empty_ninode.nif')

if not os.path.exists(empty_nif_template):
    logging.critical("empty_ninode.nif template not found, check the tool installation, exiting...")
    exit()

try:
    generate_bsa = config["write_bsa"]
except:
    generate_bsa = False


try:
    triangle_profiler = config["triangle_profiler"]
except:
    triangle_profiler = False

try:
    water_culling = config["water_culling"]
except:
    water_culling = False



class Subrecord:
    def __init__(self, sig, size, data, has_size=True, **kwargs):
        self.sig = sig   # str 4 bytes
        self.size = size # uint16
        self.data = data # raw bytes
        self.has_size = has_size

    def serialize(self):
        if self.has_size:
            header = struct.pack('<4sH', self.sig.encode('utf-8'), self.size)
            return header + self.data
        else:  
            return self.sig.encode('utf-8') + self.data

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

    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs):
        #logging.debug('Creating a record')
        self.sig = sig  # str 4 bytes
        self.data_size = data_size      # uint32
        self.flags = flags              # uint32
        self.form_id = form_id          # uint32
        self.vc_info = vc_info          # uint32
        self.data = data                # raw bytes
        self.subrecords = []
        self.parent_group = parent_group

        if self.is_compressed() and False: #disabled for now, used for testing landscape culling
            data = zlib.decompress(data[4:])          
            self.parse_subrecords(data)
        else:
            self.parse_subrecords(data)

    def is_compressed(self):
        return (self.flags & self.FLAG_COMPRESSED) != 0
    

    def parse_subrecords(self, data):
        offset = 0

        while offset < len(data):
            sig = data[offset:offset+4].decode('utf-8')
            if sig == 'OFST':
                break #actually don't need it
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
            header = struct.pack('<4sIIII', self.sig.encode('utf-8'),
                self.data_size, self.flags, self.form_id,
                self.vc_info)
            return header + self.data
        else:

            subrecords_data = b''.join(sub.serialize() for sub in self.subrecords)
            self.data_size = len(subrecords_data)
            header = struct.pack('<4sIIII', self.sig.encode('utf-8'),
                self.data_size, self.flags, self.form_id,
                self.vc_info)
            return header + subrecords_data
        
    def renumber_formids(self, formid_chg_map, formid_map):
        formid_bytes = bytearray(self.form_id.to_bytes(4, 'big'))
        mod_id = formid_bytes[0]
        if mod_id >= len(formid_chg_map):
            logging.warning(f'HITME record detected! Local FormID: {hex(self.form_id)} \n' 
                            'HITMEs most commonly occur when a master was improperly removed. The behavior of these plugins is undefined and may lead to them not working correctly or causing CTDs.')
            mod_id = len(formid_chg_map) - 1
        if formid_chg_map[mod_id] != mod_id:
            old_formid = self.form_id
            formid_bytes[0] = formid_chg_map[mod_id]
            self.form_id = int.from_bytes(formid_bytes, 'big')
            if old_formid in formid_map:
                formid_map.pop(old_formid)
            else:
                logging.warning(f'Warning: FormID {hex(self.form_id)} is used twice. \n'
                                'The behavior of plugins with such records is undefined and may lead to them not working correctly or causing CTDs.')
            formid_map[self.form_id] = self
    
class RecordTES4(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs):
        self.master_files = []
        super().__init__(sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        self.master_files = []
        for subrecord in self.subrecords:
            if subrecord.sig == 'MAST':
                self.master_files.append(subrecord.data.decode('utf-8').rstrip('\x00'))
                #print('masterfile:', self.master_files[-1])
        #print(self.master_files)

class RecordREFR(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_group, parent_worldspace, **kwargs):
        self.position = None
        self.rotation = None
        self.scale = None
        self.parentformid = None
        self.stateoppositeofparent_flag = None
        self.baserecordformid = None
        self.parent_worldspace = None
        super().__init__(sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs)
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
            if mod_id >= len(formid_chg_map):
                logging.warning(f'HITME record detected! Local FormID: {hex(self.form_id)} \n' 
                                'HITMEs most commonly occur when a master was improperly removed. The behavior of these plugins is undefined and may lead to them not working correctly or causing CTDs.')
                mod_id = len(formid_chg_map) - 1
            if formid_chg_map[mod_id] != mod_id:
                formid_bytes[0] = formid_chg_map[mod_id]
                self.parentformid = int.from_bytes(formid_bytes, 'big')
        if self.baserecordformid:
            formid_bytes = bytearray(self.baserecordformid.to_bytes(4, 'big'))
            mod_id = formid_bytes[0]
            if mod_id >= len(formid_chg_map):
                logging.warning(f'HITME record detected! Local FormID: {hex(self.form_id)} \n' 
                                'HITMEs most commonly occur when a master was improperly removed. The behavior of these plugins is undefined and may lead to them not working correctly or causing CTDs.')
                mod_id = len(formid_chg_map) - 1
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
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs):
        self.model_filename = None
        super().__init__(sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'MODL':                
                self.model_filename = subrecord.data.decode('windows-1252').rstrip('\x00')


class RecordACTI(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs):
        self.model_filename = None
        super().__init__(sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'MODL':                
                self.model_filename = subrecord.data.decode('windows-1252').rstrip('\x00')

class RecordTREE(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs):
        self.model_filename = None
        
        super().__init__(sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'MODL':
                self.model_filename = subrecord.data.decode('windows-1252').rstrip('\x00')

class RecordWRLD(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs):
        self.editor_id = None
        super().__init__(sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs)
        
        
    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'EDID':
                self.editor_id = subrecord.data.decode('windows-1252').rstrip('\x00')

class RecordCELL(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_group, parent_worldspace, **kwargs):
        self.parent_worldspace = parent_worldspace
        self.cell_coordinates = None
        super().__init__(sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'XCLC':
                self.cell_coordinates = struct.unpack_from('<ii', subrecord.data)

class RecordLAND(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs):
        self.heightmap = []
        super().__init__(sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs)
        

    def parse_subrecords(self, data):
        offset = 0       
        while offset < len(data):
            
            
            sig = data[offset:offset+4].decode('utf-8')
            size = struct.unpack_from('<H', data, offset+4)[0]

            if sig != 'VHGT':
                offset += 6 + size
                continue

            sub_data = data[offset+6:offset+6+size]
            subrecord = Subrecord(sig, size, sub_data)
            self.subrecords.append(subrecord)
            offset += 6 + size  # 6 bytes header + data

        self.data = None


    def parse_heightmap(self):
        heightmap = [[0] * 33 for _ in range(33)]
        cell_offset = None
        for subrecord in self.subrecords:
            if subrecord.sig == 'VHGT':
                cell_offset = struct.unpack('<f', subrecord.data[:4])[0] 
                gradient_data = struct.unpack('1089b', subrecord.data[4:4+1089])

        if not cell_offset:
            return False
        
        offset = cell_offset * 8
        for i in range(1089):
            row = i // 33
            col = i % 33

            if col == 0:
                row_offset = 0
                offset += gradient_data[i] * 8
            else:
                row_offset += gradient_data[i] * 8

            heightmap[row][col] = offset + row_offset

        return heightmap





class RecordUseless(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, parent_group, **kwargs):
        #print('Creating a record')
        self.sig = sig  # str 4 bytes
        if sig == 'REFR':
            self.sig = 'REFU'
        self.data_size = data_size      # uint32
        #self.flags = flags              # uint32
        self.form_id = form_id          # uint32
        #self.vc_info = vc_info          # uint32
        #self.data = None                # raw bytes
        #self.subrecords = []

        
    def parse_subrecords(self, data):
        pass



class Group:
    def __init__(self, sig, group_size, label, typeid, version, parent_group, records, parent_worldspace,**kwargs):
        self.sig = sig                  # 4 bytes
        self.size = group_size          # uint32
        self.label = label              # uint32
        self.typeid = typeid            # uint32
        self.version = version          # uint32
        self.records = records          # list
        self.parent_worldspace = parent_worldspace          # list of worldspace records
        self.parent_group = parent_group

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
        self.exterior_cell_list = []

    def parse(self, filename):
        with open(filename, 'rb') as f:
            self._parse_data(f)       
    
    def _parse_data(self, f):
        while True:
            offset = f.tell()
            record_type_b = f.read(4)
            if not record_type_b or len(record_type_b) < 4:
                break
            record_type = record_type_b.decode('utf-8')
            if record_type == 'GRUP':
                group_size_bytes = f.read(4)
                if not group_size_bytes or len(group_size_bytes) < 4:
                    break
                group_size = struct.unpack('<I', group_size_bytes)[0]
                header_b = f.read(12)
                if not header_b or len(header_b) < 12:
                    break
                label, group_type, vc_info = struct.unpack('<III', header_b)
                group = Group(record_type, group_size, label, group_type, vc_info, None, [], None)
                group_end = offset + group_size
                self._parse_group(f, group_end, group)
                self.records.append(group)
                f.seek(group_end)
            else:
                f.seek(offset)
                record = self._parse_record(f, self)
                self.records.append(record)
                self.formid_map[record.form_id] = record
                f.seek(offset + 20 + record.data_size)  # 20 bytes header + data
    
    def _parse_group(self, f, end, group):
        while f.tell() < end:
            offset = f.tell()
            record_type_b = f.read(4)
            if not record_type_b or len(record_type_b) < 4:
                break
            record_type = record_type_b.decode('utf-8')
            if record_type == 'GRUP':
                group_size_bytes = f.read(4)
                group_size = struct.unpack('<I', group_size_bytes)[0]
                label_b = f.read(12)
                label, group_type, vc_info = struct.unpack('<III', label_b)
                subgroup = Group(record_type, group_size, label, group_type, vc_info, group, [], group.parent_worldspace)
                group_end = offset + group_size 
                self._parse_group(f, group_end, subgroup)
                group.records.append(subgroup)
                f.seek(group_end)
            else:
                f.seek(offset) 
                record = self._parse_record(f, group)
                if record.sig == 'WRLD':
                    group.parent_worldspace = record
                group.records.append(record)
                self.formid_map[record.form_id] = record
                f.seek(offset + 20 + record.data_size)  # 20 bytes header + data
                
    def _parse_record(self, f, parent_group):
        offset = f.tell()
        header_b = f.read(20)
        if not header_b or len(header_b) < 20:
            return None
        header = struct.unpack('<4sIIII', header_b)
        record_type = header[0].decode('utf-8')
        data_size = header[1]
        flags = header[2]
        form_id = header[3]
        vc_info = header[4]
        if record_type in ('REFR', 'STAT', 'TREE', 'WRLD', 'TES4', 'ACHR', 'ACRE', 'CELL', 'ACTI', 'LAND'):
            record_data = f.read(data_size)
        if record_type == 'REFR' and parent_group.parent_worldspace:
            return RecordREFR(record_type, data_size, flags, form_id, vc_info, record_data, parent_group, parent_group.parent_worldspace)
        elif record_type == 'STAT':
            return RecordSTAT(record_type, data_size, flags, form_id, vc_info, record_data, parent_group)
        elif record_type == 'ACTI':
            return RecordACTI(record_type, data_size, flags, form_id, vc_info, record_data, parent_group)
        elif record_type == 'TREE':
            return RecordTREE(record_type, data_size, flags, form_id, vc_info, record_data, parent_group)
        elif record_type == 'WRLD':
            return RecordWRLD(record_type, data_size, flags, form_id, vc_info, record_data, parent_group)
        elif record_type == 'TES4':
            TES4Record = RecordTES4(record_type, data_size, flags, form_id, vc_info, record_data, parent_group)
            for i, master in enumerate(TES4Record.master_files):
                self.load_order.append([i, master])
            return TES4Record
        #elif record_type == 'CELL':
        #    cell_record = RecordCELL(record_type, data_size, flags, form_id, vc_info, record_data, parent_group, parent_group.parent_worldspace)
        #    if cell_record.cell_coordinates:
        #        self.exterior_cell_list.append([parent_group.parent_worldspace, cell_record.cell_coordinates, cell_record, parent_group])
        #    return cell_record
        #elif record_type == 'LAND':
        #    return RecordLAND(record_type, data_size, flags, form_id, vc_info, record_data, parent_group)
        elif record_type in ('ACHR', 'ACRE'):
            return Record(record_type, data_size, flags, form_id, vc_info, record_data, parent_group)
        else:
            return RecordUseless(record_type, data_size, flags, form_id, vc_info, None, parent_group)
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

    FLAG_HAS_DIRECTORY_NAMES = 0x00000001   
    FLAG_HAS_FILE_NAMES = 0x00000002        
    FLAG_COMPRESSED = 0x00000004            
    FLAG_UNKNOWN2 = 0x00000008              
    FLAG_UNKNOWN3 = 0x00000010              
    FLAG_UNKNOWN4 = 0x00000020              
    FLAG_BIG_ENDIAN = 0x00000040            
    FLAG_UNKNOWN5 = 0x00000080              
    FLAG_UNKNOWN6 = 0x00000100             
    FLAG_UNKNOWN7 = 0x00000200             
    FLAG_UNKNOWN8 = 0x00000400              

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
        #self.full_path_in_block = (self.flags & self.FLAG_FULL_PATH_IN_BLOCK)  #apparently wrong info in uesp
        

        #filenames
        offset = 36 + n_folders*16 + (l_foldernames + n_folders + 16 * n_files)
        files = {}
        for filename in data[offset:offset+l_filenames].split(b'\x00'):
            try:
                if filename != b'':
                    files[self.CalculateHash(filename.decode('windows-1252'))] = filename.decode('windows-1252')
            except:
                logging.error(f'Error: filename decoding error for {filename}')

        #folders
        for folder_index in range(n_folders):
            folder_hash, n_files, offset = struct.unpack_from('<QII', data, 36 + folder_index*16)
            offset -= l_filenames 
            string_length = data[offset]
            #string_length = int.from_bytes(data[offset], signed=False, byteorder='little')
            folder_path = data[offset + 1:offset + 1 + string_length].decode('windows-1252').rstrip('\x00')
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
                    if (self.compressed and compression_flag == 0) or (not self.compressed and compression_flag): 
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
                    data = None
                else:
                    logging.error(f'Error: file {file} not found')
        
    def pack(self, output_filename, files, root):

        file_info = []
        folders = {}
        total_folder_name_length = 0
        total_file_name_length = 0
        n_folders = 0
        n_files = 0

        hashed_files = {}

        for file in files:
            file = file.lower()
            full_path = os.path.join(root, file)
            if not os.path.isfile(full_path):
                logging.error(f"File not found: {full_path}")
                continue
            file_size = os.path.getsize(full_path)
            folder, file_name = os.path.split(file)
            file_entry = {
                'full_path': full_path,
                'relative_path': file,
                'folder': folder,
                'file_name': file_name,
                'size': file_size,
                'file_hash': self.CalculateHash(file_name),
                'file_name_bytes': file_name.encode('windows-1252') + b'\x00',
                'file_name_length': len(file_name.encode('windows-1252')) + 1
            }
            
            total_file_name_length += file_entry['file_name_length'] # (TotalFileNameLength) Total length of all file names, including \0's.


            hashed_files[self.CalculateHash(file_name)] = file_entry

        hashed_files = dict(sorted(hashed_files.items())) #sort by hash or Oblivion won't read it

        for file in hashed_files.values():            
            folder = file['folder']
            if folder not in folders:
                folders[folder] = {
                    'folder_name': folder,
                    'files': []
                }
            folders[folder]['files'].append(file)

        for folder_name, folder_data in folders.items():
            folder_data['folder_hash'] = self.CalculateHash(folder_data['folder_name'])
            folder_name_bytes = folder_data['folder_name'].encode('windows-1252')
            folder_data['folder_name_bytes'] = struct.pack('B', len(folder_name_bytes) + 1) + folder_name_bytes + b'\x00'
            folder_data['folder_name_length'] = len(folder_name_bytes) + 1  
            total_folder_name_length += folder_data['folder_name_length'] #Total length of all folder names, including \0's but not including the prefixed length byte.

        folders = dict(sorted(folders.items(), key=lambda x: x[1]['folder_hash'])) #sort by hash or Oblivion won't read it
        n_folders = len(folders)
        n_files = sum(len(folder_data['files']) for folder_data in folders.values())

        #OFFSETS
        header_size = 36
        folder_records_offset = header_size
        folder_records_size = n_folders * 16
        file_records_offset = folder_records_offset + folder_records_size
        #print(hex(file_records_offset))
        file_records_size = n_files * 16 + total_folder_name_length + n_folders
        file_names_offset = file_records_offset + file_records_size
        #print(hex(file_names_offset))
        file_data_offset = file_names_offset + total_file_name_length
        #print(hex(file_data_offset))
        offset = file_records_offset
        for folder in folders.values():
            folder['name_offset'] = offset + total_file_name_length #uint32 - Offset to name and file records for this folder. (Seems to include Total File Name Length
                                                                    # #:todd_grin:
            offset += folder_data['folder_name_length'] + 16

       
        offset = file_data_offset
        for folder in folders.values():
            for file in folder['files']:
                file['data_absolute_offset'] = offset
                offset += file['size']

        flags = self.FLAG_HAS_DIRECTORY_NAMES | self.FLAG_HAS_FILE_NAMES | self.FLAG_UNKNOWN5 | self.FLAG_UNKNOWN6 | self.FLAG_UNKNOWN7 | self.FLAG_UNKNOWN8
        content_flags = 0x00000000
        for folder_data in folders.values(): #how much perf would we save not doing this?
            for file_entry in folder_data['files']:
                ext = os.path.splitext(file_entry['file_name'].lower())[1]
                if ext == '.nif':
                    content_flags |= 0x00000001
                elif ext == '.lod':
                    content_flags |= 0x00000001
                    content_flags |= 0x00000100
                elif ext == '.dds':
                    content_flags |= 0x00000002
                elif ext == '.xml':
                    content_flags |= 0x00000004
                elif ext == '.wav':
                    content_flags |= 0x00000008
                elif ext == '.mp3':
                    content_flags |= 0x00000010
                elif ext == '.sdp':
                    content_flags |= 0x00000020
                elif ext == '.ctl':
                    content_flags |= 0x00000040
                elif ext == '.fnt':
                    content_flags |= 0x00000080
                else:
                    content_flags |= 0x00000100  

        with open(output_filename, 'wb') as f:
            
            magic_number = b'BSA\x00'
            version = 103 #Oblivion
            f.write(struct.pack(
                '<4sIIIIIIII',
                magic_number,
                version,
                folder_records_offset,
                flags,
                n_folders,
                n_files,
                total_folder_name_length,
                total_file_name_length,
                content_flags
            ))

            '''Folder records
            uint64 - Hash of the folder name (eg: menus[slash]chargen).
            uint32 - (FolderFileCount) Number of files in this folder.
            uint32 - Offset to name and file records for this folder. (Seems to include Total File Name Length'''

            for folder_data in folders.values():
                f.write(struct.pack(
                    '<QII',
                    folder_data['folder_hash'],
                    len(folder_data['files']),
                    folder_data['name_offset']
                ))

            '''Folder name and files
            bzstring - Name of the folder. (Only present if bit 1 of archive flags is set.)
            struct[FolderFileCount] - File records in the given folder.
                uint64 - Hash of the file name (eg: race_sex_menu.xml).
                uint32 - (FileSize) Size of the file data. Note that the top two bits have special meaning and are not actually part of the size.
                If bit 30 is set in the size, the default compression is inverted for this file (i.e., if the default is compressed, this file is not compressed, and vice versa).
                Bit 31 is used internally to determine if an archive has been checked yet.
                uint32 - Offset to raw file data for this folder. Note that an "offset" is offset from file byte zero (start), NOT from this location.
            '''

            for folder_data in folders.values():
                f.write(folder_data['folder_name_bytes'])
                for file_entry in folder_data['files']:
                    f.write(struct.pack(
                        '<QII',
                        file_entry['file_hash'],
                        file_entry['size'],
                        file_entry['data_absolute_offset']
                    ))

            '''File name block. (Only present if bit 2 of the archive flags is set.)
            A list of lower case file names, one after another, each ending in a \0. They are ordered in the same order as those generated with the file folder block contents in the BSA archive.
            These are all the files contained in the archive, such as "cuirass.nif" and "cuirass.dds", etc (no paths, just the root names).'''

            # Write file names
            for folder_data in folders.values():
                for file_entry in folder_data['files']:
                    f.write(file_entry['file_name_bytes'])

            # Write file data blocks
            for folder_data in folders.values():
                for file_entry in folder_data['files']:
                    with open(file_entry['full_path'], 'rb') as file_data:
                        f.write(file_data.read())

        logging.info(f"BSA archive '{output_filename}' created successfully.")

if generate_bsa:
    if not os.path.exists(os.path.join(folder, 'OBSE\\Plugins', 'SkyBSA.dll')):
        logging.critical('Critical error: SkyBSA.dll not found in OBSE\\Plugins folder. SkyBSA is required for BSA generation.')
        exit()

def sort_esp_list(filepath, folder):
    file_list = []
    with open(filepath, 'r') as file:
        filenames = [line.strip() for line in file if line.strip()]
        
    for filename in filenames:
        if filename.startswith('#'):
            continue
        full_filename = os.path.join(folder, filename)
        if not os.path.exists(full_filename):
            logging.error(f'Error: file {full_filename} is enabled but does not exist')
            continue
        _, extension = os.path.splitext(filename)
        extension = extension.lower()
        modified_time = os.path.getmtime(full_filename)   
        file_list.append((filename, extension, modified_time))

    def sorter(item):
        filename, extension, modified_time = item
        is_esp = extension.lower() != '.esm'
        return(is_esp, modified_time)
    
    sorted_list = sorted(file_list, key=sorter)

    return [n[0] for n in sorted_list]

load_order = sort_esp_list(plugins_txt, folder)

logging.info(f'{load_order}')

signatures = ['REFR', 'STAT', 'TREE', 'ACTI'] #, 'LAND', 'CELL']
object_dict = {}

try:
    mergedLOD_index = load_order.index('MergedLOD.esm')
except:
    logging.error('Error: MergedLOD.esm not found in load order')
    if not os.path.exists(os.path.join(folder, 'MergedLOD.esm')):
        logging.info('Creating MergedLOD.esm...')
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'MergedLOD.esm'), folder)
    logging.info('Adding MergedLOD.esm to load order...')
    if load_order[1][-4:] == '.esm': #there are some esms that claim that they need to be in slot 01
                                    #not really with EBF but whaterver
        l_index = 2
    else:
        l_index = 1
    mergedlod_time = os.path.getmtime(os.path.join(folder, load_order[l_index-1])) + 1
    os.utime(os.path.join(folder, 'MergedLOD.esm'), (mergedlod_time, mergedlod_time))
    with open(plugins_txt, 'r') as file:
        lines = file.readlines()
    if l_index < len(lines):
        lines.insert(l_index, 'MergedLOD.esm' + '\n')
    else:
        lines.append('MergedLOD.esm' + '\n')
    with open(plugins_txt, 'w') as file:
        file.writelines(lines)
    logging.critical(f'MegedLOD.esm is added to the load order at slot {hex(l_index)} \n'
                    '!!MAKE SURE THAT WRYE BASH OR LOOT DOES NOT CHANGE THE SLOT!! \n'
                    'If it happens, you will either need to manually fix the load order or rerun the utility \n'
                    'with skip_mesh_generation: True to fix load order in *.lod files')
    

if generate_bsa and bsa_name == "":
    if not os.path.exists(os.path.join(folder, 'MergedLOD.esp')):
        logging.error('Error: MergedLOD.esp not found in load order')
        logging.info('Creating MergedLOD.esp...')
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'MergedLOD.esp'), folder)
        logging.info('Adding MergedLOD.esm to load order...')
        l_index = len(load_order)
        mergedlod_time = os.path.getmtime(os.path.join(folder, load_order[-1])) + 1
        os.utime(os.path.join(folder, 'MergedLOD.esp'), (mergedlod_time, mergedlod_time))
        with open(plugins_txt, 'r') as file:
            lines = file.readlines()
        lines.append('MergedLOD.esp' + '\n')
        with open(plugins_txt, 'w') as file:
            file.writelines(lines)
        logging.info(f'MegedLOD.esp is added to the load order at slot {hex(l_index)} \n')

load_order = sort_esp_list(plugins_txt, folder)
mergedLOD_index = load_order.index('MergedLOD.esm')

if mergedLOD_index == 0:
    logging.critical('Error: MergedLOD.esm is the first mod in your load order (before Oblivion.esm). Fix your load order.')
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

logging.info('Processing LAND records for culling...')


'''

#landscape culling tests
land_min_height = {}

for object_id in object_dict:
    if object_dict[object_id].sig == 'LAND':
        land_record = object_dict[object_id]
        i = land_record.parent_group.parent_group.parent_group.records.index(land_record.parent_group.parent_group)
        try:
            cell = land_record.parent_group.parent_group.parent_group.records[i-1]
        except:
            continue
        if type(cell) != RecordCELL:
            continue
        worldspace = cell.parent_worldspace.editor_id

        
        try:
            x = cell.cell_coordinates[0]
            y = cell.cell_coordinates[1]
        except:
            continue

        if not worldspace in land_min_height:
            land_min_height[worldspace] = {}
        if not x in land_min_height[worldspace]:
            land_min_height[worldspace][x] = {}
        temp_heightmap = land_record.parse_heightmap()
        if temp_heightmap:
            land_min_height[worldspace][x][y] = min_value = min(min(row) for row in temp_heightmap)

'''

logging.info('Processing LOD meshes...')

bsa_files = [f for f in os.listdir(folder) if f.endswith('.bsa')]



bsa_loadorder = [] + hardcoded_bsas

#TODO: skipper for some bsas like OUT

far_mesh_list = []
tree_billboard_textures = []

for plugin in load_order:
    for file in bsa_files:
        if file.lower().startswith(plugin.lower().replace('.esp', '')):
            bsa_loadorder.append(file)
            
for bsa in bsa_loadorder:
    if not os.path.exists(os.path.join(folder, bsa)):
        continue
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
    
    if object_dict[obj].sig == 'STAT' or object_dict[obj].sig == 'ACTI':
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
                    if abs(x_cell) > 1000:
                        logging.warning(f'Object {hex(obj.form_id)} is out of bounds.')
                        continue
                    y_cell = math.floor(obj.position[1] / 4096)
                    if abs(y_cell) > 1000:
                        logging.warning(f'Object {hex(obj.form_id)} is out of bounds.')
                        continue
                    if not x_cell in LODGen[worldspace]:
                        LODGen[worldspace][x_cell] = {}
                    if not y_cell in LODGen[worldspace][x_cell]:
                        LODGen[worldspace][x_cell][y_cell] = []
                    LODGen[worldspace][x_cell][y_cell].append([obj.baserecordformid, obj.position, obj.rotation, obj.scale])

merger = NifProcessor()
merger.EMPTY_NIF_PATH = empty_nif_template

merger.IGNORE_COLLISIONS = True
merger.SKIP_TANGENT_SPACE_GENERATION = True
merger.IGNORE_AWLS = True 

def MiddleOfCellCalc(cell_x, cell_y):
    
    #returns coordinates of the cell center, useful for large cell-size merges
    x_offset = (cell_x + 0.5) * 4096
    y_offset = (cell_y + 0.5) * 4096
    z_offset = 0

    return [x_offset, y_offset, z_offset]


record_offset = 2048 #first formid of the file

MODB_Template = Subrecord('MODB', 4, struct.pack('f', 2048.0))
STAT_Group = Group('GRUP', 0, 1413567571, 0, 0, None, [], None) #1347768903 = 'STAT'

end_time = time.time()                    
elapsed_time = end_time - start_time



logging.info(f"Mesh generation started: {elapsed_time:.6f} seconds")

triangle_logger = {}

for worldspace in LODGen:
    for i in sorted(LODGen[worldspace]):
        indices = list(LODGen[worldspace][i].keys())
        min_j = min(indices)
        max_j = max(indices)
        logging.info(f'Processing {worldspace}, cells [{i}, {min_j} to {max_j}]')
        for j in sorted(LODGen[worldspace][i]):
            logging.debug(f'Processing {worldspace} [{i},{j}]')
            mergeable_count = 0
            z_buffer = 0
            obj_to_merge = []
            for obj in LODGen[worldspace][i][j]:
                if object_dict[obj[0]].sig == 'STAT' or object_dict[obj[0]].sig == 'ACTI':
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
                #try:
                #    min_land_height = land_min_height[worldspace][i][j] - 100 - average_z
                #except:
                #    min_land_height = -60000 - average_z
                middle_of_cell = MiddleOfCellCalc(i, j)
                if water_culling:
                    sea_level = - average_z
                    merger.Z_CULLING_FLAG = True
                    merger.Z_CULLING_LEVEL = sea_level #max(sea_level, min_land_height)

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

                        triangle_count = merger.triangle_count
                        merger.ProcessNif(path, position, rotations, scale)

                        if mesh_file not in triangle_logger:
                            triangle_logger[mesh_file] = 0
                        triangle_logger[mesh_file] += merger.triangle_count - triangle_count

                    #merger.CleanAnimationController()
                    merger.PreSaveProcessing()
                    vert_count = merger.CalculateVertCount()
                    if vert_count > 0:
                        merger.SaveNif(os.path.join(folder, 'meshes\\MergedLOD', worldspace + '_' + str(i) + '_' + str(j) + '_far.nif'))
                        shutil.copyfile(empty_nif_template, \
                                        os.path.join(folder, 'meshes\\MergedLOD', worldspace + '_' + str(i) + '_' + str(j) + '.nif'))
                    
                else:
                    vert_count = -1
                    if os.path.exists(os.path.join(folder, 'LODMerger', 'meshes', worldspace + '_' + str(i) + '_' + str(j) + '_far.nif')):
                        shutil.copyfile(os.path.join(folder, 'LODMerger', 'meshes', worldspace + '_' + str(i) + '_' + str(j) + '_far.nif'), \
                                        os.path.join(folder, 'meshes\\MergedLOD', worldspace + '_' + str(i) + '_' + str(j) + '_far.nif'))


                if vert_count != 0:

                    record_edid = 'LOD' + worldspace + ('n' if i < 0 else '') \
                                                + str(abs(i)) + ('n' if j < 0 else '')  + str(abs(j)) + '\x00'
                    STATRecord = RecordSTAT('STAT', 0, 0, record_offset, 0, b'', None)
                    EDID_Template = Subrecord('EDID', len(record_edid), \
                                            record_edid.encode('utf-8'))
                    MODL_Template = Subrecord('MODL', len('MergedLOD\\' + worldspace + '_' + str(i) + '_' + str(j) + '.nif\x00'), \
                                            ('MergedLOD\\' + worldspace + '_' + str(i) + '_' + str(j) + '.nif').encode('utf-8') + b'\x00')
                    STATRecord.subrecords.append(EDID_Template)
                    STATRecord.subrecords.append(MODL_Template)
                    STATRecord.subrecords.append(MODB_Template)
                    STAT_Group.records.append(STATRecord)
                    

                    LODGen[worldspace][i][j] = [obj for obj in LODGen[worldspace][i][j] if obj not in obj_to_merge]
                    LODGen[worldspace][i][j].append([record_offset + mergedLOD_index * 16777216, [middle_of_cell[0], middle_of_cell[1], middle_of_cell[2] + average_z], [0, 0, 0], [1.0]])

                    record_offset += 1

    #gc.collect()    #doing it every cell causes performance issues
                    #but it is still needed as Python doesn't clean memory properly in loops like that

end_time = time.time()                    
elapsed_time = end_time - start_time
logging.info(f"Meshes generated: {elapsed_time:.6f} seconds")

if triangle_profiler:
    with open('triangle_logger.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Mesh File', 'Triangle Count'])
        for mesh_file, triangle_count in triangle_logger.items():
            writer.writerow([mesh_file, triangle_count])    

new_esp = ESPParser()

HEDRTemplate = Subrecord('HEDR', 12, struct.pack('fII', 1.0, record_offset - 2048, record_offset))
CNAMTemplate = Subrecord('CNAM', 7, b'LODGen\x00')
mod_description = ('Generated LODGen resource file.\nMust be put at load order position ' + format(mergedLOD_index, '02X') + ' (Mod Index column in MO2)\x00').encode('windows-1252')
SNAMTemplate = Subrecord('SNAM', len(mod_description), mod_description)
TES4Record = RecordTES4('TES4', 0, 1, 0, 0, b'', None, master_files=[]) #flags = 1 == esm
TES4Record.subrecords.append(HEDRTemplate)
TES4Record.subrecords.append(CNAMTemplate)
TES4Record.subrecords.append(SNAMTemplate)
new_esp.records.append(TES4Record)
new_esp.records.append(STAT_Group)
modified_time = os.path.getmtime(os.path.join(folder, 'MergedLOD.esm'))
new_esp.reconstruct(os.path.join(folder, 'MergedLOD.esm'))
os.utime(os.path.join(folder, 'MergedLOD.esm'), (modified_time, modified_time))

logging.info('Removing temp _far nif files...')

try:
    if os.path.exists(os.path.join(folder, 'LODMerger')):
        shutil.rmtree(os.path.join(folder, 'LODMerger'))
except:
    print('Failed to remove temp _far folder.')

logging.info('Removing old LOD files...')

if os.path.exists(os.path.join(folder, 'distantlod')):
    for file in os.listdir(os.path.join(folder, 'distantlod')):
        file_path = os.path.join(folder, 'distantlod', file)
        if os.path.isfile(file_path):
            os.remove(file_path)
else:            
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



if generate_bsa:
    if bsa_name == "":
        bsa_name = 'MergedLOD'

    distantlod_files = os.listdir(os.path.join(folder, 'distantlod')) 
    meshes_files = os.listdir(os.path.join(folder, 'meshes\\MergedLOD'))


    bsapacker = BSAParser()

    bsapacker.pack(os.path.join(folder, f'{bsa_name} - LODs.bsa'), [os.path.join('distantlod', file) for file in distantlod_files], folder)
    
    if not skip_nif_generation:
        bsapacker.pack(os.path.join(folder, f'{bsa_name} - Meshes.bsa'), [os.path.join('meshes\\MergedLOD', file) for file in meshes_files], folder)

    for file in distantlod_files:
        os.remove(os.path.join(folder, 'distantlod', file))

    for file in meshes_files:
        os.remove(os.path.join(folder, 'meshes\\MergedLOD', file))

end_time = time.time()
elapsed_time = end_time - start_time
logging.info(f"Finished in {elapsed_time:.6f} seconds")
logging.info(f'IMPORTANT: make sure that MergedLOD.esm is loaded in position {mergedLOD_index:02X}')
