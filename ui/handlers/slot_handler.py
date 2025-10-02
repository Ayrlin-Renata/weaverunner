import os
from utils.file_watcher import normalize_path


def move_slot(app, index, direction):
    """
    Swaps the data of a slot with its neighbor.
    """
    new_index = index + direction
    
    if not (0 <= new_index < len(app.texture_slots)):
        return
    slot_a_data = app.texture_slots[index].get_data()
    slot_b_data = app.texture_slots[new_index].get_data()
    app.texture_slots[index].set_data(slot_b_data)
    app.texture_slots[new_index].set_data(slot_a_data)
    app.watcher_handler.update_monitoring_list(app)


def on_slot_image_changed(app, image_path, image_obj=None, removed=False):
    if not image_path: return False
    norm_path = normalize_path(image_path)
    
    if removed:
        app.updated_image_paths.discard(norm_path)
        
        if norm_path in app.image_cache: del app.image_cache[norm_path]
        app.log_to_console(f"'{os.path.basename(image_path)}' unmarked as updated.")
        return False
    else:
        if image_obj is None:
            app.updated_image_paths.add(norm_path)
            app.log_to_console(f"'{os.path.basename(image_path)}' marked as updated for next apply (no image data for comparison).")
            return True
        old_img = app.image_cache.get(norm_path)
        content_is_different = not old_img or old_img.tobytes() != image_obj.tobytes()
        
        if content_is_different:
            app.log_to_console(f"Content changed for: {os.path.basename(image_path)}. Marking for update.")
            app.image_cache[norm_path] = image_obj
            app.updated_image_paths.add(norm_path)
            return True
        else:
            app.log_to_console(f"Content is identical for: {os.path.basename(image_path)}. Skipping update mark.")
            
            if norm_path not in app.image_cache: app.image_cache[norm_path] = image_obj
            return False


def on_slot_mode_changed(app, slot_id):
    slot = app.texture_slots[slot_id]
    
    if slot.get_mode_key() == 'Managed' and slot.image_path:
         on_slot_image_changed(app, slot.image_path, image_obj=None, removed=False)
         app.log_to_console(f"Slot {slot_id+1} switched to Managed. Marked for update.")
    app.ui_handler.validate_slots_and_update_ui(app)
