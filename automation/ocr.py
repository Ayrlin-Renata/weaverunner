import threading
import easyocr
import re
import numpy as np


class OCR:
    """
    Handles all Optical Character Recognition tasks using EasyOCR.
    Manages a thread-local reader instance for safety.
    """
    def __init__(self):
        self.log = print
        self.thread_local = threading.local()
    
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
    
    def get_text_from_image(self, image_np):
        """
        Reads all text from a given NumPy image array.
        """
        
        if not self.reader:
            self.log("OCR reader not available.")
            return ""
        try:
            result = self.reader.readtext(image_np)
            return " ".join([item[1] for item in result])
        except Exception as e:
            self.log(f"An error occurred during OCR text extraction: {e}")
            return ""
    
    def find_text_in_image(self, image_np, text_to_find, region_offset=(0, 0)):
        """
        Finds all occurrences of text in a NumPy image array and returns their
        bounding boxes and confidence scores, adjusted by the region offset.
        """
        
        if not self.reader:
            self.log("OCR reader not available.")
            return []
        results = self.reader.readtext(image_np)
        potential_matches = []
        
        for (bbox, text, prob) in results:
            score = 0
            
            if re.search(r'\b' + re.escape(text_to_find) + r'\b', text, re.IGNORECASE):
                score = 1.0 if text_to_find == text else 0.95 if text_to_find.lower() == text.lower() else 0.9 - (len(text) - len(text_to_find)) * 0.1
                
                if score > 0:
                    self.log(f"  - Found potential match '{text}' for '{text_to_find}' with score {score:.2f}")
                    (tl, tr, br, bl) = bbox
                    left = int(tl[0] + region_offset[0])
                    top = int(tl[1] + region_offset[1])
                    width = int(tr[0] - tl[0])
                    height = int(bl[1] - tl[1])
                    potential_matches.append({'score': score, 'bbox': (left, top, width, height), 'text': text})
        return sorted(potential_matches, key=lambda x: x['score'], reverse=True)
