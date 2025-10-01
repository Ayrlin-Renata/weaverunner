import pyautogui
import cv2
import numpy as np
import os
import easyocr


class Vision:
    def __init__(self, assets_path):
        self.assets_path = assets_path
        self.language = 'en'
        self.app_region = None
        self.log = print
        try:
            self.reader = easyocr.Reader(['en', 'ja'], gpu=True)
            self.log("EasyOCR Reader initialized with GPU support.")
        except Exception as e:
            self.log(f"WARNING: Could not initialize EasyOCR with GPU support. Falling back to CPU. Error: {e}")
            try:
                self.reader = easyocr.Reader(['en', 'ja'], gpu=False)
                self.log("EasyOCR Reader initialized with CPU support.")
            except Exception as e2:
                 self.log(f"CRITICAL: Failed to initialize EasyOCR on CPU as well. Error: {e2}")
                 self.reader = None
    
    def set_language(self, lang_code):
        self.language = lang_code
        self.log(f"Vision language set to: {self.language}")
    
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
    
    def find_image(self, template_name, region=None, confidence=0.8):
        """
        Finds the first occurrence of a template image on the screen and returns its center point.
        """
        template_path = self.get_localized_template_path(template_name)
        display_name = os.path.basename(template_path)
        
        if not os.path.exists(template_path):
            self.log(f"  - ERROR: Template image not found at {template_path}")
            return None
        
        if region is None:
            region = self.app_region
        try:
            location = pyautogui.locateCenterOnScreen(template_path, region=region, confidence=confidence)
            
            if location:
                self.log(f"  - Found '{display_name}' at {location}")
                return location
        except pyautogui.ImageNotFoundException:
            pass
        except Exception as e:
            self.log(f"  - PyAutoGUI error finding '{display_name}': {e}. Trying OpenCV method.")
        
        try:
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            
            if template is None: return None
            res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= confidence:
                w, h = template.shape[1], template.shape[0]
                center_x = max_loc[0] + w // 2 + (region[0] if region else 0)
                center_y = max_loc[1] + h // 2 + (region[1] if region else 0)
                location = pyautogui.Point(int(center_x), int(center_y))
                self.log(f"  - Found '{display_name}' via OpenCV at {location}")
                return location
        except Exception as e:
            self.log(f"  - OpenCV error finding image: {e}")
        
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
        
        if region is None:
            region = self.app_region
        try:
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            w, h = template.shape[1], template.shape[0]
            res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            locs = np.where(res >= confidence)
            points = []
            
            for pt in zip(*locs[::-1]):
                center_x = pt[0] + w // 2 + (region[0] if region else 0)
                center_y = pt[1] + h // 2 + (region[1] if region else 0)
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
        
        if region is None:
            region = self.app_region
        try:
            location = pyautogui.locateOnScreen(image_to_find, region=region, confidence=confidence)
            
            if location:
                self.log(f"  - Found '{display_name}' box at {location}")
                return tuple(location)
        except pyautogui.ImageNotFoundException:
            pass
        except Exception as e:
            self.log(f"  - PyAutoGUI error finding '{display_name}': {e}. Trying OpenCV method.")
        
        try:
            screenshot = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            template_cv = cv2.imread(template_path, cv2.IMREAD_COLOR) if isinstance(template, str) else cv2.cvtColor(np.array(template), cv2.COLOR_RGB2BGR)
            
            if template_cv is None: return None
            res = cv2.matchTemplate(screenshot_cv, template_cv, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= confidence:
                w, h = template_cv.shape[1], template_cv.shape[0]
                left = int(max_loc[0] + (region[0] if region else 0))
                top = int(max_loc[1] + (region[1] if region else 0))
                return (left, top, w, h)
        except Exception as e:
            self.log(f"  - OpenCV error finding image box: {e}")
        
        return None
    
    def get_text_from_region(self, region):
        """
        Reads text from a specific region of the screen.
        """
        
        if not self.reader:
            self.log("OCR reader not available.")
            return ""
        try:
            screenshot = pyautogui.screenshot(region=region)
            screenshot_np = np.array(screenshot)
            result = self.reader.readtext(screenshot_np)
            return " ".join([item[1] for item in result])
        except Exception as e:
            self.log(f"An error occurred during OCR: {e}")
            return ""
    
    def find_text_on_screen(self, text_to_find, region=None):
        """
        Finds text on screen and returns the bounding box of the first match.
        """
        
        if not self.reader:
            self.log("OCR reader not available.")
            return None
        self.log(f"Reading text from region: {region or 'Full Screen'}")
        try:
            screenshot = pyautogui.screenshot(region=region)
            screenshot_np = np.array(screenshot)
            results = self.reader.readtext(screenshot_np)
            
            for (bbox, text, prob) in results:
                if text_to_find.lower() in text.lower():
                    self.log(f"  - Found matching text '{text}' with bounding box: {bbox}")
                    (tl, tr, br, bl) = bbox
                    left = int(tl[0] + (region[0] if region else 0))
                    top = int(tl[1] + (region[1] if region else 0))
                    width = int(tr[0] - tl[0])
                    height = int(bl[1] - tl[1])
                    return (left, top, width, height)
                else:
                    self.log(f"  - Found some text '{text}' with bounding box: {bbox}")
        except Exception as e:
            self.log(f"An error occurred during find_text_on_screen: {e}")
        
        return None
