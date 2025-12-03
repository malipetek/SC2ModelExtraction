import sys
import os

# Add site-packages to path if not present (sometimes needed in this env)
site_packages = os.path.join(os.getcwd(), "venv/lib/python3.11/site-packages")
if site_packages not in sys.path:
    sys.path.append(site_packages)

from PyCASC import CDNCASCReader

def find_viking_files():
    print("Connecting to CASC...")
    try:
        casc = CDNCASCReader("s2", region="eu")
    except Exception as e:
        print(f"Error connecting to CASC: {e}")
        return

    print("Listing files...")
    files = casc.list_files()
    
    viking_files = []
    for name, ckey in files:
        if "viking" in name.lower() and name.endswith(".m3"):
            viking_files.append(name)
            
    print(f"\nFound {len(viking_files)} Viking .m3 files:")
    for f in sorted(viking_files):
        print(f)

if __name__ == "__main__":
    find_viking_files()
