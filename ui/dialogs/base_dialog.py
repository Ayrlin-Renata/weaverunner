import customtkinter as ctk
import os
import json
import screeninfo


def _is_geometry_visible(geom):
    """
    Helper to check if a window geometry is on a visible screen.
    """
    try:
        _, _, x, y = map(int, geom.replace('+', ' ').replace('x', ' ').split())
        return any(m.x <= x < m.x + m.width and m.y <= y < m.y + m.height for m in screeninfo.get_monitors())
    except Exception: return False


class BaseDialog(ctk.CTkToplevel):
    """
    A custom, modern base dialog built entirely with CustomTkinter components.
    This avoids the legacy tkinter.simpledialog and its lifecycle conflicts.
    """
    def __init__(self, parent, title_key=None, i18n=None):
        super().__init__(parent)
        self.i18n = i18n
        self.result = None
        self.title_key = title_key
        self.title(self.i18n.t(title_key) if title_key and self.i18n else "")
        self._load_geometry()
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(expand=True, fill="both", padx=10, pady=10)
        self.body_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.body_frame.pack(expand=True, fill="both", padx=5, pady=5)
        self._body(self.body_frame)
        self._buttonbox()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(100, lambda: self.lift())
    
    def _body(self, master):
        """
        To be overridden by subclasses to create the dialog's main widgets.
        """
        return None
    
    def _buttonbox(self):
        box = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        box.pack(pady=(5, 10))
        self.ok_button = ctk.CTkButton(box, text=self.i18n.t('dialog_ok'), width=100, command=self._ok)
        self.ok_button.pack(side="left", padx=10)
        cancel_button = ctk.CTkButton(box, text=self.i18n.t('dialog_cancel'), width=100, command=self._cancel)
        cancel_button.pack(side="right", padx=10)
        self.bind("<Return>", self._ok)
        self.bind("<Escape>", self._cancel)
    
    def _ok(self, event=None):
        """
        Called when the OK button is pressed.
        """
        
        if not self._apply():
            return
        self._save_geometry()
        self.grab_release()
        self.destroy()
    
    def _cancel(self, event=None):
        """
        Called when the Cancel button or window X is pressed.
        """
        self.result = None
        self._save_geometry()
        self.grab_release()
        self.destroy()
    
    def _load_geometry(self):
        """
        Loads this dialog's geometry from the config file.
        """
        
        if not self.title_key: return
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    geom = config.get("dialog_geometries", {}).get(self.title_key)
                    
                    if geom and _is_geometry_visible(geom):
                        self.geometry(geom)
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            pass
    
    def _save_geometry(self):
        """
        Saves this dialog's geometry to the config file.
        """
        
        if not self.title_key: return
        config = {}
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    config = json.load(f)
            
            if "dialog_geometries" not in config:
                config["dialog_geometries"] = {}
            config["dialog_geometries"][self.title_key] = self.geometry()
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=4)
        except (IOError, json.JSONDecodeError):
            pass
    
    def _apply(self):
        """
        To be overridden by subclasses.
        Should process data and set self.result.
        Return True on success.
        """
        return True
