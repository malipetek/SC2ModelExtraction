import bpy
import os
import shutil
import tempfile
from .casc_wrapper import CascWrapper
from .m3_analyzer import M3Analyzer
from .map_importer import MapImporter

class SC2_OT_ImportMap(bpy.types.Operator):
    bl_idname = "sc2.import_map"
    bl_label = "Import SC2 Map"
    bl_description = "Import an SC2 Map file (.SC2Map)"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.SC2Map", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}

        importer = MapImporter(self.filepath, self.report)
        importer.import_map()

        return {'FINISHED'}

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
                # Import using integrated m3 importer
                self.report({'INFO'}, f"Importing {model_filename}...")
                try:
                    from . import io_m3_import
                    # opts: (get_rig, get_anims, get_mesh, get_effects)
                    opts = (True, True, True, scene.sc2_smart_extract)
                    io_m3_import.m3_import(filepath=model_dest, ob=None, bl_op=self, opts=opts)
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
                    from . import io_m3_import
                    opts = (True, True, False, False)
                    io_m3_import.m3_import(filepath=model_dest, ob=active_obj, bl_op=self, opts=opts)
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


def simplify_materials_for_gltf(objects):
    """
    Simplify material node setups for glTF export compatibility.
    Stores original connections and creates direct texture->BSDF links.
    Returns a list of restore info to undo changes after export.
    """
    restore_info = []
    
    for obj in objects:
        if obj.type != 'MESH':
            continue
            
        for mat_slot in obj.material_slots:
            mat = mat_slot.material
            if not mat or not mat.use_nodes:
                continue
            
            tree = mat.node_tree
            links = tree.links
            
            # Find Principled BSDF
            bsdf = None
            for node in tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    bsdf = node
                    break
            
            if not bsdf:
                continue
            
            # Store original links to restore later
            original_links = []
            for link in links:
                original_links.append({
                    'from_node': link.from_node.name,
                    'from_socket': link.from_socket.name,
                    'to_node': link.to_node.name,
                    'to_socket': link.to_socket.name
                })
            
            restore_info.append({
                'material': mat,
                'original_links': original_links
            })
            
            # Find texture nodes (look for diffuse/color textures)
            diffuse_tex = None
            normal_tex = None
            
            for node in tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    label = node.label.lower() if node.label else ''
                    name = node.name.lower()
                    
                    # Identify diffuse texture
                    if 'diff' in label or 'diff' in name or 'color' in label:
                        diffuse_tex = node
                    # Identify normal texture
                    elif 'norm' in label or 'norm' in name or 'normal' in label:
                        normal_tex = node
                    # Fallback: first texture without specific label as diffuse
                    elif not diffuse_tex and not ('norm' in label or 'spec' in label or 'gloss' in label):
                        diffuse_tex = node
            
            # Clear existing links to BSDF Base Color and Normal
            links_to_remove = []
            for link in links:
                if link.to_node == bsdf and link.to_socket.name in ['Base Color', 'Normal']:
                    links_to_remove.append(link)
            
            for link in links_to_remove:
                links.remove(link)
            
            # Connect diffuse directly to Base Color
            if diffuse_tex and 'Base Color' in bsdf.inputs:
                links.new(diffuse_tex.outputs['Color'], bsdf.inputs['Base Color'])
            
            # Connect normal with proper Normal Map node
            if normal_tex and 'Normal' in bsdf.inputs:
                # Check if there's already a Normal Map node we can use
                normal_map_node = None
                for node in tree.nodes:
                    if node.type == 'NORMAL_MAP':
                        normal_map_node = node
                        break
                
                if not normal_map_node:
                    normal_map_node = tree.nodes.new('ShaderNodeNormalMap')
                    normal_map_node.location = (bsdf.location.x - 300, bsdf.location.y - 200)
                
                # Connect texture to normal map node
                links.new(normal_tex.outputs['Color'], normal_map_node.inputs['Color'])
                links.new(normal_map_node.outputs['Normal'], bsdf.inputs['Normal'])
    
    return restore_info


