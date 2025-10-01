import customtkinter as ctk


class CustomDropdownMenu(ctk.CTkFrame):
    """
    The dropdown box that appears when a menu button is clicked.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=6, border_width=1, border_color="gray40", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._items = []
        self._row = 0
    
    def add_item(self, widget_class, **kwargs):
        """
        Generic method to add a widget to the dropdown.
        """
        item_kwargs = {
            "corner_radius": 0,
            "hover_color": "gray25"
        }
        text_key = kwargs.pop('text_key', None)
        item_kwargs.update(kwargs)
        item = widget_class(self, **item_kwargs)
        
        if text_key:
            item.text_key = text_key
        item.grid(row=self._row, column=0, sticky="ew", padx=10, pady=5)
        self._items.append(item)
        self._row += 1
        return item
    
    def add_radiobutton(self, **kwargs):
        return self.add_item(ctk.CTkRadioButton, **kwargs)
    
    def add_checkbutton(self, **kwargs):
        return self.add_item(ctk.CTkCheckBox, **kwargs)
    
    def add_command(self, **kwargs):
        return self.add_item(ctk.CTkButton, **kwargs)
    
    def retranslate(self, i18n):
        for item in self._items:
            if hasattr(item, 'text_key'):
                item.configure(text=i18n.t(item.text_key))


class CustomMenuBar(ctk.CTkFrame):
    """
    The main menu bar container that holds the menu buttons.
    """
    def __init__(self, master, i18n, **kwargs):
        super().__init__(master, corner_radius=0, **kwargs)
        self.i18n = i18n
        self.grid_columnconfigure(10, weight=1)
        self._menu_buttons = []
        self._dropdowns = {}
        self._active_dropdown = None
        self._col = 0
        self.winfo_toplevel().bind("<Button-1>", self._on_click_outside, add="+")
        self.winfo_toplevel().bind("<Escape>", self._on_escape, add="+")
    
    def add_cascade(self, label_key):
        """
        Adds a top-level menu button (like 'File', 'View') to the bar.
        """
        button = ctk.CTkButton(
            self,
            text=self.i18n.t(label_key),
            corner_radius=0,
            fg_color="transparent",
            hover_color="gray25"
        )
        button.label_key = label_key
        button.grid(row=0, column=self._col, sticky="w")
        dropdown = CustomDropdownMenu(self.winfo_toplevel())
        button.configure(command=lambda b=button: self._toggle_menu(b))
        self._menu_buttons.append(button)
        self._dropdowns[button] = dropdown
        self._col += 1
        return dropdown
    
    def _toggle_menu(self, button):
        dropdown = self._dropdowns[button]
        
        if self._active_dropdown == dropdown:
            self._close_active_menu()
        else:
            self._close_active_menu()
            self._open_menu(button, dropdown)
    
    def _open_menu(self, button, dropdown):
        self._active_dropdown = dropdown
        place_x = self.winfo_x() + button.winfo_x()
        place_y = self.winfo_y() + self.winfo_height()
        dropdown.place(x=place_x, y=place_y)
        dropdown.lift()
    
    def _close_active_menu(self):
        if self._active_dropdown:
            self._active_dropdown.place_forget()
            self._active_dropdown = None
    
    def _on_click_outside(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        
        if widget:
            while widget:
                if widget in self._menu_buttons or isinstance(widget, CustomDropdownMenu):
                    return
                widget = widget.master
        self._close_active_menu()
    
    def _on_escape(self, event):
        self._close_active_menu()
        self.winfo_toplevel().focus_set()
        return "break"
    
    def retranslate(self):
        for button in self._menu_buttons:
            if hasattr(button, "label_key"):
                button.configure(text=self.i18n.t(button.label_key))
        
        for dropdown in self._dropdowns.values():
            dropdown.retranslate(self.i18n)
    
    def activate_menu(self):
        """
        Gives focus to the first menu item for keyboard navigation.
        """
        
        if self._menu_buttons:
            self._menu_buttons[0].focus_set()
            
            for button in self._menu_buttons:
                button.bind("<Left>", lambda e, b=button: self._nav(e, b, -1))
                button.bind("<Right>", lambda e, b=button: self._nav(e, b, 1))
    
    def _nav(self, event, current_button, direction):
        try:
            current_index = self._menu_buttons.index(current_button)
            next_index = (current_index + direction) % len(self._menu_buttons)
            self._menu_buttons[next_index].focus_set()
        except (ValueError, IndexError):
            pass
        
        return "break"
