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

class CASC_FIND_DATA(ctypes.Structure):
    _fields_ = [
        ("szFileName", ctypes.c_char * 1024),
        ("PlainName", ctypes.c_char_p),
        ("dwFileSize", DWORD),
        ("dwFileFlags", DWORD),
        ("dwLocaleFlags", DWORD),
        ("dwTimeSpan", DWORD),
    ]

# Signatures
casc.CascOpenStorage.argtypes = [PCSTR, DWORD, ctypes.POINTER(HANDLE)]
casc.CascOpenStorage.restype = ctypes.c_bool

casc.CascFindFirstFile.argtypes = [HANDLE, PCSTR, ctypes.POINTER(CASC_FIND_DATA), PCSTR]
casc.CascFindFirstFile.restype = HANDLE

casc.CascFindNextFile.argtypes = [HANDLE, ctypes.POINTER(CASC_FIND_DATA)]
casc.CascFindNextFile.restype = ctypes.c_bool

casc.CascFindClose.argtypes = [HANDLE]
casc.CascFindClose.restype = ctypes.c_bool

casc.CascCloseStorage.argtypes = [HANDLE]
casc.CascCloseStorage.restype = ctypes.c_bool

casc.GetCascError.argtypes = []
casc.GetCascError.restype = DWORD

# Main
storage_path = "/Applications/StarCraft II"
hStorage = HANDLE()

print(f"Opening storage at {storage_path}...")
if not casc.CascOpenStorage(storage_path.encode('utf-8'), 0, ctypes.byref(hStorage)):
    err = casc.GetCascError()
    print(f"Failed to open storage. Error code: {err}")
    exit(1)

print("Storage opened!")

search_patterns = [
    "*VikingFighter*.m3",
    "*CommandCenter*.m3",
    "*Barracks*.m3",
    "*SupplyDepot*.m3",
    "*Assets/Textures/*Terrain*.dds"
]

found_files = []

with open("found_files.txt", "w") as f_out:
    for pattern in search_patterns:
        print(f"Searching for {pattern}...")
        find_data = CASC_FIND_DATA()
        hFind = casc.CascFindFirstFile(hStorage, pattern.encode('utf-8'), ctypes.byref(find_data), None)
        
        if hFind and hFind != -1:
            while True:
                filename = find_data.szFileName.decode('utf-8')
                print(f"Found: {filename}")
                found_files.append(filename)
                f_out.write(filename + "\n")
                
                if not casc.CascFindNextFile(hFind, ctypes.byref(find_data)):
                    break
            casc.CascFindClose(hFind)
        else:
            print(f"No files found for pattern: {pattern}")
            f_out.write(f"No files found for pattern: {pattern}\n")

casc.CascCloseStorage(hStorage)

print(f"\nTotal files found: {len(found_files)}")
