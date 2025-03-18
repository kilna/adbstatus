#!/usr/bin/env python3
import sys
import os
import signal
import subprocess
import threading
import time
import tempfile
import atexit
import logging
import psutil

# Constants for singleton management
PID_FILE = os.path.expanduser("~/.sleepwatcher_monitor.pid")

class SleepMonitor:
  """Monitor sleep/wake events using sleepwatcher command-line tool."""
  
  def __init__(self):
    self.on_sleep = lambda: None
    self.on_wake = lambda: None
    self._process = None
    self._temp_dir = None
    self._sleep_script = None
    self._wake_script = None
    self._running = False
    self.logger = logging.getLogger()
    
  def _is_already_running(self):
    """Check if another instance is already running by checking PID file."""
    if os.path.exists(PID_FILE):
      try:
        with open(PID_FILE, 'r') as f:
          pid = int(f.read().strip())
          
        # Check if process with this PID exists and is sleepwatcher
        if pid > 0:
          try:
            process = psutil.Process(pid)
            # If the process name contains 'sleepwatcher', it's likely our process
            if 'sleepwatcher' in process.name().lower() or any('sleepwatcher' in cmd.lower() for cmd in process.cmdline()):
              self.logger.warning(f"Sleepwatcher already running with PID {pid}")
              return True
          except psutil.NoSuchProcess:
            # Process doesn't exist anymore, we can remove the stale PID file
            self.logger.info(f"Removing stale PID file for process {pid}")
            os.unlink(PID_FILE)
      except (ValueError, IOError) as e:
        self.logger.error(f"Error reading PID file: {e}")
        # Try to remove corrupted PID file
        try:
          os.unlink(PID_FILE)
        except OSError:
          pass
    
    # Check for any running sleepwatcher processes
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
      try:
        # Check if this is a sleepwatcher process
        proc_name = proc.info['name'] or ''
        proc_cmdline = proc.info['cmdline'] or []
        
        if ('sleepwatcher' in proc_name.lower() or 
            any('sleepwatcher' in cmd.lower() for cmd in proc_cmdline if cmd)):
            
          self.logger.warning(f"Found existing sleepwatcher process (PID {proc.pid})")
          # Kill the existing process to prevent conflicts
          try:
            proc.terminate()
            proc.wait(timeout=3)
            self.logger.info(f"Terminated existing sleepwatcher process (PID {proc.pid})")
          except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            try:
              proc.kill()
              self.logger.info(f"Killed existing sleepwatcher process (PID {proc.pid})")
            except psutil.NoSuchProcess:
              pass
      except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
    
    return False
    
  def _write_pid_file(self):
    """Write process ID to PID file."""
    if self._process:
      try:
        with open(PID_FILE, 'w') as f:
          f.write(str(self._process.pid))
        self.logger.debug(f"Wrote PID file: {self._process.pid}")
      except IOError as e:
        self.logger.error(f"Failed to write PID file: {e}")
    
  def _remove_pid_file(self):
    """Remove PID file on shutdown."""
    if os.path.exists(PID_FILE):
      try:
        os.unlink(PID_FILE)
        self.logger.debug("Removed PID file")
      except OSError as e:
        self.logger.error(f"Failed to remove PID file: {e}")
  
  def _setup_scripts(self):
    """Create temporary sleep and wake scripts."""
    # Create a temporary directory for our scripts
    self._temp_dir = tempfile.mkdtemp(prefix="sleepwatcher_")
    
    # Create the sleep script with custom callback
    self._sleep_script = os.path.join(self._temp_dir, "sleep_script")
    with open(self._sleep_script, "w") as f:
      f.write(f"""#!/bin/sh
# Create a marker file to indicate sleep happened
echo "$(date)" > {self._temp_dir}/last_sleep.txt
""")
    os.chmod(self._sleep_script, 0o755)
    
    # Create the wake script with custom callback
    self._wake_script = os.path.join(self._temp_dir, "wake_script")
    with open(self._wake_script, "w") as f:
      f.write(f"""#!/bin/sh
# Create a marker file to indicate wake happened
echo "$(date)" > {self._temp_dir}/last_wake.txt
""")
    os.chmod(self._wake_script, 0o755)
    
  def _cleanup_scripts(self):
    """Clean up temporary scripts."""
    if self._temp_dir and os.path.exists(self._temp_dir):
      try:
        if self._sleep_script and os.path.exists(self._sleep_script):
          os.remove(self._sleep_script)
        if self._wake_script and os.path.exists(self._wake_script):
          os.remove(self._wake_script)
        # Remove any marker files
        for marker in ['last_sleep.txt', 'last_wake.txt']:
          marker_path = os.path.join(self._temp_dir, marker)
          if os.path.exists(marker_path):
            os.remove(marker_path)
        os.rmdir(self._temp_dir)
      except Exception:
        pass
    
  def _check_for_events(self):
    """Check for sleep/wake events by monitoring marker files."""
    last_sleep_file = os.path.join(self._temp_dir, 'last_sleep.txt')
    last_wake_file = os.path.join(self._temp_dir, 'last_wake.txt')
    
    while self._running:
      # Check for sleep event
      if os.path.exists(last_sleep_file):
        try:
          with open(last_sleep_file, 'r') as f:
            timestamp = f.read().strip()
          try:
            self.on_sleep()
          except Exception as e:
            self.logger.error(f"Error in sleep callback: {e}")
          os.remove(last_sleep_file)
        except Exception as e:
          self.logger.error(f"Error processing sleep event: {e}")
      
      # Check for wake event
      if os.path.exists(last_wake_file):
        try:
          with open(last_wake_file, 'r') as f:
            timestamp = f.read().strip()
          try:
            self.on_wake()
          except Exception as e:
            self.logger.error(f"Error in wake callback: {e}")
          os.remove(last_wake_file)
        except Exception as e:
          self.logger.error(f"Error processing wake event: {e}")
      
      # Sleep a short time before checking again
      time.sleep(0.5)
    
  def start(self):
    """Start monitoring sleep/wake events."""
    if self._running:
      self.logger.info("Monitor already running")
      return False
      
    # Check for existing sleepwatcher process
    if self._is_already_running():
      self.logger.error("Another instance of sleepwatcher is already running")
      return False
      
    # Check if sleepwatcher is installed
    try:
      # Try to find sleepwatcher in PATH first
      try:
        sleepwatcher_path = subprocess.check_output(['which', 'sleepwatcher'], text=True, stderr=subprocess.DEVNULL).strip()
      except subprocess.CalledProcessError:
        # If not in PATH, try known Homebrew locations
        for path in [
          '/usr/local/sbin/sleepwatcher',
          '/usr/local/Cellar/sleepwatcher/2.2.1/sbin/sleepwatcher',
          '/opt/homebrew/bin/sleepwatcher'
        ]:
          if os.path.exists(path):
            sleepwatcher_path = path
            break
        else:
          raise FileNotFoundError("sleepwatcher executable not found")
            
      # Set up scripts
      self._setup_scripts()
      
      # Start sleepwatcher process
      cmd = [
        sleepwatcher_path,
        '-s', self._sleep_script,
        '-w', self._wake_script
      ]
      self._process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
      )
      
      # Write PID file
      self._write_pid_file()
      
      # Start thread to monitor process output (but don't print every line)
      def monitor_output():
        for line in self._process.stdout:
          pass  # Silently consume output
          
      # Start thread to check for event marker files
      self._running = True
      threading.Thread(target=self._check_for_events, daemon=True).start()
      threading.Thread(target=monitor_output, daemon=True).start()
      
      # Register cleanup at exit
      atexit.register(self.stop)
      
      return True
      
    except (subprocess.CalledProcessError, FileNotFoundError):
      self.logger.error("sleepwatcher not installed. Install with: brew install sleepwatcher")
      return False
    except Exception as e:
      self.logger.error(f"Error starting sleepwatcher: {e}")
      self._cleanup_scripts()
      return False
    
  def stop(self):
    """Stop monitoring sleep/wake events."""
    if not self._running:
      return
      
    self._running = False
    
    # Remove PID file first in case process termination fails
    self._remove_pid_file()
    
    # Terminate process
    if self._process:
      try:
        self._process.terminate()
        self._process.wait(timeout=2)
      except Exception:
        try:
          self._process.kill()
        except:
          pass
      
      self._process = None
    
    # Clean up scripts
    self._cleanup_scripts()
    
    # Unregister exit handler
    try:
      atexit.unregister(self.stop)
    except:
      pass


