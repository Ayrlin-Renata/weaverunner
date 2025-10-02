import tkinter


def retranslate_ui(app):
    app.title(app.i18n.t('window_title'))
    app.menu_bar.retranslate()
    app.manage_presets_button.configure(text=app.i18n.t('manage_presets_button'))
    
    if not app.process_watcher.is_running:
        app.watch_process_button.configure(text=app.i18n.t('watch_map_button'))
    
    if not app.clip_watcher.is_running:
        app.watch_clip_button.configure(text=app.i18n.t('watch_clip_button'))
    app.import_button.configure(text=app.i18n.t('import_images_button'))
    app.scrollable_frame.configure(label_text=app.i18n.t('texture_slots_label'))
    app.console_label.configure(text=app.i18n.t('console_title'))
    app.fast_apply_button.configure(text=app.i18n.t('fast_apply_button') if not app.is_automation_running else app.i18n.t('apply_button_running'))
    app.full_apply_button.configure(text=app.i18n.t('full_apply_button'))
    
    for slot in app.texture_slots:
        slot.retranslate()
    
    if not app.is_automation_running:
        validate_slots_and_update_ui(app)


def on_alt_press(app, event=None):
    app.menu_bar.activate_menu()


def toggle_console(app):
    if app.show_console_var.get():
        app.console_frame.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="nsew")
        app.grid_rowconfigure(4, weight=1)
    else:
        app.console_frame.grid_forget()
        app.grid_rowconfigure(4, weight=0)


def toggle_debug_mode(app):
    app.workflow_manager.set_debug_mode(app.debug_mode_var.get())


def on_menu_action(app, action):
    app.menu_bar._close_active_menu()
    action()


def import_images(app):
    paths = tkinter.filedialog.askopenfilenames(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
    
    if paths:
        for i, path in enumerate(paths[:len(app.texture_slots)]):
            slot = app.texture_slots[i]
            slot.set_image(path)
            slot.mode_var.set(app.i18n.t('slot_mode_managed'))
            slot._on_mode_changed(None)
        app.watcher_handler.update_monitoring_list(app)


def validate_slots_and_update_ui(app):
    if app.is_automation_running:
        return
    
    for slot in app.texture_slots:
        if slot.get_mode_key() == 'Managed' and not slot.image_path:
            app.status_bar.set_status('status_warn_no_image_managed', level='warning', slot_id=slot.slot_id + 1)
            app.fast_apply_button.configure(state="disabled")
            app.full_apply_button.configure(state="disabled")
            return
    app.status_bar.set_status('status_ready')
    fast_apply_state = "normal" if not app.is_first_apply else "disabled"
    
    if fast_apply_state == "disabled":
        app.fast_apply_button.configure(fg_color="gray30")
    elif app.full_apply_button:
        app.fast_apply_button.configure(fg_color=app.full_apply_button.cget("fg_color"))
    app.fast_apply_button.configure(state=fast_apply_state)
    app.full_apply_button.configure(state="normal")
