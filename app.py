import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
from casc_interface import CascHandler
from m3_analyzer import M3Analyzer

class AssetExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SC2 Asset Extractor")
        self.root.geometry("800x600")
        
        self.casc = CascHandler()
        self.analyzer = M3Analyzer()
        self.found_files = []
        
        self._setup_ui()
        
        # Auto-connect on start
        self.log("Initializing CASC storage...")
        self.root.after(100, self._connect_casc)

    def _setup_ui(self):
        # Top Frame: Search
        search_frame = ttk.Frame(self.root, padding="10")
        search_frame.pack(fill=tk.X)
        
        ttk.Label(search_frame, text="Search Pattern:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar(value="*Viking*")
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<Return>', lambda e: self.search_files())
        
        ttk.Button(search_frame, text="Search", command=self.search_files).pack(side=tk.LEFT)
        
        # Middle Frame: Results List
        list_frame = ttk.Frame(self.root, padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview for multi-column list (Type, Filename, Path)
        columns = ("type", "filename", "path")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("type", text="Type")
        self.tree.heading("filename", text="File Name")
        self.tree.heading("path", text="Full Path")
        
        self.tree.column("type", width=100)
        self.tree.column("filename", width=200)
        self.tree.column("path", width=400)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bottom Frame: Actions
        action_frame = ttk.Frame(self.root, padding="10")
        action_frame.pack(fill=tk.X)
        
        self.smart_extract_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(action_frame, text="Smart Extract (Include Textures for Models)", 
                       variable=self.smart_extract_var).pack(side=tk.LEFT)
        
        ttk.Button(action_frame, text="Extract Selected", command=self.extract_selected).pack(side=tk.RIGHT)
        
        # Log Area
        log_frame = ttk.LabelFrame(self.root, text="Log", padding="5")
        log_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.log_text = tk.Text(log_frame, height=8, state='disabled')
        self.log_text.pack(fill=tk.X)

    def log(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.root.update_idletasks()

    def _connect_casc(self):
        def connect():
            try:
                if self.casc.open_storage():
                    self.root.after(0, lambda: self.log("Connected to SC2 Storage successfully."))
                else:
                    self.root.after(0, lambda: self.log("Failed to connect to SC2 Storage."))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"Error connecting: {e}"))
        
        threading.Thread(target=connect, daemon=True).start()

    def _get_file_type(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.m3':
            return "3D Model"
        elif ext in ['.dds', '.tga', '.png', '.jpg']:
            return "Texture/Image"
        elif ext in ['.ogg', '.wav', '.mp3']:
            return "Sound"
        elif ext == '.ogv':
            return "Video"
        elif ext == '.m3a':
            return "Animation"
        elif ext == '.sc2map':
            return "Map"
        elif ext == '.fxa':
            return "FaceFX"
        elif ext in ['.txt', '.xml', '.galaxy']:
            return "Text/Script"
        else:
            return "Unknown"

    def search_files(self):
        pattern = self.search_var.get()
        if not pattern:
            return
            
        self.log(f"Searching for '{pattern}'...")
        self.tree.delete(*self.tree.get_children())
        
        def run_search():
            results = self.casc.search_files(pattern)
            
            def update_ui():
                self.found_files = results
                for path in results:
                    filename = os.path.basename(path)
                    file_type = self._get_file_type(filename)
                    self.tree.insert("", tk.END, values=(file_type, filename, path))
                self.log(f"Found {len(results)} files.")
                
            self.root.after(0, update_ui)
            
        threading.Thread(target=run_search, daemon=True).start()

    def extract_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select files to extract.")
            return
            
        dest_dir = filedialog.askdirectory(title="Select Extraction Folder")
        if not dest_dir:
            return
            
        paths_to_extract = []
        for item in selected_items:
            item_data = self.tree.item(item)
            # Path is now the 3rd column (index 2)
            paths_to_extract.append(item_data['values'][2]) 
            
        self.log(f"Starting extraction of {len(paths_to_extract)} files...")
        
        def run_extraction():
            count = 0
            for casc_path in paths_to_extract:
                # 1. Extract the main file
                local_rel_path = casc_path.replace("mods\\liberty.sc2mod\\base.sc2assets\\", "") # Simplify path
                full_dest = os.path.join(dest_dir, local_rel_path)
                
                if self.casc.extract_file(casc_path, full_dest):
                    self.root.after(0, lambda p=casc_path: self.log(f"Extracted: {p}"))
                    count += 1
                    
                    # 2. Smart Extract (Textures)
                    if self.smart_extract_var.get() and casc_path.lower().endswith('.m3'):
                        # Pass the directory of the extracted model so we can save textures relative to it
                        model_dir = os.path.dirname(full_dest)
                        self._smart_extract_textures(casc_path, model_dir)
                else:
                    self.root.after(0, lambda p=casc_path: self.log(f"Failed: {p}"))
            
            self.root.after(0, lambda: messagebox.showinfo("Done", f"Extraction complete. {count} files processed."))

        threading.Thread(target=run_extraction, daemon=True).start()

    def _smart_extract_textures(self, m3_casc_path, model_dest_dir):
        self.root.after(0, lambda: self.log(f"Analyzing textures for {os.path.basename(m3_casc_path)}..."))
        
        # Read M3 content from memory
        content = self.casc.read_file_content(m3_casc_path)
        if not content:
            return

        # Analyze dependencies
        texture_paths = self.analyzer.get_dependencies(content)
        
        found_textures = 0
        for tex_path in texture_paths:
            # Texture paths in M3 are often relative or just filenames
            # We need to find where they actually are in CASC.
            
            candidates = []
            
            # Common CASC roots
            roots = [
                "", # As is
                "mods\\liberty.sc2mod\\base.sc2assets\\",
                "Campaigns\\Liberty.SC2Campaign\\Base.SC2Assets\\",
                "mods\\swarm.sc2mod\\base.sc2assets\\",
                "mods\\void.sc2mod\\base.sc2assets\\"
            ]
            
            # If path already has Assets/Textures, don't prepend it again
            if "assets\\textures" in tex_path.lower():
                for root in roots:
                    candidates.append(f"{root}{tex_path}")
            else:
                # Try with and without Assets/Textures prefix
                for root in roots:
                    candidates.append(f"{root}{tex_path}")
                    candidates.append(f"{root}Assets\\Textures\\{tex_path}")
            
            # We need a way to check existence efficiently. 
            # For now, we'll try to extract. If it fails, try next.
            # Ideally we'd use CascOpenFile to check existence first.
            
            extracted = False
            for candidate in candidates:
                # Construct local destination relative to the MODEL
                # This ensures Blender finds it at [ModelDir]/Assets/Textures/foo.dds
                # Normalize path separators for the local OS
                norm_tex_path = tex_path.replace('\\', os.sep).replace('/', os.sep)
                full_tex_dest = os.path.join(model_dest_dir, norm_tex_path)
                
                if self.casc.extract_file(candidate, full_tex_dest):
                    self.root.after(0, lambda p=tex_path: self.log(f"  + Extracted texture: {p}"))
                    found_textures += 1
                    extracted = True
                    break
            
            if not extracted:
                # self.root.after(0, lambda p=tex_path: self.log(f"  - Missing texture: {p}"))
                pass

if __name__ == "__main__":
    root = tk.Tk()
    app = AssetExtractorApp(root)
    root.mainloop()
