import bpy
import sys
import os
import traceback

# Add current directory to path
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    import m3addon
    print("m3addon imported.")
except ImportError as e:
    print(f"Error importing m3addon: {e}")
    sys.exit(1)

print("Attempting to register m3addon classes manually to find failure...")

from m3addon import classes, register

# Try standard registration first
try:
    register()
    print("Standard register() completed successfully.")
except Exception as e:
    print(f"Standard register() failed: {e}")
    traceback.print_exc()

# Check if property exists
scene = bpy.context.scene
if hasattr(scene, "m3_import_options"):
    print("Success: m3_import_options exists.")
else:
    print("Failure: m3_import_options MISSING.")
    
    # If missing, try to find which class failed or if properties weren't set
    print("Debugging individual classes...")
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            # often "register_class(...): already registered as ..."
            pass 
        except Exception as e:
            print(f"Failed to register class {cls}: {e}")
            # traceback.print_exc()

