import customtkinter as ctk
import json
import inspect
import pyperclip
from tkinter import messagebox
from .base_dialog import BaseDialog


class AutomationSettingsDialog(BaseDialog):
    def __init__(self, parent, i18n, config_manager, **kwargs):
        self.config_manager = config_manager
        self.settings_fields = {}
        super().__init__(parent, title_key='automation_settings_dialog_title', i18n=i18n, **kwargs)
    
    def _get_configurable_settings(self):
        """
        Dynamically get settings from the live AutomationSettings class.
        """
        settings = []
        
        for name, value in inspect.getmembers(self.config_manager.settings_class):
            if name.isupper() and name != 'DEFAULT_TEXTURE_VALUES':
                settings.append((name, value))
        return sorted(settings)
    
    def _body(self, master):
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(0, weight=1)
        scrollable_frame = ctk.CTkScrollableFrame(master, label_text="Delays and Timeouts (seconds)")
        scrollable_frame.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)
        scrollable_frame.grid_columnconfigure(1, weight=1)
        configurable_settings = self._get_configurable_settings()
        
        for i, (name, value) in enumerate(configurable_settings):
            label = ctk.CTkLabel(scrollable_frame, text=name)
            label.grid(row=i, column=0, padx=10, pady=(5,10), sticky="w")
            entry = ctk.CTkEntry(scrollable_frame)
            entry.insert(0, str(value))
            entry.grid(row=i, column=1, padx=10, pady=(5,10), sticky="ew")
            self.settings_fields[name] = entry
        extra_button_frame = ctk.CTkFrame(master, fg_color="transparent")
        extra_button_frame.grid(row=1, column=0, pady=5)
        reset_button = ctk.CTkButton(extra_button_frame, text=self.i18n.t('reset_to_defaults_button'), command=self._reset_to_defaults)
        reset_button.pack(side="left", padx=5)
        copy_button = ctk.CTkButton(extra_button_frame, text=self.i18n.t('copy_settings_button'), command=self._copy_settings)
        copy_button.pack(side="left", padx=5)
        paste_button = ctk.CTkButton(extra_button_frame, text=self.i18n.t('paste_settings_button'), command=self._paste_settings)
        paste_button.pack(side="left", padx=5)
    
    def _reset_to_defaults(self):
        defaults = self.config_manager.defaults
        
        for name, entry in self.settings_fields.items():
            if name in defaults:
                entry.delete(0, 'end')
                entry.insert(0, str(defaults[name]))
    
    def _copy_settings(self):
        settings_to_copy = {name: entry.get() for name, entry in self.settings_fields.items()}
        try:
            json_string = json.dumps(settings_to_copy, indent=4)
            pyperclip.copy(json_string)
            messagebox.showinfo("Success", self.i18n.t('settings_copied_msg'), parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Could not copy settings: {e}", parent=self)
    
    def _paste_settings(self):
        try:
            json_string = pyperclip.paste()
            pasted_settings = json.loads(json_string)
            
            for name, value in pasted_settings.items():
                if name in self.settings_fields:
                    self.settings_fields[name].delete(0, 'end')
                    self.settings_fields[name].insert(0, str(value))
            messagebox.showinfo("Success", self.i18n.t('settings_pasted_msg'), parent=self)
        except Exception as e:
            messagebox.showerror("Error", self.i18n.t('paste_error_msg', error=e), parent=self)
    
    def _apply(self):
        try:
            for name, entry in self.settings_fields.items():
                value = float(entry.get())
                
                if value.is_integer(): value = int(value)
                setattr(self.config_manager.settings_class, name, value)
            self.config_manager.save_settings()
            self.master.log_to_console("Automation settings updated and saved.")
            return True
        except ValueError as e:
            messagebox.showerror("Validation Error", f"Invalid value for a setting: must be a number.\n\nError: {e}", parent=self)
            return False
