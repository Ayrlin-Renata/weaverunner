import json
import os
import inspect


class AutomationConfigManager:
    """
    Manages loading and saving of automation settings to a JSON file,
    while using a settings class for defaults.
    """
    def __init__(self, settings_class, config_path='automation_config.json', log_callback=print):
        self.settings_class = settings_class
        self.config_path = config_path
        self.log = log_callback
        self.defaults = self._get_class_defaults()
    
    def _get_class_defaults(self):
        """
        Introspects the settings class to get default values.
        """
        defaults = {}
        
        for name, value in inspect.getmembers(self.settings_class):
            if name.isupper() and name != 'DEFAULT_TEXTURE_VALUES':
                defaults[name] = value
        return defaults
    
    def load_settings(self):
        """
        Loads settings from the JSON file, merges them with defaults,
        and applies them to the live settings class.
        """
        loaded_settings = {}
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    loaded_settings = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        final_settings = self.defaults.copy()
        final_settings.update(loaded_settings)
        
        for key, value in final_settings.items():
            setattr(self.settings_class, key, value)
    
    def save_settings(self):
        """
        Saves the current state of the settings class to the JSON file.
        """
        settings_to_save = {name: getattr(self.settings_class, name) for name in self.defaults}
        try:
            with open(self.config_path, 'w') as f:
                json.dump(settings_to_save, f, indent=4)
        except IOError as e:
            self.log(f"Error: Could not save automation configuration to {self.config_path}. Error: {e}")
