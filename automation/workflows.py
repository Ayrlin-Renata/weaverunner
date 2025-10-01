import time
import threading
import screeninfo
import pyautogui
from pyscreeze import Box
import pyperclip
import platform
import numpy as np
import os
from automation.vision import Vision
from automation.controller import Controller
from automation.automation_config import AutomationSettings
from PIL import Image


class AutomationStoppedError(Exception):
    """
    Custom exception for when the user stops the automation.
    """
    pass


class UIVisibilityError(Exception):
    """
    Custom exception for when a critical UI element cannot be found or its state is ambiguous.
    """
    pass


class FastApplyError(Exception):
    """
    Custom exception for when Fast Apply cannot proceed safely.
    """
    pass


class WorkflowManager:
    def __init__(self, assets_path):
        self.assets_path = assets_path
        self.vision = Vision(assets_path)
        self.controller = Controller()
        self.stop_event = threading.Event()
        self.ui_cache = {}
        self.group_header_cache = {}
        self.anchor_box = None
        self.group_x_positions = []
    
    def find_app_window_and_set_region(self):
        self.vision.log("Attempting to find app anchor 'app_anchor.png'...")
        anchor_box_tuple = self.vision.find_image_box('app_anchor.png', confidence=0.8)
        
        if not anchor_box_tuple:
            self.vision.log("ERROR: App anchor image not found on any screen.")
            self.vision.app_region = None
            self.anchor_box = None
            return None
        self.anchor_box = Box(*anchor_box_tuple)
        anchor_center_x = self.anchor_box.left + self.anchor_box.width // 2
        anchor_center_y = self.anchor_box.top + self.anchor_box.height // 2
        self.vision.log(f"Found anchor box at {self.anchor_box}")
        monitors = screeninfo.get_monitors()
        
        for monitor in monitors:
            if monitor.x <= anchor_center_x < monitor.x + monitor.width and \
               monitor.y <= anchor_center_y < monitor.y + monitor.height:
                self.vision.app_region = (monitor.x, monitor.y, monitor.width, monitor.height)
                self.controller.action_region = self.vision.app_region
                self.vision.log(f"Set automation region to: {self.vision.app_region}")
                return monitor
        self.vision.log("ERROR: Could not determine monitor for the anchor.")
        return None
    
    def request_stop(self):
        self.stop_event.set()
    
    def set_language(self, lang_code):
        self.vision.set_language(lang_code)
    
    def set_debug_mode(self, enabled):
        self.vision.set_debug_mode(enabled)
    
    def _check_for_stop(self):
        if self.stop_event.is_set():
            raise AutomationStoppedError("Automation stopped by user.")
    
    def run(self, texture_slots_data, old_texture_map, is_full_run, log_callback=print):
        self.stop_event.clear()
        self.group_x_positions.clear()
        self.vision.log = log_callback
        self.controller.log = log_callback
        log_callback("Starting automation workflow...")
        try:
            removed_slots_by_group = {}
            
            if is_full_run:
                self._process_removals_full(texture_slots_data)
            else:
                removed_slots_by_group = self._process_removals_fast(texture_slots_data, old_texture_map)
            self._check_for_stop()
            slots_to_manage = [s for s in texture_slots_data if s['mode'] == 'Managed' and s.get('is_updated', False)]
            uploaded_slots_by_group = self._manage_textures(slots_to_manage)
            
            if is_full_run:
                new_texture_map = self._compute_new_texture_map_from_ui(texture_slots_data)
            else:
                new_texture_map = self._compute_new_texture_map_from_ops(old_texture_map, removed_slots_by_group, uploaded_slots_by_group)
            log_callback("\nAutomation workflow finished successfully.")
            return (True, new_texture_map)
        except FastApplyError as e:
            log_callback(f"--- Fast Apply failed: {e} ---")
            return ('FAST_APPLY_FAILED', old_texture_map)
        except (AutomationStoppedError, UIVisibilityError) as e:
            log_callback(f"--- Automation halted: {e} ---")
            return (False, old_texture_map)
        except Exception as e:
            log_callback(f"--- An unexpected error occurred: {type(e).__name__}: {e} ---")
            import traceback
            traceback.print_exc()
            return (False, old_texture_map)
    
    def _process_removals_full(self, slots_data):
        self.vision.log("\n--- Phase 1: Processing removals for a Full Apply/First Run ---")
        all_groups = sorted(list({s['group'] for s in slots_data if s['group']}))
        ui_slots_by_group = {}
        
        for s in slots_data:
            if s['group']:
                if s['group'] not in ui_slots_by_group:
                    ui_slots_by_group[s['group']] = []
                ui_slots_by_group[s['group']].append(s)
        
        for group_name in ui_slots_by_group:
            ui_slots_by_group[group_name].sort(key=lambda s: s['slot_id'])
        
        for group_name in all_groups:
            self._check_for_stop()
            self.vision.log(f"\nScanning group for removal: '{group_name}'")
            slots_in_group = ui_slots_by_group.get(group_name, [])
            group_header, group_arrow = self._find_and_expand_group(group_name, slots_in_group)
            
            if not group_header:
                self.vision.log(f"  - Could not find group '{group_name}'. Assuming it's empty.")
                continue
            web_textures = self._get_textures_in_group(group_header, group_arrow)
            
            if not web_textures:
                self.vision.log("  - Group is empty in web app. No removals needed.")
                continue
            ui_slots_for_group = ui_slots_by_group.get(group_name, [])
            indices_to_keep = {i for i, slot in enumerate(ui_slots_for_group) if slot['mode'] == 'Ignored'}
            self.vision.log(f"  - UI specifies {len(ui_slots_for_group)} slots for this group.")
            self.vision.log(f"  - Will keep textures at web app positions: {indices_to_keep or 'None'}")
            coords_to_remove = []
            
            for i, web_texture in enumerate(web_textures):
                if i not in indices_to_keep:
                    self.vision.log(f"  - Marking texture at position {i} for removal. {web_texture['texture_item_coords']}")
                    coords_to_remove.append(web_texture['texture_item_coords'])
            
            if coords_to_remove:
                self.vision.log(f"\nExecuting {len(coords_to_remove)} removals for group '{group_name}'")
                
                for coords in reversed(coords_to_remove):
                    self._check_for_stop()
                    self._remove_texture(coords)
                    time.sleep(AutomationSettings.POST_REMOVAL_DELAY)
            else:
                self.vision.log("  - No removals needed for this group based on 'Ignored' slots.")
    
    def _process_removals_fast(self, slots_data, old_texture_map):
        self.vision.log("\n--- Phase 1: Processing removals for a Fast Apply ---")
        
        if not old_texture_map:
            self.vision.log("  - No previous texture map found. Cannot perform Fast Apply removals safely. Skipping removals.")
            raise FastApplyError("No previous texture map available for Fast Apply.")
        groups_to_process = sorted(list(old_texture_map.keys()))
        removals_by_group = {}
        removed_slots_by_group = {}
        
        for group_name in groups_to_process:
            self._check_for_stop()
            previous_slot_ids = old_texture_map.get(group_name, [])
            needs_scan = False
            
            for slot_id in previous_slot_ids:
                slot_data = next((s for s in slots_data if s['slot_id'] == slot_id), None)
                
                if not slot_data or slot_data.get('group') != group_name:
                    needs_scan = True
                    break
                
                if slot_data['mode'] == 'Managed' and slot_data.get('is_updated', False):
                    needs_scan = True
                    break
            
            if not needs_scan:
                self.vision.log(f"\nSkipping removal scan for group '{group_name}': No updated or moved-out slots found.")
                continue
            self.vision.log(f"\nScanning group for removal: '{group_name}'")
            slots_for_group = [s for s in slots_data if s.get('group') == group_name]
            group_header, group_arrow = self._find_and_expand_group(group_name, slots_for_group)
            
            if not group_header:
                self.vision.log(f"  - Warning: Could not find group '{group_name}'. Skipping.")
                continue
            web_textures = self._get_textures_in_group(group_header, group_arrow)
            web_textures_coords = [t['texture_item_coords'] for t in web_textures]
            previous_slot_order = old_texture_map.get(group_name, [])
            
            if len(web_textures_coords) != len(previous_slot_order):
                self.vision.log(f"  - WARNING: Mismatch between expected textures ({len(previous_slot_order)}) and found textures ({len(web_textures_coords)}) in group '{group_name}'. The user may have manually changed textures. Aborting removal for this group to be safe.")
                continue
            removals_by_group[group_name] = []
            removed_slots_by_group[group_name] = []
            
            for i, slot_id in enumerate(previous_slot_order):
                slot_data = next((s for s in slots_data if s['slot_id'] == slot_id), None)
                
                if not slot_data or slot_data.get('group') != group_name:
                    self.vision.log(f"  - Slot {slot_id+1} is no longer in group '{group_name}'. Marking for removal.")
                    removals_by_group[group_name].append(web_textures_coords[i])
                    removed_slots_by_group[group_name].append(slot_id)
                elif slot_data['mode'] == 'Managed' and slot_data.get('is_updated', False):
                    self.vision.log(f"  - Slot {slot_id+1} is Managed and updated. Marking for removal.")
                    removals_by_group[group_name].append(web_textures_coords[i])
                    removed_slots_by_group[group_name].append(slot_id)
        
        for group_name, coords_to_remove in removals_by_group.items():
            self.vision.log(f"\nExecuting {len(coords_to_remove)} removals for group '{group_name}'")
            
            for coords in reversed(coords_to_remove):
                self._check_for_stop()
                self._remove_texture(coords)
                time.sleep(AutomationSettings.POST_REMOVAL_DELAY)
        return removed_slots_by_group
    
    def _compute_new_texture_map_from_ui(self, slots_data):
        new_map = {}
        slots_by_group = {}
        
        for s in slots_data:
            if s['group'] and s['mode'] in ['Managed', 'Ignored']:
                if s['group'] not in slots_by_group:
                    slots_by_group[s['group']] = []
                slots_by_group[s['group']].append(s)
        
        for group_name, slots in slots_by_group.items():
            sorted_slots = sorted(slots, key=lambda x: x['slot_id'])
            new_map[group_name] = [s['slot_id'] for s in sorted_slots]
        self.vision.log(f"Computed new texture map from UI state: {new_map}")
        return new_map
    
    def _compute_new_texture_map_from_ops(self, old_map, removed_by_group, uploaded_by_group):
        new_map = {}
        all_groups = set(old_map.keys()) | set(uploaded_by_group.keys())
        
        for group_name in all_groups:
            old_order = old_map.get(group_name, [])
            removed_slots = set(removed_by_group.get(group_name, []))
            uploaded_slots = uploaded_by_group.get(group_name, [])
            survivors = [slot_id for slot_id in old_order if slot_id not in removed_slots]
            new_order = survivors + uploaded_slots
            
            if new_order:
                new_map[group_name] = new_order
        self.vision.log(f"Computed new texture map from operations: {new_map}")
        return new_map
    
    def _manage_textures(self, slots_to_manage):
        self.vision.log("\n--- Phase 2: Managing textures (upload/update) ---")
        uploaded_slots_by_group = {}
        
        if not slots_to_manage:
            self.vision.log("  - No updated textures to manage in this run. Skipping phase.")
            return uploaded_slots_by_group
        num_slots_to_manage = len(slots_to_manage)
        
        for i, slot_data in enumerate(slots_to_manage):
            is_last_slot = (i == num_slots_to_manage - 1)
            self._check_for_stop()
            log_callback = self.vision.log
            log_callback(f"\nProcessing texture: {slot_data['image_path']}")
            
            if slot_data.get('group') and slot_data.get('image_path'):
                group_header_coords, _ = self._find_and_expand_group(slot_data['group'], [slot_data])
                
                if group_header_coords:
                    self._check_for_stop()
                    self._upload_texture_to_group(group_header_coords, slot_data['image_path'])
                    time.sleep(AutomationSettings.POST_UPLOAD_FINISH_DELAY)
                    self._check_for_stop()
                    self._apply_texture_settings(slot_data['values'], is_last_slot=is_last_slot)
                    group = slot_data['group']
                    
                    if group not in uploaded_slots_by_group:
                        uploaded_slots_by_group[group] = []
                    uploaded_slots_by_group[group].append(slot_data['slot_id'])
        return uploaded_slots_by_group
    
    def _find_image_with_cache(self, template_name, cache_key, region=None, confidence=0.8):
        """
        Finds an image, prioritizing a cached region if available.
        """
        
        if cache_key in self.ui_cache:
            cached_region = self.ui_cache[cache_key]
            self.vision.log(f"  - Searching for '{template_name}' in cached region: {cached_region}")
            location = self.vision.find_image(template_name, region=cached_region, confidence=confidence)
            
            if location:
                return location
        self.vision.log(f"  - Searching for '{template_name}' in wider region: {region or 'Full Screen'}")
        location = self.vision.find_image(template_name, region=region, confidence=confidence)
        
        if location:
            cache_size = AutomationSettings.CACHE_REGION_SIZE
            new_cached_region = (
                int(location[0] - cache_size / 2), int(location[1] - cache_size / 2),
                cache_size, cache_size
            )
            self.ui_cache[cache_key] = new_cached_region
            self.vision.log(f"  - Found '{template_name}' and updated cache '{cache_key}' to {new_cached_region}")
        return location
    
    def _select_best_group_match(self, matches):
        """
        Applies heuristics to a list of potential OCR matches to find the best one.
        """
        
        if not matches:
            return None
        predicted_x = None
        
        if self.group_x_positions:
            predicted_x = np.median(self.group_x_positions)
            self.vision.log(f"  - Applying heuristics with predicted X-indentation: {predicted_x:.0f}")
        scored_matches = []
        
        for match in matches:
            final_score = match['score']
            bbox = match['bbox']
            
            if predicted_x is not None:
                x_diff = abs(bbox[0] - predicted_x)
                penalty = (x_diff / 50.0) * 0.1
                final_score -= penalty
                self.vision.log(f"    - Candidate '{match['text']}' at x={bbox[0]}. X-diff penalty: {penalty:.2f}. New score: {final_score:.2f}")
            arrow_search_region = (int(bbox[0] + bbox[2]), int(bbox[1] - 5), 300, int(bbox[3] + 10))
            expanded_arrow = self.vision.find_image('group_expanded.png', region=arrow_search_region, confidence=0.7)
            collapsed_arrow = self.vision.find_image('group_collapsed.png', region=arrow_search_region, confidence=0.7)
            
            if expanded_arrow or collapsed_arrow:
                final_score += 0.5
                self.vision.log(f"    - Candidate '{match['text']}' has an arrow nearby. Bonus applied. New score: {final_score:.2f}")
            
            if final_score > 0:
                scored_matches.append({'match': match, 'final_score': final_score})
        
        if not scored_matches:
            self.vision.log("  - No candidates survived heuristic filtering.")
            return None
        sorted_matches = sorted(scored_matches, key=lambda x: x['final_score'], reverse=True)
        best_match_info = sorted_matches[0]
        
        if best_match_info['final_score'] < 0.7:
             self.vision.log(f"  - Best candidate '{best_match_info['match']['text']}' has score {best_match_info['final_score']:.2f}, which is below threshold 0.7. Discarding.")
             return None
        self.vision.log(f"  - Selected best group match '{best_match_info['match']['text']}' with final score {best_match_info['final_score']:.2f}")
        return best_match_info['match']
    
    def _wait_for_element(self, template_name, timeout, cache_key=None, region=None, confidence=0.8):
        """
        Waits for a UI element to appear by repeatedly searching for it until a timeout is reached.
        Returns the element's coordinates or raises UIVisibilityError.
        """
        start_time = time.time()
        self.vision.log(f"  - Waiting up to {timeout}s for '{template_name}' to appear...")
        
        while time.time() - start_time < timeout:
            self._check_for_stop()
            
            if cache_key:
                location = self._find_image_with_cache(template_name, cache_key, region=region, confidence=confidence)
            else:
                location = self.vision.find_image(template_name, region=region, confidence=confidence)
            
            if location:
                self.vision.log(f"  - Found '{template_name}' after {time.time() - start_time:.2f}s.")
                return location
            time.sleep(0.1)
        raise UIVisibilityError(f"Timed out after {timeout}s waiting for '{template_name}'.")
    
    def _find_and_expand_group(self, group_name, slots_for_group=None):
        self._check_for_stop()
        self.vision.log(f"Action: Find and expand group '{group_name}'.")
        search_names = [group_name]
        
        if slots_for_group:
            all_alternates = set()
            
            for slot in slots_for_group:
                all_alternates.update(slot.get('alternate_groups', []))
            search_names.extend(list(all_alternates))
        
        if len(search_names) > 1:
            self.vision.log(f"  - Search candidates: {search_names}")
        ocr_region = None
        
        if self.anchor_box and self.vision.app_region:
            ocr_left = self.anchor_box.left
            ocr_top = self.anchor_box.top + self.anchor_box.height
            ocr_width = self.anchor_box.width * 2.5
            ocr_height = self.vision.app_region[3] - ocr_top
            ocr_region = (int(ocr_left), int(ocr_top), int(ocr_width), int(ocr_height))
        def attempt_to_find_header():
            cached_image = self.group_header_cache.get(group_name)
            
            if cached_image:
                self.vision.log(f"  - Attempting to find group '{group_name}' using cached image.")
                location = self.vision.find_image_box(cached_image, region=ocr_region, confidence=0.9)
                
                if location:
                    self.vision.log(f"  - Found group '{group_name}' via cached image.")
                    return location
                self.vision.log(f"  - Cached image for '{group_name}' not found. Falling back to OCR.")
            
            for name_to_find in search_names:
                self.vision.log(f"  - Attempting to find group '{name_to_find}' using OCR.")
                potential_matches = self.vision.find_text_on_screen(name_to_find, region=ocr_region)
                
                if not potential_matches:
                    continue
                best_match = self._select_best_group_match(potential_matches)
                
                if best_match:
                    ocr_bbox = best_match['bbox']
                    self.vision.log(f"  - Found a match for '{name_to_find}' via OCR. Caching image for primary name '{group_name}'.")
                    self.group_x_positions.append(ocr_bbox[0])
                    try:
                        buffer = 2
                        capture_region = (
                            ocr_bbox[0] - buffer, ocr_bbox[1] - buffer,
                            ocr_bbox[2] + buffer * 2, ocr_bbox[3] + buffer * 2
                        )
                        header_image = self.vision.screenshot(region=capture_region)
                        
                        if header_image:
                            self.group_header_cache[group_name] = header_image
                            self.vision.log(f"  - Re-locating with newly cached image for precision.")
                            vision_bbox = self.vision.find_image_box(header_image, region=ocr_region, confidence=0.9)
                            return vision_bbox if vision_bbox else ocr_bbox
                        self.vision.log(f"  - Warning: Failed to capture image for group '{group_name}'. Using OCR box.")
                    except Exception as e:
                        self.vision.log(f"  - Warning: Could not cache/re-verify image for group '{group_name}'. Using OCR box. Error: {e}")
                        return ocr_bbox
            return None
        group_header = attempt_to_find_header()
        
        if not group_header:
            if ocr_region:
                pyautogui.moveTo(ocr_region[0] + 200, ocr_region[1] + 200, duration=0.2)
            
            for _ in range(5):
                self.controller.scroll(-200); time.sleep(AutomationSettings.SCROLL_DELAY)
                group_header = attempt_to_find_header()
                
                if group_header: break
        
        if not group_header:
            raise UIVisibilityError(f"Could not find group '{group_name}'.")
        arrow_search_region = (int(group_header[0] + group_header[2]), int(group_header[1] - 5), 300, int(group_header[3] + 10))
        expanded_arrow = self.vision.find_image('group_expanded.png', region=arrow_search_region)
        
        if expanded_arrow:
            return group_header, expanded_arrow
        collapsed_arrow = self.vision.find_image('group_collapsed.png', region=arrow_search_region)
        
        if collapsed_arrow:
            self.controller.click(collapsed_arrow)
            expanded_arrow = self._wait_for_element('group_expanded.png', timeout=AutomationSettings.GENERIC_ELEMENT_TIMEOUT, region=arrow_search_region)
            
            if expanded_arrow:
                return group_header, expanded_arrow
        raise UIVisibilityError(f"Cannot determine state of group '{group_name}'.")
    
    def _get_textures_in_group(self, group_header_coords, group_arrow_coords):
        self._check_for_stop()
        ocr_region = None
        
        if self.anchor_box and self.vision.app_region:
            ocr_left = self.anchor_box.left
            ocr_top = self.anchor_box.top + self.anchor_box.height
            ocr_width = self.anchor_box.width * 2.5
            ocr_height = self.vision.app_region[3] - ocr_top
            ocr_region = (int(ocr_left), int(ocr_top), int(ocr_width), int(ocr_height))
        
        if not ocr_region: ocr_region = self.vision.app_region
        search_y_start = group_header_coords[1] + group_header_coords[3]
        search_x = group_header_coords[0]
        search_width = 400
        bottom_boundary = None
        upload_button_search_region = (search_x, search_y_start, search_width, (ocr_region[1] + ocr_region[3]) - search_y_start)
        upload_button = self.vision.find_image('group_upload_button.png', region=upload_button_search_region)
        
        if upload_button:
            bottom_boundary = upload_button.y - 20
            self.vision.log(f"  - Group upload button found at y={bottom_boundary}. Bounding search.")
        else:
            expanded_arrows = self.vision.find_all_images('group_expanded.png', region=ocr_region)
            collapsed_arrows = self.vision.find_all_images('group_collapsed.png', region=ocr_region)
            all_arrows = sorted(expanded_arrows + collapsed_arrows, key=lambda p: p.y)
            current_arrow_y = group_arrow_coords.y
            next_arrow_y = None
            
            for arrow in all_arrows:
                if arrow.y > current_arrow_y + 5:
                    next_arrow_y = arrow.y
                    break
            
            if next_arrow_y:
                bottom_boundary = next_arrow_y
                self.vision.log(f"  - Next group found at y={next_arrow_y}. Bounding search.")
            else:
                bottom_boundary = ocr_region[1] + ocr_region[3]
                self.vision.log("  - No subsequent group or upload button found. Searching to bottom of region.")
        search_height = bottom_boundary - search_y_start
        
        if search_height <= 0:
             self.vision.log("  - Search region has zero or negative height. No textures to find.")
             return []
        search_region = (int(search_x), int(search_y_start), int(search_width), int(search_height))
        self.vision.log(f"  - Defined bounded search region for textures: {search_region}")
        texture_items = self.vision.find_all_images('texture_item.png', region=search_region, confidence=0.99)
        selected_texture_items = self.vision.find_all_images('texture_item_selected.png', region=search_region, confidence=0.99)
        all_items = sorted(texture_items + selected_texture_items, key=lambda p: p.y)
        
        if not all_items:
            self.vision.log("  - No textures found in this group.")
            return []
        textures = []
        
        for item_coords in all_items:
            textures.append({'texture_item_coords': item_coords})
        self.vision.log(f"  - Found {len(textures)} textures in group.")
        return textures
    
    def _remove_texture(self, texture_item_coords):
        self._check_for_stop()
        selection_click_point = (texture_item_coords.x, texture_item_coords.y - 10)
        self.controller.click(selection_click_point)
        more_button_search_region = (
            int(texture_item_coords.x),
            int(texture_item_coords.y - 100),
            200,
            100
        )
        self.vision.log(f"More Button Search Region: {more_button_search_region}")
        more_button_coords = self._wait_for_element('more_button.png', timeout=AutomationSettings.MENU_TIMEOUT, region=more_button_search_region)
        
        if not more_button_coords:
            raise UIVisibilityError(f"Could not find 'more' button for texture at {texture_item_coords}")
        self.controller.click(more_button_coords)
        remove_button = self._wait_for_element('remove_button.png', timeout=AutomationSettings.MENU_TIMEOUT)
        self.controller.click(remove_button)
        confirm_button = self._wait_for_element(
            'remove_confirm_button.png',
            timeout=AutomationSettings.DIALOG_TIMEOUT,
            cache_key='remove_confirm_dialog'
        )
        self.controller.click(confirm_button)
    
    def _upload_texture_to_group(self, group_header_coords, image_path):
        self._check_for_stop()
        self.vision.log(f"  - Action: Uploading '{image_path}' to group.")
        search_region = (group_header_coords[0], group_header_coords[1], 400, self.vision.app_region[3] - group_header_coords[1])
        upload_button_coords = self.vision.find_image('group_upload_button.png', region=search_region)
        
        if not upload_button_coords:
            raise UIVisibilityError("Could not find group upload button.")
        self.controller.click(upload_button_coords)
        choose_file_coords = self._wait_for_element('choose_file_button.png', timeout=AutomationSettings.CHOOSE_FILE_TIMEOUT)
        self.controller.click(choose_file_coords)
        time.sleep(AutomationSettings.POST_UPLOAD_DIALOG_DELAY)
        real_path = os.path.realpath(image_path)
        self.vision.log("  - Using robust clipboard paste for file path.")
        original_clipboard = None
        try:
            original_clipboard = pyperclip.paste()
            pyperclip.copy(real_path)
            paste_key = "command" if platform.system() == "Darwin" else "ctrl"
            self.controller.hotkey(paste_key, 'v')
            time.sleep(AutomationSettings.POST_PASTE_DELAY)
            self.controller.press('enter')
        except Exception as e:
            self.vision.log(f"  - Clipboard paste method failed: {e}. Falling back to slower typing method.")
            self.controller.write(real_path, interval=0.01)
            self.controller.press('enter')
        finally:
            if original_clipboard is not None:
                pyperclip.copy(original_clipboard)
                self.vision.log("  - Original clipboard content restored.")
    
    def _apply_texture_settings(self, values, is_last_slot=False):
        self._check_for_stop()
        last_set_entry_coords = None
        self.vision.log("  - Action: Applying texture settings.")
        
        for panel_icon in ['adjust_panel_icon.png', 'repeat_panel_icon.png']:
            icon_coords = self._find_image_with_cache(panel_icon, cache_key=panel_icon)
            
            if icon_coords:
                search_region = (int(icon_coords[0] + 50), int(icon_coords[1] - 10), 300, 40)
                collapsed_arrow = self.vision.find_image('panel_collapsed.png', region=search_region)
                
                if collapsed_arrow:
                    self.controller.click(collapsed_arrow)
        param_map = {'size': 'size_input.png', 'angle': 'angle_input.png', 'opacity': 'opacity_input.png'}
        
        for key, template_name in param_map.items():
            target_value = values.get(key)
            default_value = AutomationSettings.DEFAULT_TEXTURE_VALUES.get(key)
            
            if target_value is not None and default_value is not None and abs(target_value - default_value) < 1e-4:
                self.vision.log(f"  - Skipping '{key}' as its value ({target_value:.3f}) matches the default.")
                continue
            _, entry_coords = self._set_parameter_value(key, template_name, values)
            
            if entry_coords:
                last_set_entry_coords = entry_coords
        self.vision.log("  - Setting X and Y positions with stricter logic...")
        target_x = values.get('x_position')
        default_x = AutomationSettings.DEFAULT_TEXTURE_VALUES.get('x_position')
        x_pos_coords = None
        
        if target_x is not None and default_x is not None and abs(target_x - default_x) < 1e-4:
            self.vision.log(f"  - Skipping 'x_position' as its value ({target_x:.3f}) matches the default.")
            x_pos_coords = self.vision.find_image('x_pos_input.png')
        else:
            x_pos_coords, entry_coords = self._set_parameter_value('x_position', 'x_pos_input.png', values)
            
            if entry_coords:
                last_set_entry_coords = entry_coords
        
        if x_pos_coords:
            y_search_region = (int(x_pos_coords[0] - 150), int(x_pos_coords[1] + 5), 300, 75)
            target_y = values.get('y_position')
            default_y = AutomationSettings.DEFAULT_TEXTURE_VALUES.get('y_position')
            
            if target_y is not None and default_y is not None and abs(target_y - default_y) < 1e-4:
                self.vision.log(f"  - Skipping 'y_position' as its value ({target_y:.3f}) matches the default.")
            else:
                _, entry_coords = self._set_parameter_value('y_position', 'y_pos_input.png', values, region=y_search_region)
                
                if entry_coords:
                    last_set_entry_coords = entry_coords
            self.vision.log(f"y_search_region: {y_search_region}")
        else:
            self.vision.log("  - Skipping Y position because X position was not found.")
        
        if is_last_slot:
            if last_set_entry_coords:
                self.vision.log("  - Applying final click to confirm last input.")
                final_click_point = (last_set_entry_coords[0] - 30, last_set_entry_coords[1])
                self.controller.click(final_click_point)
            else:
                self.vision.log("  - No numeric parameters were set for the last slot, skipping final confirmation click.")
        
        if values.get('h_flip'):
            self.controller.click(self.vision.find_image('h_flip.png'))
        
        if values.get('v_flip'):
            self.controller.click(self.vision.find_image('v_flip.png'))
        
        for key in ['h_repeat', 'v_repeat']:
            target_value = values.get(key, False)
            default_value = AutomationSettings.DEFAULT_TEXTURE_VALUES.get(key)
            
            if target_value == default_value:
                self.vision.log(f"  - Skipping '{key}' as its value ({target_value}) matches the default.")
            else:
                self._set_checkbox_state(key, target_value)
    
    def _set_parameter_value(self, key, template_name, values, region=None):
        if key not in values:
            return None, None
        label_coords = self._wait_for_element(
            template_name, timeout=AutomationSettings.GENERIC_ELEMENT_TIMEOUT, region=region
        )
        
        if label_coords:
            try:
                template_path = self.vision.get_localized_template_path(template_name)
                with Image.open(template_path) as img: img_width, _ = img.size
                right_edge = label_coords[0] + (img_width / 2)
                click_x = right_edge + 5
                click_y = label_coords[1]
                self.controller.click((click_x, click_y), clicks=3, interval=0.1)
                self.controller.write(f"{values[key]:.3f}")
                return label_coords, (click_x, click_y)
            except (IndexError, TypeError, FileNotFoundError):
                 self.vision.log(f"  - Error processing parameter {key}. Could not calculate click position.")
        else:
            self.vision.log(f"  - Could not find label '{template_name}' for parameter '{key}'.")
        return None, None
    
    def _set_checkbox_state(self, base_name, should_be_checked):
        self._check_for_stop()
        on_template, off_template = f'{base_name}_on.png', f'{base_name}_off.png'
        off_coords = self.vision.find_image(off_template)
        
        if not off_coords:
            self.vision.log(f"  - Warning: Could not locate checkbox element using '{off_template}'. Skipping.")
            return
        check_region = (int(off_coords[0] - 25), int(off_coords[1] - 25), int(off_coords[0] + 325), int(off_coords[1] + 25))
        is_on = self.vision.find_image(on_template, region=check_region) is not None
        action_needed = (should_be_checked and not is_on) or \
                        (not should_be_checked and is_on)
        
        if action_needed:
            self.vision.log(f"  - Checkbox '{base_name}' state is incorrect. Clicking to change.")
            try:
                template_path = self.vision.get_localized_template_path(off_template)
                with Image.open(template_path) as img: img_width, _ = img.size
                right_edge = off_coords[0] + (img_width / 2)
                click_x = right_edge - 5
                click_y = off_coords[1]
                self.controller.click((click_x, click_y))
            except (IndexError, TypeError, FileNotFoundError):
                 self.vision.log(f"  - Error setting checkbox state for '{base_name}'. Could not calculate click position.")
        else:
            self.vision.log(f"  - Checkbox '{base_name}' state is already correct.")
