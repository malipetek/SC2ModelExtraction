import ctypes
import os

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

# Target file
target = "campaigns\\liberty.sc2campaign\\base.sc2assets\\assets\\storymodecharacters\\terran\\sm_viking\\sm_viking.m3"

print(f"Extracting {target}...")
hFile = HANDLE()
if casc.CascOpenFile(hStorage, target.encode('utf-8'), CASC_LOCALE_ALL, 0, ctypes.byref(hFile)):
    file_size = casc.CascGetFileSize(hFile, None)
    print(f"File size: {file_size}")
    
    if file_size > 0:
        buffer = ctypes.create_string_buffer(file_size)
        bytes_read = DWORD()
        if casc.CascReadFile(hFile, buffer, file_size, ctypes.byref(bytes_read)):
            print(f"Read {bytes_read.value} bytes")
            with open("Viking.m3", "wb") as f:
                f.write(buffer.raw)
            print("Saved to Viking.m3")
        else:
            print("Failed to read file")
    
    casc.CascCloseFile(hFile)
else:
    err = casc.GetCascError()
    print(f"Failed to open file. Error code: {err}")

casc.CascCloseStorage(hStorage)
