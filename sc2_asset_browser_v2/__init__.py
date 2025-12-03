bl_info = {
    "name": "SC2 Asset Browser (Fixed)",
    "author": "Antigravity",
    "version": (2, 2),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > SC2 Assets",
    "description": "Browse and import StarCraft II assets directly in Blender",
    "warning": "",
    "doc_url": "",
    "category": "Import-Export",
}

import bpy
from . import preferences
from . import ui
from . import operators

def register():
    print("-" * 40)
    print("SC2 Asset Browser V2: Registering...")
    preferences.register()
    operators.register()
    ui.register()
    print("SC2 Asset Browser V2: Registered successfully!")
    print("-" * 40)

def unregister():
    ui.unregister()
    operators.unregister()
    preferences.unregister()

if __name__ == "__main__":
    register()
