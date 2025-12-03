import struct
import re

class M3Analyzer:
    def __init__(self):
        pass

    def get_dependencies(self, m3_data):
        """
        Parses binary M3 data and returns a list of referenced texture paths.
        This is a heuristic parser that looks for strings ending in .dds or .tga.
        """
        if not m3_data:
            return []

        dependencies = set()
        
        # Heuristic: Search for strings that look like file paths ending in .dds or .tga
        # M3 strings are usually null-terminated or length-prefixed, but a regex search 
        # on the binary data is robust enough for finding paths.
        
        # Regex for common texture extensions in SC2
        # Looks for: [alphanumeric/path_chars] + .dds|.tga|.tga
        # We assume paths are ASCII/UTF-8
        
        try:
            # Decode binary to string with errors='ignore' to use regex on text
            # This is safer than binary regex for simple path finding
            text_data = m3_data.decode('utf-8', errors='ignore')
            
            # Pattern: 
            # (?:[a-zA-Z0-9_\\/.-]+) -> Match path characters
            # \.(?:dds|tga) -> Match extension
            pattern = re.compile(r'(?:[a-zA-Z0-9_\\/.-]+)\.(?:dds|tga)', re.IGNORECASE)
            
            matches = pattern.findall(text_data)
            
            for match in matches:
                # Filter out likely garbage
                if len(match) > 4 and len(match) < 260:
                    # Normalize path separators
                    clean_path = match.replace('/', '\\')
                    dependencies.add(clean_path)
                    
        except Exception as e:
            print(f"Error analyzing M3 data: {e}")

        return list(dependencies)

# Example usage
if __name__ == "__main__":
    # Test with a dummy file if needed
    pass
