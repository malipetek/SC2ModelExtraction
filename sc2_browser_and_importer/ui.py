import bpy
import os

class SearchResultItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="File Name")
    path: bpy.props.StringProperty(name="Full Path")
    file_type: bpy.props.StringProperty(name="Type")
    preview_id: bpy.props.IntProperty(name="Preview ID", default=0)

class MapResultItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Map Name")
    path: bpy.props.StringProperty(name="CASC Path")
    map_type: bpy.props.StringProperty(name="Map Type")

class SC2_PT_AssetBrowserPanelV2(bpy.types.Panel):
    bl_label = "SC2 Asset Browser (v2)"
    bl_idname = "SC2_PT_asset_browser_v2"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SC2 Assets'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Search section
        box = layout.box()
        box.label(text="Search Assets:", icon='VIEWZOOM')
        box.prop(scene, "sc2_search_query", text="")
        box.operator("sc2.search_assets_v2", text="Search", icon='PLAY')
        
        # Filter Tabs
        row = layout.row(align=True)
        row.prop(scene, "sc2_filter_type", expand=True)

        # Results section
        box = layout.box()
        
        # Show different views based on filter
        is_texture_filter = scene.sc2_filter_type == 'TEXTURE'
        
        if is_texture_filter:
            box.label(text="Textures:", icon='TEXTURE')
            # View mode toggle for textures
            row = box.row(align=True)
            row.prop(scene, "sc2_texture_view_mode", expand=True)
        else:
            box.label(text="Results:", icon='PRESET')
        
        if hasattr(scene, "sc2_search_results") and len(scene.sc2_search_results) > 0:
            if is_texture_filter and scene.sc2_texture_view_mode == 'GRID':
                # Thumbnail grid view for textures
                self.draw_texture_grid(context, box, scene)
            else:
                # Standard list view
                box.template_list(
                    "SC2_UL_SearchResults", 
                    "", 
                    scene, 
                    "sc2_search_results", 
                    scene, 
                    "sc2_active_result_index"
                )
        else:
            box.label(text="No results", icon='INFO')
        
        # Texture preview section (only show when texture filter is active)
        if is_texture_filter and hasattr(scene, 'sc2_preview_texture') and scene.sc2_preview_texture:
            self.draw_texture_preview(context, layout, scene)
        
        # Options section
        box = layout.box()
        box.prop(scene, "sc2_smart_extract", text="Smart Extract (with textures)")
        
        # Import button
        layout.separator()
        row = layout.row()
        row.scale_y = 1.5
        row.operator("sc2.import_asset_v2", text="Import Selected", icon='IMPORT')

        # Map Browser section
        layout.separator()
        box = layout.box()
        box.label(text="Map Browser:", icon='WORLD_DATA')
        
        # Search for maps in CASC
        row = box.row(align=True)
        row.prop(scene, "sc2_map_search_query", text="")
        row.operator("sc2.search_maps", text="", icon='VIEWZOOM')
        
        # Map results list
        if hasattr(scene, "sc2_map_results") and len(scene.sc2_map_results) > 0:
            box.template_list(
                "SC2_UL_MapResults",
                "",
                scene,
                "sc2_map_results",
                scene,
                "sc2_active_map_index",
                rows=4
            )
            
            # Import selected map from CASC
            row = box.row()
            row.scale_y = 1.3
            row.operator("sc2.import_map_from_casc", text="Import Selected Map", icon='IMPORT')
        else:
            box.label(text="Click search to find maps in CASC", icon='INFO')
        
        # Separator and fallback to file browser
        box.separator()
        row = box.row()
        row.operator("sc2.import_map", text="Import from File...", icon='FILE_FOLDER')
        
        # Export Tools section
        layout.separator()
        box = layout.box()
        box.label(text="Export Tools:", icon='EXPORT')
        row = box.row()
        row.operator("sc2.calculate_tangents", text="Calculate Tangents", icon='NORMALS_FACE')
        row = box.row()
        row.operator("sc2.export_textures", text="Export Textures", icon='TEXTURE')
        row = box.row()
        row.operator("sc2.convert_textures", text="Convert to PNG/JPG", icon='IMAGE_DATA')
        row = box.row()
        row.scale_y = 1.3
        row.operator("sc2.export_glb", text="Export to GLB", icon='EXPORT')
    
    def draw_texture_grid(self, context, box, scene):
        """Draw a thumbnail grid for texture results"""
        from .operators import get_texture_cache
        
        # Filter to only texture items
        texture_items = []
        for i, item in enumerate(scene.sc2_search_results):
            if 'Texture' in item.file_type:
                texture_items.append((i, item))
        
        if not texture_items:
            box.label(text="No textures found", icon='INFO')
            return
        
        # Load thumbnails button
        row = box.row()
        row.operator("sc2.load_texture_thumbnails", text="Load Thumbnails", icon='IMAGE_DATA')
        
        cache = get_texture_cache()
        
        # Grid layout - 3 columns for bigger thumbnails
        cols = 3
        grid = box.grid_flow(row_major=True, columns=cols, even_columns=True, even_rows=True, align=True)
        
        for idx, item in texture_items:
            col = grid.column(align=True)
            
            # Check if we have a cached thumbnail
            img = None
            if item.path in cache:
                img = bpy.data.images.get(cache[item.path])
            
            is_selected = (idx == scene.sc2_active_result_index)
            
            if img and img.preview:
                # Show actual thumbnail - use template_icon for bigger size
                col.template_icon(icon_value=img.preview.icon_id, scale=4.0)
                op = col.operator("sc2.select_texture_item", text="Select", emboss=is_selected, depress=is_selected)
                op.item_index = idx
            else:
                # Show placeholder icon
                op = col.operator("sc2.select_texture_item", text="", icon='FILE_IMAGE', emboss=is_selected, depress=is_selected)
                op.item_index = idx
            
            # Show truncated filename
            name = item.name
            if len(name) > 12:
                name = name[:10] + ".."
            col.label(text=name)
        
        box.label(text=f"{len(texture_items)} texture(s)")
    
    def draw_texture_preview(self, context, layout, scene):
        """Draw texture preview panel"""
        box = layout.box()
        box.label(text="Texture Preview:", icon='IMAGE')
        
        img = bpy.data.images.get(scene.sc2_preview_texture)
        if img:
            # Show image preview
            box.template_icon(icon_value=img.preview.icon_id, scale=8.0)
            
            # Image info
            col = box.column(align=True)
            col.label(text=f"Name: {img.name}")
            col.label(text=f"Size: {img.size[0]} x {img.size[1]}")
            # DDS format may not have a valid enum, get extension from name
            try:
                fmt = img.file_format if img.file_format else "Unknown"
            except:
                fmt = os.path.splitext(img.name)[1].upper().replace('.', '') or "DDS"
            col.label(text=f"Format: {fmt}")
            
            # Save button
            row = box.row()
            row.scale_y = 1.2
            row.operator("sc2.save_texture_as", text="Save as PNG/JPG", icon='EXPORT')
        else:
            box.label(text="Preview not available")

