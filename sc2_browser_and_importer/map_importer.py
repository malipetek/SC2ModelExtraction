import bpy
import os
import xml.etree.ElementTree as ET
from .lib.mpyq import MPQArchive
import tempfile
import mathutils
import math

class MapImporter:
    def __init__(self, filepath, report=print):
        self.filepath = filepath
        self.report = report
        self.archive = None
        self.map_info = {}
        self.objects = []

    def import_map(self):
        try:
            self.archive = MPQArchive(self.filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open map archive: {e}")
            return

        self.read_map_info()
        self.import_objects()

    def read_map_info(self):
        try:
            content = self.archive.read_file('MapInfo')
            if not content:
                self.report({'WARNING'}, "MapInfo not found")
                return

            # Check if XML
            if content.strip().startswith(b'<'):
                try:
                    root = ET.fromstring(content)
                    # Try to get map dimensions if available
                    # Note: MapInfo XML structure varies
                    pass
                except ET.ParseError:
                     self.report({'WARNING'}, "MapInfo is not valid XML")
            else:
                self.report({'WARNING'}, "MapInfo is binary (not supported yet)")

        except Exception as e:
            self.report({'WARNING'}, f"Failed to read MapInfo: {e}")

    def import_objects(self):
        # Try to read 'Objects' file (placed units/doodads)
        # In newer maps this is a binary file 'Objects'
        # In older maps or XML maps it might be 'Base.SC2Data/GameData/LevelData.xml' or similar
        # But commonly placed objects are in 'Objects' file.

        # We will look for XML files that look like object placements if 'Objects' is binary or missing

        content = self.archive.read_file('Objects')

        if content and content.strip().startswith(b'<'):
            self.parse_objects_xml(content)
        else:
            # Check for Objects.xml (sometimes used)
            content = self.archive.read_file('Objects.xml')
            if content and content.strip().startswith(b'<'):
                self.parse_objects_xml(content)
            else:
                self.report({'WARNING'}, "The map's 'Objects' file is binary. Only XML format is currently supported for object import.")

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
                        # SC2 coordinates: X, Y, Z (Z is up)
                        # Blender coordinates: X, Y, Z (Z is up)
                        # But typically games match X->X, Y->Y, Z->Z or Y-up. SC2 is Z-up.

                        rot = float(rot_str) if rot_str else 0
                        # Rotation in SC2 is usually radians or degrees around Z.
                        # Assuming radians for now (common in XML data), or degrees?
                        # Editor uses degrees. XML might use degrees.

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
        # Unlink from default collection first (primitive_add links to active collection)
        for col in obj.users_collection:
            col.objects.unlink(obj)
        collection.objects.link(obj)

        # Add custom property for identification
        obj['SC2_UnitID'] = name

        # Set show_name to True for easier identification
        obj.show_name = True
