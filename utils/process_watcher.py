import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
from utils.tile_splitter import run_split


class ProcessEventHandler(FileSystemEventHandler):
    def __init__(self, target_file, callback):
        super().__init__()
        self.target_file = os.path.normpath(os.path.normcase(target_file))
        self.callback = callback
        self.last_event_time = 0
    
    def _handle_event(self, event):
        """
        Generic event handler for file modifications and creations.
        """
        
        if event.is_directory:
            return
        event_path = os.path.normpath(os.path.normcase(event.src_path))
        
        if event_path == self.target_file:
            now = time.time()
            
            if (now - self.last_event_time) > 2.0:
                self.last_event_time = now
                self.callback(event.src_path)
    
    def on_modified(self, event):
        self._handle_event(event)
    
    def on_created(self, event):
        self._handle_event(event)
    
    def on_moved(self, event):
        """
        Handles file 'move' events, which are critical for applications
        that use a "safe save" (rename temporary file) workflow.
        """
        
        if event.is_directory:
            return
        event_path = os.path.normpath(os.path.normcase(event.dest_path))
        
        if event_path == self.target_file:
            now = time.time()
            
            if (now - self.last_event_time) > 2.0:
                self.last_event_time = now
                self.callback(event.dest_path)


class ProcessWatcher:
    def __init__(self, log_callback=print):
        self.log = log_callback
        self.observer = Observer()
        self.target_file = None
        self.is_running = False
    
    def start(self, file_to_watch):
        if self.is_running:
            self.stop()
        self.target_file = file_to_watch
        directory_to_watch = os.path.dirname(self.target_file)
        event_handler = ProcessEventHandler(self.target_file, self._run_process)
        try:
            self.observer = Observer()
            self.observer.schedule(event_handler, directory_to_watch, recursive=False)
            self.observer.start()
            self.is_running = True
            self.log(f"Started watching '{os.path.basename(self.target_file)}' for changes.")
        except Exception as e:
            self.log(f"Error starting process watcher: {e}")
    
    def stop(self):
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        self.is_running = False
        self.log("Stopped watching for post-process file.")
    
    def _run_process(self, changed_path):
        self.log(f"Detected change in '{os.path.basename(changed_path)}'. Starting tile-splitter...")
        process_thread = threading.Thread(target=run_split, args=(changed_path,), daemon=True)
        process_thread.start()
