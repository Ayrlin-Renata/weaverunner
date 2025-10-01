import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import tempfile
import shutil
from PIL import Image
from utils.clip_extractor import find_and_extract_db, extract_layer
from utils.tile_splitter import run_split
DOWNSCALING_METHODS = {
    "Lanczos": Image.Resampling.LANCZOS,
    "Bicubic": Image.Resampling.BICUBIC,
    "Bilinear": Image.Resampling.BILINEAR,
    "Box": Image.Resampling.BOX,
    "Nearest": Image.Resampling.NEAREST,
    "Hamming": Image.Resampling.HAMMING,
}


class ClipChangeHandler(FileSystemEventHandler):
    """
    An event handler that triggers a callback for a specific file,
    with a debounce mechanism suitable for large files like .clip.
    """
    def __init__(self, target_file, callback):
        super().__init__()
        self.target_file = os.path.normpath(os.path.normcase(target_file))
        self.callback = callback
        self.last_event_time = 0
        self.debounce_period = 5.0
    
    def _handle_event(self, event_path):
        """
        Checks if the event path matches the target file and debounces.
        """
        normalized_path = os.path.normpath(os.path.normcase(event_path))
        
        if normalized_path == self.target_file:
            now = time.time()
            
            if (now - self.last_event_time) > self.debounce_period:
                self.last_event_time = now
                self.callback(event_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            self._handle_event(event.src_path)
    
    def on_created(self, event):
        if not event.is_directory:
            self._handle_event(event.src_path)
    
    def on_moved(self, event):
        if not event.is_directory:
            self._handle_event(event.dest_path)


class ClipWatcher:
    """
    Monitors a .clip file for changes and runs a multi-step process:
    1. Extract a specific layer to a PNG.
    2. Downscale the PNG.
    3. Split the downscaled PNG into tiles.
    """
    def __init__(self, log_callback=print):
        self.log = log_callback
        self.observer = Observer()
        self.target_file = None
        self.layer_name = None
        self.scale_factor = None
        self.resample_method = None
        self.is_running = False
        self.processing_thread = None
    
    def start(self, file_to_watch, layer_name, scale_factor, algorithm_name="Lanczos"):
        """
        Starts watching the specified .clip file.
        """
        
        if self.is_running:
            self.stop()
        self.target_file = file_to_watch
        self.layer_name = layer_name
        self.scale_factor = scale_factor
        self.resample_method = DOWNSCALING_METHODS.get(algorithm_name, Image.Resampling.LANCZOS)
        directory_to_watch = os.path.dirname(self.target_file)
        event_handler = ClipChangeHandler(self.target_file, self._run_process)
        try:
            self.observer = Observer()
            self.observer.schedule(event_handler, directory_to_watch, recursive=False)
            self.observer.start()
            self.is_running = True
            self.log(f"Started watching '{os.path.basename(self.target_file)}' for changes.")
            self._run_process(self.target_file)
        except Exception as e:
            self.log(f"Error starting clip watcher: {e}")
    
    def stop(self):
        """
        Stops watching the file.
        """
        
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        self.is_running = False
        self.log("Stopped watching .clip file.")
    
    def _run_process(self, changed_path):
        """
        Queues the processing to run in a background thread.
        """
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.log("Processing is already in progress. Skipping new trigger.")
            return
        self.log(f"Detected change in '{os.path.basename(changed_path)}'. Starting extraction process...")
        self.processing_thread = threading.Thread(
            target=self._process_file,
            args=(changed_path, self.layer_name, self.scale_factor, self.resample_method),
            daemon=True
        )
        self.processing_thread.start()
    
    def _process_file(self, clip_file_path, layer_name, scale_factor, resample_method):
        """
        The core processing logic: extract, downscale, and split.
        """
        temp_dir = None
        db_temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="weaverunner_clip_")
            self.log(f"Using temporary directory for processing: {temp_dir}")
            self.log(f"Extracting layer '{layer_name}' from .clip file...")
            extracted_png_path = os.path.join(temp_dir, 'extracted_layer.png')
            db_path, db_temp_dir = find_and_extract_db(clip_file_path)
            
            if not db_path:
                self.log("Failed to extract database from .clip file. Aborting process.")
                return
            extract_layer(db_path, clip_file_path, layer_name, extracted_png_path)
            
            if not os.path.exists(extracted_png_path):
                self.log(f"Layer extraction did not produce an output file for layer '{layer_name}'. It might be empty or not found. Aborting.")
                return
            self.log("Layer extracted successfully.")
            self.log(f"Downscaling image by a factor of {scale_factor}...")
            img = Image.open(extracted_png_path)
            new_width = img.width // scale_factor
            new_height = img.height // scale_factor
            
            if new_width < 1 or new_height < 1:
                self.log(f"Error: Downscaling resulted in a zero or negative size image ({new_width}x{new_height}). Aborting.")
                return
            downscaled_img = img.resize((new_width, new_height), resample_method)
            output_dir = os.path.dirname(clip_file_path)
            base_name = os.path.splitext(os.path.basename(clip_file_path))[0]
            downscaled_png_path = os.path.join(output_dir, f"{base_name}.png")
            downscaled_img.save(downscaled_png_path, 'PNG')
            self.log(f"Image downscaled to {new_width}x{new_height} and saved as {os.path.basename(downscaled_png_path)}.")
            self.log("Running tile-splitter on the downscaled image...")
            output_tile_dir = os.path.dirname(clip_file_path)
            success = run_split(downscaled_png_path, output_dir=output_tile_dir)
            
            if success:
                self.log("Tile splitting process completed successfully.")
            else:
                self.log("Tile splitting process failed.")
        except Exception as e:
            self.log(f"An error occurred during .clip processing: {e}")
        finally:
            if db_temp_dir and os.path.exists(db_temp_dir):
                shutil.rmtree(db_temp_dir)
            
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                self.log("Cleaned up temporary processing files.")