def restore_materials(restore_info):
    """Restore original material connections after export."""
    for info in restore_info:
        mat = info['material']
        tree = mat.node_tree
        links = tree.links
        
        # Clear all current links
        links.clear()
        
        # Restore original links
        for link_info in info['original_links']:
            from_node = tree.nodes.get(link_info['from_node'])
            to_node = tree.nodes.get(link_info['to_node'])
            
            if from_node and to_node:
                from_socket = from_node.outputs.get(link_info['from_socket'])
                to_socket = to_node.inputs.get(link_info['to_socket'])
                
                if from_socket and to_socket:
                    links.new(from_socket, to_socket)


def setup_nla_for_m3_animations(objects):
    """
    Setup NLA tracks for m3_animation_groups before glTF export.
    Returns restore info to clean up after export.
    """
    restore_info = []
    
    for obj in objects:
        if obj.type != 'ARMATURE':
            continue
        
        # Check if object has m3_animation_groups
        if not hasattr(obj, 'm3_animation_groups') or len(obj.m3_animation_groups) == 0:
            continue
        
        # Store original NLA state
        original_nla_tracks = []
        if obj.animation_data:
            for track in obj.animation_data.nla_tracks:
                original_nla_tracks.append({
                    'name': track.name,
                    'mute': track.mute,
                    'strips': [(s.name, s.action.name if s.action else None) for s in track.strips]
                })
        
        original_action = obj.animation_data.action if obj.animation_data else None
        
        restore_info.append({
            'object': obj,
            'original_action': original_action,
            'original_nla_tracks': original_nla_tracks,
            'created_tracks': []
        })
        
        # Ensure animation data exists
        if not obj.animation_data:
            obj.animation_data_create()
        
        # Clear current action to avoid conflicts
        obj.animation_data.action = None
        
        # Mute all existing NLA tracks
        for track in obj.animation_data.nla_tracks:
            track.mute = True
        
        # Create NLA tracks for each m3_animation_group
        for group in obj.m3_animation_groups:
            # Each group can have multiple animations
            for anim in group.animations:
                if anim.action:
                    # Create a new NLA track for this animation
                    track_name = f"{group.name}_{anim.name}" if anim.name else group.name
                    track = obj.animation_data.nla_tracks.new()
                    track.name = track_name
                    
                    # Add the action as a strip
                    start_frame = group.frame_start if hasattr(group, 'frame_start') else 0
                    try:
                        strip = track.strips.new(track_name, int(start_frame), anim.action)
                        strip.name = track_name
                    except Exception:
                        pass  # Strip creation may fail if action has no keyframes
                    
                    restore_info[-1]['created_tracks'].append(track.name)
    
    return restore_info


def restore_nla_state(restore_info):
    """Restore original NLA state after export."""
    for info in restore_info:
        obj = info['object']
        
        if not obj.animation_data:
            continue
        
        # Remove created tracks
        tracks_to_remove = []
        for track in obj.animation_data.nla_tracks:
            if track.name in info['created_tracks']:
                tracks_to_remove.append(track)
        
        for track in tracks_to_remove:
            obj.animation_data.nla_tracks.remove(track)
        
        # Restore mute state of original tracks
        for orig_track_info in info['original_nla_tracks']:
            for track in obj.animation_data.nla_tracks:
                if track.name == orig_track_info['name']:
                    track.mute = orig_track_info['mute']
                    break
        
        # Restore original action
        obj.animation_data.action = info['original_action']


