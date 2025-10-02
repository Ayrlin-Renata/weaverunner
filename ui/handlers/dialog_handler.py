from ui.dialogs import (
    PresetManagerDialog,
    UserAgreementDialog,
    AutomationSettingsDialog,
    ClipWatchSettingsDialog
)
from utils.clip_watcher import DOWNSCALING_METHODS


def show_user_agreement(app):
    dialog = UserAgreementDialog(app, i18n=app.i18n, callback=lambda: on_agreement_accepted(app))
    app.wait_window(dialog)


def on_agreement_accepted(app):
    app.log_to_console("User agreement accepted.")
    app.user_agreed = True
    app.config_handler.save_config(app)


def open_preset_manager(app):
    dialog = PresetManagerDialog(app, app=app)
    app.wait_window(dialog)


def open_automation_settings(app):
    dialog = AutomationSettingsDialog(app, i18n=app.i18n, config_manager=app.automation_config_manager)
    app.wait_window(dialog)
