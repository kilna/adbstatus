#!/usr/bin/env python3
import yaml
import time
import subprocess
import os
import tempfile
import argparse
import logging
import sys
import datetime
from adb_info import ADBInfo
from sleep_monitor import SleepMonitor

def setup_logging(log_file=None):
  """Configure logging based on whether we're in daemon mode or not."""
  logger = logging.getLogger()
  logger.setLevel(logging.INFO)
  
  # Custom formatter that adds timestamps
  formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
  
  # Always have a console handler
  console = logging.StreamHandler(sys.stdout)
  console.setFormatter(formatter)
  logger.addHandler(console)
  
  # Add file handler if log file is specified
  if log_file:
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
  return logger

def load_config():
  with open('adb-monitor.yml', 'r') as f:
    return yaml.safe_load(f)

def matches_device(device_info, device_config):
  if not device_config: return True
  for key, value in device_config.items():
    if device_info.get(key) != value: return False
  return True

def run_script(script, device_serial=None):
  if not script: return ""
  env = os.environ.copy()
  if device_serial: env['ANDROID_SERIAL'] = device_serial
  if not script.startswith('#!'):
    script = '#!/bin/sh\n' + script
  with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
      f.write(script)
      temp_path = f.name
  os.chmod(temp_path, 0o755)  # Make executable
  try:
    process = subprocess.Popen(
      temp_path,
      env=env,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    stdout_text = stdout.decode().strip()
    stderr_text = stderr.decode().strip()
    
    if process.returncode != 0:
      return f"Script failed with error: {stderr_text}"
    elif stdout_text:
      return stdout_text
    else:
      return "Script executed successfully"
  finally:
    os.unlink(temp_path)  # Clean up temporary file

def get_matching_configs(device_info, configs):
  """Returns all configs that match the given device info."""
  matching = []
  for config in configs:
    if matches_device(device_info, config.get('device', {})):
      matching.append(config)
  return matching

def run_unique_scripts(device_serial, configs, script_key):
  """Runs all unique scripts of given type from matching configs."""
  executed_scripts = set()
  results = []
  
  for config in configs:
    script = config.get(script_key)
    if script and script not in executed_scripts:
      result = run_script(script, device_serial)
      results.append(result)
      executed_scripts.add(script)
      
  return results

class Monitor:
  def __init__(self, config=None):
    self.config = config or load_config()
    self.known_devices = set()
    self.logger = logging.getLogger()
    
    # Initialize sleep monitor
    self._sleep_monitor = SleepMonitor()
    self._sleep_monitor.on_sleep = self._handle_sleep
    self._sleep_monitor.on_wake = self._handle_wake
    
    # Start the sleep monitor
    if not self._sleep_monitor.start():
      self.logger.warning("Sleep monitor could not be started. Sleep/wake events will not be monitored.")
      self.logger.warning("Make sure sleepwatcher is installed: brew install sleepwatcher")

  def _handle_sleep(self):
    self.logger.info("System sleeping")
    devices = ADBInfo.get_devices()
    for device in devices:
      matching_configs = get_matching_configs(device, self.config)
      results = run_unique_scripts(device['serial'], matching_configs, 'sleep')
      for result in results:
        self.logger.info(f"  → {device['serial']}: {result}")

  def _handle_wake(self):
    self.logger.info("System waking")
    devices = ADBInfo.get_devices()
    for device in devices:
      matching_configs = get_matching_configs(device, self.config)
      results = run_unique_scripts(device['serial'], matching_configs, 'wake')
      for result in results:
        self.logger.info(f"  → {device['serial']}: {result}")

  def run(self):
    self.logger.info("ADB Monitor running")
    while True:
      current_devices = set()
      devices = ADBInfo.get_devices()
      
      # Handle new connections
      for device in devices:
        serial = device['serial']
        current_devices.add(serial)
        if serial not in self.known_devices:
          self.logger.info(f"Device connected: {serial}")
          matching_configs = get_matching_configs(device, self.config)
          results = run_unique_scripts(serial, matching_configs, 'connect')
          for result in results:
            self.logger.info(f"  → {serial}: {result}")

      # Handle disconnections
      disconnected = self.known_devices - current_devices
      for serial in disconnected:
        self.logger.info(f"Device disconnected: {serial}")
        device_info = {'serial': serial}  # Only serial available for disconnected devices
        matching_configs = get_matching_configs(device_info, self.config)
        results = run_unique_scripts(serial, matching_configs, 'disconnect')
        for result in results:
          self.logger.info(f"  → {serial}: {result}")

      self.known_devices = current_devices
      time.sleep(2)

def main():
  # Check required dependencies
  try:
    import psutil
  except ImportError:
    print("Required package 'psutil' is missing. Please install it with:")
    print("pip install psutil")
    sys.exit(1)

  # Parse command line arguments
  parser = argparse.ArgumentParser(description='ADB Monitor')
  parser.add_argument('-d', '--daemon', action='store_true', help='Run in daemon mode')
  parser.add_argument('-l', '--log', help='Log file path when running in daemon mode')
  args = parser.parse_args()
  
  # Setup logging based on arguments
  log_file = args.log if args.daemon else None
  logger = setup_logging(log_file)
  
  # If daemon mode is enabled and no log file is specified, use a default
  if args.daemon and not args.log:
    log_file = os.path.expanduser("~/adb_monitor.log")
    logger.warning(f"No log file specified, using default: {log_file}")
    
    # Add file handler for default log
    file_handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
  monitor = Monitor()
  try:
    # Uncomment the next two lines to manually test sleep/wake handlers
    # monitor._handle_sleep()
    # monitor._handle_wake()
    
    monitor.run()
  except KeyboardInterrupt:
    logger.info("Shutting down")

if __name__ == "__main__":
  main() 