def collect_textures_from_objects(objects):
    """
    Collect all texture image paths used by the given objects.
    Returns a list of (image, filepath) tuples.
    """
    textures = []
    seen_paths = set()
    
    for obj in objects:
        if obj.type != 'MESH':
            continue
        
        for mat_slot in obj.material_slots:
            mat = mat_slot.material
            if not mat or not mat.use_nodes:
                continue
            
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    img = node.image
                    # Get the filepath
                    filepath = bpy.path.abspath(img.filepath) if img.filepath else None
                    
                    if filepath and os.path.isfile(filepath) and filepath not in seen_paths:
                        textures.append((img, filepath))
                        seen_paths.add(filepath)
    
    return textures


def export_textures_to_folder(textures, export_dir, report_func=None):
    """
    Copy texture files to the export directory.
    Returns number of textures copied.
    """
    copied = 0
    textures_dir = os.path.join(export_dir, 'textures')
    
    for img, src_path in textures:
        try:
            # Create textures subdirectory if needed
            if not os.path.exists(textures_dir):
                os.makedirs(textures_dir)
            
            filename = os.path.basename(src_path)
            dest_path = os.path.join(textures_dir, filename)
            
            # Copy the file
            if not os.path.exists(dest_path):
                shutil.copy2(src_path, dest_path)
                copied += 1
                if report_func:
                    report_func({'INFO'}, f"Copied texture: {filename}")
        except Exception as e:
            if report_func:
                report_func({'WARNING'}, f"Failed to copy texture {src_path}: {str(e)}")
    
    return copied


class SC2_OT_ExportGLB(bpy.types.Operator):
    """Export selected objects to GLB with automatic tangent calculation"""
    bl_idname = "sc2.export_glb"
    bl_label = "Export SC2 Model to GLB"
    bl_description = "Export selected objects to GLB with automatic tangent calculation for proper normal maps"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Path to export the GLB file",
        subtype='FILE_PATH'
    )
    
    export_textures: bpy.props.BoolProperty(
        name="Export Textures",
        description="Include textures in the GLB file",
        default=True
    )
    
    copy_textures_to_folder: bpy.props.BoolProperty(
        name="Copy Textures to Folder",
        description="Copy texture files to a 'textures' subfolder next to the GLB",
        default=False
    )
    
    export_animations: bpy.props.BoolProperty(
        name="Export Animations",
        description="Include animations in the GLB file",
        default=True
    )
    
    def invoke(self, context, event):
        # Set default filename
        if context.active_object:
            self.filepath = context.active_object.name + ".glb"
        else:
            self.filepath = "export.glb"
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        # Ensure filepath has .glb extension
        if not self.filepath.lower().endswith('.glb'):
            self.filepath += '.glb'
        
        # Store current selection
        original_selection = context.selected_objects.copy()
        original_active = context.active_object
        original_mode = context.mode if context.active_object else 'OBJECT'
        
        # Switch to object mode if needed
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # If an armature is active or selected, select it and all its children
        objects_to_export = []
        for obj in context.selected_objects:
            objects_to_export.append(obj)
            if obj.type == 'ARMATURE':
                # Select all children of the armature
                for child in obj.children_recursive:
                    if child not in objects_to_export:
                        objects_to_export.append(child)
                        child.select_set(True)
        
        # If nothing selected, try to use active object
        if not objects_to_export and context.active_object:
            obj = context.active_object
            obj.select_set(True)
            objects_to_export.append(obj)
            if obj.type == 'ARMATURE':
                for child in obj.children_recursive:
                    child.select_set(True)
                    objects_to_export.append(child)
        
        if not objects_to_export:
            self.report({'ERROR'}, "No objects selected for export")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Exporting {len(objects_to_export)} object(s)")
        
        # Calculate tangents for all mesh objects
        tangent_count = 0
        for obj in objects_to_export:
            if obj.type == 'MESH':
                mesh = obj.data
                if mesh.uv_layers:
                    try:
                        mesh.calc_tangents()
                        tangent_count += 1
                    except RuntimeError as e:
                        self.report({'WARNING'}, f"Could not calculate tangents for {obj.name}: {str(e)}")
        
        if tangent_count > 0:
            self.report({'INFO'}, f"Calculated tangents for {tangent_count} mesh(es)")
        
        # Simplify materials for glTF compatibility
        mat_restore_info = simplify_materials_for_gltf(objects_to_export)
        if mat_restore_info:
            self.report({'INFO'}, f"Simplified {len(mat_restore_info)} material(s) for glTF export")
        
        # Setup NLA tracks for m3_animation_groups (only export these animations)
        nla_restore_info = []
        if self.export_animations:
            nla_restore_info = setup_nla_for_m3_animations(objects_to_export)
            if nla_restore_info:
                anim_count = sum(len(info['created_tracks']) for info in nla_restore_info)
                self.report({'INFO'}, f"Setup {anim_count} animation(s) from m3_animation_groups")
        
        # Export to GLB
        try:
            bpy.ops.export_scene.gltf(
                filepath=self.filepath,
                export_format='GLB',
                use_selection=True,
                export_apply=True,
                export_texcoords=True,
                export_normals=True,
                export_tangents=True,
                export_materials='EXPORT',
                export_animations=self.export_animations,
                export_skins=True,
                export_morph=True,
                export_lights=False,
                export_image_format='AUTO' if self.export_textures else 'NONE',
            )
            self.report({'INFO'}, f"Exported to: {self.filepath}")
        except Exception as e:
            # Restore state even if export failed
            restore_nla_state(nla_restore_info)
            restore_materials(mat_restore_info)
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}
        
        # Copy textures to folder if requested
        if self.copy_textures_to_folder:
            export_dir = os.path.dirname(self.filepath)
            textures = collect_textures_from_objects(objects_to_export)
            if textures:
                copied = export_textures_to_folder(textures, export_dir, self.report)
                self.report({'INFO'}, f"Copied {copied} texture(s) to {os.path.join(export_dir, 'textures')}")
        
        # Restore original state
        restore_nla_state(nla_restore_info)
        restore_materials(mat_restore_info)
        
        return {'FINISHED'}


