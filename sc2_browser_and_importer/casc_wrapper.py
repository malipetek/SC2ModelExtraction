import ctypes
import os
import sys
import bpy

# Define types
HANDLE = ctypes.c_void_p
DWORD = ctypes.c_uint32
PVOID = ctypes.c_void_p
PCSTR = ctypes.c_char_p
PDWORD = ctypes.POINTER(DWORD)

# Constants
CASC_LOCALE_ALL = 0xFFFFFFFF

class CASC_FIND_DATA(ctypes.Structure):
    _fields_ = [
        ("szFileName", ctypes.c_char * 1024),
        ("PlainName", ctypes.c_char * 1024),
        ("dwFileSize", DWORD),
        ("dwFileFlags", DWORD),
        ("dwLocaleFlags", DWORD),
        ("dwContentFlags", DWORD),
    ]

class CascWrapper:
    def __init__(self):
        preferences = bpy.context.preferences.addons[__package__].preferences
        self.storage_path = preferences.sc2_install_path
        
        # Use embedded library
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.lib_path = os.path.join(current_dir, "lib", "libcasc.dylib")
        
        self.casc = None
        self.hStorage = None
        self.is_open = False
        
        if not os.path.exists(self.lib_path):
            print(f"Embedded CascLib not found at: {self.lib_path}")
            return

        self._load_library()

    def _load_library(self):
        print(f"SC2 Asset Browser: Loading library from {self.lib_path}")
        try:
            self.casc = ctypes.cdll.LoadLibrary(self.lib_path)
            print("SC2 Asset Browser: Library loaded successfully")
            
            # Signatures
            self.casc.CascOpenStorage.argtypes = [PCSTR, DWORD, ctypes.POINTER(HANDLE)]
            self.casc.CascOpenStorage.restype = ctypes.c_bool

            self.casc.CascOpenFile.argtypes = [HANDLE, PCSTR, DWORD, DWORD, ctypes.POINTER(HANDLE)]
            self.casc.CascOpenFile.restype = ctypes.c_bool

            self.casc.CascReadFile.argtypes = [HANDLE, PVOID, DWORD, PDWORD]
            self.casc.CascReadFile.restype = ctypes.c_bool

            self.casc.CascCloseFile.argtypes = [HANDLE]
            self.casc.CascCloseFile.restype = ctypes.c_bool

            self.casc.CascCloseStorage.argtypes = [HANDLE]
            self.casc.CascCloseStorage.restype = ctypes.c_bool

            self.casc.CascGetFileSize.argtypes = [HANDLE, PDWORD]
            self.casc.CascGetFileSize.restype = DWORD

            self.casc.GetCascError.argtypes = []
            self.casc.GetCascError.restype = DWORD
            
            self.casc.CascFindFirstFile.argtypes = [HANDLE, PCSTR, ctypes.POINTER(CASC_FIND_DATA), PCSTR]
            self.casc.CascFindFirstFile.restype = HANDLE

            self.casc.CascFindNextFile.argtypes = [HANDLE, ctypes.POINTER(CASC_FIND_DATA)]
            self.casc.CascFindNextFile.restype = ctypes.c_bool

            self.casc.CascFindClose.argtypes = [HANDLE]
            self.casc.CascFindClose.restype = ctypes.c_bool
            
        except OSError as e:
            print(f"Failed to load CascLib: {e}")
            # Don't raise here, just log, so Blender doesn't crash on init
            
    def open_storage(self):
        if self.is_open:
            return True
        
        if not self.casc:
            print("CascLib not loaded.")
            return False
            
        print(f"Opening storage at {self.storage_path}...")
        self.hStorage = HANDLE()
        if self.casc.CascOpenStorage(self.storage_path.encode('utf-8'), 0, ctypes.byref(self.hStorage)):
            self.is_open = True
            print("Storage opened!")
            return True
        else:
            err = self.casc.GetCascError()
            print(f"Failed to open storage. Error code: {err}")
            return False

    def close_storage(self):
        if self.is_open and self.hStorage:
            self.casc.CascCloseStorage(self.hStorage)
            self.is_open = False
            self.hStorage = None

    def search_files(self, pattern="*"):
        if not self.is_open:
            return []

        results = []
        find_data = CASC_FIND_DATA()
        
        mask = pattern.encode('utf-8')
        
        hFind = self.casc.CascFindFirstFile(self.hStorage, mask, ctypes.byref(find_data), None)
        
        if hFind and hFind != -1:
            filename = find_data.szFileName.decode('utf-8', errors='ignore')
            results.append(filename)
            
            while self.casc.CascFindNextFile(hFind, ctypes.byref(find_data)):
                filename = find_data.szFileName.decode('utf-8', errors='ignore')
                results.append(filename)
                
            self.casc.CascFindClose(hFind)
            
        return results

    def extract_file(self, casc_path, dest_path):
        if not self.is_open:
            return False

        hFile = HANDLE()
        if self.casc.CascOpenFile(self.hStorage, casc_path.encode('utf-8'), CASC_LOCALE_ALL, 0, ctypes.byref(hFile)):
            file_size = self.casc.CascGetFileSize(hFile, None)
            
            if file_size > 0:
                buffer = ctypes.create_string_buffer(file_size)
                bytes_read = DWORD()
                if self.casc.CascReadFile(hFile, buffer, file_size, ctypes.byref(bytes_read)):
                    
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    
                    with open(dest_path, "wb") as f:
                        f.write(buffer.raw)
                    
                    self.casc.CascCloseFile(hFile)
                    return True
            
            self.casc.CascCloseFile(hFile)
        
        return False

    def read_file_content(self, casc_path):
        if not self.is_open:
            return None

        hFile = HANDLE()
        content = None
        
        if self.casc.CascOpenFile(self.hStorage, casc_path.encode('utf-8'), CASC_LOCALE_ALL, 0, ctypes.byref(hFile)):
            file_size = self.casc.CascGetFileSize(hFile, None)
            
            if file_size > 0:
                buffer = ctypes.create_string_buffer(file_size)
                bytes_read = DWORD()
                if self.casc.CascReadFile(hFile, buffer, file_size, ctypes.byref(bytes_read)):
                    content = buffer.raw
            
            self.casc.CascCloseFile(hFile)
            
        return content
