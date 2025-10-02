import customtkinter as ctk
from PIL import Image, ImageDraw


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, i18n, **kwargs):
        super().__init__(master, corner_radius=6, height=30, **kwargs)
        self.i18n = i18n
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.animation_id = None
        self.animation_frames = []
        self.animation_index = 0
        self.default_bg_color = self.cget("fg_color")
        self.animation_label = ctk.CTkLabel(self, text="")
        self.text_label = ctk.CTkLabel(self, text="", anchor="w", fg_color="transparent")
        self.text_label.grid(row=0, column=0, sticky="w", padx=(10, 0))
        self.default_text_color = self.text_label.cget("text_color")
    
    def set_status(self, text_key, level='info', **kwargs):
        text = self.i18n.t(text_key, **kwargs)
        
        if self.animation_id:
            self.after_cancel(self.animation_id)
            self.animation_id = None
        
        if level == 'running':
            bg_color, text_color = "#E67E22", "white"
            
            if not self.animation_frames: self._create_striped_frames()
            self.configure(fg_color=bg_color)
            self.text_label.configure(text=text, text_color=text_color, fg_color=bg_color, padx=15, corner_radius=6)
            self.text_label.grid_configure(sticky="", padx=0)
            self.animation_label.configure(image=self.animation_frames[0])
            self.animation_label.grid(row=0, column=0, sticky="nsew")
            self.text_label.lift()
            self.animation_index = 0
            self._animate()
        else:
            self.animation_label.grid_forget()
            color_map = {
                'info': self.default_bg_color,
                'warning': "#F39C12",
                'error': "#E74C3C",
                'success': "#2ECC71",
            }
            bg_color = color_map.get(level, self.default_bg_color)
            text_color = "black" if level == 'warning' else self.default_text_color
            self.configure(fg_color=bg_color)
            self.text_label.configure(text=text, text_color=text_color, fg_color="transparent", padx=0, corner_radius=0)
            self.text_label.grid_configure(sticky="w", padx=(10, 0))
    
    def _create_striped_frames(self):
        if self.animation_frames: return
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
            self.animation_frames.append(ctk_image)
    
    def _animate(self):
        self.animation_index = (self.animation_index + 1) % len(self.animation_frames)
        self.animation_label.configure(image=self.animation_frames[self.animation_index])
        self.animation_id = self.after(50, self._animate)
