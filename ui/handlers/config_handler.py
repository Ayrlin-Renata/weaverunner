import json
import os
import screeninfo


def load_config(app):
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                geom = config.get("window_geometry")
                
                if geom and is_geometry_visible(geom):
                    app.geometry(geom)
                else:
                    center_and_set_default_geometry(app)
                lang = config.get("language", "en")
                app.lang_var.set(lang)
                app.i18n.set_language(lang)
                app.clip_watch_layer_name = config.get("clip_watch_layer_name", "full-export-merge")
                app.user_agreed = config.get("user_agreement", False)
                app.debug_mode_var.set(config.get("debug_mode", False))
                app.workflow_manager.set_debug_mode(app.debug_mode_var.get())
                return not app.user_agreed
    except (json.JSONDecodeError, FileNotFoundError): pass
    
    center_and_set_default_geometry(app)
    app.user_agreed = False
    return True


def center_and_set_default_geometry(app):
    width, height = 950, 950
    screen_width = app.winfo_screenwidth()
    screen_height = app.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    app.geometry(f"{width}x{height}+{x}+{y}")


def save_config(app):
    config = {}
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f: config = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): pass
    
    try:
        config["window_geometry"] = app.geometry()
        config["language"] = app.lang_var.get()
        config["clip_watch_layer_name"] = app.clip_watch_layer_name
        config["user_agreement"] = app.user_agreed
        config["debug_mode"] = app.debug_mode_var.get()
        with open('config.json', 'w') as f: json.dump(config, f, indent=4)
    except IOError:
        app.log_to_console("Error: Could not save configuration.")


def is_geometry_visible(geom):
    try:
        _, _, x, y = map(int, geom.replace('+', ' ').replace('x', ' ').split())
        return any(m.x <= x < m.x + m.width and m.y <= y < m.y + m.height for m in screeninfo.get_monitors())
    except Exception: return False
