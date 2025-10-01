import pyautogui
import time


class Controller:
    """
    Handles all mouse and keyboard simulation.
    """
    def __init__(self):
        self.action_delay = 0.1
        self.action_region = None
        self.log = print
    
    def click(self, coords, clicks=1, interval=0.1):
        """
        Moves to coordinates and clicks.
        """
        
        if not coords:
            self.log("  - Click skipped: coordinates are None.")
            return
        x, y = coords
        self.log(f"  - Clicking at ({x}, {y})")
        pyautogui.moveTo(x, y, duration=0.1)
        pyautogui.click(clicks=clicks, interval=interval)
        time.sleep(self.action_delay)
    
    def write(self, text, interval=0.01):
        """
        Types a string of text.
        """
        self.log(f"  - Typing: '{text[:30]}...'")
        pyautogui.write(text, interval=interval)
        time.sleep(self.action_delay)
    
    def press(self, key):
        """
        Presses a single key.
        """
        self.log(f"  - Pressing key: '{key}'")
        pyautogui.press(key)
        time.sleep(self.action_delay)
    
    def key_down(self, key):
        """
        Presses and holds a key down.
        """
        self.log(f"  - Key down: '{key}'")
        pyautogui.keyDown(key)
        time.sleep(self.action_delay)
    
    def key_up(self, key):
        """
        Releases a key.
        """
        self.log(f"  - Key up: '{key}'")
        pyautogui.keyUp(key)
        time.sleep(self.action_delay)
    
    def scroll(self, amount, x=None, y=None):
        """
        Scrolls the mouse wheel.
        """
        self.log(f"  - Scrolling by {amount} units.")
        pyautogui.scroll(amount, x, y)
        time.sleep(self.action_delay)
    
    def hotkey(self, *args):
        """
        Presses multiple keys simultaneously (e.g., for shortcuts like Ctrl+V).
        """
        self.log(f"  - Pressing hotkey: '{'+'.join(args)}'")
        pyautogui.hotkey(*args)
        time.sleep(self.action_delay)
