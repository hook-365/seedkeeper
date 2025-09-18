#!/usr/bin/env python3
"""
Hot-reload utility for Seedkeeper workers
Monitors file changes and triggers worker module reloads
"""

import os
import sys
import time
import importlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Set, Callable
from pathlib import Path

class ModuleReloadHandler(FileSystemEventHandler):
    """Handles file system events for module reloading"""
    
    def __init__(self, reload_callback: Callable, watch_patterns: Set[str] = None):
        self.reload_callback = reload_callback
        self.watch_patterns = watch_patterns or {'.py'}
        self.last_reload = 0
        self.reload_delay = 1  # Minimum seconds between reloads
    
    def should_reload(self, file_path: str) -> bool:
        """Check if file should trigger a reload"""
        if not any(file_path.endswith(pattern) for pattern in self.watch_patterns):
            return False
        
        # Ignore __pycache__ and other temp files
        if '__pycache__' in file_path or file_path.endswith('.pyc'):
            return False
        
        # Rate limiting
        now = time.time()
        if now - self.last_reload < self.reload_delay:
            return False
        
        return True
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if self.should_reload(event.src_path):
            print(f"📝 File changed: {event.src_path}")
            self.last_reload = time.time()
            self.reload_callback(event.src_path)
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        if self.should_reload(event.src_path):
            print(f"🆕 File created: {event.src_path}")
            self.last_reload = time.time()
            self.reload_callback(event.src_path)

class HotReloader:
    """Manages hot reloading of Python modules"""
    
    def __init__(self, watch_dir: str = None, worker_callback: Callable = None):
        self.watch_dir = Path(watch_dir or os.getcwd())
        self.worker_callback = worker_callback
        self.observer = None
        self.loaded_modules = {}
        
        # Find modules to watch
        self.discover_modules()
    
    def discover_modules(self):
        """Discover Python modules in the watch directory"""
        for py_file in self.watch_dir.glob('*.py'):
            module_name = py_file.stem
            if module_name.startswith('__'):
                continue
            
            self.loaded_modules[module_name] = {
                'path': py_file,
                'last_modified': py_file.stat().st_mtime if py_file.exists() else 0
            }
        
        print(f"🔍 Watching {len(self.loaded_modules)} modules for changes")
    
    def reload_module(self, file_path: str):
        """Reload a specific module"""
        file_path = Path(file_path)
        module_name = file_path.stem
        
        if module_name not in self.loaded_modules:
            print(f"⚠️ Module {module_name} not in watch list")
            return False
        
        try:
            # Check if module is in sys.modules
            if module_name in sys.modules:
                print(f"🔄 Reloading module: {module_name}")
                importlib.reload(sys.modules[module_name])
            else:
                print(f"🆕 Loading new module: {module_name}")
                importlib.import_module(module_name)
            
            # Update last modified time
            self.loaded_modules[module_name]['last_modified'] = file_path.stat().st_mtime
            
            # Notify worker if callback provided
            if self.worker_callback:
                self.worker_callback(module_name, file_path)
            
            print(f"✅ Successfully reloaded: {module_name}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to reload {module_name}: {e}")
            return False
    
    def start_watching(self):
        """Start the file system watcher"""
        if self.observer:
            print("⚠️ Already watching for changes")
            return
        
        # Create event handler
        handler = ModuleReloadHandler(
            reload_callback=self.reload_module,
            watch_patterns={'.py'}
        )
        
        # Setup observer
        self.observer = Observer()
        self.observer.schedule(handler, str(self.watch_dir), recursive=False)
        
        print(f"👁️ Started watching {self.watch_dir} for changes")
        self.observer.start()
    
    def stop_watching(self):
        """Stop the file system watcher"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            print("🛑 Stopped watching for file changes")
    
    def manual_reload(self, module_name: str) -> bool:
        """Manually reload a specific module"""
        if module_name not in self.loaded_modules:
            print(f"⚠️ Module {module_name} not found in watch list")
            print(f"Available modules: {', '.join(self.loaded_modules.keys())}")
            return False
        
        module_info = self.loaded_modules[module_name]
        return self.reload_module(str(module_info['path']))
    
    def reload_all(self) -> int:
        """Reload all watched modules"""
        reloaded_count = 0
        
        for module_name, module_info in self.loaded_modules.items():
            if self.reload_module(str(module_info['path'])):
                reloaded_count += 1
        
        print(f"🔄 Reloaded {reloaded_count}/{len(self.loaded_modules)} modules")
        return reloaded_count
    
    def get_status(self) -> dict:
        """Get hot reload status"""
        return {
            'watching': self.observer is not None and self.observer.is_alive(),
            'watch_dir': str(self.watch_dir),
            'module_count': len(self.loaded_modules),
            'modules': list(self.loaded_modules.keys())
        }

class WorkerHotReloader(HotReloader):
    """Hot reloader specifically for Seedkeeper workers"""
    
    def __init__(self, worker_instance=None):
        self.worker_instance = worker_instance
        super().__init__(
            watch_dir=os.path.dirname(os.path.abspath(__file__)),
            worker_callback=self.notify_worker
        )
    
    def notify_worker(self, module_name: str, file_path: Path):
        """Notify worker instance of module reload"""
        if self.worker_instance and hasattr(self.worker_instance, 'on_module_reloaded'):
            self.worker_instance.on_module_reloaded(module_name, str(file_path))

def create_reload_command_handler(reloader: HotReloader):
    """Create a command handler for reload operations"""
    
    async def handle_reload_command(args: list) -> str:
        """Handle !reload command with options"""
        if not args:
            # Reload all modules
            count = reloader.reload_all()
            return f"🔄 Reloaded {count} modules"
        
        command = args[0].lower()
        
        if command == 'status':
            status = reloader.get_status()
            return f"""🔄 **Hot Reload Status**
**Watching**: {'✅ Active' if status['watching'] else '❌ Inactive'}
**Directory**: {status['watch_dir']}
**Modules**: {status['module_count']} ({', '.join(status['modules'])})"""
        
        elif command == 'start':
            if not reloader.observer:
                reloader.start_watching()
                return "👁️ Started file system watcher"
            else:
                return "⚠️ Already watching for changes"
        
        elif command == 'stop':
            if reloader.observer:
                reloader.stop_watching()
                return "🛑 Stopped file system watcher"
            else:
                return "⚠️ Not currently watching"
        
        elif command == 'list':
            modules = reloader.loaded_modules.keys()
            return f"📦 **Watched Modules**: {', '.join(modules)}"
        
        else:
            # Try to reload specific module
            if reloader.manual_reload(command):
                return f"✅ Reloaded module: {command}"
            else:
                return f"❌ Failed to reload module: {command}"
    
    return handle_reload_command

if __name__ == "__main__":
    # Test the hot reloader
    def test_callback(module_name, file_path):
        print(f"🔔 Worker would be notified: {module_name} changed")
    
    reloader = HotReloader(worker_callback=test_callback)
    reloader.start_watching()
    
    try:
        print("Press Ctrl+C to stop...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping hot reloader...")
        reloader.stop_watching()