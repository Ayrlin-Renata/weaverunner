import customtkinter as ctk
import os
from tkinter import messagebox
import json
import inspect
import pyperclip
from automation.automation_config import AutomationSettings
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


class PresetManagerDialog(BaseDialog):
    def __init__(self, parent, app, **kwargs):
        self.app = app
        self.preset_manager = app.preset_manager
        self.i18n = app.i18n
        self.preset_widgets = {}
        self.display_names = {}
        super().__init__(parent, title_key='preset_manager_title', i18n=self.i18n, **kwargs)
    
    def _body(self, master):
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)
        content_frame = ctk.CTkFrame(master, fg_color="transparent")
        content_frame.grid(row=0, column=0, sticky="nsew")
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        self.scroll_frame = ctk.CTkScrollableFrame(content_frame, label_text=self.i18n.t('load_preset_available'), height=400)
        self.scroll_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=5)
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        side_buttons_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        side_buttons_frame.grid(row=0, column=1, sticky="ns", padx=(5, 0), pady=5)
        load_button = ctk.CTkButton(side_buttons_frame, text=self.i18n.t('preset_manager_load'), command=self._load_selected)
        load_button.pack(pady=(5,20), fill="x")
        import_button = ctk.CTkButton(side_buttons_frame, text=self.i18n.t('preset_manager_import'), command=self._import)
        import_button.pack(pady=5, fill="x")
        export_button = ctk.CTkButton(side_buttons_frame, text=self.i18n.t('preset_manager_export'), command=self._export)
        export_button.pack(pady=5, fill="x")
        delete_button = ctk.CTkButton(side_buttons_frame, text=self.i18n.t('preset_manager_delete'), command=self._delete, fg_color="#D2042D", hover_color="#AA0324")
        delete_button.pack(pady=(20, 5), fill="x")
        open_folder_button = ctk.CTkButton(side_buttons_frame, text=self.i18n.t('preset_manager_open_folder'), command=self._open_folder)
        open_folder_button.pack(pady=(5, 5), fill="x")
        self._create_save_section(master)
        close_button = ctk.CTkButton(master, text=self.i18n.t('preset_manager_close'), command=self._cancel)
        close_button.grid(row=2, column=0, pady=(5,0))
        self._refresh_preset_list()
    
    def _refresh_preset_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.preset_widgets = {}
        all_presets = self.preset_manager.load_all()
        grouped_presets = {}
        
        for preset_id, data in all_presets.items():
            name = data.get('name', preset_id)
            
            if name not in grouped_presets:
                grouped_presets[name] = {}
            grouped_presets[name][data.get('language', 'en')] = {'id': preset_id, 'data': data}
        
        if not grouped_presets:
            ctk.CTkLabel(self.scroll_frame, text=self.i18n.t('load_preset_none')).pack(pady=20)
            return
        current_lang = self.i18n.language
        
        for name, lang_versions in sorted(grouped_presets.items()):
            if current_lang in lang_versions:
                display_version = lang_versions[current_lang]
            elif 'en' in lang_versions:
                display_version = lang_versions['en']
            else:
                display_version = next(iter(lang_versions.values()))
            preset_id = display_version['id']
            data = display_version['data']
            frame = ctk.CTkFrame(self.scroll_frame)
            frame.pack(fill="x", padx=5, pady=5)
            frame.grid_columnconfigure(1, weight=1)
            var = ctk.BooleanVar()
            cb = ctk.CTkCheckBox(frame, text="", variable=var, width=20)
            cb.grid(row=0, column=0, rowspan=2, padx=5)
            def create_toggle_command(v):
                return lambda event=None: v.set(not v.get())
            toggle_command = create_toggle_command(var)
            display_name = data.get('display_names', {}).get(self.i18n.language, data.get('name', preset_id))
            name_label = ctk.CTkLabel(frame, text=display_name, font=ctk.CTkFont(weight="bold"))
            name_label.grid(row=0, column=1, sticky="w", padx=5)
            desc_text = data.get('description') or self.i18n.t('load_preset_no_desc')
            desc_label = ctk.CTkLabel(frame, text=desc_text, text_color="gray60", wraplength=400, justify="left")
            desc_label.grid(row=1, column=1, sticky="w", padx=5)
            widgets_to_bind = [frame, name_label, desc_label]
            other_langs = [lang for lang in lang_versions.keys() if lang != display_version['data'].get('language')]
            
            if other_langs:
                lang_indicator = ctk.CTkLabel(frame, text=self.i18n.t('preset_manager_other_languages', langs=", ".join(other_langs).upper()), font=ctk.CTkFont(size=10), text_color="gray50")
                lang_indicator.grid(row=0, column=2, padx=5, sticky="e")
                widgets_to_bind.append(lang_indicator)
            
            for widget in widgets_to_bind:
                widget.bind("<Button-1>", toggle_command)
            self.preset_widgets[preset_id] = {'var': var, 'frame': frame, 'data': data}
    
    def _get_selected_ids(self):
        return [pid for pid, widget in self.preset_widgets.items() if widget['var'].get()]
    
    def _create_save_section(self, master):
        save_frame = ctk.CTkFrame(master)
        save_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(10, 5))
        save_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(save_frame, text=self.i18n.t('preset_manager_save_section_title'), font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(save_frame, text=self.i18n.t('save_preset_name')).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.save_name_entry = ctk.CTkEntry(save_frame)
        self.save_name_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(save_frame, text=self.i18n.t('save_preset_desc')).grid(row=2, column=0, sticky="nw", padx=10, pady=5)
        self.save_desc_entry = ctk.CTkTextbox(save_frame, height=50, wrap="word")
        self.save_desc_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=5)
        self.lang_names_button = ctk.CTkButton(save_frame, text=self.i18n.t('language_names_button'), command=self._open_lang_names_dialog)
        self.lang_names_button.grid(row=1, column=2, pady=(5, 5), sticky="ns")
        save_new_button = ctk.CTkButton(save_frame, text=self.i18n.t('preset_manager_save_new'), command=self._save_current)
        save_new_button.grid(row=2, column=2, padx=10, pady=5, sticky="ns")
    
    def _buttonbox(self):
        pass
    
    def _load_selected(self):
        selected_ids = self._get_selected_ids()
        
        if not selected_ids:
            messagebox.showwarning("Warning", self.i18n.t('preset_manager_no_selection'), parent=self)
            return
        preset_id_to_load = selected_ids[0]
        preset_data = self.preset_widgets[preset_id_to_load]['data']
        slots_to_apply = preset_data.get('slots', [])
        
        for i, slot_data in enumerate(slots_to_apply):
            if i < len(self.app.texture_slots):
                self.app.texture_slots[i].set_data(slot_data, from_preset=True)
        self.app.log_to_console(f"Preset '{preset_data.get('name')}' loaded.")
        self.app.update_monitoring_list()
        self._cancel()
    
    def _save_current(self):
        name = self.save_name_entry.get().strip()
        description = self.save_desc_entry.get("1.0", "end-1c").strip()
        
        if not name:
            messagebox.showwarning(self.i18n.t('save_preset_dialog_title'), self.i18n.t('preset_manager_name_empty'), parent=self)
            return
        slots_data = [slot.get_data(for_preset=True) for slot in self.app.texture_slots]
        success = self.preset_manager.save(
            name,
            description,
            slots_data,
            self.i18n.language,
            display_names=self.display_names
        )
        
        if success:
            self.display_names = {}
            self._refresh_preset_list()
            self.save_name_entry.delete(0, 'end')
            self.save_desc_entry.delete("1.0", 'end')
    
    def _import(self):
        count = self.preset_manager.import_presets(self)
        
        if count > 0:
            messagebox.showinfo("Success", self.i18n.t('preset_manager_import_success', count=count), parent=self)
            self._refresh_preset_list()
    
    def _export(self):
        selected_ids = self._get_selected_ids()
        
        if not selected_ids:
            messagebox.showwarning("Warning", self.i18n.t('preset_manager_no_selection'), parent=self)
            return
        self.preset_manager.export_presets(selected_ids, self)
    
    def _delete(self):
        selected_ids = self._get_selected_ids()
        
        if not selected_ids:
            messagebox.showwarning("Warning", self.i18n.t('preset_manager_no_selection'), parent=self)
            return
        confirm = messagebox.askyesno(
            self.i18n.t('preset_manager_confirm_delete_title'),
            self.i18n.t('preset_manager_confirm_delete_msg', count=len(selected_ids)),
            parent=self
        )
        
        if confirm:
            self.preset_manager.delete(selected_ids)
            self._refresh_preset_list()
    
    def _open_folder(self):
        self.preset_manager.open_user_presets_folder()
    
    def _open_lang_names_dialog(self):
        dialog = LanguageNamesDialog(self, self.i18n, self.display_names)
        result = dialog.get_display_names()
        
        if result is not None:
            self.display_names = result
    
    def _ok(self, event=None):
        pass
    
    def _apply(self):
        return True


