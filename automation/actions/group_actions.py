import pyautogui
import time
from automation.automation_config import AutomationSettings
from automation.exceptions import UIVisibilityError


def find_and_expand_group(manager, group_name, slots_for_group=None):
    manager._check_for_stop()
    manager.vision.log(f"Action: Find and expand group '{group_name}'.")
    search_names = [group_name]
    
    if slots_for_group:
        all_alternates = set()
        
        for slot in slots_for_group:
            all_alternates.update(slot.get('alternate_groups', []))
        search_names.extend(list(all_alternates))
    
    if len(search_names) > 1:
        manager.vision.log(f"  - Search candidates: {search_names}")
    ocr_region = None
    
    if manager.anchor_box and manager.vision.app_region:
        ocr_left = manager.anchor_box.left + manager.anchor_box.width * 0.25
        ocr_top = manager.anchor_box.top + manager.anchor_box.height * 3
        ocr_width = manager.anchor_box.width * 1.5
        ocr_height = manager.vision.app_region[3] - ocr_top
        ocr_region = (int(ocr_left), int(ocr_top), int(ocr_width), int(ocr_height))
    def attempt_to_find_header():
        def _process_and_cache_match(best_match, method_name):
            ocr_bbox = best_match['bbox']
            manager.vision.log(f"  - Found a match for '{best_match['text']}' via {method_name}. Caching image for primary name '{group_name}'.")
            manager.group_x_positions.append(ocr_bbox[0])
            try:
                buffer = 2
                capture_region = (
                    ocr_bbox[0] - buffer, ocr_bbox[1] - buffer,
                    ocr_bbox[2] + buffer * 2, ocr_bbox[3] + buffer * 2
                )
                header_image = manager.vision.screenshot(region=capture_region)
                
                if header_image:
                    manager.group_header_cache[group_name] = header_image
                    manager.vision.log(f"  - Re-locating with newly cached image for precision.")
                    vision_bbox = manager.vision.find_image_box(header_image, region=ocr_region, confidence=0.9)
                    return vision_bbox if vision_bbox else ocr_bbox
                manager.vision.log(f"  - Warning: Failed to capture image for group '{group_name}'. Using OCR box.")
            except Exception as e:
                manager.vision.log(f"  - Warning: Could not cache/re-verify image for group '{group_name}'. Using OCR box. Error: {e}")
            
            return ocr_bbox
        cached_image = manager.group_header_cache.get(group_name)
        
        if cached_image:
            manager.vision.log(f"  - Attempting to find group '{group_name}' using cached image.")
            location = manager.vision.find_image_box(cached_image, region=ocr_region, confidence=0.95)
            
            if location:
                manager.vision.log(f"  - Found group '{group_name}' via cached image.")
                return location
            manager.vision.log(f"  - Cached image for '{group_name}' not found. Falling back to other methods.")
        manager.vision.log("  - Trying targeted OCR strategy based on group icons.")
        expanded_arrows = manager.vision.find_all_images('group_expanded.png', region=ocr_region, confidence=0.8)
        collapsed_arrows = manager.vision.find_all_images('group_collapsed.png', region=ocr_region, confidence=0.8)
        all_arrows = sorted(expanded_arrows + collapsed_arrows, key=lambda p: p.y)
        
        if all_arrows:
            manager.vision.log(f"  - Found {len(all_arrows)} group icons to target.")
            all_potential_matches = []
            
            for arrow_pos in all_arrows:
                target_ocr_width = 300
                target_ocr_height = 30
                target_ocr_left = arrow_pos.x - target_ocr_width
                target_ocr_top = arrow_pos.y - (target_ocr_height / 2)
                targeted_region = (
                    int(max(ocr_region[0], target_ocr_left)),
                    int(max(ocr_region[1], target_ocr_top)),
                    int(target_ocr_width),
                    int(target_ocr_height)
                )
                
                for name_to_find in search_names:
                    potential_matches = manager.vision.find_text_on_screen(name_to_find, region=targeted_region)
                    
                    if potential_matches:
                        all_potential_matches.extend(potential_matches)
            
            if all_potential_matches:
                manager.vision.log(f"  - Targeted OCR found {len(all_potential_matches)} potential matches across all icons.")
                best_match = manager._select_best_group_match(all_potential_matches)
                
                if best_match:
                    return _process_and_cache_match(best_match, "targeted OCR")
        else:
            manager.vision.log("  - No group icons found for targeted OCR.")
        manager.vision.log("  - Targeted OCR failed. Falling back to wide-area OCR.")
        
        for name_to_find in search_names:
            manager.vision.log(f"  - Attempting to find group '{name_to_find}' using OCR.")
            potential_matches = manager.vision.find_text_on_screen(name_to_find, region=ocr_region)
            
            if not potential_matches:
                continue
            best_match = manager._select_best_group_match(potential_matches)
            
            if best_match:
                return _process_and_cache_match(best_match, "wide-area OCR")
        return None
    group_header = attempt_to_find_header()
    
    if not group_header:
        if ocr_region:
            pyautogui.moveTo(ocr_region[0] + 150, ocr_region[1] + 200, duration=0.2)
        
        for _ in range(5):
            manager.controller.scroll(-200); time.sleep(AutomationSettings.SCROLL_DELAY)
            group_header = attempt_to_find_header()
            
            if group_header: break
    
    if not group_header:
        raise UIVisibilityError(f"Could not find group '{group_name}'.")
    arrow_search_region = (int(group_header[0] + group_header[2]), int(group_header[1] - 5), 300, int(group_header[3] + 10))
    expanded_arrow = manager.vision.find_image('group_expanded.png', region=arrow_search_region)
    
    if expanded_arrow:
        return group_header, expanded_arrow
    collapsed_arrow = manager.vision.find_image('group_collapsed.png', region=arrow_search_region)
    
    if collapsed_arrow:
        manager.controller.click(collapsed_arrow)
        expanded_arrow = manager._wait_for_element('group_expanded.png', timeout=AutomationSettings.GENERIC_ELEMENT_TIMEOUT, region=arrow_search_region)
        
        if expanded_arrow:
            return group_header, expanded_arrow
    raise UIVisibilityError(f"Cannot determine state of group '{group_name}'.")


