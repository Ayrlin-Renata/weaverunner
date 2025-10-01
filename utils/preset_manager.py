import json
import os
import re
import shutil
import zipfile
from tkinter import filedialog, messagebox
import sys
import subprocess
PRESET_VERSION = "1.0"


class PresetManager:
    def __init__(self, app_name="WeaveRunner"):
        self.app_name = app_name
        self.default_presets_dir = 'presets'
        self.user_presets_dir = self._get_user_presets_path()
        self._initialize_user_presets()
    
    def _get_user_presets_path(self):
        """
        Gets the path to the user-specific presets directory.
        """
        
        if sys.platform == 'win32':
            base_path = os.getenv('APPDATA')
        elif sys.platform == 'darwin':
            base_path = os.path.expanduser('~/Library/Application Support')
        else:
            base_path = os.path.expanduser('~/.config')
        return os.path.join(base_path, self.app_name, 'presets')
    
    def _initialize_user_presets(self):
        """
        Ensures the user presets directory exists. If it's the first time
        creating it, it copies the default presets over.
        """
        user_dir_existed = os.path.isdir(self.user_presets_dir)
        os.makedirs(self.user_presets_dir, exist_ok=True)
        os.makedirs(self.default_presets_dir, exist_ok=True)
        
        if not user_dir_existed:
            print("User presets folder not found, creating and populating with defaults...")
            try:
                if not os.path.isdir(self.default_presets_dir): return
                
                for filename in os.listdir(self.default_presets_dir):
                    if filename.endswith('.json'):
                        default_path = os.path.join(self.default_presets_dir, filename)
                        user_path = os.path.join(self.user_presets_dir, filename)
                        shutil.copy2(default_path, user_path)
                        print(f"Copied default preset '{filename}' to user directory.")
            except (IOError, OSError) as e:
                print(f"Could not initialize user presets: {e}")
    
    def _sanitize_filename(self, name):
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = name.replace(' ', '_')
        return name
    
    def load_all(self):
        """
        Loads all presets from the user presets directory.
        """
        presets = {}
        
        for filename in os.listdir(self.user_presets_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.user_presets_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        if 'name' in data and 'version' in data and 'slots' in data:
                            preset_id = os.path.splitext(filename)[0]
                            presets[preset_id] = data
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error loading preset {filename}: {e}")
        return presets
    
    def save(self, name, description, slots_data, lang_code, display_names=None):
        """
        Saves a single preset as a new .json file in the user directory.
        """
        preset_id = self._sanitize_filename(name)
        filepath = os.path.join(self.user_presets_dir, f"{preset_id}.json")
        
        if os.path.exists(filepath):
            i = 1
            
            while os.path.exists(os.path.join(self.user_presets_dir, f"{preset_id}_{i}.json")):
                i += 1
            preset_id = f"{preset_id}_{i}"
            filepath = os.path.join(self.user_presets_dir, f"{preset_id}.json")
            name = f"{name} ({i})"
        data = {
            "version": PRESET_VERSION,
            "name": name,
            "description": description,
            "language": lang_code,
            "slots": slots_data
        }
        
        if display_names:
            data["display_names"] = display_names
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"Successfully saved preset to '{filepath}'.")
            return True
        except IOError as e:
            print(f"Error saving preset file: {e}")
            return False
    
    def delete(self, preset_ids):
        """
        Deletes a list of presets by their IDs (filenames).
        """
        
        for preset_id in preset_ids:
            filepath = os.path.join(self.user_presets_dir, f"{preset_id}.json")
            
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print(f"Deleted preset: {filepath}")
                except OSError as e:
                    print(f"Error deleting preset file {filepath}: {e}")
    
    def import_presets(self, parent):
        """
        Opens a dialog to import presets from .json or .zip files.
        """
        paths = filedialog.askopenfilenames(
            parent=parent,
            title="Import Presets",
            filetypes=[("Preset Files", "*.json *.zip"), ("All files", "*.*")]
        )
        
        if not paths:
            return 0
        imported_count = 0
        
        for path in paths:
            if path.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(path, 'r') as zf:
                        for member in zf.infolist():
                            if not member.is_dir() and member.filename.lower().endswith('.json'):
                                member_filename = os.path.basename(member.filename)
                                target_path = os.path.join(self.user_presets_dir, member_filename)
                                with zf.open(member) as source, open(target_path, "wb") as target:
                                    shutil.copyfileobj(source, target)
                                imported_count += 1
                except (zipfile.BadZipFile, IOError) as e:
                    print(f"Error importing from zip {path}: {e}")
            elif path.lower().endswith('.json'):
                try:
                    shutil.copy(path, self.user_presets_dir)
                    imported_count += 1
                except (IOError, shutil.SameFileError) as e:
                    print(f"Error importing json {path}: {e}")
        return imported_count
    
    def export_presets(self, preset_ids, parent):
        """
        Exports selected presets to a zip file.
        """
        
        if not preset_ids:
            return
        zip_path = filedialog.asksaveasfilename(
            parent=parent,
            title="Export Presets",
            defaultextension=".zip",
            filetypes=[("Zip Archive", "*.zip")]
        )
        
        if not zip_path:
            return
        try:
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for preset_id in preset_ids:
                    filepath = os.path.join(self.user_presets_dir, f"{preset_id}.json")
                    
                    if os.path.exists(filepath):
                        zf.write(filepath, arcname=f"{preset_id}.json")
            print(f"Successfully exported {len(preset_ids)} presets to {zip_path}")
        except (IOError, zipfile.BadZipFile) as e:
            print(f"Error exporting presets: {e}")
    
    def open_user_presets_folder(self):
        """
        Opens the user presets folder in the system's file explorer.
        """
        path = self.user_presets_dir
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', path])
            else:
                subprocess.run(['xdg-open', path])
        except (OSError, FileNotFoundError) as e:
            print(f"Could not open presets folder at '{path}': {e}")
            messagebox.showerror("Error", f"Could not open folder:\n{path}")
