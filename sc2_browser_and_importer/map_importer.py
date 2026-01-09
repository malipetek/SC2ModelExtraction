import bpy
import os
import xml.etree.ElementTree as ET
from .lib.mpyq import MPQArchive
import tempfile
import mathutils
import math
import struct
from io import BytesIO


class ByteDecoder:
    """
    Simple byte decoder for reading binary data in little-endian format.
    Based on sc2reader's ByteDecoder.
    """
    def __init__(self, contents):
        if hasattr(contents, 'read'):
            self._contents = contents.read()
        else:
            self._contents = contents
        
        self._buffer = BytesIO(self._contents)
        self.length = len(self._contents)
    
    def read(self, count):
        return self._buffer.read(count)
    
    def seek(self, pos):
        return self._buffer.seek(pos)
    
    def tell(self):
        return self._buffer.tell()
    
    def done(self):
        return self.tell() == self.length
    
    def read_uint8(self):
        data = self.read(1)
        if len(data) < 1:
            return 0
        return struct.unpack('<B', data)[0]
    
    def read_uint16(self):
        data = self.read(2)
        if len(data) < 2:
            return 0
        return struct.unpack('<H', data)[0]
    
    def read_uint32(self):
        data = self.read(4)
        if len(data) < 4:
            return 0
        return struct.unpack('<I', data)[0]
    
    def read_bytes(self, count):
        return self.read(count)
    
    def read_string(self, count, encoding='utf8'):
        return self.read_bytes(count).decode(encoding, errors='replace')
    
    def read_cstring(self, encoding='utf8'):
        """Read a NULL-terminated string"""
        result = BytesIO()
        while True:
            c = self.read(1)
            if len(c) == 0 or c[0] == 0:
                return result.getvalue().decode(encoding, errors='replace')
            result.write(c)


class MapInfoPlayer:
    """Describes player data from the MapInfo binary file."""
    def __init__(self, pid, control, color, race, unknown, start_point, ai, decal):
        self.pid = pid
        self.control = control  # 1=User, 2=Computer, 3=Neutral, 4=Hostile
        self.color = color
        self.race = race
        self.unknown = unknown
        self.start_point = start_point
        self.ai = ai
        self.decal = decal


class BinaryMapInfo:
    """
    Parses the binary MapInfo file found in SC2Map archives.
    Based on sc2reader's MapInfo parser and http://www.galaxywiki.net/MapInfo_(File_Format)
    """
    def __init__(self, contents, report=print):
        self.report = report
        self.valid = False
        self.width = 0
        self.height = 0
        self.fog_type = ""
        self.tile_set = ""
        self.camera_left = 0
        self.camera_bottom = 0
        self.camera_right = 0
        self.camera_top = 0
        self.base_height = 0
        self.load_screen_path = ""
        self.players = []
        self.start_locations = []
        self.version = 0
        
        self._parse(contents)
    
    def _parse(self, contents):
        try:
            data = ByteDecoder(contents)
            
            # Check magic bytes "MapI" (may appear as "IpaM" due to endianness)
            magic_bytes = data.read(4)
            # Accept both orderings: "MapI" (big-endian) or "IpaM" (little-endian read)
            if magic_bytes not in (b'MapI', b'IpaM'):
                self.report({'WARNING'}, f"Invalid MapInfo magic: {magic_bytes}")
                return
            
            self.valid = True
            
            # Version
            self.version = data.read_uint32()
            
            # Unknown fields for version >= 0x18
            if self.version >= 0x18:
                data.read_uint32()  # unknown1
                data.read_uint32()  # unknown2
            
            # Map dimensions
            self.width = data.read_uint32()
            self.height = data.read_uint32()
            
            # Small preview
            small_preview_type = data.read_uint32()
            if small_preview_type == 2:
                data.read_cstring()  # small_preview_path
            
            # Large preview
            large_preview_type = data.read_uint32()
            if large_preview_type == 2:
                data.read_cstring()  # large_preview_path
            
            # More unknown for version >= 0x1f
            if self.version >= 0x1f:
                data.read_cstring()  # unknown3
                data.read_uint32()   # unknown4
            
            data.read_uint32()  # unknown5
            
            # Fog type and tile set
            self.fog_type = data.read_cstring()
            self.tile_set = data.read_cstring()
            
            # Camera bounds
            self.camera_left = data.read_uint32()
            self.camera_bottom = data.read_uint32()
            self.camera_right = data.read_uint32()
            self.camera_top = data.read_uint32()
            
            # Base height
            self.base_height = data.read_uint32() / 4096
            
            # Load screen
            load_screen_type = data.read_uint32()
            self.load_screen_path = data.read_cstring()
            
            # Skip some optional fields
            unknown6_len = data.read_uint16()
            data.read_bytes(unknown6_len)  # unknown6
            
            data.read_uint32()  # load_screen_scaling
            data.read_uint32()  # text_position
            data.read_uint32()  # text_position_offset_x
            data.read_uint32()  # text_position_offset_y
            data.read_uint32()  # text_position_size_x
            data.read_uint32()  # text_position_size_y
            data.read_uint32()  # data_flags
            data.read_uint32()  # unknown7
            
            if self.version >= 0x19:
                data.read_bytes(8)  # unknown8
            
            if self.version >= 0x1f:
                data.read_bytes(9)  # unknown9
            
            if self.version >= 0x20:
                data.read_bytes(4)  # unknown10
            
            # Players
            player_count = data.read_uint32()
            for i in range(player_count):
                try:
                    pid = data.read_uint8()
                    control = data.read_uint32()
                    color = data.read_uint32()
                    race = data.read_cstring()
                    unknown = data.read_uint32()
                    start_point = data.read_uint32()
                    ai = data.read_uint32()
                    decal = data.read_cstring()
                    
                    self.players.append(MapInfoPlayer(
                        pid, control, color, race, unknown, start_point, ai, decal
                    ))
                except Exception:
                    break
            
            # Start locations
            start_loc_count = data.read_uint32()
            for i in range(start_loc_count):
                try:
                    self.start_locations.append(data.read_uint32())
                except Exception:
                    break
            
        except Exception as e:
            self.report({'WARNING'}, f"Error parsing binary MapInfo: {e}")


