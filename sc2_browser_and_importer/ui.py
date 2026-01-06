import bpy

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
        box.label(text="Results:", icon='PRESET')
        
        if hasattr(scene, "sc2_search_results") and len(scene.sc2_search_results) > 0:
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
        
        # Options section
        box = layout.box()
        box.prop(scene, "sc2_smart_extract", text="Smart Extract (with textures)")
        
        # Import button
        layout.separator()
        row = layout.row()
        row.scale_y = 1.5
        row.operator("sc2.import_asset_v2", text="Import Selected", icon='IMPORT')

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

def register():
    # Register properties
    bpy.types.Scene.sc2_search_query = bpy.props.StringProperty(
        name="Search Query",
        description="Search pattern (e.g., *Viking*, *Marine*)",
        default="*"
    )
    
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

    bpy.types.Scene.sc2_smart_extract = bpy.props.BoolProperty(
        name="Smart Extract",
        description="Automatically extract textures with models",
        default=True
    )
    
    bpy.types.Scene.sc2_active_result_index = bpy.props.IntProperty(
        name="Active Result",
        default=0
    )
    
    # Register classes
    bpy.utils.register_class(SC2_UL_SearchResults)
    bpy.utils.register_class(SC2_PT_AssetBrowserPanelV2)

def unregister():
    bpy.utils.unregister_class(SC2_PT_AssetBrowserPanelV2)
    bpy.utils.unregister_class(SC2_UL_SearchResults)
    
    del bpy.types.Scene.sc2_search_query
    del bpy.types.Scene.sc2_filter_type
    del bpy.types.Scene.sc2_smart_extract
    del bpy.types.Scene.sc2_active_result_index
