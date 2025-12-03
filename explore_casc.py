from PyCASC import DirCASCReader
import os

paths = [
    "/Applications/StarCraft II",
    "/Applications/StarCraft II/SC2Data",
    "/Applications/StarCraft II/SC2Data/data",
    "/Applications/StarCraft II/SC2Data/config"
]

for path in paths:
    print(f"Trying path: {path}")
    try:
        casc = DirCASCReader(path)
        print(f"SUCCESS: Opened CASC storage at {path}")
        # List some files to verify
        files = list(casc.list_files())
        print(f"Found {len(files)} files")
        break
    except Exception as e:
        print(f"Failed: {e}")
