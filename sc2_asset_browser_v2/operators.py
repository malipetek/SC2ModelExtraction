import bpy
import os
import tempfile
from .casc_wrapper import CascWrapper
from .m3_analyzer import M3Analyzer

class SearchResultItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="File Name")
    path: bpy.props.StringProperty(name="Full Path")
    file_type: bpy.props.StringProperty(name="Type")

class SC2_UL_SearchResults(bpy.types.UIList):
    # This class is defined in ui.py now, remove duplicate or just import?
    # Actually, UIList should be in ui.py. 
    # Let's remove this block from operators.py to avoid conflict if it's also in ui.py
    pass

class SC2_OT_SearchAssetsV2(bpy.types.Operator):
    bl_idname = "sc2.search_assets_v2"
    bl_label = "Search SC2 Assets"
    bl_description = "Search for assets in the SC2 CASC archives"
    
    def execute(self, context):
        scene = context.scene
        query = scene.sc2_search_query
        
        if not query:
            self.report({'WARNING'}, "Please enter a search query")
            return {'CANCELLED'}
        
        # Clear previous results
        scene.sc2_search_results.clear()
        
        # Initialize CASC
        try:
            casc = CascWrapper()
            if not casc.open_storage():
                # Try to get error info
                err_msg = f"Failed to open SC2 storage at '{casc.storage_path}'."
                if casc.casc:
                    err_code = casc.casc.GetCascError()
                    err_msg += f" (Error: {err_code})"
                else:
                    err_msg += " (CascLib not loaded)"
                
                self.report({'ERROR'}, err_msg)
                return {'CANCELLED'}
            
            # Search
            self.report({'INFO'}, f"Searching for: {query}")
            results = casc.search_files(query)
            
            # Populate results
            for file_path in results:
                item = scene.sc2_search_results.add()
                item.name = os.path.basename(file_path)
                item.path = file_path
                item.file_type = self._get_file_type(file_path)
            
            casc.close_storage()
            
            self.report({'INFO'}, f"Found {len(results)} files")
            
        except Exception as e:
            self.report({'ERROR'}, f"Search failed: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    def _get_file_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        type_map = {
            '.m3': '3D Model',
            '.m3a': 'Animation',
            '.dds': 'Texture/Image',
            '.tga': 'Texture/Image',
            '.ogg': 'Audio',
            '.wav': 'Audio',
            '.txt': 'Text',
            '.xml': 'Data',
        }
        return type_map.get(ext, 'Unknown')

