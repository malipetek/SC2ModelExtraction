import bpy
import os

class SC2AssetBrowserPreferencesV2(bpy.types.AddonPreferences):
    bl_idname = __package__

    sc2_install_path: bpy.props.StringProperty(
        name="SC2 Installation Path",
        subtype='DIR_PATH',
        default="/Applications/StarCraft II",
        description="Path to the StarCraft II installation directory"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "sc2_install_path")

def register():
    pass

def unregister():
    pass
