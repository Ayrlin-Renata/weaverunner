import customtkinter as ctk
from tkinter import messagebox
from .base_dialog import BaseDialog
from .language_names_dialog import LanguageNamesDialog


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
        self.app.watcher_handler.update_monitoring_list(self.app)
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
