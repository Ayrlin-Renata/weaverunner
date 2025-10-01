class AutomationSettings:
    """
    Centralized configuration for automation timings and default values.
    Tuning these values can improve performance and reliability.
    """
    MENU_TIMEOUT = 2.0
    DIALOG_TIMEOUT = 3.0
    CHOOSE_FILE_TIMEOUT = 3.0
    GENERIC_ELEMENT_TIMEOUT = 5.0
    POST_UPLOAD_DIALOG_DELAY = 0.8
    POST_UPLOAD_FINISH_DELAY = 0.0
    POST_PASTE_DELAY = 0.0
    POST_SETTING_APPLIED_DELAY = 0.0
    POST_REMOVAL_DELAY = 0.2
    SCROLL_DELAY = 0.25
    DEFAULT_TEXTURE_VALUES = {
        "size": 0.5, "angle": 0.0, "x_position": 0.5, "y_position": 0.5, "opacity": 1.0,
        "h_repeat": False,
        "v_repeat": False,
    }
    CACHE_REGION_SIZE = 150
