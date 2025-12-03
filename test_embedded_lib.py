import ctypes
import os
import sys

# Define types
HANDLE = ctypes.c_void_p
DWORD = ctypes.c_uint32
PCSTR = ctypes.c_char_p

class TestHandler:
    def __init__(self):
        # Point to the embedded library in the addon folder
        self.lib_path = os.path.abspath("sc2_asset_browser_v2/lib/libcasc.dylib")
        print(f"Testing library at: {self.lib_path}")
        
        try:
            self.casc = ctypes.cdll.LoadLibrary(self.lib_path)
            print("Library loaded successfully.")
            
            self.casc.CascOpenStorage.argtypes = [PCSTR, DWORD, ctypes.POINTER(HANDLE)]
            self.casc.CascOpenStorage.restype = ctypes.c_bool
            
            self.casc.GetCascError.argtypes = []
            self.casc.GetCascError.restype = DWORD
            
        except Exception as e:
            print(f"Failed to load library: {e}")
            sys.exit(1)

    def test_open(self):
        storage_path = "/Applications/StarCraft II"
        print(f"Attempting to open storage at: {storage_path}")
        
        hStorage = HANDLE()
        if self.casc.CascOpenStorage(storage_path.encode('utf-8'), 0, ctypes.byref(hStorage)):
            print("SUCCESS: Storage opened!")
            self.casc.CascCloseStorage(hStorage)
        else:
            err = self.casc.GetCascError()
            print(f"FAILURE: Failed to open storage. Error code: {err}")

if __name__ == "__main__":
    test = TestHandler()
    test.test_open()
