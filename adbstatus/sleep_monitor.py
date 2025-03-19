"""ADBStatusSleepMonitor - Monitor sleep/wake events using sleepwatcher."""

from typing import Callable, Optional, Dict, Any
import atexit
import logging
import os
import subprocess
import tempfile
import threading
import time

class ADBStatusSleepMonitor:
  """Monitor sleep/wake events using sleepwatcher command-line tool.
  
  This class leverages the sleepwatcher utility to detect system
  sleep and wake events, and calls registered callbacks when these
  events occur.
  """
  
  def __init__(self, sleep_callback: Optional[Callable[[], None]] = None, 
               wake_callback: Optional[Callable[[], None]] = None,
               pid_file: str = '~/.adbstatus_sleepwatcher.pid',
               logger: Optional[logging.Logger] = None) -> None:
    """Initialize the sleep monitor.
    
    Args:
        sleep_callback: Function to call when system sleeps
        wake_callback: Function to call when system wakes
        pid_file: Path to store PID file
        logger: Logger instance
    """
    self._sleep_callback = sleep_callback
    self._wake_callback = wake_callback
    self._pid_file = os.path.expanduser(pid_file)
    self._logger = logger or logging.getLogger(__name__)
    self._process = None
    self._running = False
    self._sleep_script = None
    self._wake_script = None
    self._output_thread = None  # Track the output monitoring thread
    self._event_thread = None   # Track the event monitoring thread
    self._event_dir = os.path.join(tempfile.gettempdir(), "adbstatus_events")
    self._sleep_marker = os.path.join(self._event_dir, "sleep_event")
    self._wake_marker = os.path.join(self._event_dir, "wake_event")
    
    # Create event directory
    os.makedirs(self._event_dir, exist_ok=True)
    
    # Clean up any existing marker files
    for file in [self._sleep_marker, self._wake_marker]:
      if os.path.exists(file):
        os.unlink(file)

  def _is_already_running(self):
    """Check if sleepwatcher is already running.
    
    Returns:
      bool: True if sleepwatcher is already running.
    """
    # Check PID file
    if os.path.exists(self._pid_file):
      try:
        with open(self._pid_file, 'r') as f:
          pid = int(f.read().strip())
        # Check if process is running
        import psutil
        if psutil.pid_exists(pid):
          return True
      except (ValueError, FileNotFoundError, psutil.NoSuchProcess):
        # PID file exists but process is not running
        pass
    
    return False

  def _setup_scripts(self):
    """Create temporary scripts for sleep/wake events."""
    # Handle Windows platform differently
    if os.name == 'nt':
        self._logger.error("Windows is not supported for sleep monitoring")
        return False
        
    # ... existing code for Unix systems

  def _cleanup_scripts(self):
    """Clean up temporary scripts."""
    for script in [self._sleep_script, self._wake_script]:
      if script and os.path.exists(script):
        try:
          os.unlink(script)
        except:
          pass
    self._sleep_script = None
    self._wake_script = None

  def _write_pid_file(self):
    """Write PID file."""
    if self._process:
      with open(self._pid_file, 'w') as f:
        f.write(str(self._process.pid))

  def _remove_pid_file(self):
    """Remove PID file."""
    if os.path.exists(self._pid_file):
      try:
        os.unlink(self._pid_file)
      except:
        pass

  def _handle_sleep(self):
    """Handle sleep event."""
    self._logger.info("System going to sleep")
    if self._sleep_callback:
      try:
        self._sleep_callback()
      except Exception as e:
        self._logger.error(f"Error in sleep callback: {e}")

  def _handle_wake(self):
    """Handle wake event."""
    self._logger.info("System waking up")
    if self._wake_callback:
      try:
        self._wake_callback()
      except Exception as e:
        self._logger.error(f"Error in wake callback: {e}")

  def _check_for_events(self):
    """Check for event marker files."""
    while self._running:
      # Check for sleep event
      if os.path.exists(self._sleep_marker):
        os.unlink(self._sleep_marker)
        self._handle_sleep()
      
      # Check for wake event
      if os.path.exists(self._wake_marker):
        os.unlink(self._wake_marker)
        self._handle_wake()
      
      # Sleep briefly
      time.sleep(0.5)
      
  def start(self) -> bool:
    """Start monitoring sleep/wake events.
    
    Returns:
        bool: True if started successfully, False otherwise
    """
    if self._running:
      self._logger.info("Monitor already running")
      return False
      
    # Check for existing sleepwatcher process
    if self._is_already_running():
      self._logger.error("Another instance of sleepwatcher is already running")
      return False
      
    # Check if sleepwatcher is installed
    try:
      # Try to find sleepwatcher in PATH first
      try:
        sleepwatcher_path = subprocess.check_output(['which', 'sleepwatcher'], 
                                                  text=True, 
                                                  stderr=subprocess.DEVNULL).strip()
      except subprocess.CalledProcessError:
        # If not in PATH, try known Homebrew locations
        for path in [
          '/usr/local/sbin/sleepwatcher',
          '/usr/local/bin/sleepwatcher',
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
        text=True,  # Use text=True instead of universal_newlines=True (deprecated)
        bufsize=1
      )
      
      # Write PID file
      self._write_pid_file()
      
      # Start thread to monitor process output
      def monitor_output() -> None:
        for line in self._process.stdout:
          # Optionally log the output for debugging
          self._logger.debug(f"sleepwatcher: {line.strip()}")
          
      self._output_thread = threading.Thread(target=monitor_output, daemon=True)
      self._output_thread.start()
      
      # Start thread to check for event marker files
      self._running = True
      self._event_thread = threading.Thread(target=self._check_for_events, daemon=True)
      self._event_thread.start()
      
      # Register cleanup at exit
      atexit.register(self.stop)
      
      return True
      
    except (subprocess.CalledProcessError, FileNotFoundError):
      self._logger.error("sleepwatcher not installed. Install with: brew install sleepwatcher")
      return False
    except Exception as e:
      self._logger.error(f"Error starting sleepwatcher: {e}")
      self._cleanup_scripts()
      return False
  
  def stop(self) -> bool:
    """Stop monitoring sleep/wake events.
    
    Returns:
        bool: True if stopped successfully, False otherwise
    """
    # Rest of method implementation...
    # Be sure to set self._output_thread = None and self._event_thread = None when cleaned up 