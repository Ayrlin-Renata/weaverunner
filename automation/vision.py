import pyautogui
import cv2
from pyscreeze import Box
import numpy as np
import pyscreeze
import os
import mss
from PIL import Image
import screeninfo
import threading
import easyocr
import re


class Vision:
    def __init__(self, assets_path):
        self.assets_path = assets_path
        self.language = 'en'
        self.app_region = None
        self.log = print
        self.thread_local = threading.local()
        self.debug_mode = False
    
    @property
    def sct(self):
        """
        Lazy-loads the MSS screenshot utility instance for the current thread.
        """
        
        if not hasattr(self.thread_local, 'sct') or self.thread_local.sct is None:
            self.log("Initializing MSS for this thread...")
            try:
                self.thread_local.sct = mss.mss()
            except Exception as e:
                self.log(f"CRITICAL: Failed to initialize MSS for this thread. Error: {e}")
                self.thread_local.sct = None
        return self.thread_local.sct
    
    @property
    def reader(self):
        """
        Lazy-loads the EasyOCR reader instance.
        This is to ensure it's initialized in the same thread that uses it, avoiding
        potential cross-thread GDI issues on Windows. Uses thread-local storage to
        maintain a separate reader instance per thread.
        """
        
        if not hasattr(self.thread_local, 'reader') or self.thread_local.reader is None:
            self.log("Initializing EasyOCR Reader for this thread...")
            try:
                self.thread_local.reader = easyocr.Reader(['en', 'ja'], gpu=True)
                self.log("EasyOCR Reader initialized with GPU support.")
            except Exception as e:
                self.log(f"WARNING: Could not initialize EasyOCR with GPU support. Falling back to CPU. Error: {e}")
                try:
                    self.thread_local.reader = easyocr.Reader(['en', 'ja'], gpu=False)
                    self.log("EasyOCR Reader initialized with CPU support.")
                except Exception as e2:
                    self.log(f"CRITICAL: Failed to initialize EasyOCR on CPU as well. Error: {e2}")
                    self.thread_local.reader = None
        return self.thread_local.reader
    
    def set_language(self, lang_code):
        self.language = lang_code
        self.log(f"Vision language set to: {self.language}")
    
    def set_debug_mode(self, enabled):
        self.debug_mode = enabled
        
        if enabled:
            self.log("Debug mode enabled. Saving diagnostic images.")
    
    def get_localized_template_path(self, template_name):
        """
        Constructs a path to a localized template if it exists, otherwise falls back to the base template.
        """
        localized_templates = {
            'angle_input.png', 'choose_file_button.png', 'h_repeat_on.png',
            'h_repeat_off.png', 'v_repeat_on.png', 'v_repeat_off.png',
            'opacity_input.png', 'remove_button.png', 'remove_confirm_button.png',
            'size_input.png', 'x_pos_input.png', 'y_pos_input.png'
        }
        
        if template_name in localized_templates:
            base, ext = os.path.splitext(template_name)
            localized_name = f"{base}_{self.language}{ext}"
            localized_path = os.path.join(self.assets_path, localized_name)
            
            if os.path.exists(localized_path):
                return localized_path
        return os.path.join(self.assets_path, template_name)
    
    def screenshot(self, region=None):
        """
        Public method to take a screenshot using the configured backend (MSS).
        Returns a PIL Image.
        """
        
        if not self.sct:
            self.log("CRITICAL: Screenshot utility not initialized.")
            return None
        try:
            if region:
                if region[2] <= 0 or region[3] <= 0:
                    self.log(f"  - ERROR: Invalid screenshot region with non-positive dimensions: {region}")
                    return None
                monitor = {'top': int(region[1]), 'left': int(region[0]), 'width': int(region[2]), 'height': int(region[3])}
                sct_img = self.sct.grab(monitor)
                return Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
            else:
                sct_img = self.sct.grab(self.sct.monitors[0])
                return Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
        except mss.exception.ScreenShotError as e:
            self.log(f"  - ERROR: MSS failed to take screenshot for region {region}. Error: {e}")
            return None
    
    def find_image(self, template_name, region=None, confidence=0.8):
        """
        Finds the first occurrence of a template image and returns its center point.
        Searches all monitors if no region is specified.
        """
        template_path = self.get_localized_template_path(template_name)
        display_name = os.path.basename(template_path)
        
        if not os.path.exists(template_path):
            self.log(f"  - ERROR: Template image not found at {template_path}")
            return None
        search_regions = []
        
        if region:
            search_regions.append(region)
        elif self.app_region:
            search_regions.append(self.app_region)
        else:
            self.log("  - No region specified. Searching all monitors for center.")
            
            for m in screeninfo.get_monitors():
                search_regions.append((m.x, m.y, m.width, m.height))
        debug_dir = None
        
        if self.debug_mode:
            project_root = os.path.abspath(os.path.join(self.assets_path, "..", ".."))
            debug_dir = os.path.join(project_root, 'debug')
            os.makedirs(debug_dir, exist_ok=True)
        
        for i, current_region in enumerate(search_regions):
            self.log(f"  - Analyzing region: {current_region}")
            try:
                haystack_image = self.screenshot(region=current_region)
                
                if self.debug_mode:
                    haystack_image.save(os.path.join(debug_dir, f"haystack_color_{display_name}_region_{i}.png"))
            except (mss.exception.ScreenShotError, AttributeError) as e:
                self.log(f"  - ERROR: Failed to take screenshot for region {current_region}: {e}")
                continue
            
            left, top, _, _ = current_region
            try:
                location_box = pyscreeze.locate(template_path, haystack_image, confidence=confidence)
                
                if location_box:
                    center_x = location_box.left + location_box.width / 2
                    center_y = location_box.top + location_box.height / 2
                    abs_x = center_x + left
                    abs_y = center_y + top
                    location = pyautogui.Point(int(abs_x), int(abs_y))
                    self.log(f"  - Found '{display_name}' at {location} in region {current_region}")
                    return location
            except pyscreeze.ImageNotFoundException:
                self.log(f"  - PyAutoGUI: '{display_name}' center not found in this region.")
            except Exception as e:
                self.log(f"  - PyAutoGUI error on cropped image for region {current_region}: {e}. Trying OpenCV.")
            
            try:
                haystack_gray = cv2.cvtColor(np.array(haystack_image), cv2.COLOR_RGB2GRAY)
                
                if self.debug_mode:
                    cv2.imwrite(os.path.join(debug_dir, f"haystack_gray_{display_name}_region_{i}.png"), haystack_gray)
                original_template_color = cv2.imread(template_path, cv2.IMREAD_COLOR)
                
                if original_template_color is None: continue
                scales_to_try = [1.0, 1.25, 0.75, 1.5]
                best_confidence_in_region = -1.0
                best_match_info = None
                
                for scale in scales_to_try:
                    if scale == 1.0:
                        template_color = original_template_color
                    else:
                        width = int(original_template_color.shape[1] * scale)
                        height = int(original_template_color.shape[0] * scale)
                        
                        if width < 1 or height < 1: continue
                        template_color = cv2.resize(original_template_color, (width, height), interpolation=cv2.INTER_AREA)
                    template_gray = cv2.cvtColor(template_color, cv2.COLOR_BGR2GRAY)
                    
                    if self.debug_mode:
                        cv2.imwrite(os.path.join(debug_dir, f"template_{display_name}_scale_{scale:.2f}.png"), template_gray)
                    
                    if template_gray.shape[0] > haystack_gray.shape[0] or template_gray.shape[1] > haystack_gray.shape[1]:
                        continue
                    res = cv2.matchTemplate(haystack_gray, template_gray, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    
                    if max_val > best_confidence_in_region:
                        best_confidence_in_region = max_val
                        
                        if max_val >= confidence:
                            best_match_info = (max_val, max_loc, template_gray.shape, scale)
                self.log(f"  - OpenCV: Max confidence for '{display_name}' center in this region is {best_confidence_in_region:.3f}.")
                
                if best_match_info:
                    max_val, max_loc, shape, scale = best_match_info
                    self.log(f"  - OpenCV: Found match for '{display_name}' center with scale {scale:.2f} (confidence: {max_val:.3f}).")
                    w, h = shape[1], shape[0]
                    center_x = max_loc[0] + w // 2 + left
                    center_y = max_loc[1] + h // 2 + top
                    return pyautogui.Point(int(center_x), int(center_y))
            except Exception as e:
                self.log(f"  - OpenCV error finding image in region {current_region}: {e}")
        return None
    
    def find_all_images(self, template_name, region=None, confidence=0.8):
        """
        Finds all occurrences of a template image within a region using OpenCV.
        Returns a list of center points.
        """
        template_path = self.get_localized_template_path(template_name)
        display_name = os.path.basename(template_path)
        
        if not os.path.exists(template_path):
            self.log(f"  - ERROR: Template image not found at {template_path}")
            return []
        search_region = region
        
        if search_region is None:
            search_region = self.app_region
        
        if search_region is None:
            self.log(f"  - ERROR in find_all_images: No search region provided for '{display_name}'.")
            return []
        try:
            haystack_image = self.screenshot(region=search_region)
            
            if not haystack_image:
                self.log(f"  - ERROR in find_all_images: Failed to get screenshot for region {search_region}.")
                return []
            left, top, width, height = search_region
            screenshot_cv = cv2.cvtColor(np.array(haystack_image), cv2.COLOR_RGB2BGR)
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            
            if template is None: return []
            
            if screenshot_cv.shape[0] < template.shape[0] or screenshot_cv.shape[1] < template.shape[1]:
                 self.log(f"  - WARNING in find_all_images: Template '{display_name}' is larger than the screenshot of region {search_region}. This may be a DPI scaling issue.")
                 return []
            w, h = template.shape[1], template.shape[0]
            res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            locs = np.where(res >= confidence)
            points = []
            
            for pt in zip(*locs[::-1]):
                center_x = pt[0] + w // 2 + left
                center_y = pt[1] + h // 2 + top
                points.append(pyautogui.Point(int(center_x), int(center_y)))
            
            if not points:
                return []
            filtered_points = [points[0]]
            
            for pt in points[1:]:
                is_far_enough = all(np.linalg.norm(np.array(pt) - np.array(fpt)) > 15 for fpt in filtered_points)
                
                if is_far_enough:
                    filtered_points.append(pt)
            
            if filtered_points:
                self.log(f"  - Found {len(filtered_points)} instances of '{display_name}'.")
            return filtered_points
        except Exception as e:
            self.log(f"  - An unexpected error occurred in find_all_images: {e}")
            return []
    
    def find_image_box(self, template, region=None, confidence=0.8):
        """
        Finds an image and returns its bounding box (left, top, width, height).
        The template can be a path (string) or a PIL Image object.
        Searches all monitors if no region is specified.
        """
        display_name = "PIL Image"
        template_path = None
        image_to_find = template
        
        if isinstance(template, str):
            template_path = self.get_localized_template_path(template)
            display_name = os.path.basename(template_path)
            
            if not os.path.exists(template_path):
                self.log(f"  - ERROR: Template image not found at {template_path}")
                return None
            image_to_find = template_path
        search_regions = []
        
        if region:
            search_regions.append(region)
        elif self.app_region:
            search_regions.append(self.app_region)
        else:
            self.log("  - No region specified. Searching all monitors individually.")
            
            for m in screeninfo.get_monitors():
                search_regions.append((m.x, m.y, m.width, m.height))
        debug_dir = None
        
        if self.debug_mode:
            project_root = os.path.abspath(os.path.join(self.assets_path, "..", ".."))
            debug_dir = os.path.join(project_root, 'debug')
            os.makedirs(debug_dir, exist_ok=True)
        
        for i, current_region in enumerate(search_regions):
            self.log(f"  - Analyzing region: {current_region}")
            try:
                haystack_image = self.screenshot(region=current_region)
                
                if self.debug_mode:
                    haystack_image.save(os.path.join(debug_dir, f"haystack_color_{display_name}_region_{i}.png"))
            except (mss.exception.ScreenShotError, AttributeError) as e:
                self.log(f"  - ERROR: Failed to take screenshot for region {current_region}: {e}")
                continue
            
            left, top, _, _ = current_region
            try:
                location = pyscreeze.locate(image_to_find, haystack_image, confidence=confidence)
                
                if location:
                    abs_left = location.left + left
                    abs_top = location.top + top
                    box = (abs_left, abs_top, location.width, location.height)
                    self.log(f"  - Found '{display_name}' box at {Box(*box)} in region {current_region}")
                    return box
            except pyscreeze.ImageNotFoundException:
                self.log(f"  - PyAutoGUI: '{display_name}' box not found in this region.")
            except Exception as e:
                self.log(f"  - PyAutoGUI error on cropped image for region {current_region}: {e}. Trying OpenCV.")
            
            try:
                haystack_gray = cv2.cvtColor(np.array(haystack_image), cv2.COLOR_RGB2GRAY)
                
                if self.debug_mode:
                    cv2.imwrite(os.path.join(debug_dir, f"haystack_gray_{display_name}_region_{i}.png"), haystack_gray)
                
                if isinstance(template, str):
                    original_template_color = cv2.imread(template_path, cv2.IMREAD_COLOR)
                else:
                    original_template_color = cv2.cvtColor(np.array(template), cv2.COLOR_RGB2BGR)
                
                if original_template_color is None: continue
                scales_to_try = [1.0, 1.25, 0.75, 1.5]
                best_confidence_in_region = -1.0
                best_match_info = None
                
                for scale in scales_to_try:
                    if scale == 1.0:
                        template_color = original_template_color
                    else:
                        width = int(original_template_color.shape[1] * scale)
                        height = int(original_template_color.shape[0] * scale)
                        
                        if width < 1 or height < 1: continue
                        template_color = cv2.resize(original_template_color, (width, height), interpolation=cv2.INTER_AREA)
                    template_gray = cv2.cvtColor(template_color, cv2.COLOR_BGR2GRAY)
                    
                    if self.debug_mode:
                        cv2.imwrite(os.path.join(debug_dir, f"template_{display_name}_scale_{scale:.2f}.png"), template_gray)
                    
                    if template_gray.shape[0] > haystack_gray.shape[0] or template_gray.shape[1] > haystack_gray.shape[1]:
                        continue
                    res = cv2.matchTemplate(haystack_gray, template_gray, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    
                    if max_val > best_confidence_in_region:
                        best_confidence_in_region = max_val
                        
                        if max_val >= confidence:
                             best_match_info = (max_val, max_loc, template_gray.shape, scale)
                self.log(f"  - OpenCV: Max confidence for '{display_name}' box in this region is {best_confidence_in_region:.3f}.")
                
                if best_match_info:
                    max_val, max_loc, shape, scale = best_match_info
                    self.log(f"  - OpenCV: Found match for '{display_name}' box with scale {scale:.2f} (confidence: {max_val:.3f}).")
                    w, h = shape[1], shape[0]
                    abs_left = int(max_loc[0] + left)
                    abs_top = int(max_loc[1] + top)
                    return (abs_left, abs_top, int(w), int(h))
            except Exception as e:
                self.log(f"  - OpenCV error finding image box in region {current_region}: {e}")
        return None
    
    def get_text_from_region(self, region):
        """
        Reads text from a specific region of the screen.
        """
        
        if not self.reader:
            self.log("OCR reader not available.")
            return ""
        try:
            screenshot = self.screenshot(region=region)
            
            if not screenshot:
                self.log(f"An error occurred during OCR: Failed to get screenshot for region {region}.")
                return ""
            screenshot_np = np.array(screenshot)
            result = self.reader.readtext(screenshot_np)
            return " ".join([item[1] for item in result])
        except (mss.exception.ScreenShotError, AttributeError, Exception) as e:
            self.log(f"An error occurred during OCR: {e}")
            return ""
    
    def find_text_on_screen(self, text_to_find, region=None):
        """
        Finds all potential matches for text on screen, scores them, and returns a list of candidates.
        Prioritizes exact, whole-word matches.
        """
        
        if not self.reader:
            self.log("OCR reader not available.")
            return []
        self.log(f"Reading text from region: {region or 'Full Screen'}")
        try:
            screenshot = self.screenshot(region=region)
            
            if not screenshot:
                self.log(f"An error occurred during find_text_on_screen: Failed to get screenshot for region {region}.")
                return []
            screenshot_np = np.array(screenshot)
            results = self.reader.readtext(screenshot_np)
            potential_matches = []
            
            for (bbox, text, prob) in results:
                score = 0
                
                if re.search(r'\b' + re.escape(text_to_find) + r'\b', text, re.IGNORECASE):
                    if text_to_find == text:
                        score = 1.0
                    elif text_to_find.lower() == text.lower():
                        score = 0.95
                    else:
                        score = 0.9 - (len(text) - len(text_to_find)) * 0.1
                    
                    if score > 0:
                        self.log(f"  - Found potential match '{text}' for '{text_to_find}' with score {score:.2f}")
                        (tl, tr, br, bl) = bbox
                        left = int(tl[0] + (region[0] if region else 0))
                        top = int(tl[1] + (region[1] if region else 0))
                        width = int(tr[0] - tl[0])
                        height = int(bl[1] - tl[1])
                        potential_matches.append({'score': score, 'bbox': (left, top, width, height), 'text': text})
                else:
                    self.log(f"  - Found non-matching text '{text}'")
            return sorted(potential_matches, key=lambda x: x['score'], reverse=True)
        except (mss.exception.ScreenShotError, AttributeError, Exception) as e:
            self.log(f"An error occurred during find_text_on_screen: {e}")
        
        return []
