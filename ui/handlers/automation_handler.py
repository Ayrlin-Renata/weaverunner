import keyboard
import os
from utils.file_watcher import normalize_path


def automation_worker(app):
    """
    A long-running worker thread that waits for and processes automation jobs.
    Initializes its own instances of thread-sensitive libraries (via Vision properties).
    """
    app.log_to_console_safe("Automation worker: Initializing libraries...")
    app.workflow_manager.vision.initialize_dependencies()
    app.log_to_console_safe("Automation worker: Libraries initialized. Ready for jobs.")
    
    while True:
        job = app.automation_job_queue.get()
        
        if job is None:
            app.log_to_console_safe("Automation worker thread shutting down.")
            break
        slots_data, texture_map, is_full_run, log_callback = job
        result = app.workflow_manager.run(slots_data, texture_map, is_full_run, log_callback)
        app.automation_result_queue.put(result)


def run_automation_thread(app, full_run=False):
    app.log_to_console("Finding application window anchor...")
    app.workflow_manager.set_language(app.i18n.language)
    monitor = app.workflow_manager.find_app_window_and_set_region()
    
    if not monitor:
        app.status_bar.set_status('status_error_anchor', level='error')
        return
    app.status_bar.set_status('status_found_anchor', level='info', monitor_name=monitor.name)
    app.log_to_console("App window located successfully.")
    slots_data = []
    has_updatable_action = False
    
    for slot in app.texture_slots:
        slot_data = slot.get_data()
        is_new_to_group = (
            slot_data['group'] and
            slot_data['slot_id'] not in app.texture_map.get(slot_data['group'], [])
        )
        is_updated = (
            app.is_first_apply or full_run or
            (normalize_path(slot.image_path) in app.updated_image_paths) or
            (slot_data['mode'] == 'Managed' and is_new_to_group)
        )
        slot_data['is_updated'] = is_updated
        
        if slot_data['mode'] == 'Managed' and is_updated:
            has_updatable_action = True
        
        if slot_data['mode'] == 'Managed':
            if not slot_data['image_path']:
                app.status_bar.set_status('status_warn_no_image', level='warning', slot_id=slot_data['slot_id']+1)
                return
            
            if not slot_data['group']:
                app.status_bar.set_status('status_warn_no_group', level='warning', slot_id=slot_data['slot_id']+1)
                app.log_to_console(f"Aborting: Slot {slot_data['slot_id']+1} is Managed but has no group name.")
                return
            
            if not slot.is_512x512:
                 app.status_bar.set_status('status_warn_not_512', level='warning', slot_id=slot_data['slot_id']+1)
                 return
        slots_data.append(slot_data)
    
    if not full_run and not has_updatable_action:
        app.status_bar.set_status('status_no_updates')
        app.log_to_console(app.i18n.t('status_no_updates'))
        return
    app.is_automation_running = True
    app.fast_apply_button.configure(state="disabled", text=app.i18n.t('apply_button_running'))
    app.full_apply_button.configure(state="disabled")
    app.status_bar.set_status('status_running', level='running')
    app.stop_hotkey_id = keyboard.add_hotkey('esc', app.emergency_stop)
    is_full_run = app.is_first_apply or full_run
    job = (slots_data, app.texture_map, is_full_run, app.log_to_console)
    app.automation_job_queue.put(job)
    app.monitor_automation_thread()


def monitor_automation_thread(app):
    if not app.automation_result_queue.empty():
        result_tuple = app.automation_result_queue.get()
        status = result_tuple[0] if result_tuple else False
        
        if status is True:
            app.is_first_apply = False
            app.updated_image_paths.clear()
            app.texture_map = result_tuple[1]
        app.automation_finished(status=status)
    else:
        app.after(100, app.monitor_automation_thread)


def emergency_stop(app):
    if app.is_automation_running:
        app.log_to_console("EMERGENCY STOP received.")
        app.workflow_manager.request_stop()


def automation_finished(app, status=True):
    app.is_automation_running = False
    app.ui_handler.validate_slots_and_update_ui(app)
    app.fast_apply_button.configure(text=app.i18n.t('fast_apply_button'))
    
    if status is True:
        app.status_bar.set_status('status_finished', level='success')
    elif status == 'FAST_APPLY_FAILED':
        app.status_bar.set_status('status_fast_apply_failed', level='error')
    else:
        app.status_bar.set_status('status_halted', level='error')
    
    if app.stop_hotkey_id:
        try: keyboard.remove_hotkey(app.stop_hotkey_id)
        except KeyError: pass
        
        app.stop_hotkey_id = None