class SC2_UL_SearchResults(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Show only filename, truncating long paths is handled by os.path.basename in operators.py
            # but here item.name is already basename.
            # item.path contains full path if needed.
            
            row = layout.row()
            row.label(text=item.name, icon='FILE')
            
            # Right align the type
            sub = row.row()
            sub.alignment = 'RIGHT'
            sub.label(text=item.file_type)
            
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE')

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        scene = context.scene
        
        # Default behavior
        flt_flags = []
        flt_neworder = []
        
        if not items:
            return flt_flags, flt_neworder
            
        # Helper to filter by type
        def check_type(item_type, filter_opt):
            if filter_opt == 'ALL': return True
            if filter_opt == 'MODEL' and '3D Model' in item_type: return True
            if filter_opt == 'ANIM' and 'Animation' in item_type: return True
            if filter_opt == 'TEXTURE' and 'Texture' in item_type: return True
            if filter_opt == 'SOUND' and 'Audio' in item_type: return True
            return False

        # Generate flags
        flt_flags = [0] * len(items)
        for i, item in enumerate(items):
            if check_type(item.file_type, scene.sc2_filter_type):
                flt_flags[i] = self.bitflag_filter_item
                
        return flt_flags, flt_neworder

class SC2_UL_MapResults(bpy.types.UIList):
    """UIList for displaying SC2 map search results"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row()
            row.label(text=item.name, icon='WORLD_DATA')
            
            # Right align the map type
            sub = row.row()
            sub.alignment = 'RIGHT'
            sub.label(text=item.map_type)
            
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='WORLD_DATA')

def register():
    if not hasattr(bpy.types.Scene, 'sc2_search_query'):
        bpy.types.Scene.sc2_search_query = bpy.props.StringProperty(
            name="Search Query",
            description="Search pattern (e.g., *Viking*, *Marine*)",
            default="*"
        )
    if not hasattr(bpy.types.Scene, 'sc2_filter_type'):
        bpy.types.Scene.sc2_filter_type = bpy.props.EnumProperty(
            name="Filter",
            description="Filter asset types",
            items=[
                ('ALL', "All", "All files"),
                ('MODEL', "Models", "3D Models (.m3)"),
                ('ANIM', "Anims", "Animations (.m3a)"),
                ('TEXTURE', "Textures", "Images (.dds, .tga)"),
                ('SOUND', "Sounds", "Audio files")
            ],
            default='ALL'
        )
    if not hasattr(bpy.types.Scene, 'sc2_smart_extract'):
        bpy.types.Scene.sc2_smart_extract = bpy.props.BoolProperty(
            name="Smart Extract",
            description="Automatically extract textures with models",
            default=True
        )
    if not hasattr(bpy.types.Scene, 'sc2_active_result_index'):
        bpy.types.Scene.sc2_active_result_index = bpy.props.IntProperty(
            name="Active Result",
            default=0
        )
    if not hasattr(bpy.types.Scene, 'sc2_search_results'):
        bpy.types.Scene.sc2_search_results = bpy.props.CollectionProperty(type=SearchResultItem)
    if not hasattr(bpy.types.Scene, 'sc2_texture_view_mode'):
        bpy.types.Scene.sc2_texture_view_mode = bpy.props.EnumProperty(
            name="View Mode",
            description="How to display texture results",
            items=[
                ('LIST', "List", "Show as list"),
                ('GRID', "Grid", "Show as thumbnail grid"),
            ],
            default='GRID'
        )
    if not hasattr(bpy.types.Scene, 'sc2_preview_texture'):
        bpy.types.Scene.sc2_preview_texture = bpy.props.StringProperty(
            name="Preview Texture",
            description="Name of the currently previewed texture",
            default=""
        )
    
    # Map browser properties
    if not hasattr(bpy.types.Scene, 'sc2_map_search_query'):
        bpy.types.Scene.sc2_map_search_query = bpy.props.StringProperty(
            name="Map Search",
            description="Search pattern for maps (e.g., *Campaign*, *Melee*)",
            default="*.SC2Map"
        )
    if not hasattr(bpy.types.Scene, 'sc2_map_results'):
        bpy.types.Scene.sc2_map_results = bpy.props.CollectionProperty(type=MapResultItem)
    if not hasattr(bpy.types.Scene, 'sc2_active_map_index'):
        bpy.types.Scene.sc2_active_map_index = bpy.props.IntProperty(
            name="Active Map",
            default=0
        )

def unregister():
    if hasattr(bpy.types.Scene, 'sc2_search_query'):
        del bpy.types.Scene.sc2_search_query
    if hasattr(bpy.types.Scene, 'sc2_filter_type'):
        del bpy.types.Scene.sc2_filter_type
    if hasattr(bpy.types.Scene, 'sc2_smart_extract'):
        del bpy.types.Scene.sc2_smart_extract
    if hasattr(bpy.types.Scene, 'sc2_active_result_index'):
        del bpy.types.Scene.sc2_active_result_index
    if hasattr(bpy.types.Scene, 'sc2_search_results'):
        del bpy.types.Scene.sc2_search_results
    if hasattr(bpy.types.Scene, 'sc2_texture_view_mode'):
        del bpy.types.Scene.sc2_texture_view_mode
    if hasattr(bpy.types.Scene, 'sc2_preview_texture'):
        del bpy.types.Scene.sc2_preview_texture
    # Map browser properties
    if hasattr(bpy.types.Scene, 'sc2_map_search_query'):
        del bpy.types.Scene.sc2_map_search_query
    if hasattr(bpy.types.Scene, 'sc2_map_results'):
        del bpy.types.Scene.sc2_map_results
    if hasattr(bpy.types.Scene, 'sc2_active_map_index'):
        del bpy.types.Scene.sc2_active_map_index
