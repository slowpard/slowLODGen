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
from processors.NifProcessor import NifProcessor

start_time = time.time()

#PATHS


with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LODGen_config.yaml'), "r") as file:
    config = yaml.safe_load(file)



try:
    debug_level = config["debug_level"]
except:
    debug_level = "INFO"


logging.basicConfig(
    level=logging._nameToLevel[debug_level.upper()],  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(levelname)s - %(message)s',  
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output.log'), mode='w'),  # Log to a file
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

try:
    hardcoded_bsas = config["hardcoded_bsas"]
except:
    hardcoded_bsas = ['Oblivion - Meshes.bsa', 'Oblivion - Misc.bsa', 'Oblivion - Textures - Compressed.bsa',
                    'N - Meshes.bsa', 'N - Textures1.bsa', 'N - Textures2.bsa', 'N - Misc.bsa']

empty_nif_template = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'empty_ninode.nif')

#pyffi has extremly abstract struct classes defined from xmls
#this is a hack to make them *much* faster to work with 




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
            sig = data[offset:offset+4].decode('utf-8')
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
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        self.master_files = []
        super().__init__(sig, data_size, flags, form_id, vc_info, data, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        self.master_files = []
        for subrecord in self.subrecords:
            if subrecord.sig == 'MAST':
                self.master_files.append(subrecord.data.decode('utf-8').rstrip('\x00'))
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
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        self.model_filename = None
        super().__init__(sig, data_size, flags, form_id, vc_info, data, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'MODL':                
                self.model_filename = subrecord.data.decode('windows-1252').rstrip('\x00')

class RecordTREE(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        self.model_filename = None
        
        super().__init__(sig, data_size, flags, form_id, vc_info, data, **kwargs)
        

    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'MODL':
                self.model_filename = subrecord.data.decode('windows-1252').rstrip('\x00')

class RecordWRLD(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        self.editor_id = None
        super().__init__(sig, data_size, flags, form_id, vc_info, data, **kwargs)
        
        
    def parse_subrecords(self, data):
        super().parse_subrecords(data)
        for subrecord in self.subrecords:
            if subrecord.sig == 'EDID':
                self.editor_id = subrecord.data.decode('windows-1252').rstrip('\x00')
                

class RecordUseless(Record):
    def __init__(self, sig, data_size, flags, form_id, vc_info, data, **kwargs):
        #print('Creating a record')
        self.sig = sig  # str 4 bytes
        if sig == 'REFR':
            self.sig = 'REFU'
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
                group = Group(record_type, group_size, label, group_type, vc_info, [], None)
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
                subgroup = Group(record_type, group_size, label, group_type, vc_info, [], group.parent_worldspace)
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
        if record_type in ('REFR', 'STAT', 'TREE', 'WRLD', 'TES4', 'ACHR', 'ACRE', 'CELL'):
            record_data = f.read(data_size)
        if record_type == 'REFR' and parent_group.parent_worldspace:
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
        elif record_type in ('ACHR', 'ACRE', 'CELL'):
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
                else:
                    logging.error(f'Error: file {file} not found')
        





def sort_esp_list(filepath, folder):
    file_list = []
    with open(filepath, 'r') as file:
        filenames = [line.strip() for line in file if line.strip()]
        
    for filename in filenames:
        if filename.startswith('#'):
            continue
        full_filename = os.path.join(folder, filename)
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

signatures = ['REFR', 'STAT', 'TREE']
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
    logging.critical(f'MegedLOD.esm is added to the load order at slot {l_index} \n'
                    '!!MAKE SURE THAT WRYE BASH OR LOOT DOES NOT CHANGE THE SLOT!! \n'
                    'If it happens, you will either need to manually fix the load order or rerun the utility \n'
                    'with skip_mesh_generation: True to fix load order in *.lod files')

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

logging.info('Processing LOD files')

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

end_time = time.time()                    
elapsed_time = end_time - start_time
logging.info(f"Meshes generated: {elapsed_time:.6f} seconds")

new_esp = ESPParser()

HEDRTemplate = Subrecord('HEDR', 12, struct.pack('fII', 1.0, record_offset - 2048, record_offset))
CNAMTemplate = Subrecord('CNAM', 7, b'LODGen\x00')
SNAMTemplate = Subrecord('SNAM', 7, b'LODGen\x00')
TES4Record = RecordTES4('TES4', 0, 1, 0, 0, b'', master_files=[]) #flags = 1 == esm
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
