class AutomationStoppedError(Exception):
    """
    Custom exception for when the user stops the automation.
    """
    pass


class UIVisibilityError(Exception):
    """
    Custom exception for when a critical UI element cannot be found or its state is ambiguous.
    """
    pass


class FastApplyError(Exception):
    """
    Custom exception for when Fast Apply cannot proceed safely.
    """
    pass
