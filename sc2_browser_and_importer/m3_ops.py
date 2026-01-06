import bpy
from . import io_m3_import
from . import io_m3_export
from . import m3_object_armature


class M3ImportOperator(bpy.types.Operator):
    bl_idname = 'm3.import'
    bl_label = 'Import M3'
    bl_options = {'UNDO'}

    filename_ext = '.m3'
    filter_glob: bpy.props.StringProperty(options={'HIDDEN'}, default='*.m3;*.m3a')
    filepath: bpy.props.StringProperty(name='File Path', description='File path for import operation', maxlen=1023, default='')
    id_name: bpy.props.EnumProperty(items=lambda self, ctx: list(m3_import_id_names(self, ctx)), name='Armature Object', description='The armature object to add m3 data into. Select an existing armature object to import m3 data directly into it')

    get_mesh: bpy.props.BoolProperty(default=True, name='Mesh Data', description='Imports mesh data and their associated materials. Applies only to m3 (not m3a) import')
    get_effects: bpy.props.BoolProperty(default=False, name='Effects', description='Imports effect data, such as particle systems or ribbons, and their associated materials. Applies only to m3 (not m3a) import')
    get_rig: bpy.props.BoolProperty(default=False, name='Rig', description='Imports bones and various bone related data. (Attachment points, hit test volumes, etc.) Applies only to m3 (not m3a) import')
    get_anims: bpy.props.BoolProperty(default=False, name='Animations', description='Imports animation data. Applies only to m3 (not m3a) import')

    def draw(self, context):
        layout = self.layout
        layout.label(text='Armature Object')
        layout.prop(self, 'id_name', text='')
        if self.id_name != '(New Object)':
            layout.separator()
            layout.label(text='Import Options')
            col = layout.column()
            col.prop(self, 'get_mesh')
            col.prop(self, 'get_effects')
            col.prop(self, 'get_rig')
            row = col.row()
            row.active = self.get_rig
            row.prop(self, 'get_anims')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        opts = (self.get_rig, self.get_anims, self.get_mesh, self.get_effects)
        io_m3_import.m3_import(filepath=self.filepath, ob=bpy.data.objects.get(self.id_name), bl_op=self, opts=opts)
        return {'FINISHED'}


def m3_import_id_names(self, context):
    yield '(New Object)', '(New Object)', 'Creates a new object to hold the imported M3 data.'
    for ob in bpy.data.objects:
        if ob.type == 'ARMATURE':
            yield ob.name, ob.name, 'Imports the M3 data into the selected object. Note that various data such as animations will not be imported.'


class M3ExportOperator(bpy.types.Operator):
    bl_idname = 'm3.export'
    bl_label = 'Export M3'

    filename_ext = '.m3'
    filter_glob: bpy.props.StringProperty(options={'HIDDEN'}, default='*.m3;*.m3a')
    filepath: bpy.props.StringProperty(name='File Path', description='File path for export operation', maxlen=1023, default='')

    output_anims: bpy.props.BoolProperty(default=True, name='Output Animations', description='Include animations in the resulting m3 file. (Unchecked does not apply when exporting as m3a)')
    section_reuse_mode: bpy.props.EnumProperty(default='EXPLICIT', name='Section Reuse', items=m3_object_armature.e_section_reuse_mode)
    cull_unused_bones: bpy.props.BoolProperty(default=True, name='Cull Unused Bones', description='Bones which the exporter determines will not be referenced in the m3 file are removed')
    cull_material_layers: bpy.props.BoolProperty(default=True, name='Cull Material Layers', description='Fills all blank material layer slots with a reference to a single layer section, which reduces file size.')
    use_only_max_bounds: bpy.props.BoolProperty(default=False, name='Use Only Max Bounds', description='Animations will have exactly one bounding box key with maximum dimensions.')

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type == 'ARMATURE')

    def invoke(self, context, event):
        if context.active_object.m3_filepath_export:
            self.filepath = context.active_object.m3_filepath_export
        for key in type(context.active_object.m3_export_opts).__annotations__.keys():
            prop = getattr(context.active_object.m3_export_opts, key)
            setattr(self, key, prop)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        io_m3_export.m3_export(ob=context.active_object, filepath=self.filepath, bl_op=self)
        context.active_object.m3_filepath_export = self.filepath
        for key in type(context.active_object.m3_export_opts).__annotations__.keys():
            prop = getattr(self, key)
            setattr(context.active_object.m3_export_opts, key, prop)
        return {'FINISHED'}


def top_bar_import(self, context):
    self.layout.operator('m3.import', text='StarCraft 2 Model (.m3)')


def top_bar_export(self, context):
    col = self.layout.column()
    if not context.object or (context.object and context.object.type != 'ARMATURE'):
        col.active = False
    col.operator('m3.export', text='StarCraft 2 Model (.m3, .m3a)')


def register():
    try:
        bpy.types.TOPBAR_MT_file_import.remove(top_bar_import)
    except Exception:
        pass
    try:
        bpy.types.TOPBAR_MT_file_export.remove(top_bar_export)
    except Exception:
        pass
    bpy.types.TOPBAR_MT_file_import.append(top_bar_import)
    bpy.types.TOPBAR_MT_file_export.append(top_bar_export)


def unregister():
    try:
        bpy.types.TOPBAR_MT_file_import.remove(top_bar_import)
    except Exception:
        pass
    try:
        bpy.types.TOPBAR_MT_file_export.remove(top_bar_export)
    except Exception:
        pass
