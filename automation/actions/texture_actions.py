import time
import os
import platform
import pyperclip
from PIL import Image
from automation.automation_config import AutomationSettings
from automation.exceptions import UIVisibilityError
from . import group_actions


def manage_textures(manager, slots_to_manage):
    manager.vision.log("\n--- Phase 2: Managing textures (upload/update) ---")
    uploaded_slots_by_group = {}
    
    if not slots_to_manage:
        manager.vision.log("  - No updated textures to manage in this run. Skipping phase.")
        return uploaded_slots_by_group
    num_slots_to_manage = len(slots_to_manage)
    
    for i, slot_data in enumerate(slots_to_manage):
        is_last_slot = (i == num_slots_to_manage - 1)
        manager._check_for_stop()
        log_callback = manager.vision.log
        log_callback(f"\nProcessing texture: {slot_data['image_path']}")
        
        if slot_data.get('group') and slot_data.get('image_path'):
            group_header_coords, _ = group_actions.find_and_expand_group(manager, slot_data['group'], [slot_data])
            
            if group_header_coords:
                manager._check_for_stop()
                upload_texture_to_group(manager, group_header_coords, slot_data['image_path'])
                manager._interruptible_sleep(AutomationSettings.POST_UPLOAD_FINISH_DELAY)
                manager._check_for_stop()
                apply_texture_settings(manager, slot_data['values'], is_last_slot=is_last_slot)
                group = slot_data['group']
                
                if group not in uploaded_slots_by_group:
                    uploaded_slots_by_group[group] = []
                uploaded_slots_by_group[group].append(slot_data['slot_id'])
    return uploaded_slots_by_group


def remove_texture(manager, texture_item_coords):
    manager._check_for_stop()
    selection_click_point = (texture_item_coords.x, texture_item_coords.y - 10)
    manager.controller.click(selection_click_point)
    more_button_search_region = (
        int(texture_item_coords.x),
        int(texture_item_coords.y - 100),
        200,
        100
    )
    manager.vision.log(f"More Button Search Region: {more_button_search_region}")
    more_button_coords = manager._wait_for_element('more_button.png', timeout=AutomationSettings.MENU_TIMEOUT, region=more_button_search_region)
    
    if not more_button_coords:
        raise UIVisibilityError(f"Could not find 'more' button for texture at {texture_item_coords}")
    manager.controller.click(more_button_coords)

    remove_menu_region = (
        int(more_button_coords.x - 75),
        int(more_button_coords.y - 20),
        200,
        150
    )
    manager.vision.log(f"Remove button search region: {remove_menu_region}")
    remove_button = manager._wait_for_element(
        'remove_button.png',
        timeout=AutomationSettings.MENU_TIMEOUT,
        region=remove_menu_region,
        cache_key='remove_button_context_menu'
    )

    if not remove_button:
        raise UIVisibilityError(f"Could not find 'remove' button after clicking 'more' at {more_button_coords}")

    manager.controller.click(remove_button)
    confirm_button = manager._wait_for_element(
        'remove_confirm_button.png',
        timeout=AutomationSettings.DIALOG_TIMEOUT,
        cache_key='remove_confirm_dialog'
    )
    manager.controller.click(confirm_button)