class SC2_OT_ExportTextures(bpy.types.Operator):
    """Export textures used by selected objects to a folder"""
    bl_idname = "sc2.export_textures"
    bl_label = "Export Textures"
    bl_description = "Copy all textures used by selected objects to a folder"
    bl_options = {'REGISTER', 'UNDO'}
    
    directory: bpy.props.StringProperty(
        name="Output Directory",
        description="Directory to export textures to",
        subtype='DIR_PATH'
    )
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        if not self.directory:
            self.report({'ERROR'}, "No directory selected")
            return {'CANCELLED'}
        
        # Collect objects
        objects_to_process = list(context.selected_objects)
        if not objects_to_process and context.active_object:
            objects_to_process = [context.active_object]
        
        if not objects_to_process:
            self.report({'ERROR'}, "No objects selected")
            return {'CANCELLED'}
        
        # Include children of armatures
        expanded_objects = []
        for obj in objects_to_process:
            expanded_objects.append(obj)
            if obj.type == 'ARMATURE':
                for child in obj.children_recursive:
                    if child not in expanded_objects:
                        expanded_objects.append(child)
        
        # Collect and export textures
        textures = collect_textures_from_objects(expanded_objects)
        
        if not textures:
            self.report({'WARNING'}, "No textures found in selected objects")
            return {'CANCELLED'}
        
        # Export directly to the selected directory (not a subdirectory)
        copied = 0
        for img, src_path in textures:
            try:
                filename = os.path.basename(src_path)
                dest_path = os.path.join(self.directory, filename)
                
                if not os.path.exists(dest_path):
                    shutil.copy2(src_path, dest_path)
                    copied += 1
                    self.report({'INFO'}, f"Copied: {filename}")
            except Exception as e:
                self.report({'WARNING'}, f"Failed to copy {src_path}: {str(e)}")
        
        self.report({'INFO'}, f"Exported {copied} texture(s) to {self.directory}")
        return {'FINISHED'}


