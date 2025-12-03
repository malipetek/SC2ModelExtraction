import os
import re
import shutil
import zipfile

def get_version_parts(content):
    match = re.search(r'[\'"]version[\'"]:\s*\((\d+),\s*(\d+),\s*(\d+)\)', content)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    raise ValueError("Could not find version in __init__.py")

def increment_version():
    init_path = os.path.join('m3studio-main', '__init__.py')
    with open(init_path, 'r') as f:
        content = f.read()
    
    major, minor, patch = get_version_parts(content)
    new_patch = patch + 1
    
    old_version_regex = r'([\'"]version[\'"]:\s*\()(\d+),\s*(\d+),\s*(\d+)(\))'
    
    new_content = re.sub(
        old_version_regex, 
        f'\\g<1>{major}, {minor}, {new_patch}\\g<5>', 
        content
    )
    
    with open(init_path, 'w') as f:
        f.write(new_content)
        
    print(f"Incremented version from {major}.{minor}.{patch} to {major}.{minor}.{new_patch}")
    return f"{major}.{minor}.{new_patch}"

def build():
    # Ensure dist directory exists
    if not os.path.exists('dist'):
        os.makedirs('dist')

    # Clean up old m3studio-main zip files
    for filename in os.listdir('dist'):
        if filename.startswith('m3studio-main') and filename.endswith('.zip'):
            print(f"Removing old version: {filename}")
            os.remove(os.path.join('dist', filename))

    version = increment_version()
    zip_name = f"m3studio-main_v{version}.zip"
    zip_path = os.path.join('dist', zip_name)
    
    print(f"Creating {zip_name}...")
    
    # Create the zip file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('m3studio-main'):
            # Filter out unwanted directories
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.vscode', 'dist']]
            
            for file in files:
                if file in ['.DS_Store', '.gitignore', '.gitmodules']:
                    continue
                if file.endswith('.pyc'):
                    continue
                
                file_path = os.path.join(root, file)
                # Keep the m3addon/ prefix in the zip
                arcname = file_path
                zipf.write(file_path, arcname)
                
    print(f"Successfully created {zip_path}")

if __name__ == '__main__':
    build()
