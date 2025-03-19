"""ADBStatusService - Base class for ADB Status services.

This module provides the core functionality for ADBStatus services, including:
- Configuration management with multi-location support
- Logging setup
- Service lifecycle management (start/stop)
- Command-line argument parsing

Author: Kilna, Anthony <kilna@kilna.com>
License: MIT
"""

import argparse
import json
import logging
import os
import psutil
import signal
import subprocess
import sys
import time
import yaml
from typing import Dict, Any, Optional, List, Tuple, Type, ClassVar, Union
from . import version_info

class ADBStatusService:
  """Base class for ADB Status services.
  
  This class provides common functionality for ADBStatus services:
  - Configuration loading from multiple possible locations
  - Logging configuration
  - Service lifecycle management (start/stop)
  - Process management
  
  It's designed to be subclassed by specific services like ADBStatusServer
  and ADBStatusMonitor.
  """
  
  def __init__(self, service_name: str, config_path: Optional[str] = None, 
               logger: Optional[logging.Logger] = None) -> None:
    """Initialize the service with the given configuration.
    
    Args:
        service_name: Name of the service.
        config_path: Path to configuration file.
        logger: Logger instance.
    """
    self.service_name = service_name
    self.config = self.load_config(config_path)
    self.logger = logger or self.setup_logging(self.config)
    self.running = False
    self.start_time: Optional[float] = None
  
  def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load service configuration from YAML file.
    
    This method attempts to load configuration from the following locations
    in order of precedence:
    1. The specified config_path (if provided)
    2. /usr/local/etc/adbstatus/{service_name}.yml (Intel Macs, Linux)
    3. /opt/homebrew/etc/adbstatus/{service_name}.yml (Apple Silicon Macs)
    4. ~/Library/Application Support/adbstatus/{service_name}.yml
    5. Package-relative etc/{service_name}.yml
    
    If no configuration file is found, default settings are used.
    
    Args:
        config_path: Path to configuration file.
        
    Returns:
        dict: Service configuration with defaults applied.
    """
    # If a specific path was provided, use it directly
    if not config_path:
      # Check common locations in order of precedence
      possible_paths = [
        # User-specific location in Homebrew prefix
        f'/usr/local/etc/adbstatus/{self.service_name}.yml',
        # Apple Silicon Mac Homebrew location
        f'/opt/homebrew/etc/adbstatus/{self.service_name}.yml',
        # Default fallback location
        f'~/Library/Application Support/adbstatus/{self.service_name}.yml',
        # Package-relative location
        os.path.join(os.path.dirname(__file__), "etc", f"{self.service_name}.yml")
      ]
      
      # Use the first config file that exists
      for path in possible_paths:
        expanded_path = os.path.expanduser(path)
        if os.path.exists(expanded_path):
          config_path = expanded_path
          break
      else:
        # Default to the first path if none exist (it will be created later if needed)
        config_path = os.path.expanduser(possible_paths[0])
        # Log that we're using a default path that doesn't exist yet
        logging.info(f"No configuration file found, will use default settings (would save to {config_path})")
    
    # Default configuration to be overridden by subclasses
    default_config = {
      'logging': {
        'file': f'~/Library/Logs/adbstatus-{self.service_name}.log',
        'level': 'info'
      }
    }
    
    # Load configuration from file if it exists
    if os.path.exists(config_path):
      try:
        with open(config_path, 'r') as f:
          config = yaml.safe_load(f)
        
        # Merge with default config
        if config:
          # Handle nested dictionaries
          for k, v in config.items():
            if k in default_config and isinstance(default_config[k], dict) and isinstance(v, dict):
              default_config[k].update(v)
            else:
              default_config[k] = v
      except Exception as e:
        logging.error(f"Error loading config from {config_path}: {e}")
        logging.info("Using default configuration")
    else:
      logging.info(f"Configuration file {config_path} not found, using default settings")
      
      # Optionally create parent directories for the config file
      # Uncomment these lines if you want to create the directory structure for future use
      # config_dir = os.path.dirname(config_path)
      # os.makedirs(config_dir, exist_ok=True)
    
    return default_config
  
  def setup_logging(self, config):
    """Set up logging based on configuration.
    
    Args:
        config (dict): Service configuration.
    
    Returns:
        logging.Logger: Configured logger.
    """
    log_config = config.get('logging', {})
    log_file = os.path.expanduser(log_config.get('file', f'~/Library/Logs/adbstatus-{self.service_name}.log'))
    log_level_name = log_config.get('level', 'info').upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    
    # Configure logger
    logger = logging.getLogger(f"adbstatus-{self.service_name}")
    logger.setLevel(log_level)
    logger.handlers = []  # Clear existing handlers
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger
  
  def start(self, foreground=False):
    """Start the service.
    
    Args:
        foreground (bool): Run in foreground if True, daemon mode if False.
        
    Returns:
        bool: True if service started successfully, False otherwise.
    """
    # Check if already running
    if self.is_running():
      self.logger.error(f"{self.service_name} is already running")
      return False
    
    if not foreground:
      # Fork and run in background
      if os.name != 'posix':
        self.logger.error("Daemon mode only supported on POSIX systems")
        return False
        
      if os.fork() == 0:
        # Child process
        # Detach from parent process
        os.setsid()
        
        # Close standard file descriptors
        for fd in range(3):
          try:
            os.close(fd)
          except OSError:
            pass
        
        # Open /dev/null as stdin, stdout, stderr
        os.open(os.devnull, os.O_RDWR) # stdin
        os.dup2(0, 1) # stdout
        os.dup2(0, 2) # stderr
        
        # Start service
        self._run_service()
        sys.exit(0)
      else:
        # Parent process
        self.logger.info(f"{self.service_name} started in daemon mode")
        return True
    else:
      # Run in foreground
      return self._run_service()
  
  def _run_service(self):
    """Internal method to run the service. To be implemented by subclasses."""
    raise NotImplementedError("Subclasses must implement _run_service")
  
  def stop(self):
    """Stop the service.
    
    Returns:
        bool: True if service stopped successfully, False otherwise.
    """
    # Stop our own instance
    if self.running:
      self.logger.info(f"Stopping {self.service_name}...")
      self.running = False
      return True
    else:
      # Stop other instances
      stopped = self.stop_other_instances()
      if stopped:
        self.logger.info(f"Other {self.service_name} instances stopped")
      else:
        self.logger.info(f"No running {self.service_name} found")
      return stopped
  
  def is_running(self):
    """Check if this service is already running.
    
    Returns:
        bool: True if service is running, False otherwise.
    """
    try:
      for proc in psutil.process_iter(['pid', 'cmdline']):
        if proc.info['cmdline'] and f'adbstatus-{self.service_name}' in ' '.join(proc.info['cmdline']) and proc.pid != os.getpid():
          return True
      return False
    except Exception:
      return False
  
  def stop_other_instances(self):
    """Stop any other running instances of this service.
    
    Returns:
        bool: True if any instances were stopped, False otherwise.
    """
    try:
      stopped = False
      for proc in psutil.process_iter(['pid', 'cmdline']):
        if proc.info['cmdline'] and f'adbstatus-{self.service_name}' in ' '.join(proc.info['cmdline']) and proc.pid != os.getpid():
          proc.send_signal(signal.SIGTERM)
          stopped = True
          try:
            proc.wait(timeout=2)
          except psutil.TimeoutExpired:
            proc.kill()  # Force kill if it doesn't terminate gracefully
      return stopped
    except Exception:
      return False
  
  def get_status(self):
    """Get current service status. To be extended by subclasses.
    
    Returns:
        dict: Status information.
    """
    return {
      "running": self.is_running(),
      "uptime": time.time() - self.start_time if self.running and self.start_time else None
    }
  
  @classmethod
  def parse_args(cls, description=None, prog=None):
    """Parse command line arguments.
    
    Args:
        description (str, optional): Description for the argument parser.
        prog (str, optional): Program name for help messages.
        
    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description=description, prog=prog,
                                   add_help=False)  # Disable automatic help
    
    # Add help argument manually
    parser.add_argument('-h', '--help', action='store_true',
                      help='Show this help message and exit')
    
    # Add version argument
    parser.add_argument('-v', '--version', action='store_true',
                      help='Show version information')
    
    # Command argument
    parser.add_argument('command', nargs='?', 
                      choices=['start', 'stop', 'status', 'version', 'help'], 
                      default='status', 
                      help='Command to execute')
    
    # Other arguments
    parser.add_argument('-c', '--config', 
                      help='Path to configuration file')
    parser.add_argument('-f', '--foreground', action='store_true',
                      help='Run in foreground (for start command)')
    
    args = parser.parse_args()
    
    # Handle help flag or command
    if args.help or args.command == 'help':
      parser.print_help()
      sys.exit(0)
    
    return args 