class SC2_OT_ImportAssetV2(bpy.types.Operator):
    bl_idname = "sc2.import_asset_v2"
    bl_label = "Import SC2 Asset"
    bl_description = "Import the selected asset into Blender"
    
    def execute(self, context):
        scene = context.scene
        
        if not scene.sc2_search_results:
            self.report({'WARNING'}, "No search results available")
            return {'CANCELLED'}
        
        if scene.sc2_active_result_index >= len(scene.sc2_search_results):
            self.report({'WARNING'}, "No asset selected")
            return {'CANCELLED'}
        
        selected_item = scene.sc2_search_results[scene.sc2_active_result_index]
        casc_path = selected_item.path
        
        is_m3 = casc_path.lower().endswith('.m3')
        is_m3a = casc_path.lower().endswith('.m3a')
        
        if not (is_m3 or is_m3a):
            self.report({'WARNING'}, "Only .m3 or .m3a files can be imported")
            return {'CANCELLED'}
        
        # Create temp directory for extraction
        temp_dir = tempfile.mkdtemp(prefix="sc2_import_")
        model_filename = os.path.basename(casc_path)
        model_dest = os.path.join(temp_dir, model_filename)
        
        try:
            # Initialize CASC
            casc = CascWrapper()
            if not casc.open_storage():
                self.report({'ERROR'}, "Failed to open SC2 storage")
                return {'CANCELLED'}
            
            # Extract model
            self.report({'INFO'}, f"Extracting {model_filename}...")
            if not casc.extract_file(casc_path, model_dest):
                self.report({'ERROR'}, f"Failed to extract {model_filename}")
                casc.close_storage()
                return {'CANCELLED'}
            
            # Smart extract textures
            if scene.sc2_smart_extract:
                self._extract_textures(casc, casc_path, temp_dir, model_dest)
            
            casc.close_storage()
            
            if is_m3:
                # Check if m3addon is installed
                if not (hasattr(bpy.ops, 'm3') and hasattr(bpy.ops.m3, 'import')):
                    self.report({'ERROR'}, "M3 Addon not installed or not enabled. Please enable 'm3addon' in Preferences.")
                    self.report({'INFO'}, f"Model extracted to: {model_dest}")
                    return {'CANCELLED'}
                
                # Import into Blender
                self.report({'INFO'}, f"Importing {model_filename}...")
                try:
                    getattr(bpy.ops.m3, "import")(filepath=model_dest)
                    self.report({'INFO'}, f"Successfully imported {model_filename}")
                except Exception as import_error:
                    self.report({'ERROR'}, f"M3 import failed: {str(import_error)}")
                    self.report({'INFO'}, f"Model extracted to: {model_dest}")
                    return {'CANCELLED'}
            elif is_m3a:
                # Handle animation import
                # We assume the user has selected the model they want to apply the animation to
                active_obj = context.active_object
                if not active_obj:
                     self.report({'WARNING'}, "Please select a target object (Armature) to import animation onto.")
                     return {'CANCELLED'}

                self.report({'INFO'}, f"Importing animation {model_filename}...")
                try:
                    getattr(bpy.ops.m3, "import")(filepath=model_dest)
                    self.report({'INFO'}, f"Successfully imported animation {model_filename}")
                except Exception as import_error:
                    self.report({'ERROR'}, f"M3A import failed: {str(import_error)}")
                    return {'CANCELLED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Extraction failed: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    def _extract_textures(self, casc, model_casc_path, temp_dir, model_dest_path):
        """Extract textures referenced by the model"""
        try:
            # Read model data
            m3_data = casc.read_file_content(model_casc_path)
            if not m3_data:
                return
            
            # Analyze for dependencies
            analyzer = M3Analyzer()
            dependencies = analyzer.get_dependencies(m3_data)
            
            if not dependencies:
                return
            
            self.report({'INFO'}, f"Found {len(dependencies)} texture dependencies")
            
            # Extract each texture
            for tex_path in dependencies:
                # Generate candidate paths
                candidates = self._generate_texture_candidates(tex_path)
                
                # Try to extract
                for candidate in candidates:
                    # Normalize path for local OS
                    norm_tex_path = tex_path.replace('\\', os.sep).replace('/', os.sep)
                    full_tex_dest = os.path.join(os.path.dirname(model_dest_path), norm_tex_path)
                    
                    if casc.extract_file(candidate, full_tex_dest):
                        self.report({'INFO'}, f"  + Extracted texture: {tex_path}")
                        break
                        
        except Exception as e:
            self.report({'WARNING'}, f"Texture extraction failed: {str(e)}")
    
    def _generate_texture_candidates(self, tex_path):
        """Generate possible CASC paths for a texture"""
        candidates = []
        
        # Common CASC roots
        roots = [
            "", # As is
            "mods\\liberty.sc2mod\\base.sc2assets\\",
            "Campaigns\\Liberty.SC2Campaign\\Base.SC2Assets\\",
            "mods\\swarm.sc2mod\\base.sc2assets\\",
            "mods\\void.sc2mod\\base.sc2assets\\"
        ]
        
        # Normalize path separators in tex_path to backslash for CASC
        tex_path = tex_path.replace('/', '\\')
        
        # If path already has Assets/Textures, don't prepend it again
        if "assets\\textures" in tex_path.lower():
            for root in roots:
                candidates.append(f"{root}{tex_path}")
        else:
            # Try with and without Assets/Textures prefix
            for root in roots:
                candidates.append(f"{root}{tex_path}")
                candidates.append(f"{root}Assets\\Textures\\{tex_path}")
        
        return candidates

def register():
    bpy.utils.register_class(SearchResultItem)
    bpy.utils.register_class(SC2_OT_SearchAssetsV2)
    bpy.utils.register_class(SC2_OT_ImportAssetV2)
    
    # Register collection property
    bpy.types.Scene.sc2_search_results = bpy.props.CollectionProperty(type=SearchResultItem)

def unregister():
    bpy.utils.unregister_class(SC2_OT_ImportAssetV2)
    bpy.utils.unregister_class(SC2_OT_SearchAssetsV2)
    bpy.utils.unregister_class(SearchResultItem)
    
    del bpy.types.Scene.sc2_search_results
