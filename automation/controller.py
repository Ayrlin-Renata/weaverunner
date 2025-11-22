import pyautogui
import time
from .exceptions import AutomationStoppedError


class Controller:
    """
    Handles all mouse and keyboard simulation.
    """
    def __init__(self):
        self.action_delay = 0.1
        self.action_region = None
        self.log = print
        self.stop_event = None
    
    def _check_stop(self):
        if self.stop_event and self.stop_event.is_set():
            raise AutomationStoppedError("Automation stopped during a controller action.")
    
    def _interruptible_sleep(self, duration):
        """
        A sleep that can be interrupted by the stop event.
        """
        
        if duration <= 0:
            return
        end_time = time.time() + duration
        
        while time.time() < end_time:
            self._check_stop()
            remaining = end_time - time.time()
            
            if remaining > 0:
                time.sleep(min(0.05, remaining))
    
    def click(self, coords, clicks=1, interval=0.1):
        """
        Moves to coordinates and clicks, checking for stop event between clicks.
        """
        
        if not coords:
            self.log("  - Click skipped: coordinates are None.")
            return
        x, y = coords
        self.log(f"  - Clicking at ({x}, {y}) {clicks} time(s)")
        pyautogui.moveTo(x, y, duration=0.1)
        self._check_stop()
        
        for i in range(clicks):
            pyautogui.click()
            self._check_stop()
            
            if i < clicks - 1:
                self._interruptible_sleep(interval)
        self._interruptible_sleep(self.action_delay)
    
    def write(self, text, interval=0.01):
        """
        Types a string of text, checking for stop event between characters.
        """
        self.log(f"  - Typing: '{text[:30]}...'")
        
        for char in text:
            self._check_stop()
            pyautogui.write(char)
            
            if interval > 0:
                self._interruptible_sleep(interval)
        self._interruptible_sleep(self.action_delay)
    
    def press(self, key):
        """
        Presses a single key.
        """
        self.log(f"  - Pressing key: '{key}'")
        self._check_stop()
        pyautogui.press(key)
        self._interruptible_sleep(self.action_delay)
    
    def key_down(self, key):
        """
        Presses and holds a key down.
        """
        self.log(f"  - Key down: '{key}'")
        pyautogui.keyDown(key)
    
    def key_up(self, key):
        """
        Releases a key.
        """
        self.log(f"  - Key up: '{key}'")
        pyautogui.keyUp(key)
    
    def scroll(self, amount, x=None, y=None):
        """
        Scrolls the mouse wheel.
        """
        self.log(f"  - Scrolling by {amount} units.")
        self._check_stop()
        pyautogui.scroll(amount, x, y)
        self._interruptible_sleep(self.action_delay)
    
    def hotkey(self, *args):
        """
        Presses multiple keys simultaneously (e.g., for shortcuts like Ctrl+V).
        """
        self.log(f"  - Pressing hotkey: '{'+'.join(args)}'")
        self._check_stop()
        pyautogui.hotkey(*args)
        self._interruptible_sleep(self.action_delay)
