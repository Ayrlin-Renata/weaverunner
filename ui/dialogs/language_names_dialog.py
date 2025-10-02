import customtkinter as ctk


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
