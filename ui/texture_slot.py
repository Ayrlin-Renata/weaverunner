import customtkinter as ctk
from tkinter import filedialog
from PIL import Image
import os


class TextureSlotFrame(ctk.CTkFrame):
    def __init__(self, master, slot_id, slot_index, total_slots, reorder_callback, i18n, image_update_callback=None, image_change_callback=None, mode_change_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.slot_id = slot_id
        self.slot_index = slot_index
        self.total_slots = total_slots
        self.reorder_callback = reorder_callback
        self.i18n = i18n
        self.image_update_callback = image_update_callback
        self.image_change_callback = image_change_callback
        self.mode_change_callback = mode_change_callback
        self.image_path = None
        self.is_512x512 = True
        self.ctk_image_preview = None
        self.alternate_groups = []
        self.pil_image_preview = None
        self.placeholder_pil_image = Image.new('RGBA', (1, 1), (0,0,0,0))
        self.placeholder_ctk_image = ctk.CTkImage(light_image=self.placeholder_pil_image, size=(128, 128))
        self.default_mode_colors = {}
        self.default_border_color = None
        self.grid_columnconfigure(3, weight=1)
        self._create_widgets()
    
    def _create_widgets(self):
        reorder_frame = ctk.CTkFrame(self, fg_color="transparent")
        reorder_frame.grid(row=0, column=0, rowspan=2, padx=5, sticky="ns")
        reorder_frame.grid_rowconfigure(0, weight=1)
        reorder_frame.grid_rowconfigure(3, weight=1)
        self.up_button = ctk.CTkButton(reorder_frame, text="▲", fg_color="gray20", width=25, command=lambda: self.reorder_callback(self.slot_index, -1))
        self.up_button.grid(row=0, column=0, pady=(0, 2))
        
        if self.slot_index == 0:
            self.up_button.configure(state="disabled")
        self.down_button = ctk.CTkButton(reorder_frame, text="▼", fg_color="gray20", width=25, command=lambda: self.reorder_callback(self.slot_index, 1))
        self.down_button.grid(row=1, column=0)
        
        if self.slot_index == self.total_slots - 1:
            self.down_button.configure(state="disabled")
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=0, column=1, rowspan=2, padx=5, pady=5, sticky="ns")
        self.mode_label = ctk.CTkLabel(left_frame, text=self.i18n.t('slot_mode'))
        self.mode_label.pack(anchor="w")
        self.mode_var = ctk.StringVar(value=self.i18n.t('slot_mode_ignored'))
        self.mode_menu = ctk.CTkOptionMenu(left_frame, variable=self.mode_var, values=[self.i18n.t('slot_mode_managed'), self.i18n.t('slot_mode_ignored')], command=self._on_mode_changed)
        self.mode_menu.pack(anchor="w", pady=(0, 10))
        self.default_mode_colors['fg_color'] = self.mode_menu.cget("fg_color")
        self.default_mode_colors['dropdown_fg_color'] = self.mode_menu.cget("dropdown_fg_color")
        self.group_label = ctk.CTkLabel(left_frame, text=self.i18n.t('slot_group'))
        self.group_label.pack(anchor="w")
        self.group_entry = ctk.CTkEntry(left_frame, placeholder_text=self.i18n.t('slot_group_placeholder'))
        self.group_entry.bind("<KeyRelease>", lambda e: self._update_visual_state())
        self.group_entry.pack(anchor="w")
        self.default_border_color = self.group_entry.cget("border_color")
        self.image_frame = ctk.CTkFrame(self, fg_color="gray20", width=128, height=128)
        self.image_frame.grid(row=0, column=3, padx=10, pady=5, sticky="nsew")
        self.image_frame.grid_propagate(False)
        self.image_frame.grid_rowconfigure(0, weight=1)
        self.image_frame.grid_columnconfigure(0, weight=1)
        self.image_label = ctk.CTkLabel(self.image_frame, text=self.i18n.t('slot_image_placeholder'), text_color="gray60")
        self.image_label.grid(row=0, column=0, sticky="nsew")
        self.image_label.bind("<Button-1>", lambda e: self.select_image())
        filename_frame = ctk.CTkFrame(self, fg_color="transparent")
        filename_frame.grid(row=1, column=3, pady=(0, 5), padx=10, sticky="ew")
        filename_frame.grid_columnconfigure(0, weight=1)
        self.image_filename_label = ctk.CTkLabel(filename_frame, text=self.i18n.t('slot_no_file'), text_color="gray50", wraplength=150, anchor="w")
        self.image_filename_label.grid(row=0, column=0, sticky="ew")
        self.clear_image_button = ctk.CTkButton(filename_frame, text="✖", width=20, command=self.clear_image, fg_color="transparent", hover_color="gray25")
        self.warning_label = ctk.CTkLabel(self, text="⚠️", text_color="orange", font=("Segoe UI Emoji", 16))
        params_frame = ctk.CTkFrame(self, fg_color="transparent")
        params_frame.grid(row=0, column=4, rowspan=2, padx=5, pady=5, sticky="ns")
        self.params = {}
        param_list = {
            "slot_size": (0.0, 1.0, 1.0),
            "slot_angle": (0.0, 1.0, 0.0),
            "slot_x_pos": (0.0, 1.0, 0.5),
            "slot_y_pos": (0.0, 1.0, 0.5),
            "slot_opacity": (0.0, 1.0, 1.0)
        }
        
        for i, (key, (p_min, p_max, p_default)) in enumerate(param_list.items()):
            label = ctk.CTkLabel(params_frame, text=self.i18n.t(key), width=80, anchor="w")
            label.grid(row=i, column=0, padx=5, pady=2)
            slider = ctk.CTkSlider(params_frame, from_=p_min, to=p_max)
            slider.set(p_default)
            slider.grid(row=i, column=1, padx=5, pady=2)
            entry = ctk.CTkEntry(params_frame, width=70)
            entry.insert(0, f"{p_default:.4f}")
            entry.grid(row=i, column=2, padx=5, pady=2)
            internal_key = key.replace("slot_", "")
            
            if internal_key == "x_pos": internal_key = "x_position"
            
            if internal_key == "y_pos": internal_key = "y_position"
            self.params[internal_key] = {"slider": slider, "entry": entry, "label": label, "i18n_key": key}
            slider.configure(command=lambda value, k=internal_key: self.update_entry_from_slider(k, value))
            entry.bind("<Return>", lambda event, k=internal_key: self.update_slider_from_entry(k))
        toggles_frame = ctk.CTkFrame(params_frame, fg_color="transparent")
        toggles_frame.grid(row=len(param_list), column=0, columnspan=3, pady=5)
        self.h_flip_var = ctk.BooleanVar(value=False); self.v_flip_var = ctk.BooleanVar(value=False)
        self.h_repeat_var = ctk.BooleanVar(value=False); self.v_repeat_var = ctk.BooleanVar(value=False)
        self.h_flip_check = ctk.CTkCheckBox(toggles_frame, text=self.i18n.t('slot_h_flip'), variable=self.h_flip_var)
        self.h_flip_check.pack(side="left", padx=5)
        self.v_flip_check = ctk.CTkCheckBox(toggles_frame, text=self.i18n.t('slot_v_flip'), variable=self.v_flip_var)
        self.v_flip_check.pack(side="left", padx=5)
        self.h_repeat_check = ctk.CTkCheckBox(toggles_frame, text=self.i18n.t('slot_h_repeat'), variable=self.h_repeat_var)
        self.h_repeat_check.pack(side="left", padx=5)
        self.v_repeat_check = ctk.CTkCheckBox(toggles_frame, text=self.i18n.t('slot_v_repeat'), variable=self.v_repeat_var)
        self.v_repeat_check.pack(side="left", padx=5)
        self._update_visual_state()
    
    def retranslate(self):
        current_translated_mode = self.mode_var.get()
        reverse_mode_map = {}
        
        for lang_data in self.i18n.languages.values():
            reverse_mode_map[lang_data['slot_mode_managed']] = 'Managed'
            reverse_mode_map[lang_data['slot_mode_ignored']] = 'Ignored'
        current_mode_key = reverse_mode_map.get(current_translated_mode, 'Ignored')
        self.mode_label.configure(text=self.i18n.t('slot_mode'))
        self.group_label.configure(text=self.i18n.t('slot_group'))
        self.group_entry.configure(placeholder_text=self.i18n.t('slot_group_placeholder'))
        
        if not self.image_path:
            self.image_label.configure(text=self.i18n.t('slot_image_placeholder'))
            self.image_filename_label.configure(text=self.i18n.t('slot_no_file'))
        
        for internal_key, data in self.params.items():
            data["label"].configure(text=self.i18n.t(data["i18n_key"]))
        self.h_flip_check.configure(text=self.i18n.t('slot_h_flip'))
        self.v_flip_check.configure(text=self.i18n.t('slot_v_flip'))
        self.h_repeat_check.configure(text=self.i18n.t('slot_h_repeat'))
        self.v_repeat_check.configure(text=self.i18n.t('slot_v_repeat'))
        translated_values = [self.i18n.t('slot_mode_managed'), self.i18n.t('slot_mode_ignored')]
        self.mode_menu.configure(values=translated_values)
        mode_map = {'Managed': self.i18n.t('slot_mode_managed'), 'Ignored': self.i18n.t('slot_mode_ignored')}
        self.mode_var.set(mode_map.get(current_mode_key, self.i18n.t('slot_mode_ignored')))
        self._update_visual_state()
    
    def select_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        
        if path:
            self.set_image(path)
            self.mode_var.set(self.i18n.t('slot_mode_managed'))
            self._on_mode_changed(None)
            
            if self.image_update_callback:
                self.image_update_callback()
    
    def clear_image(self):
        old_path = self.image_path
        self.image_path = None
        self.image_label.configure(image=self.placeholder_ctk_image, text=self.i18n.t('slot_image_placeholder'))
        self.ctk_image_preview = None
        self.pil_image_preview = None
        self.clear_image_button.grid_forget()
        self.hide_warning()
        self.is_512x512 = True
        self._update_visual_state()
        
        if self.image_change_callback:
            self.image_change_callback(old_path, image_obj=None, removed=True)
        
        if self.image_update_callback: self.image_update_callback()
    
    def set_image(self, path):
        """
        Called when a user selects a new image file for the slot.
        """
        self.image_path = path
        self.clear_image_button.grid(row=0, column=1, sticky="e")
        self._update_visual_state()
        try:
            img = Image.open(path)
            img.load()
            
            if self.image_change_callback:
                self.image_change_callback(path, image_obj=img, removed=False)
            self.refresh_preview(img)
        except Exception as e:
            self.image_label.configure(image=self.placeholder_ctk_image, text=f"Error:\n{e}")
            self.show_warning(self.i18n.t('slot_warn_load_fail'))
            self.is_512x512 = False
    
    def refresh_preview(self, image_obj):
        """
        Updates the image preview from a pre-loaded PIL Image object.
        """
        
        if image_obj.size != (512, 512):
            self.show_warning(self.i18n.t('slot_warn_not_512'))
            self.is_512x512 = False
        else:
            self.hide_warning()
            self.is_512x512 = True
        self.pil_image_preview = image_obj
        self.ctk_image_preview = ctk.CTkImage(light_image=image_obj, dark_image=image_obj, size=(128, 128))
        self.image_label.configure(image=self.ctk_image_preview, text="")
    
    def show_warning(self, message):
        self.warning_label.grid(row=0, column=3, sticky="ne", padx=15, pady=5)
        self.warning_label.configure(text=f"⚠️ {message}")
    
    def hide_warning(self):
        self.warning_label.grid_remove()
    
    def update_entry_from_slider(self, internal_key, value):
        entry = self.params[internal_key]['entry']
        entry.delete(0, 'end')
        entry.insert(0, f"{value:.4f}")
    
    def update_slider_from_entry(self, internal_key):
        slider = self.params[internal_key]['slider']
        try: slider.set(float(self.params[internal_key]['entry'].get()))
        except (ValueError, TypeError): pass
    
    def _on_mode_changed(self, choice):
        self._update_visual_state()
        
        if self.mode_change_callback:
            self.mode_change_callback(self.slot_id)
    
    def _update_visual_state(self):
        """
        Updates the visual state of the slot based on its mode and whether it has an image.
        """
        is_managed = self.get_mode_key() == 'Managed'
        has_image = bool(self.image_path)
        has_group = bool(self.group_entry.get().strip())
        
        if is_managed:
            self.mode_menu.configure(fg_color=self.default_mode_colors['fg_color'], dropdown_fg_color=self.default_mode_colors['dropdown_fg_color'])
        else:
            self.mode_menu.configure(fg_color="gray30", dropdown_fg_color="gray30")
        
        if is_managed and not has_image:
            self.image_filename_label.configure(text=self.i18n.t('slot_no_file'), fg_color="#F39C12", text_color="black", corner_radius=4, padx=5)
        else:
            text = os.path.basename(self.image_path) if has_image else self.i18n.t('slot_no_file')
            default_text_color = self.group_label.cget("text_color")
            self.image_filename_label.configure(text=text, fg_color="transparent", text_color=default_text_color, corner_radius=0, padx=0)
        
        if is_managed and not has_group:
            self.group_entry.configure(border_color="#F39C12")
        else:
            self.group_entry.configure(border_color=self.default_border_color)
    
    def get_mode_key(self):
        """
        Gets the language-independent key for the current mode.
        """
        reverse_mode_map = {self.i18n.t('slot_mode_managed'): 'Managed', self.i18n.t('slot_mode_ignored'): 'Ignored'}
        return reverse_mode_map.get(self.mode_var.get(), 'Ignored')
    
    def get_data(self, for_preset=False):
        data = {
            "slot_id": self.slot_id, "mode": self.get_mode_key(),
            "group": self.group_entry.get(),
            "values": {
                "size": self.params["size"]["slider"].get(), "angle": self.params["angle"]["slider"].get(),
                "x_position": self.params["x_position"]["slider"].get(),
                "y_position": self.params["y_position"]["slider"].get(),
                "opacity": self.params["opacity"]["slider"].get(), "h_flip": self.h_flip_var.get(),
                "v_flip": self.v_flip_var.get(), "h_repeat": self.h_repeat_var.get(), "v_repeat": self.v_repeat_var.get(),
            }
        }
        
        if self.alternate_groups:
            data['alternate_groups'] = self.alternate_groups
        
        if not for_preset:
            data['image_path'] = self.image_path
        return data
    
    def set_data(self, data, from_preset=False):
        mode_map = {'Managed': self.i18n.t('slot_mode_managed'), 'Ignored': self.i18n.t('slot_mode_ignored')}
        self.mode_var.set(mode_map.get(data.get("mode", "Ignored"), self.i18n.t('slot_mode_ignored')))
        self.group_entry.delete(0, 'end')
        self.group_entry.insert(0, data.get("group", ""))
        self.alternate_groups = data.get('alternate_groups', [])
        self._update_visual_state()
        
        if from_preset:
            pass
        else:
            new_image_path = data.get("image_path")
            
            if new_image_path:
                self.set_image(new_image_path)
            else:
                self.clear_image()
        values = data.get("values", {})
        
        for name, val_dict in self.params.items():
            value = values.get(name, val_dict["slider"].cget("from_"))
            val_dict["slider"].set(value)
            self.update_entry_from_slider(name, value)
        self.h_flip_var.set(values.get("h_flip", False))
        self.v_flip_var.set(values.get("v_flip", False))
        self.h_repeat_var.set(values.get("h_repeat", False))
        self.v_repeat_var.set(values.get("v_repeat", False))