def upload_texture_to_group(manager, group_header_coords, image_path):
    manager._check_for_stop()
    manager.vision.log(f"  - Action: Uploading '{image_path}' to group.")
    search_region = (group_header_coords[0], group_header_coords[1], 400, manager.vision.app_region[3] - group_header_coords[1])
    upload_button_coords = manager.vision.find_image('group_upload_button.png', region=search_region)
    
    if not upload_button_coords:
        raise UIVisibilityError("Could not find group upload button.")
    manager.controller.click(upload_button_coords)
    choose_file_coords = manager._wait_for_element('choose_file_button.png', timeout=AutomationSettings.CHOOSE_FILE_TIMEOUT)
    manager.controller.click(choose_file_coords)
    manager._interruptible_sleep(AutomationSettings.POST_UPLOAD_DIALOG_DELAY)
    manager.vision.log(f"  - Waited {AutomationSettings.POST_UPLOAD_DIALOG_DELAY} seconds for dialog to appear.")
    real_path = os.path.realpath(image_path)
    manager.vision.log("  - Using robust clipboard paste for file path.")
    original_clipboard = None
    try:
        original_clipboard = pyperclip.paste()
        manager.vision.log(f"  - Attempting to copy '{real_path}' to clipboard.")
        pyperclip.copy(real_path)
        
        max_wait = 2.0
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if pyperclip.paste() == real_path:
                manager.vision.log("  - Clipboard content verified.")
                break
            manager._interruptible_sleep(0.05)
        else:
            raise UIVisibilityError("Failed to verify clipboard content after 2s.")

        paste_key = "command" if platform.system() == "Darwin" else "ctrl"
        manager.vision.log(f"  - Performing robust paste action (holding '{paste_key}' and pressing 'v').")
        manager.controller.key_down(paste_key)
        manager.controller.press('v')
        manager.controller.key_up(paste_key)
        manager._interruptible_sleep(AutomationSettings.POST_PASTE_DELAY)
        manager.controller.press('enter')
    except Exception as e:
        manager.vision.log(f"  - Clipboard paste method failed: {e}. Falling back to slower typing method.")
        manager.controller.write(real_path, interval=0.01)
        manager.controller.press('enter')
    finally:
        if original_clipboard is not None:
            pyperclip.copy(original_clipboard)
            manager.vision.log("  - Original clipboard content restored.")


def apply_texture_settings(manager, values, is_last_slot=False):
    manager._check_for_stop()
    last_set_entry_coords = None
    manager.vision.log("  - Action: Applying texture settings.")
    
    for panel_icon in ['adjust_panel_icon.png', 'repeat_panel_icon.png']:
        icon_coords = manager._find_image_with_cache(panel_icon, cache_key=panel_icon)
        
        if icon_coords:
            search_region = (int(icon_coords[0] + 50), int(icon_coords[1] - 10), 300, 40)
            collapsed_arrow = manager.vision.find_image('panel_collapsed.png', region=search_region)
            
            if collapsed_arrow:
                manager.controller.click(collapsed_arrow)
    param_map = {'size': 'size_input.png', 'angle': 'angle_input.png', 'opacity': 'opacity_input.png'}
    
    for key, template_name in param_map.items():
        target_value = values.get(key)
        default_value = AutomationSettings.DEFAULT_TEXTURE_VALUES.get(key)
        
        if target_value is not None and default_value is not None and abs(target_value - default_value) < 1e-4:
            manager.vision.log(f"  - Skipping '{key}' as its value ({target_value:.3f}) matches the default.")
            continue
        _, entry_coords = set_parameter_value(manager, key, template_name, values)
        
        if entry_coords:
            last_set_entry_coords = entry_coords
    manager.vision.log("  - Setting X and Y positions with stricter logic...")
    target_x = values.get('x_position')
    default_x = AutomationSettings.DEFAULT_TEXTURE_VALUES.get('x_position')
    x_pos_coords = None
    
    if target_x is not None and default_x is not None and abs(target_x - default_x) < 1e-4:
        manager.vision.log(f"  - Skipping 'x_position' as its value ({target_x:.3f}) matches the default.")
        x_pos_coords = manager.vision.find_image('x_pos_input.png')
    else:
        x_pos_coords, entry_coords = set_parameter_value(manager, 'x_position', 'x_pos_input.png', values)
        
        if entry_coords:
            last_set_entry_coords = entry_coords
    
    if x_pos_coords:
        y_search_region = (int(x_pos_coords[0] - 150), int(x_pos_coords[1] + 5), 300, 75)
        target_y = values.get('y_position')
        default_y = AutomationSettings.DEFAULT_TEXTURE_VALUES.get('y_position')
        
        if target_y is not None and default_y is not None and abs(target_y - default_y) < 1e-4:
            manager.vision.log(f"  - Skipping 'y_position' as its value ({target_y:.3f}) matches the default.")
        else:
            _, entry_coords = set_parameter_value(manager, 'y_position', 'y_pos_input.png', values, region=y_search_region)
            
            if entry_coords:
                last_set_entry_coords = entry_coords
        manager.vision.log(f"y_search_region: {y_search_region}")
    else:
        manager.vision.log("  - Skipping Y position because X position was not found.")
    
    if is_last_slot:
        if last_set_entry_coords:
            manager.vision.log("  - Applying final click to confirm last input.")
            final_click_point = (last_set_entry_coords[0] - 30, last_set_entry_coords[1])
            manager.controller.click(final_click_point)
        else:
            manager.vision.log("  - No numeric parameters were set for the last slot, skipping final confirmation click.")
    
    if values.get('h_flip'):
        manager.controller.click(manager.vision.find_image('h_flip.png'))
    
    if values.get('v_flip'):
        manager.controller.click(manager.vision.find_image('v_flip.png'))
    
    for key in ['h_repeat', 'v_repeat']:
        target_value = values.get(key, False)
        default_value = AutomationSettings.DEFAULT_TEXTURE_VALUES.get(key)
        
        if target_value == default_value:
            manager.vision.log(f"  - Skipping '{key}' as its value ({target_value}) matches the default.")
        else:
            set_checkbox_state(manager, key, target_value)


