import bpy
import sys
import os
import glob
import traceback

# Instructions:
# Run this script with Blender:
# blender -b -P validate_pipeline.py -- <m3_file_path> <output_glb_path>

def log(msg):
    print(f"[Validation] {msg}")

def main():
    # Get arguments after "--"
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
    else:
        args = []

    if len(args) < 1:
        log("Usage: blender -b -P validate_pipeline.py -- <m3_file_path> [output_glb_path]")
        log("No input file provided. Looking for sample .m3 files in current directory...")
        m3_files = glob.glob("*.m3")
        if not m3_files:
             log("No .m3 files found. Exiting.")
             sys.exit(1)
        m3_path = m3_files[0]
        log(f"Using found file: {m3_path}")
    else:
        m3_path = args[0]

    if len(args) >= 2:
        glb_path = args[1]
    else:
        glb_path = os.path.splitext(m3_path)[0] + ".glb"

    m3_path = os.path.abspath(m3_path)
    glb_path = os.path.abspath(glb_path)

    # Ensure m3addon is available
    # We assume this script is in the project root where 'm3addon' folder is located
    current_dir = os.getcwd()
    
    # 1. Reset Blender to factory settings first
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 2. Disable installed m3addon if present to avoid conflicts
    try:
        import addon_utils
        is_enabled, is_loaded = addon_utils.check("m3addon")
        if is_enabled:
            log("Disabling installed m3addon to avoid conflicts...")
            addon_utils.disable("m3addon")
    except ImportError:
        pass

    # 3. Setup path and force fresh import of local m3addon
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Unload existing m3addon modules to ensure we use the local version
    modules_to_unload = [m for m in sys.modules if m.startswith("m3addon")]
    for m in modules_to_unload:
        del sys.modules[m]

    try:
        import m3addon
        from m3addon import m3import, cm
        
        # Register the addon
        m3addon.register()
        log("m3addon registered successfully.")
    except Exception as e:
        log(f"Error during import/registration: {e}")
        traceback.print_exc()
        sys.exit(1)

    # Setup Scene
    scene = bpy.context.scene
    
    # Check if m3_import_options exists
    if not hasattr(scene, "m3_import_options"):
        log("Error: m3_import_options not found in scene. Addon registration might have failed.")
        sys.exit(1)

    # Configure Import
    scene.m3_import_options.path = m3_path
    scene.m3_import_options.contentPreset = 'EVERYTHING' 
    # We can set other options if needed, e.g.
    # scene.m3_import_options.importAnimations = True
    
    # Run Import
    log(f"Importing {m3_path}...")
    try:
        importer = m3import.Importer()
        importer.importM3BasedOnM3ImportOptions(scene)
    except Exception as e:
        log(f"Import failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    # Validation
    objects = bpy.data.objects
    if not objects:
        log("Failure: No objects imported.")
        sys.exit(1)
    
    log(f"Imported {len(objects)} objects.")
    
    # Check Materials
    materials = bpy.data.materials
    log(f"Imported {len(materials)} materials.")
    for mat in materials:
        if mat.use_nodes:
            # Check for Principled BSDF
            has_principled = any(n.type == 'BSDF_PRINCIPLED' for n in mat.node_tree.nodes)
            if has_principled:
                log(f"  [OK] Material '{mat.name}' has Principled BSDF.")
            else:
                log(f"  [WARN] Material '{mat.name}' does NOT have Principled BSDF.")
        else:
            log(f"  [WARN] Material '{mat.name}' does not use nodes.")

    # Check Animations (Actions)
    actions = bpy.data.actions
    log(f"Imported {len(actions)} actions.")
    if actions:
        log(f"Action names: {[a.name for a in actions]}")
    
    # Check NLA Tracks (for GLB export)
    armatures = [obj for obj in objects if obj.type == 'ARMATURE']
    for arm in armatures:
        if arm.animation_data and arm.animation_data.nla_tracks:
            log(f"Armature '{arm.name}' has {len(arm.animation_data.nla_tracks)} NLA tracks.")
            for track in arm.animation_data.nla_tracks:
                log(f"  Track: {track.name}")
        else:
            log(f"Armature '{arm.name}' has NO NLA tracks (Animations might not export to GLB correctly).")

    # Select all for export
    bpy.ops.object.select_all(action='SELECT')
    
    # Export GLB
    log(f"Exporting to {glb_path}...")
    try:
        bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB', export_nla_strips=True)
        log("Export successful!")
    except Exception as e:
        log(f"Export failed: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
