from PyCASC import CDNCASCReader
import os

print("Attempting to use CDNCASCReader for 's2' (eu)...")

try:
    # region="eu" based on local .build.info
    casc = CDNCASCReader("s2", region="eu")
    print("SUCCESS: Opened CASC storage via CDN")
    
    print("Listing files...")
    files = casc.list_files()
    print(f"Found {len(files)} named files")
    
    viking_files = [f for f in files if "viking" in f[0].lower() and f[0].endswith(".m3")]
    print(f"Found {len(viking_files)} Viking .m3 files")
    
    target_file = None
    # Prefer the base model
    for name, ckey in viking_files:
        print(f"Found: {name}")
        if name.lower().endswith("assets/units/terran/viking/viking.m3"):
            target_file = (name, ckey)
            break
    
    if not target_file and viking_files:
        target_file = viking_files[0]

    if target_file:
        name, ckey = target_file
        print(f"Extracting {name}...")
        content = casc.get_file_by_ckey(ckey)
        if content:
            local_name = os.path.basename(name)
            with open(local_name, "wb") as f:
                f.write(content)
            print(f"Extracted to {local_name}")
        else:
            print("Failed to get content")
    else:
        print("Viking model not found")

except Exception as e:
    print(f"Failed: {e}")
    import traceback
    traceback.print_exc()
