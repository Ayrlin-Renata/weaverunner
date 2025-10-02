import customtkinter as ctk
import tkinter
import threading
from queue import Queue
from ui.texture_slot import TextureSlotFrame
from ui.i18n import I18N
from ui.custom_menu import CustomMenuBar
from ui.widgets.status_bar import StatusBar
from ui.handlers import (automation_handler, config_handler, dialog_handler,
                       slot_handler, ui_handler, watcher_handler)
from utils.file_watcher import FileWatcher
from utils.process_watcher import ProcessWatcher
from utils.clip_watcher import ClipWatcher, DOWNSCALING_METHODS
from automation.automation_config import AutomationSettings
from utils.config_manager import AutomationConfigManager


class App(ctk.CTk):
    def __init__(self, preset_manager, workflow_manager):
        super().__init__()
        self.preset_manager = preset_manager
        self.workflow_manager = workflow_manager
        self.i18n = I18N()
        self.automation_handler = automation_handler
        self.config_handler = config_handler
        self.dialog_handler = dialog_handler
        self.slot_handler = slot_handler
        self.ui_handler = ui_handler
        self.watcher_handler = watcher_handler
        self.console = None
        self.automation_config_manager = AutomationConfigManager(AutomationSettings, log_callback=self.log_to_console_safe)
        self.clip_watch_layer_name = "full-export-merge"
        self.automation_config_manager.load_settings()
        self.lang_var = ctk.StringVar(value="en")
        self.show_console_var = ctk.BooleanVar(value=False)
        self.debug_mode_var = ctk.BooleanVar(value=False)
        self.user_agreed = False
        self.updated_image_paths = set()
        self.is_first_apply = True
        self.texture_map = {}
        self.image_cache = {}
        show_agreement = self.config_handler.load_config(self)
        self.bind_all("<KeyPress-Alt_L>", lambda e: self.ui_handler.on_alt_press(self, e))
        self.bind_all("<KeyPress-Alt_R>", lambda e: self.ui_handler.on_alt_press(self, e))
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(4, weight=0)
        self.texture_slots = []
        self.is_automation_running = False
        self.stop_hotkey_id = None
        self.image_refresh_queue = Queue()
        self.automation_job_queue = Queue()
        self.automation_result_queue = Queue()
        self.file_watcher = FileWatcher(self.image_refresh_queue, self.log_to_console)
        self.process_watcher = ProcessWatcher(self.log_to_console)
        self.clip_watcher = ClipWatcher(self.log_to_console)
        self._create_widgets()
        self.watcher_handler.process_image_refresh_queue(self)
        self.ui_handler.retranslate_ui(self)
        self.automation_worker_thread = threading.Thread(target=lambda: self.automation_handler.automation_worker(self), daemon=True)
        self.automation_worker_thread.start()
        
        if show_agreement:
            self.dialog_handler.show_user_agreement(self)
    
    def _on_closing(self):
        if self.user_agreed:
            self.config_handler.save_config(self)
        self.automation_job_queue.put(None)
        self.file_watcher.stop()
        self.process_watcher.stop()
        self.clip_watcher.stop()
        self.destroy()
    
    def _create_widgets(self):
        self._create_menu()
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.manage_presets_button = ctk.CTkButton(top_frame, command=lambda: self.dialog_handler.open_preset_manager(self))
        self.manage_presets_button.pack(side="left", padx=5)
        self.watch_clip_button = ctk.CTkButton(top_frame, command=self.select_clip_file_to_watch)
        self.watch_clip_button.pack(side="right", padx=5)
        self.watch_process_button = ctk.CTkButton(top_frame, command=self.select_post_process_file)
        self.watch_process_button.pack(side="right", padx=5)
        self.import_button = ctk.CTkButton(top_frame, command=self.import_images)
        self.import_button.pack(side="right", padx=5)
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.grid(row=2, column=0, padx=10, pady=(0,10), sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        for i in range(5):
            slot = TextureSlotFrame(
                self.scrollable_frame, slot_id=i, slot_index=i, total_slots=5,
                reorder_callback=lambda idx, direction: self.slot_handler.move_slot(self, idx, direction),
                i18n=self.i18n,
                image_update_callback=lambda: self.watcher_handler.update_monitoring_list(self),
                image_change_callback=lambda path, image_obj, removed: self.slot_handler.on_slot_image_changed(self, path, image_obj, removed),
                mode_change_callback=lambda slot_id: self.slot_handler.on_slot_mode_changed(self, slot_id)
            )
            slot.pack(expand=True, fill="x", padx=5, pady=5)
            self.texture_slots.append(slot)
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)
        self.status_bar = StatusBar(bottom_frame, i18n=self.i18n)
        self.status_bar.grid(row=0, column=0, columnspan=2, padx=(10, 5), pady=5, sticky="ew")
        self.fast_apply_button = ctk.CTkButton(bottom_frame, command=lambda: self.run_automation_thread(full_run=False))
        self.fast_apply_button.grid(row=0, column=2, padx=5, pady=5)
        self.fast_apply_button.configure(state="disabled", fg_color="gray30")
        self.full_apply_button = ctk.CTkButton(bottom_frame, command=lambda: self.run_automation_thread(full_run=True))
        self.full_apply_button.grid(row=0, column=3, padx=5, pady=5)
        self.console_frame = ctk.CTkFrame(self)
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(1, weight=1)
        self.console_label = ctk.CTkLabel(self.console_frame, font=ctk.CTkFont(weight="bold"))
        self.console_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.console = ctk.CTkTextbox(self.console_frame, wrap="word", state="disabled")
        self.console.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
    
    def _create_menu(self):
        self.menu_bar = CustomMenuBar(self, i18n=self.i18n)
        self.menu_bar.grid(row=0, column=0, sticky="ew")
        lang_menu = self.menu_bar.add_cascade('menu_language')
        lang_menu.add_radiobutton(text="English", variable=self.lang_var, value='en', command=lambda: self.ui_handler.on_menu_action(self, lambda: self._switch_language('en')))
        lang_menu.add_radiobutton(text="日本語", variable=self.lang_var, value='ja', command=lambda: self.ui_handler.on_menu_action(self, lambda: self._switch_language('ja')))
        view_menu = self.menu_bar.add_cascade('menu_view')
        view_menu.add_checkbutton(text=self.i18n.t('menu_show_console'), text_key='menu_show_console',
                                  variable=self.show_console_var, command=lambda: self.ui_handler.on_menu_action(self, lambda: self.ui_handler.toggle_console(self)))
        automation_menu = self.menu_bar.add_cascade('menu_automation')
        automation_menu.add_command(text=self.i18n.t('menu_control_settings'), text_key='menu_control_settings',
                                  command=lambda: self.ui_handler.on_menu_action(self, lambda: self.dialog_handler.open_automation_settings(self)))
    
    def _switch_language(self, lang_code):
        self.lang_var.set(lang_code)
        self.i18n.set_language(lang_code)
        self.ui_handler.retranslate_ui(self)
    
    def log_to_console(self, message):
        self.console.configure(state="normal")
        self.console.insert("end", message + "\n")
        self.console.configure(state="disabled")
        self.console.see("end")
    
    def import_images(self):
        self.ui_handler.import_images(self)
    
    def log_to_console_safe(self, message):
        """
        A version of log_to_console that can be called before the UI is fully built.
        """
        
        if self.console:
            self.log_to_console(message)
        else:
            print(message)
    
    def select_clip_file_to_watch(self):
        self.watcher_handler.select_clip_file_to_watch(self)
    
    def select_post_process_file(self):
        self.watcher_handler.select_post_process_file(self)
    
    def run_automation_thread(self, full_run=False):
        self.automation_handler.run_automation_thread(self, full_run)
    
    def monitor_automation_thread(self):
        self.automation_handler.monitor_automation_thread(self)
    
    def emergency_stop(self):
        self.automation_handler.emergency_stop(self)
    
    def automation_finished(self, status=True):
        self.automation_handler.automation_finished(self, status)