def set_parameter_value(manager, key, template_name, values, region=None):
    if key not in values:
        return None, None
    label_coords = manager._wait_for_element(
        template_name, timeout=AutomationSettings.GENERIC_ELEMENT_TIMEOUT, region=region
    )
    
    if label_coords:
        try:
            template_path = manager.vision.get_localized_template_path(template_name)
            with Image.open(template_path) as img: img_width, _ = img.size
            right_edge = label_coords[0] + (img_width / 2)
            click_x = right_edge + 5
            click_y = label_coords[1]
            manager.controller.click((click_x, click_y), clicks=3, interval=0.1)
            manager.controller.write(f"{values[key]:.3f}")
            return label_coords, (click_x, click_y)
        except (IndexError, TypeError, FileNotFoundError):
             manager.vision.log(f"  - Error processing parameter {key}. Could not calculate click position.")
    else:
        manager.vision.log(f"  - Could not find label '{template_name}' for parameter '{key}'.")
    return None, None


def set_checkbox_state(manager, base_name, should_be_checked):
    manager._check_for_stop()
    on_template, off_template = f'{base_name}_on.png', f'{base_name}_off.png'
    off_coords = manager.vision.find_image(off_template)
    
    if not off_coords:
        manager.vision.log(f"  - Warning: Could not locate checkbox element using '{off_template}'. Skipping.")
        return
    check_region = (int(off_coords[0] - 25), int(off_coords[1] - 25), int(off_coords[0] + 325), int(off_coords[1] + 25))
    is_on = manager.vision.find_image(on_template, region=check_region) is not None
    action_needed = (should_be_checked and not is_on) or \
                    (not should_be_checked and is_on)
    
    if action_needed:
        manager.vision.log(f"  - Checkbox '{base_name}' state is incorrect. Clicking to change.")
        try:
            template_path = manager.vision.get_localized_template_path(off_template)
            with Image.open(template_path) as img: img_width, _ = img.size
            right_edge = off_coords[0] + (img_width / 2)
            click_x = right_edge - 5
            click_y = off_coords[1]
            manager.controller.click((click_x, click_y))
        except (IndexError, TypeError, FileNotFoundError):
             manager.vision.log(f"  - Error setting checkbox state for '{base_name}'. Could not calculate click position.")
    else:
        manager.vision.log(f"  - Checkbox '{base_name}' state is already correct.")