class LanguageNamesDialog(ctk.CTkToplevel):
    def __init__(self, parent, i18n, current_display_names=None):
        super().__init__(parent)
        self.i18n = i18n
        self.transient(parent)
        self.grab_set()
        self.title(self.i18n.t('language_names_dialog_title'))
        self.result = None
        
        if current_display_names is None:
            current_display_names = {}
        self.entries = {}
        ctk.CTkLabel(self, text=self.i18n.t('language_names_en')).pack(padx=20, pady=(10, 2), anchor="w")
        self.en_entry = ctk.CTkEntry(self, width=300)
        self.en_entry.pack(padx=20, pady=(0, 10), fill="x", expand=True)
        self.en_entry.insert(0, current_display_names.get('en', ''))
        self.entries['en'] = self.en_entry
        ctk.CTkLabel(self, text=self.i18n.t('language_names_ja')).pack(padx=20, pady=(10, 2), anchor="w")
        self.ja_entry = ctk.CTkEntry(self, width=300)
        self.ja_entry.pack(padx=20, pady=(0, 10), fill="x", expand=True)
        self.ja_entry.insert(0, current_display_names.get('ja', ''))
        self.entries['ja'] = self.ja_entry
        ok_button = ctk.CTkButton(self, text=self.i18n.t('dialog_ok'), command=self._on_ok)
        ok_button.pack(padx=20, pady=20)
        self.en_entry.focus()
    
    def _on_ok(self):
        self.result = {lang: entry.get() for lang, entry in self.entries.items() if entry.get()}
        self.destroy()
    
    def get_display_names(self):
        self.wait_window()
        return self.result


