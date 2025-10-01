import os
import sys
import customtkinter as ctk

if not getattr(sys, 'frozen', False):
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
from utils.preset_manager import PresetManager
from automation.workflows import WorkflowManager
from ui.main_window import App


def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller
    """
    
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    assets_path = resource_path(os.path.join('assets', 'templates'))
    preset_manager = PresetManager()
    workflow_manager = WorkflowManager(assets_path)
    app = App(preset_manager, workflow_manager)
    try:
        icon_path = resource_path('assets/icon.ico')
        app.iconbitmap(icon_path)
    except Exception:
        pass
    
    app.mainloop()