class SC2_OT_ConvertTextures(bpy.types.Operator):
    """Convert DDS textures to PNG/JPG for use with Three.js and other engines"""
    bl_idname = "sc2.convert_textures"
    bl_label = "Convert Textures to PNG"
    bl_description = "Convert DDS/TGA textures to PNG format for web use (Three.js compatible)"
    bl_options = {'REGISTER', 'UNDO'}
    
    directory: bpy.props.StringProperty(
        name="Output Directory",
        description="Directory to save converted textures",
        subtype='DIR_PATH'
    )
    
    output_format: bpy.props.EnumProperty(
        name="Format",
        description="Output image format",
        items=[
            ('PNG', "PNG", "PNG format (lossless, supports transparency)"),
            ('JPEG', "JPEG", "JPEG format (smaller, no transparency)"),
        ],
        default='PNG'
    )
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        if not self.directory:
            self.report({'ERROR'}, "No directory selected")
            return {'CANCELLED'}
        
        # Collect objects
        objects_to_process = list(context.selected_objects)
        if not objects_to_process and context.active_object:
            objects_to_process = [context.active_object]
        
        if not objects_to_process:
            self.report({'ERROR'}, "No objects selected")
            return {'CANCELLED'}
        
        # Include children of armatures
        expanded_objects = []
        for obj in objects_to_process:
            expanded_objects.append(obj)
            if obj.type == 'ARMATURE':
                for child in obj.children_recursive:
                    if child not in expanded_objects:
                        expanded_objects.append(child)
        
        # Collect textures
        textures = collect_textures_from_objects(expanded_objects)
        
        if not textures:
            self.report({'WARNING'}, "No textures found in selected objects")
            return {'CANCELLED'}
        
        # Convert and save textures
        converted = 0
        ext = '.png' if self.output_format == 'PNG' else '.jpg'
        
        for img, src_path in textures:
            try:
                # Get base filename without extension
                base_name = os.path.splitext(os.path.basename(src_path))[0]
                dest_path = os.path.join(self.directory, base_name + ext)
                
                # Save using Blender's image API
                # Store original settings
                orig_format = img.file_format
                orig_path = img.filepath_raw
                
                # Set new format and save
                img.file_format = self.output_format
                img.filepath_raw = dest_path
                img.save_render(dest_path)
                
                # Restore original settings
                img.file_format = orig_format
                img.filepath_raw = orig_path
                
                converted += 1
                self.report({'INFO'}, f"Converted: {base_name}{ext}")
            except Exception as e:
                self.report({'WARNING'}, f"Failed to convert {src_path}: {str(e)}")
        
        self.report({'INFO'}, f"Converted {converted} texture(s) to {self.output_format}")
        return {'FINISHED'}


# Global cache for loaded texture thumbnails
_texture_cache = {}

def get_texture_cache():
    return _texture_cache

def clear_texture_cache():
    global _texture_cache
    _texture_cache = {}


