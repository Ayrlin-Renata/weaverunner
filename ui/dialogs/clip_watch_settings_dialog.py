import customtkinter as ctk
from tkinter import messagebox
from .base_dialog import BaseDialog


class ClipWatchSettingsDialog(BaseDialog):
    def __init__(self, parent, i18n, algorithms, **kwargs):
        self.scale_factor_var = ctk.StringVar(value="2")
        self.algorithm_var = ctk.StringVar(value=algorithms[0] if algorithms else "Lanczos")
        self.algorithms = algorithms
        super().__init__(parent, title_key='clip_watch_settings_dialog_title', i18n=i18n, **kwargs)
    
    def _body(self, master):
        master.grid_columnconfigure(1, weight=1)
        scale_factor_label = ctk.CTkLabel(master, text=self.i18n.t('clip_watch_scale_factor_label'))
        scale_factor_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.scale_factor_entry = ctk.CTkEntry(master, textvariable=self.scale_factor_var)
        self.scale_factor_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        algorithm_label = ctk.CTkLabel(master, text=self.i18n.t('clip_watch_algorithm_label'))
        algorithm_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.algorithm_menu = ctk.CTkOptionMenu(master, variable=self.algorithm_var, values=self.algorithms)
        self.algorithm_menu.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.scale_factor_entry.focus()
    
    def _apply(self):
        scale_factor_str = self.scale_factor_var.get().strip()
        try:
            scale_factor = int(scale_factor_str)
            
            if scale_factor <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror(self.i18n.t('dialog_error'), self.i18n.t('clip_watch_error_invalid_scale'), parent=self)
            return False
        
        algorithm = self.algorithm_var.get()
        self.result = {"scale_factor": scale_factor, "algorithm": algorithm}
        return True