class UserAgreementDialog(ctk.CTkToplevel):
    def __init__(self, parent, i18n, callback):
        super().__init__(parent)
        self.i18n = i18n
        self.callback = callback
        self.parent = parent
        self.title(self.i18n.t('agreement_dialog_title'))
        width = 500
        height = 350
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        lang_frame = ctk.CTkFrame(self, fg_color="transparent")
        lang_frame.grid(row=0, column=0, sticky="ne", padx=10, pady=5)
        self.en_button = ctk.CTkButton(lang_frame, text="EN", width=40, command=lambda: self._switch_lang('en'))
        self.en_button.pack(side="left", padx=(0, 5))
        self.ja_button = ctk.CTkButton(lang_frame, text="JA", width=40, command=lambda: self._switch_lang('ja'))
        self.ja_button.pack(side="left")
        self.heading_label = ctk.CTkLabel(self, text=self.i18n.t('window_title'), font=ctk.CTkFont(size=20, weight="bold"))
        self.heading_label.grid(row=1, column=0, pady=(0, 10))
        self.textbox = ctk.CTkTextbox(self, wrap="word")
        self.textbox.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.textbox.insert("1.0", self.i18n.t('agreement_dialog_text'))
        self.textbox.configure(state="disabled")
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, pady=10)
        self.accept_button = ctk.CTkButton(button_frame, text=self.i18n.t('agreement_dialog_button'), command=self._on_accept)
        self.accept_button.pack(side="left", padx=10)
        self.close_app_button = ctk.CTkButton(button_frame, text=self.i18n.t('agreement_dialog_close_app'), command=self.parent._on_closing, fg_color="gray50", hover_color="gray40")
        self.close_app_button.pack(side="right", padx=10)
        self.after(100, lambda: self.lift())
    
    def _on_accept(self):
        self.callback()
        self.grab_release()
        self.destroy()
    
    def _switch_lang(self, lang_code):
        self.parent._switch_language(lang_code)
        self._retranslate()
    
    def _retranslate(self):
        self.title(self.i18n.t('agreement_dialog_title'))
        self.heading_label.configure(text=self.i18n.t('window_title'))
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", self.i18n.t('agreement_dialog_text'))
        self.textbox.configure(state="disabled")
        self.accept_button.configure(text=self.i18n.t('agreement_dialog_button'))
        self.close_app_button.configure(text=self.i18n.t('agreement_dialog_close_app'))


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
