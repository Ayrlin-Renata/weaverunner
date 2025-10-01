import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os


def normalize_path(path):
    """
    Standardizes a file path for reliable, case-insensitive comparison.
    """
    
    if not path:
        return None
    return os.path.normpath(os.path.normcase(path))


class FileChangeHandler(FileSystemEventHandler):
    """
    An event handler that checks against a specific set of file paths
    and puts any modified, matching file into a queue.
    """
    def __init__(self, queue, watched_files):
        super().__init__()
        self.queue = queue
        self.watched_files = {normalize_path(f) for f in watched_files if f}
        self.last_event = {}
    
    def _handle_event(self, event):
        """
        A generic handler for both modification and creation events.
        """
        
        if event.is_directory:
            return
        normalized_path = normalize_path(event.src_path)
        
        if normalized_path in self.watched_files:
            now = time.time()
            
            if normalized_path in self.last_event and (now - self.last_event[normalized_path]) < 1.0:
                return
            self.last_event[normalized_path] = now
            self.queue.put(event.src_path)
    
    def on_modified(self, event):
        self._handle_event(event)
    
    def on_created(self, event):
        self._handle_event(event)


class FileWatcher:
    """
    Manages the file monitoring thread using the Watchdog library.
    """
    def __init__(self, queue, log_callback=print):
        self.queue = queue
        self.log = log_callback
        self.observer = Observer()
        self.watched_files = set()
    
    def start(self, files_to_watch):
        """
        Starts the monitoring thread if it's not already running.
        """
        self.update_watched_files(files_to_watch)
        
        if self.watched_files and not self.observer.is_alive():
            try:
                self.observer.start()
                self.log("File watcher thread started.")
            except RuntimeError:
                self.observer = Observer()
                self.update_watched_files(files_to_watch, force_reschedule=True)
                self.observer.start()
                self.log("Recreated and started file watcher thread.")
    
    def stop(self):
        """
        Stops the monitoring thread if it's running.
        """
        
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            self.log("File watcher thread stopped.")
    
    def update_watched_files(self, files, force_reschedule=False):
        """
        Updates the list of files to be monitored, scheduling watches only for
        the necessary parent directories.
        """
        new_files_set = {f for f in files if f and os.path.exists(f)}
        
        if new_files_set == self.watched_files and not force_reschedule:
            return
        self.watched_files = new_files_set
        
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            self.observer = Observer()
        
        if not self.watched_files:
            self.log("No valid files to watch. Watcher is stopped.")
            return
        dirs_to_watch = {os.path.dirname(path) for path in self.watched_files}
        event_handler = FileChangeHandler(self.queue, self.watched_files)
        
        for directory in dirs_to_watch:
            self.observer.schedule(event_handler, directory, recursive=False)
            self.log(f"Watching directory: {directory}")
        
        if not self.observer.is_alive():
            self.start(self.watched_files)
