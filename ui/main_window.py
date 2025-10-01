import customtkinter as ctk
import tkinter
import threading
import keyboard
import os
import json
import screeninfo
from PIL import Image, ImageDraw
from queue import Queue
from ui.texture_slot import TextureSlotFrame
from ui.i18n import I18N
from ui.custom_menu import CustomMenuBar
from ui.dialogs import PresetManagerDialog, UserAgreementDialog, AutomationSettingsDialog, ClipWatchSettingsDialog
from utils.file_watcher import FileWatcher
from utils.file_watcher import normalize_path
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
        self.console = None
        self.automation_config_manager = AutomationConfigManager(AutomationSettings, log_callback=self.log_to_console_safe)
        self.clip_watch_layer_name = "full-export-merge"
        self.automation_config_manager.load_settings()
        self.lang_var = ctk.StringVar(value="en")
        self.show_console_var = ctk.BooleanVar(value=False)
        self.user_agreed = False
        self.updated_image_paths = set()
        self.is_first_apply = True
        self.texture_map = {}
        self.image_cache = {}
        self.status_bar_animation_id = None
        self.status_bar_animation_frames = []
        self.status_bar_animation_index = 0
        self.default_status_bar_color = None
        self.default_status_bar_text_color = None
        show_agreement = self._load_config()
        self.bind_all("<KeyPress-Alt_L>", self._on_alt_press)
        self.bind_all("<KeyPress-Alt_R>", self._on_alt_press)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(4, weight=0)
        self.texture_slots = []
        self.is_automation_running = False
        self.stop_hotkey_id = None
        self.image_refresh_queue = Queue()
        self.file_watcher = FileWatcher(self.image_refresh_queue, self.log_to_console)
        self.process_watcher = ProcessWatcher(self.log_to_console)
        self.clip_watcher = ClipWatcher(self.log_to_console)
        self._create_widgets()
        self._process_image_refresh_queue()
        self._retranslate_ui()
        
        if show_agreement:
            self.show_user_agreement()
    
    def _on_closing(self):
        if self.user_agreed:
            self._save_config()
        self.file_watcher.stop()
        self.process_watcher.stop()
        self.clip_watcher.stop()
        self.destroy()
    
    def _load_config(self):
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    geom = config.get("window_geometry")
                    
                    if geom and self._is_geometry_visible(geom):
                        self.geometry(geom)
                    else:
                        self._center_and_set_default_geometry()
                    lang = config.get("language", "en")
                    self.lang_var.set(lang)
                    self.i18n.set_language(lang)
                    self.clip_watch_layer_name = config.get("clip_watch_layer_name", "full-export-merge")
                    self.user_agreed = config.get("user_agreement", False)
                    return not self.user_agreed
        except (json.JSONDecodeError, FileNotFoundError): pass
        
        self._center_and_set_default_geometry()
        self.user_agreed = False
        return True
    
    def _center_and_set_default_geometry(self):
        width = 950
        height = 950
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
    
    def _save_config(self):
        config = {}
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    config = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
        
        try:
            config["window_geometry"] = self.geometry()
            config["language"] = self.lang_var.get()
            config["clip_watch_layer_name"] = self.clip_watch_layer_name
            config["user_agreement"] = self.user_agreed
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=4)
        except IOError:
            self.log_to_console("Error: Could not save configuration.")
    
    def _is_geometry_visible(self, geom):
        try:
            _, _, x, y = map(int, geom.replace('+', ' ').replace('x', ' ').split())
            return any(m.x <= x < m.x + m.width and m.y <= y < m.y + m.height for m in screeninfo.get_monitors())
        except Exception: return False
    
    def _create_widgets(self):
        self._create_menu()
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.manage_presets_button = ctk.CTkButton(top_frame, command=self.open_preset_manager)
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
            slot = TextureSlotFrame(self.scrollable_frame, slot_id=i, slot_index=i, total_slots=5,
                                    reorder_callback=self.move_slot,
                                    i18n=self.i18n,
                                    image_update_callback=self.update_monitoring_list,
                                    image_change_callback=self.on_slot_image_changed,
                                    mode_change_callback=self.on_slot_mode_changed)
            slot.pack(expand=True, fill="x", padx=5, pady=5)
            self.texture_slots.append(slot)
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)
        self.status_bar_container = ctk.CTkFrame(bottom_frame, corner_radius=6, height=30)
        self.status_bar_container.grid(row=0, column=0, columnspan=2, padx=(10, 5), pady=5, sticky="ew")
        self.status_bar_container.grid_propagate(False)
        self.status_bar_container.grid_rowconfigure(0, weight=1)
        self.status_bar_container.grid_columnconfigure(0, weight=1)
        self.status_bar_animation_label = ctk.CTkLabel(self.status_bar_container, text="")
        self.status_bar_text_label = ctk.CTkLabel(self.status_bar_container, text="", anchor="w", fg_color="transparent")
        self.status_bar_text_label.grid(row=0, column=0, sticky="w", padx=(10, 0))
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
        lang_menu.add_radiobutton(text="English", variable=self.lang_var, value='en', command=lambda: self._on_menu_action(lambda: self._switch_language('en')))
        lang_menu.add_radiobutton(text="日本語", variable=self.lang_var, value='ja', command=lambda: self._on_menu_action(lambda: self._switch_language('ja')))
        view_menu = self.menu_bar.add_cascade('menu_view')
        view_menu.add_checkbutton(text=self.i18n.t('menu_show_console'), text_key='menu_show_console',
                                  variable=self.show_console_var, command=lambda: self._on_menu_action(self._toggle_console))
        automation_menu = self.menu_bar.add_cascade('menu_automation')
        automation_menu.add_command(text=self.i18n.t('menu_control_settings'), text_key='menu_control_settings',
                                  command=lambda: self._on_menu_action(self.open_automation_settings))
    
    def _on_alt_press(self, event=None):
        """
        Handler for Alt key press to activate keyboard navigation for the menu.
        """
        self.menu_bar.activate_menu()
    
    def _toggle_console(self):
        if self.show_console_var.get():
            self.console_frame.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="nsew")
            self.grid_rowconfigure(4, weight=1)
        else:
            self.console_frame.grid_forget()
            self.grid_rowconfigure(4, weight=0)
    
    def _on_menu_action(self, action):
        """
        Helper to close the menu after a menu item's action is performed.
        """
        self.menu_bar._close_active_menu()
        action()
    
    def _switch_language(self, lang_code):
        self.lang_var.set(lang_code)
        self.i18n.set_language(lang_code)
        self._retranslate_ui()
    
    def _retranslate_ui(self):
        self.title(self.i18n.t('window_title'))
        self.menu_bar.retranslate()
        self.manage_presets_button.configure(text=self.i18n.t('manage_presets_button'))
        
        if not self.process_watcher.is_running:
            self.watch_process_button.configure(text=self.i18n.t('watch_map_button'))
        
        if not self.clip_watcher.is_running:
            self.watch_clip_button.configure(text=self.i18n.t('watch_clip_button'))
        self.import_button.configure(text=self.i18n.t('import_images_button'))
        self.scrollable_frame.configure(label_text=self.i18n.t('texture_slots_label'))
        self.console_label.configure(text=self.i18n.t('console_title'))
        self.fast_apply_button.configure(text=self.i18n.t('fast_apply_button') if not self.is_automation_running else self.i18n.t('apply_button_running'))
        self.full_apply_button.configure(text=self.i18n.t('full_apply_button'))
        
        for slot in self.texture_slots:
            slot.retranslate()
        
        if not self.is_automation_running:
            self._validate_slots_and_update_ui()
    
    def move_slot(self, index, direction):
        """
        Swaps the data of a slot with its neighbor.
        """
        new_index = index + direction
        
        if not (0 <= new_index < len(self.texture_slots)):
            return
        slot_a_data = self.texture_slots[index].get_data()
        slot_b_data = self.texture_slots[new_index].get_data()
        self.texture_slots[index].set_data(slot_b_data)
        self.texture_slots[new_index].set_data(slot_a_data)
        self.update_monitoring_list()
    
    def set_status(self, text_key, level='info', **kwargs):
        text = self.i18n.t(text_key, **kwargs)
        
        if self.status_bar_animation_id:
            self.after_cancel(self.status_bar_animation_id)
            self.status_bar_animation_id = None
        
        if self.default_status_bar_color is None:
            self.default_status_bar_color = self.status_bar_container.cget("fg_color")
        
        if self.default_status_bar_text_color is None:
            self.default_status_bar_text_color = self.status_bar_text_label.cget("text_color")
        
        if level == 'running':
            bg_color = "#E67E22"
            text_color = "white"
            
            if not self.status_bar_animation_frames:
                self._create_striped_frames()
            self.status_bar_container.configure(fg_color=bg_color)
            self.status_bar_text_label.configure(
                text=text,
                text_color=text_color,
                fg_color=bg_color,
                padx=15,
                corner_radius=6
            )
            self.status_bar_text_label.grid_configure(sticky="", padx=0)
            self.status_bar_animation_label.configure(image=self.status_bar_animation_frames[0])
            self.status_bar_animation_label.grid(row=0, column=0, sticky="nsew")
            self.status_bar_text_label.lift()
            self.status_bar_animation_index = 0
            self._animate_status_bar()
        else:
            self.status_bar_animation_label.grid_forget()
            color_map = {
                'info': self.default_status_bar_color,
                'warning': "#F39C12",
                'error': "#E74C3C",
                'success': "#2ECC71",
            }
            bg_color = color_map.get(level, self.default_status_bar_color)
            text_color = "black" if level == 'warning' else self.default_status_bar_text_color
            self.status_bar_container.configure(fg_color=bg_color)
            self.status_bar_text_label.configure(
                text=text,
                text_color=text_color,
                fg_color="transparent",
                padx=0,
                corner_radius=0
            )
            self.status_bar_text_label.grid_configure(sticky="w", padx=(10, 0))
    
    def _create_striped_frames(self):
        if self.status_bar_animation_frames:
            return
        width, height = 2000, 30
        stripe_width, gap = 15, 15
        num_frames = 8
        orange_light, orange_dark = "#E67E22", "#D35400"
        
        for i in range(num_frames):
            img = Image.new('RGB', (width, height), orange_light)
            draw = ImageDraw.Draw(img)
            offset = i * ((stripe_width + gap) / num_frames)
            
            for x_start in range(-2 * (stripe_width + gap), width + height, stripe_width + gap):
                p1, p2 = (x_start - offset, height), (x_start - offset + stripe_width, height)
                p3, p4 = (x_start - offset + stripe_width + height, 0), (x_start - offset + height, 0)
                draw.polygon([p1, p2, p3, p4], fill=orange_dark)
            ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))
            self.status_bar_animation_frames.append(ctk_image)
    
    def _animate_status_bar(self):
        self.status_bar_animation_index = (self.status_bar_animation_index + 1) % len(self.status_bar_animation_frames)
        self.status_bar_animation_label.configure(image=self.status_bar_animation_frames[self.status_bar_animation_index])
        self.status_bar_animation_id = self.after(50, self._animate_status_bar)
    
    def _validate_slots_and_update_ui(self):
        if self.is_automation_running:
            return
        
        for slot in self.texture_slots:
            if slot.get_mode_key() == 'Managed' and not slot.image_path:
                self.set_status('status_warn_no_image_managed', level='warning', slot_id=slot.slot_id + 1)
                self.fast_apply_button.configure(state="disabled")
                self.full_apply_button.configure(state="disabled")
                return
        self.set_status('status_ready')
        fast_apply_state = "normal" if not self.is_first_apply else "disabled"
        
        if fast_apply_state == "disabled":
            self.fast_apply_button.configure(fg_color="gray30")
        elif self.full_apply_button:
            self.fast_apply_button.configure(fg_color=self.full_apply_button.cget("fg_color"))
        self.fast_apply_button.configure(state=fast_apply_state)
        self.full_apply_button.configure(state="normal")
    
    def log_to_console(self, message):
        self.console.configure(state="normal")
        self.console.insert("end", message + "\n")
        self.console.configure(state="disabled")
        self.console.see("end")
    
    def on_slot_image_changed(self, image_path, image_obj=None, removed=False):
        """
        Handles caching and marking images as updated.
        Returns True if the image content is new or different, False otherwise.
        """
        
        if not image_path: return False
        norm_path = normalize_path(image_path)
        
        if removed:
            self.updated_image_paths.discard(norm_path)
            
            if norm_path in self.image_cache:
                del self.image_cache[norm_path]
            self.log_to_console(f"'{os.path.basename(image_path)}' unmarked as updated.")
            return False
        else:
            if image_obj is None:
                self.updated_image_paths.add(norm_path)
                self.log_to_console(f"'{os.path.basename(image_path)}' marked as updated for next apply (no image data for comparison).")
                return True
            old_img = self.image_cache.get(norm_path)
            content_is_different = not old_img or old_img.tobytes() != image_obj.tobytes()
            
            if content_is_different:
                self.log_to_console(f"Content changed for: {os.path.basename(image_path)}. Marking for update.")
                self.image_cache[norm_path] = image_obj
                self.updated_image_paths.add(norm_path)
                return True
            else:
                self.log_to_console(f"Content is identical for: {os.path.basename(image_path)}. Skipping update mark.")
                
                if norm_path not in self.image_cache:
                    self.image_cache[norm_path] = image_obj
                return False
    
    def on_slot_mode_changed(self, slot_id):
        slot = self.texture_slots[slot_id]
        
        if slot.get_mode_key() == 'Managed' and slot.image_path:
             self.on_slot_image_changed(slot.image_path, image_obj=None, removed=False)
             self.log_to_console(f"Slot {slot_id+1} switched to Managed. Marked for update.")
        self._validate_slots_and_update_ui()
    
    def show_user_agreement(self):
        """
        Creates and displays the modal user agreement dialog.
        """
        dialog = UserAgreementDialog(self, i18n=self.i18n, callback=self.on_agreement_accepted)
        self.wait_window(dialog)
    
    def on_agreement_accepted(self):
        """
        Callback for when the user accepts the agreement.
        """
        self.log_to_console("User agreement accepted.")
        self.user_agreed = True
        self._save_config()
    
    def open_preset_manager(self):
        dialog = PresetManagerDialog(self, app=self)
        self.wait_window(dialog)
    
    def open_automation_settings(self):
        dialog = AutomationSettingsDialog(self, i18n=self.i18n, config_manager=self.automation_config_manager)
        self.wait_window(dialog)
    
    def import_images(self):
        paths = tkinter.filedialog.askopenfilenames(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        
        if paths:
            for i, path in enumerate(paths[:len(self.texture_slots)]):
                slot = self.texture_slots[i]
                slot.set_image(path)
                slot.mode_var.set(self.i18n.t('slot_mode_managed'))
                slot._on_mode_changed(None)
            self.update_monitoring_list()
    
    def log_to_console_safe(self, message):
        """
        A version of log_to_console that can be called before the UI is fully built.
        """
        
        if self.console:
            self.log_to_console(message)
        else:
            print(message)
    
    def select_clip_file_to_watch(self):
        """
        Opens a file dialog to select a .clip file and settings for watching.
        """
        
        if self.clip_watcher.is_running:
            self.clip_watcher.stop()
            self.watch_clip_button.configure(text=self.i18n.t('watch_clip_button'))
            self.set_status('status_stopped_watching_clip')
        else:
            path = tkinter.filedialog.askopenfilename(
                title="Select .clip file to watch",
                filetypes=[("Clip Studio Paint File", "*.clip")]
            )
            
            if not path:
                return
            dialog = ClipWatchSettingsDialog(self, i18n=self.i18n, algorithms=list(DOWNSCALING_METHODS.keys()))
            self.wait_window(dialog)
            
            if dialog.result:
                settings = dialog.result
                self.clip_watcher.start(
                    path,
                    self.clip_watch_layer_name,
                    settings['scale_factor'],
                    settings['algorithm']
                )
                self.watch_clip_button.configure(text=self.i18n.t('stop_watching_clip_button', filename=os.path.basename(path)))
                self.set_status('status_watching_clip', layer_name=self.clip_watch_layer_name)
    
    def select_post_process_file(self):
        """
        Opens a file dialog to select the single file to watch for tile splitting.
        """
        
        if self.process_watcher.is_running:
            self.process_watcher.stop()
            self.watch_process_button.configure(text=self.i18n.t('watch_map_button'))
            self.set_status('status_stopped_watching')
        else:
            path = tkinter.filedialog.askopenfilename(title="Select file to watch for tile splitting",
                                              filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
            
            if path:
                self.process_watcher.start(path)
                self.watch_process_button.configure(text=self.i18n.t('stop_watching_map_button', filename=os.path.basename(path)))
                self.set_status('status_watching')
    
    def update_monitoring_list(self):
        paths_to_watch = [slot.image_path for slot in self.texture_slots if slot.image_path]
        
        if paths_to_watch:
            self.file_watcher.start(paths_to_watch)
        else:
            self.file_watcher.stop()
        self._validate_slots_and_update_ui()
    
    def _process_image_refresh_queue(self):
        while not self.image_refresh_queue.empty():
            image_path = self.image_refresh_queue.get()
            norm_path = normalize_path(image_path)
            try:
                new_img = Image.open(image_path)
                new_img.load()
            except Exception as e:
                self.log_to_console(f"Error loading changed file {os.path.basename(image_path)}: {e}")
                continue
            
            content_was_updated = self.on_slot_image_changed(image_path, image_obj=new_img, removed=False)
            
            if content_was_updated:
                for slot in self.texture_slots:
                    if slot.image_path and normalize_path(slot.image_path) == norm_path:
                        slot.refresh_preview(new_img)
        self.after(500, self._process_image_refresh_queue)
    
    def run_automation_thread(self, full_run=False):
        self.log_to_console("Finding application window anchor...")
        self.workflow_manager.set_language(self.i18n.language)
        monitor = self.workflow_manager.find_app_window_and_set_region()
        
        if not monitor:
            self.set_status('status_error_anchor', level='error')
            return
        self.set_status('status_found_anchor', level='info', monitor_name=monitor.name)
        self.log_to_console("App window located successfully.")
        slots_data = []
        has_updatable_action = False
        
        for slot in self.texture_slots:
            slot_data = slot.get_data()
            is_new_to_group = (
                slot_data['group'] and
                slot_data['slot_id'] not in self.texture_map.get(slot_data['group'], [])
            )
            is_updated = (
                self.is_first_apply or full_run or
                (normalize_path(slot.image_path) in self.updated_image_paths) or
                (slot_data['mode'] == 'Managed' and is_new_to_group)
            )
            slot_data['is_updated'] = is_updated
            
            if slot_data['mode'] == 'Managed' and is_updated:
                has_updatable_action = True
            
            if slot_data['mode'] == 'Managed':
                if not slot_data['image_path']:
                    self.set_status('status_warn_no_image', level='warning', slot_id=slot_data['slot_id']+1)
                    return
                
                if not slot_data['group']:
                    self.set_status('status_warn_no_group', level='warning', slot_id=slot_data['slot_id']+1)
                    self.log_to_console(f"Aborting: Slot {slot_data['slot_id']+1} is Managed but has no group name.")
                    return
                
                if not slot.is_512x512:
                     self.set_status('status_warn_not_512', level='warning', slot_id=slot_data['slot_id']+1)
                     return
            slots_data.append(slot_data)
        
        if not full_run and not has_updatable_action:
            self.set_status('status_no_updates')
            self.log_to_console(self.i18n.t('status_no_updates'))
            return
        self.is_automation_running = True
        self.fast_apply_button.configure(state="disabled", text=self.i18n.t('apply_button_running'))
        self.full_apply_button.configure(state="disabled")
        self.set_status('status_running', level='running')
        self.stop_hotkey_id = keyboard.add_hotkey('esc', self.emergency_stop)
        is_full_run = self.is_first_apply or full_run
        result_container = [None]
        thread = threading.Thread(target=lambda: result_container.__setitem__(0, self.workflow_manager.run(slots_data, self.texture_map, is_full_run, self.log_to_console)), daemon=True)
        thread.start()
        self.monitor_automation_thread(thread, result_container)
    
    def monitor_automation_thread(self, thread, result_container):
        if thread.is_alive():
            self.after(100, lambda: self.monitor_automation_thread(thread, result_container))
        else:
            result_tuple = result_container[0]
            status = result_tuple[0] if result_tuple else False
            
            if status is True:
                self.is_first_apply = False
                self.updated_image_paths.clear()
                self.texture_map = result_tuple[1]
            self.automation_finished(status=status)
    
    def emergency_stop(self):
        if self.is_automation_running:
            self.log_to_console("EMERGENCY STOP received.")
            self.workflow_manager.request_stop()
    
    def automation_finished(self, status=True):
        self.is_automation_running = False
        fast_apply_state = "normal" if not self.is_first_apply else "disabled"
        
        if fast_apply_state == "disabled":
            self.fast_apply_button.configure(fg_color="gray30")
        else:
            self.fast_apply_button.configure(fg_color=self.full_apply_button.cget("fg_color"))
        self.fast_apply_button.configure(state=fast_apply_state, text=self.i18n.t('fast_apply_button'))
        self.full_apply_button.configure(state="normal")
        
        if status is True:
            self.set_status('status_finished', level='success')
        elif status == 'FAST_APPLY_FAILED':
            self.set_status('status_fast_apply_failed', level='error')
        else:
            self.set_status('status_halted', level='error')
        
        if self.stop_hotkey_id:
            try: keyboard.remove_hotkey(self.stop_hotkey_id)
            except KeyError: pass
            
            self.stop_hotkey_id = None
