import time
import threading
import screeninfo
from pyscreeze import Box
import numpy as np
from automation.vision import Vision
from automation.controller import Controller
from automation.automation_config import AutomationSettings
from .exceptions import AutomationStoppedError, UIVisibilityError, FastApplyError
from .actions import group_actions, removal_actions, state_actions, texture_actions, ui_helpers


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
        self.controller.stop_event = self.stop_event
        
        if is_full_run:
            log_callback("Full Apply detected. Clearing group header image cache.")
            self.group_header_cache.clear()
        log_callback("Starting automation workflow...")
        try:
            removed_slots_by_group = {}
            
            if is_full_run:
                removal_actions.process_removals_full(self, texture_slots_data)
            else:
                removed_slots_by_group = removal_actions.process_removals_fast(self, texture_slots_data, old_texture_map)
            self._check_for_stop()
            slots_to_manage = [s for s in texture_slots_data if s['mode'] == 'Managed' and s.get('is_updated', False)]
            uploaded_slots_by_group = texture_actions.manage_textures(self, slots_to_manage)
            
            if is_full_run:
                new_texture_map = state_actions.compute_new_texture_map_from_ui(self, texture_slots_data)
            else:
                new_texture_map = state_actions.compute_new_texture_map_from_ops(self, old_texture_map, removed_slots_by_group, uploaded_slots_by_group)
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
    
    def _interruptible_sleep(self, duration):
        """
        A sleep that can be interrupted by the stop event in small intervals.
        """
        end_time = time.time() + duration
        
        while time.time() < end_time:
            self._check_for_stop()
            remaining = end_time - time.time()
            
            if remaining > 0:
                time.sleep(min(0.05, remaining))
    
    def _find_image_with_cache(self, template_name, cache_key, region=None, confidence=0.8):
        """
        Finds an image, prioritizing a cached region if available.
        """
        return ui_helpers.find_image_with_cache(self, template_name, cache_key, region=region, confidence=confidence)
    
    def _select_best_group_match(self, matches):
        """
        Applies heuristics to a list of potential OCR matches to find the best one.
        """
        
        if not matches:
            return None
        return ui_helpers.select_best_group_match(self, matches)
    
    def _wait_for_element(self, template_name, timeout, cache_key=None, region=None, confidence=0.8):
        """
        Waits for a UI element to appear by repeatedly searching for it until a timeout is reached.
        Returns the element's coordinates or raises UIVisibilityError.
        """
        start_time = time.time()
        return ui_helpers.wait_for_element(self, template_name, timeout, start_time, cache_key, region, confidence)