def get_textures_in_group(manager, group_header_coords, group_arrow_coords):
    manager._check_for_stop()
    ocr_region = None
    
    if manager.anchor_box and manager.vision.app_region:
        ocr_left = manager.anchor_box.left
        ocr_top = manager.anchor_box.top + manager.anchor_box.height
        ocr_width = manager.anchor_box.width * 2.5
        ocr_height = manager.vision.app_region[3] - ocr_top
        ocr_region = (int(ocr_left), int(ocr_top), int(ocr_width), int(ocr_height))
    
    if not ocr_region: ocr_region = manager.vision.app_region
    search_y_start = group_header_coords[1] + group_header_coords[3]
    search_x = group_header_coords[0]
    search_width = 400
    bottom_boundary = None
    upload_button_search_region = (search_x, search_y_start, search_width, (ocr_region[1] + ocr_region[3]) - search_y_start)
    upload_button = manager.vision.find_image('group_upload_button.png', region=upload_button_search_region)
    
    if upload_button:
        bottom_boundary = upload_button.y - 20
        manager.vision.log(f"  - Group upload button found at y={bottom_boundary}. Bounding search.")
    else:
        expanded_arrows = manager.vision.find_all_images('group_expanded.png', region=ocr_region)
        collapsed_arrows = manager.vision.find_all_images('group_collapsed.png', region=ocr_region)
        all_arrows = sorted(expanded_arrows + collapsed_arrows, key=lambda p: p.y)
        current_arrow_y = group_arrow_coords.y
        next_arrow_y = None
        
        for arrow in all_arrows:
            if arrow.y > current_arrow_y + 5:
                next_arrow_y = arrow.y
                break
        
        if next_arrow_y:
            bottom_boundary = next_arrow_y
            manager.vision.log(f"  - Next group found at y={next_arrow_y}. Bounding search.")
        else:
            bottom_boundary = ocr_region[1] + ocr_region[3]
            manager.vision.log("  - No subsequent group or upload button found. Searching to bottom of region.")
    search_height = bottom_boundary - search_y_start
    
    if search_height <= 0:
         manager.vision.log("  - Search region has zero or negative height. No textures to find.")
         return []
    search_region = (int(search_x), int(search_y_start), int(search_width), int(search_height))
    manager.vision.log(f"  - Defined bounded search region for textures: {search_region}")
    texture_items = manager.vision.find_all_images('texture_item.png', region=search_region, confidence=0.99)
    selected_texture_items = manager.vision.find_all_images('texture_item_selected.png', region=search_region, confidence=0.99)
    all_items = sorted(texture_items + selected_texture_items, key=lambda p: p.y)
    
    if not all_items:
        manager.vision.log("  - No textures found in this group.")
        return []
    textures = []
    
    for item_coords in all_items:
        textures.append({'texture_item_coords': item_coords})
    manager.vision.log(f"  - Found {len(textures)} textures in group.")
    return textures