def sleep_monitor():
  """Factory function to create and start a sleep monitor."""
  monitor = SleepMonitor()
  monitor.start()
  return monitor


if __name__ == "__main__":
  # Check required dependencies
  try:
    import psutil
  except ImportError:
    print("Required package 'psutil' is missing. Please install it with:")
    print("pip install psutil")
    sys.exit(1)
    
  # Set up logging
  logger = logging.getLogger()
  logger.setLevel(logging.INFO)
  handler = logging.StreamHandler(sys.stdout)
  formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  
  logger.info(f"Sleep/wake monitor starting (platform: {sys.platform})")
  
  # Create and start the monitor
  monitor = SleepMonitor()
  
  # Set up signal handling for clean exit
  def signal_handler(sig, frame):
    logger.info("Received signal to exit. Cleaning up...")
    monitor.stop()
    logger.info("Exited cleanly")
    sys.exit(0)
    
  signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
  signal.signal(signal.SIGTERM, signal_handler)  # kill command
  
  # Start the monitor
  if monitor.start():
    logger.info("Monitor running. Press Ctrl+C to exit...")
  else:
    logger.error("Failed to start monitor")
    sys.exit(1)
  
  # Keep the main thread alive
  try:
    while True:
      time.sleep(1)
  except KeyboardInterrupt:
    logger.info("Exiting on keyboard interrupt...")
    monitor.stop()
    logger.info("Exited cleanly") 