import customtkinter as ctk


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
