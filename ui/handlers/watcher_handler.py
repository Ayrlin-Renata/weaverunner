import tkinter
import os
from PIL import Image
from utils.file_watcher import normalize_path
from utils.clip_watcher import DOWNSCALING_METHODS
from ui.dialogs import ClipWatchSettingsDialog


def select_clip_file_to_watch(app):
    if app.clip_watcher.is_running:
        app.clip_watcher.stop()
        app.watch_clip_button.configure(text=app.i18n.t('watch_clip_button'))
        app.status_bar.set_status('status_stopped_watching_clip')
    else:
        path = tkinter.filedialog.askopenfilename(
            title="Select .clip file to watch",
            filetypes=[("Clip Studio Paint File", "*.clip")]
        )
        
        if not path:
            return
        dialog = ClipWatchSettingsDialog(app, i18n=app.i18n, algorithms=list(DOWNSCALING_METHODS.keys()))
        app.wait_window(dialog)
        
        if dialog.result:
            settings = dialog.result
            app.clip_watcher.start(
                path,
                app.clip_watch_layer_name,
                settings['scale_factor'],
                settings['algorithm']
            )
            app.watch_clip_button.configure(text=app.i18n.t('stop_watching_clip_button', filename=os.path.basename(path)))
            app.status_bar.set_status('status_watching_clip', layer_name=app.clip_watch_layer_name)


def select_post_process_file(app):
    if app.process_watcher.is_running:
        app.process_watcher.stop()
        app.watch_process_button.configure(text=app.i18n.t('watch_map_button'))
        app.status_bar.set_status('status_stopped_watching')
    else:
        path = tkinter.filedialog.askopenfilename(title="Select file to watch for tile splitting",
                                          filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        
        if path:
            app.process_watcher.start(path)
            app.watch_process_button.configure(text=app.i18n.t('stop_watching_map_button', filename=os.path.basename(path)))
            app.status_bar.set_status('status_watching')


def update_monitoring_list(app):
    paths_to_watch = [slot.image_path for slot in app.texture_slots if slot.image_path]
    app.file_watcher.start(paths_to_watch) if paths_to_watch else app.file_watcher.stop()
    app.ui_handler.validate_slots_and_update_ui(app)


def process_image_refresh_queue(app):
    while not app.image_refresh_queue.empty():
        image_path = app.image_refresh_queue.get()
        norm_path = normalize_path(image_path)
        try:
            new_img = Image.open(image_path); new_img.load()
        except Exception as e:
            app.log_to_console(f"Error loading changed file {os.path.basename(image_path)}: {e}")
            continue
        
        if app.slot_handler.on_slot_image_changed(app, image_path, image_obj=new_img, removed=False):
            for slot in app.texture_slots:
                if slot.image_path and normalize_path(slot.image_path) == norm_path:
                    slot.refresh_preview(new_img)
    app.after(500, lambda: process_image_refresh_queue(app))