class MapImporter:
    def __init__(self, filepath, report=print):
        self.filepath = filepath
        self.report = report
        self.archive = None
        self.map_info = {}
        self.binary_map_info = None
        self.objects = []

    def import_map(self):
        try:
            self.archive = MPQArchive(self.filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open map archive: {e}")
            return

        self.read_map_info()
        self.import_objects()
        self.create_map_plane()

    def read_map_info(self):
        try:
            content = self.archive.read_file('MapInfo')
            if not content:
                self.report({'WARNING'}, "MapInfo not found")
                return

            # Check if XML (starts with '<')
            if content.strip().startswith(b'<'):
                try:
                    root = ET.fromstring(content)
                    self.report({'INFO'}, "Parsed XML MapInfo")
                except ET.ParseError:
                    self.report({'WARNING'}, "MapInfo is not valid XML")
            else:
                # Try to parse as binary
                self.binary_map_info = BinaryMapInfo(content, self.report)
                if self.binary_map_info.valid:
                    self.report({'INFO'}, f"Parsed binary MapInfo: {self.binary_map_info.width}x{self.binary_map_info.height}, "
                                f"{len(self.binary_map_info.players)} players, tileset: {self.binary_map_info.tile_set}")
                    self.map_info = {
                        'width': self.binary_map_info.width,
                        'height': self.binary_map_info.height,
                        'tileset': self.binary_map_info.tile_set,
                        'players': len(self.binary_map_info.players),
                    }
                else:
                    self.report({'WARNING'}, "Failed to parse binary MapInfo")

        except Exception as e:
            self.report({'WARNING'}, f"Failed to read MapInfo: {e}")

    def create_map_plane(self):
        """Create a plane representing the map bounds if we have dimension info."""
        if not self.binary_map_info or not self.binary_map_info.valid:
            return
        
        width = self.binary_map_info.width
        height = self.binary_map_info.height
        
        if width <= 0 or height <= 0:
            return
        
        # Create a plane at the map center
        bpy.ops.mesh.primitive_plane_add(
            size=1,
            location=(width / 2, height / 2, 0)
        )
        plane = bpy.context.active_object
        plane.name = f"Map_{os.path.basename(self.filepath)}"
        
        # Scale to map dimensions
        plane.scale = (width, height, 1)
        
        # Apply scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Add material to visualize the map
        mat = bpy.data.materials.new(name="MapGroundMaterial")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.2, 0.3, 0.1, 1.0)  # Greenish
        plane.data.materials.append(mat)
        
        # Add custom properties
        plane['SC2_MapWidth'] = width
        plane['SC2_MapHeight'] = height
        plane['SC2_Tileset'] = self.binary_map_info.tile_set
        plane['SC2_PlayerCount'] = len(self.binary_map_info.players)
        
        self.report({'INFO'}, f"Created map plane: {width}x{height}")

    def import_objects(self):
        # Try to read 'Objects' file (placed units/doodads)
        content = self.archive.read_file('Objects')

        if content and content.strip().startswith(b'<'):
            self.parse_objects_xml(content)
        else:
            # Check for Objects.xml (sometimes used)
            content = self.archive.read_file('Objects.xml')
            if content and content.strip().startswith(b'<'):
                self.parse_objects_xml(content)
            else:
                self.report({'INFO'}, "Objects file is binary or not found. Skipping object import.")

    def parse_objects_xml(self, content):
        try:
            root = ET.fromstring(content)
            count = 0

            # Create a collection for the map objects
            collection_name = os.path.basename(self.filepath)
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)

            for obj in root.findall('.//Object'):
                unit_type = obj.get('Unit')
                pos_str = obj.get('Position')
                rot_str = obj.get('Rotation')

                if unit_type and pos_str:
                    try:
                        x, y, z = map(float, pos_str.split(','))
                        rot = float(rot_str) if rot_str else 0
                        self.create_placeholder(unit_type, (x, y, z), rot, collection)
                        count += 1
                    except ValueError:
                        continue

            self.report({'INFO'}, f"Imported {count} objects")

        except ET.ParseError:
            self.report({'ERROR'}, "Failed to parse Objects XML")

    def create_placeholder(self, name, location, rotation_z, collection):
        # Create a cube as placeholder
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        obj = bpy.context.active_object
        obj.name = name

        # SC2 rotation is usually degrees
        obj.rotation_euler[2] = math.radians(rotation_z)

        # Link to collection
        for col in obj.users_collection:
            col.objects.unlink(obj)
        collection.objects.link(obj)

        # Add custom property for identification
        obj['SC2_UnitID'] = name
        obj.show_name = True
