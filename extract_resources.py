import ctypes
import os
import sys

# Load library
lib_path = os.path.abspath("CascLib/build/casc.framework/casc")
casc = ctypes.cdll.LoadLibrary(lib_path)

# Define types
HANDLE = ctypes.c_void_p
DWORD = ctypes.c_uint32
PVOID = ctypes.c_void_p
PCSTR = ctypes.c_char_p
PDWORD = ctypes.POINTER(DWORD)

# Signatures
casc.CascOpenStorage.argtypes = [PCSTR, DWORD, ctypes.POINTER(HANDLE)]
casc.CascOpenStorage.restype = ctypes.c_bool

casc.CascOpenFile.argtypes = [HANDLE, PCSTR, DWORD, DWORD, ctypes.POINTER(HANDLE)]
casc.CascOpenFile.restype = ctypes.c_bool

casc.CascReadFile.argtypes = [HANDLE, PVOID, DWORD, PDWORD]
casc.CascReadFile.restype = ctypes.c_bool

casc.CascCloseFile.argtypes = [HANDLE]
casc.CascCloseFile.restype = ctypes.c_bool

casc.CascCloseStorage.argtypes = [HANDLE]
casc.CascCloseStorage.restype = ctypes.c_bool

casc.CascGetFileSize.argtypes = [HANDLE, PDWORD]
casc.CascGetFileSize.restype = DWORD

casc.GetCascError.argtypes = []
casc.GetCascError.restype = DWORD

# Constants
CASC_LOCALE_ALL = 0xFFFFFFFF

# Main
storage_path = "/Applications/StarCraft II"
hStorage = HANDLE()

print(f"Opening storage at {storage_path}...")
if not casc.CascOpenStorage(storage_path.encode('utf-8'), 0, ctypes.byref(hStorage)):
    err = casc.GetCascError()
    print(f"Failed to open storage. Error code: {err}")
    exit(1)

print("Storage opened!")

files_to_extract = [
    # Viking Fighter
    ("mods\\liberty.sc2mod\\base.sc2assets\\assets\\units\\terran\\vikingfighter\\vikingfighter.m3", "VikingFighter.m3"),
    
    # Buildings
    ("mods\\liberty.sc2mod\\base.sc2assets\\assets\\buildings\\terran\\commandcenter\\commandcenter.m3", "CommandCenter.m3"),
    ("mods\\liberty.sc2mod\\base.sc2assets\\assets\\buildings\\terran\\barracks\\barracks.m3", "Barracks.m3"),
    ("mods\\liberty.sc2mod\\base.sc2assets\\assets\\buildings\\terran\\supplydepot\\supplydepot.m3", "SupplyDepot.m3"),
    
    # Textures (Char Planet)
    ("mods\\liberty.sc2mod\\base.sc2assets\\assets\\textures\\planetview_charterraindiffuse.dds", "CharTerrain_Diffuse.dds"),
    ("mods\\liberty.sc2mod\\base.sc2assets\\assets\\textures\\planetview_charterrainnormal.dds", "CharTerrain_Normal.dds"),
    ("mods\\liberty.sc2mod\\base.sc2assets\\assets\\textures\\planetview_charterrainspecular.dds", "CharTerrain_Specular.dds")
]

for casc_path, local_name in files_to_extract:
    print(f"Extracting {local_name}...")
    hFile = HANDLE()
    if casc.CascOpenFile(hStorage, casc_path.encode('utf-8'), CASC_LOCALE_ALL, 0, ctypes.byref(hFile)):
        file_size = casc.CascGetFileSize(hFile, None)
        print(f"  Size: {file_size} bytes")
        
        if file_size > 0:
            buffer = ctypes.create_string_buffer(file_size)
            bytes_read = DWORD()
            if casc.CascReadFile(hFile, buffer, file_size, ctypes.byref(bytes_read)):
                with open(local_name, "wb") as f:
                    f.write(buffer.raw)
                print(f"  Saved to {local_name}")
            else:
                print("  Failed to read file content")
        
        casc.CascCloseFile(hFile)
    else:
        err = casc.GetCascError()
        print(f"  Failed to open file in CASC. Error code: {err}")

casc.CascCloseStorage(hStorage)
print("Done!")