class SC2_OT_LoadTextureThumbnails(bpy.types.Operator):
    """Load thumbnails for all texture search results"""
    bl_idname = "sc2.load_texture_thumbnails"
    bl_label = "Load Thumbnails"
    bl_description = "Extract and load thumbnails for texture results (may take a moment)"
    bl_options = {'REGISTER'}
    
    max_textures: bpy.props.IntProperty(name="Max Textures", default=50)
    
    def execute(self, context):
        scene = context.scene
        
        if not scene.sc2_search_results:
            self.report({'WARNING'}, "No search results")
            return {'CANCELLED'}
        
        # Collect texture items
        texture_items = []
        for i, item in enumerate(scene.sc2_search_results):
            if 'Texture' in item.file_type:
                texture_items.append((i, item))
        
        if not texture_items:
            self.report({'WARNING'}, "No textures in results")
            return {'CANCELLED'}
        
        # Limit to avoid long load times
        texture_items = texture_items[:self.max_textures]
        
        # Create temp directory for extraction
        temp_dir = tempfile.mkdtemp(prefix="sc2_thumbnails_")
        
        try:
            casc = CascWrapper()
            if not casc.open_storage():
                self.report({'ERROR'}, "Failed to open SC2 storage")
                return {'CANCELLED'}
            
            loaded = 0
            cache = get_texture_cache()
            
            for idx, item in texture_items:
                casc_path = item.path
                ext = os.path.splitext(casc_path)[1].lower()
                
                if ext not in ['.dds', '.tga', '.png', '.jpg', '.jpeg']:
                    continue
                
                # Skip if already cached
                if casc_path in cache:
                    continue
                
                # CASC paths use backslashes - normalize and get just the filename
                tex_filename = os.path.basename(casc_path.replace('\\', '/'))
                tex_dest = os.path.join(temp_dir, f"{idx}_{tex_filename}")
                
                if casc.extract_file(casc_path, tex_dest):
                    try:
                        # Load into Blender
                        img = bpy.data.images.load(tex_dest, check_existing=False)
                        img.name = f"thumb_{tex_filename}"
                        
                        # Generate preview
                        img.preview_ensure()
                        
                        # Cache it
                        cache[casc_path] = img.name
                        loaded += 1
                    except Exception as e:
                        print(f"Failed to load {tex_filename}: {e}")
            
            casc.close_storage()
            
            self.report({'INFO'}, f"Loaded {loaded} thumbnail(s)")
            
            # Force UI redraw
            for area in context.screen.areas:
                area.tag_redraw()
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load thumbnails: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class SC2_OT_LoadTexturePreview(bpy.types.Operator):
    """Load selected texture from search results for preview"""
    bl_idname = "sc2.load_texture_preview"
    bl_label = "Preview Texture"
    bl_description = "Load the selected texture for preview"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        scene = context.scene
        
        if not scene.sc2_search_results:
            self.report({'WARNING'}, "No search results")
            return {'CANCELLED'}
        
        if scene.sc2_active_result_index >= len(scene.sc2_search_results):
            self.report({'WARNING'}, "No texture selected")
            return {'CANCELLED'}
        
        selected_item = scene.sc2_search_results[scene.sc2_active_result_index]
        casc_path = selected_item.path
        
        # Check if it's a texture
        ext = os.path.splitext(casc_path)[1].lower()
        if ext not in ['.dds', '.tga', '.png', '.jpg', '.jpeg']:
            self.report({'WARNING'}, "Selected file is not a texture")
            return {'CANCELLED'}
        
        # Check cache first
        cache = get_texture_cache()
        if casc_path in cache:
            img = bpy.data.images.get(cache[casc_path])
            if img:
                scene.sc2_preview_texture = img.name
                self.report({'INFO'}, f"Loaded from cache: {img.name}")
                return {'FINISHED'}
        
        # Extract and load texture
        temp_dir = tempfile.mkdtemp(prefix="sc2_texture_preview_")
        # CASC paths use backslashes - normalize and get just the filename
        tex_filename = os.path.basename(casc_path.replace('\\', '/'))
        tex_dest = os.path.join(temp_dir, tex_filename)
        
        try:
            casc = CascWrapper()
            if not casc.open_storage():
                self.report({'ERROR'}, "Failed to open SC2 storage")
                return {'CANCELLED'}
            
            if not casc.extract_file(casc_path, tex_dest):
                self.report({'ERROR'}, f"Failed to extract {tex_filename}")
                casc.close_storage()
                return {'CANCELLED'}
            
            casc.close_storage()
            
            # Load into Blender
            img = bpy.data.images.load(tex_dest, check_existing=True)
            img.name = tex_filename
            
            # Generate preview
            img.preview_ensure()
            
            # Cache it
            cache[casc_path] = img.name
            
            # Store reference for the UI
            scene.sc2_preview_texture = img.name
            
            self.report({'INFO'}, f"Loaded texture: {tex_filename}")
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load texture: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class SC2_OT_SaveTextureAs(bpy.types.Operator):
    """Save the previewed texture as PNG/JPG"""
    bl_idname = "sc2.save_texture_as"
    bl_label = "Save Texture As"
    bl_description = "Save the current preview texture as PNG or JPG"
    bl_options = {'REGISTER'}
    
    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Path to save the texture",
        subtype='FILE_PATH'
    )
    
    output_format: bpy.props.EnumProperty(
        name="Format",
        description="Output image format",
        items=[
            ('PNG', "PNG", "PNG format (lossless, supports transparency)"),
            ('JPEG', "JPEG", "JPEG format (smaller, no transparency)"),
        ],
        default='PNG'
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.jpg;*.jpeg",
        options={'HIDDEN'}
    )
    
    def invoke(self, context, event):
        scene = context.scene
        
        # Set default filename from preview texture
        if hasattr(scene, 'sc2_preview_texture') and scene.sc2_preview_texture:
            base_name = os.path.splitext(scene.sc2_preview_texture)[0]
            self.filepath = base_name + ".png"
        else:
            self.filepath = "texture.png"
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        scene = context.scene
        
        if not hasattr(scene, 'sc2_preview_texture') or not scene.sc2_preview_texture:
            self.report({'ERROR'}, "No texture loaded for preview")
            return {'CANCELLED'}
        
        img = bpy.data.images.get(scene.sc2_preview_texture)
        if not img:
            self.report({'ERROR'}, "Preview texture not found")
            return {'CANCELLED'}
        
        # Ensure correct extension
        ext = '.png' if self.output_format == 'PNG' else '.jpg'
        if not self.filepath.lower().endswith(ext):
            self.filepath = os.path.splitext(self.filepath)[0] + ext
        
        try:
            # Save the image
            img.file_format = self.output_format
            img.save_render(self.filepath)
            
            self.report({'INFO'}, f"Saved texture to: {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save texture: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class SC2_OT_SelectTextureItem(bpy.types.Operator):
    """Select a texture item from the grid and load preview"""
    bl_idname = "sc2.select_texture_item"
    bl_label = "Select Texture"
    bl_description = "Select this texture and load preview"
    bl_options = {'REGISTER'}
    
    item_index: bpy.props.IntProperty(name="Item Index", default=0)
    
    def execute(self, context):
        scene = context.scene
        scene.sc2_active_result_index = self.item_index
        
        # Auto-load preview
        bpy.ops.sc2.load_texture_preview()
        
        return {'FINISHED'}


class SC2_OT_CalculateTangents(bpy.types.Operator):
    """Calculate tangents for selected mesh objects"""
    bl_idname = "sc2.calculate_tangents"
    bl_label = "Calculate Tangents"
    bl_description = "Calculate tangent data for selected meshes (required for GLB export with normal maps)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        tangent_count = 0
        error_count = 0
        
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                mesh = obj.data
                if mesh.uv_layers:
                    try:
                        mesh.calc_tangents()
                        tangent_count += 1
                    except RuntimeError as e:
                        self.report({'WARNING'}, f"Could not calculate tangents for {obj.name}: {str(e)}")
                        error_count += 1
                else:
                    self.report({'WARNING'}, f"{obj.name} has no UV layers, skipping tangent calculation")
        
        if tangent_count > 0:
            self.report({'INFO'}, f"Calculated tangents for {tangent_count} mesh(es)")
        elif error_count == 0:
            self.report({'WARNING'}, "No meshes with UV layers found in selection")
        
        return {'FINISHED'}


def menu_func_export(self, context):
    self.layout.operator(SC2_OT_ExportGLB.bl_idname, text="SC2 Model (.glb)")


def register():
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
