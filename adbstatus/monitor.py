#!/usr/bin/env python3
"""ADBStatusMonitor - Monitor for ADB device connections and sleep/wake events."""

import json
import logging
import os
import subprocess
import sys
import time
from typing import Dict, Any, Optional, List, Set, Callable, Union
from . import version_info
from .core import ADBStatus
from .service import ADBStatusService
from .sleep_monitor import ADBStatusSleepMonitor

class ADBStatusMonitor(ADBStatusService):
    """ADB Monitor to handle device connections and sleep/wake events."""
    
    def __init__(self, config_path: Optional[str] = None, 
                 logger: Optional[logging.Logger] = None) -> None:
        """Initialize the monitor with the given configuration.
        
        Args:
            config_path (str, optional): Path to configuration file.
            logger (logging.Logger, optional): Logger instance.
        """
        super().__init__('monitor', config_path, logger)
        self.known_devices: Set[str] = set()
        
        # Initialize sleep monitor if enabled
        sleep_config = self.config.get('sleep_monitor', {})
        if sleep_config.get('enabled', True):
            self._sleep_monitor = ADBStatusSleepMonitor(
                sleep_callback=self._handle_sleep,
                wake_callback=self._handle_wake,
                pid_file=os.path.expanduser(sleep_config.get('pid_file', '~/.adbstatus_sleepwatcher.pid'))
            )
        else:
            self.logger.info("Sleep monitor is disabled in configuration")
            self._sleep_monitor = None
    
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load monitor configuration from YAML file.
        
        Args:
            config_path (str, optional): Path to configuration file.
            
        Returns:
            dict: Monitor configuration.
        """
        # Get base configuration
        config = super().load_config(config_path)
        
        # Add monitor-specific defaults
        monitor_defaults = {
            'check_interval': 5,
            'sleep_monitor': {
                'enabled': True,
                'pid_file': '~/.adbstatus_sleepwatcher.pid'
            },
            'devices': []
        }
        
        # Merge with monitor defaults
        for k, v in monitor_defaults.items():
            if k not in config:
                config[k] = v
        
        return config
    
    def get_matching_configs(self, device: Dict[str, str]) -> List[Dict[str, Any]]:
        """Get device configurations that match the given device.
        
        Args:
            device (dict): Device information dictionary.
            
        Returns:
            list: List of matching configurations.
        """
        config_list = self.config.get('devices', [])
        matches = []
        
        for config in config_list:
            device_config = config.get('device', {})
            if not device_config:  # Empty device config matches all devices
                matches.append(config)
                continue
                
            # Check if all criteria match
            match = True
            for key, value in device_config.items():
                if key not in device or device[key] != value:
                    match = False
                    break
            
            if match:
                matches.append(config)
        
        return matches
    
    def run_unique_scripts(self, device_id, configs, action_type):
        """Run scripts for a specific action type, avoiding duplicates.
        
        Args:
            device_id (str): Device serial number.
            configs (list): List of device configurations.
            action_type (str): Type of action ('connect', 'disconnect', 'sleep', 'wake').
            
        Returns:
            list: List of results.
        """
        seen_scripts = set()
        results = []
        
        for config in configs:
            script = config.get(action_type)
            if not script or script in seen_scripts:
                continue
                
            seen_scripts.add(script)
            
            # Execute script
            env = os.environ.copy()
            env['ANDROID_SERIAL'] = device_id
            
            try:
                result = subprocess.run(
                    ['bash', '-c', script],
                    env=env,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    results.append(f"{action_type} action successful")
                else:
                    results.append(f"{action_type} action failed: {result.stderr.strip()}")
            except Exception as e:
                results.append(f"{action_type} action error: {e}")
        
        return results
    
    def _handle_sleep(self):
        """Handle sleep event."""
        self.logger.info("System going to sleep")
        devices = ADBStatus.get_devices()
        for device in devices:
            matching_configs = self.get_matching_configs(device)
            results = self.run_unique_scripts(device['serial'], matching_configs, 'sleep')
            for result in results:
                self.logger.info(f"  → {device['serial']}: {result}")

    def _handle_wake(self):
        """Handle wake event."""
        self.logger.info("System waking up")
        devices = ADBStatus.get_devices()
        for device in devices:
            matching_configs = self.get_matching_configs(device)
            results = self.run_unique_scripts(device['serial'], matching_configs, 'wake')
            for result in results:
                self.logger.info(f"  → {device['serial']}: {result}")

    def check_devices(self):
        """Check for connected/disconnected devices and run appropriate actions."""
        current_devices = set()
        
        # Get current devices
        for device in ADBStatus.get_devices():
            serial = device['serial']
            current_devices.add(serial)
            
            # Handle new devices
            if serial not in self.known_devices:
                self.logger.info(f"Device connected: {serial}")
                matching_configs = self.get_matching_configs(device)
                results = self.run_unique_scripts(serial, matching_configs, 'connect')
                for result in results:
                    self.logger.info(f"  → {serial}: {result}")
        
        # Handle disconnected devices
        for serial in self.known_devices - current_devices:
            self.logger.info(f"Device disconnected: {serial}")
            # We can't get device details for disconnected devices, so just use serial
            device_info = {'serial': serial}
            matching_configs = self.get_matching_configs(device_info)
            results = self.run_unique_scripts(serial, matching_configs, 'disconnect')
            for result in results:
                self.logger.info(f"  → {serial}: {result}")
        
        # Update known devices
        self.known_devices = current_devices

    def _run_service(self):
        """Run the monitoring service."""
        try:
            # Start sleep monitor if available
            if self._sleep_monitor and not self._sleep_monitor.start():
                self.logger.warning("Sleep monitor could not be started. Sleep/wake events will not be monitored.")
                self.logger.warning("Make sure sleepwatcher is installed: brew install sleepwatcher")
            
            # Set running flag and start time
            self.running = True
            self.start_time = time.time()
            self.logger.info("ADB Monitor started")
            
            # Run the monitoring loop
            try:
                check_interval = self.config.get('check_interval', 5)
                
                while self.running:
                    self.check_devices()
                    time.sleep(check_interval)
            except KeyboardInterrupt:
                self.logger.info("Shutting down ADB Monitor")
            finally:
                # Stop sleep monitor if it was started
                if self._sleep_monitor:
                    self._sleep_monitor.stop()
            
            self.running = False
            
            return True
        except Exception as e:
            self.logger.error(f"Error starting monitor: {e}")
            return False
    
    def stop(self):
        """Stop the monitor.
        
        Returns:
            bool: True if monitor stopped successfully, False otherwise.
        """
        # Stop sleep monitor if it exists
        if self._sleep_monitor:
            self._sleep_monitor.stop()
        
        # Call parent stop method
        return super().stop()
    
    def get_status(self):
        """Get current monitor status.
        
        Returns:
            dict: Status information.
        """
        # Get base status
        status = super().get_status()
        
        # Add monitor-specific info
        status.update({
            "known_devices": list(self.known_devices),
            "sleep_monitor_active": self._sleep_monitor is not None and self._sleep_monitor._running if self._sleep_monitor else False,
            "devices": ADBStatus.get_devices()
        })
        
        return status


def main():
    """CLI entry point for the monitor."""
    from . import version_info
    
    # Parse arguments with program-specific settings
    args = ADBStatusService.parse_args(
        description='ADBStatus Monitor - Monitor for ADB device connections and sleep/wake events',
        prog='adbstatus-monitor'
    )
    
    # Handle version flag or command
    if args.version or args.command == 'version':
        version_info("ADBStatus Monitor")
        return 0  # Success exit code
    
    if args.command == 'start':
        monitor = ADBStatusMonitor(args.config)
        success = monitor.start(foreground=args.foreground)
        if success and args.foreground:
            # This will block until monitor is stopped
            pass
        else:
            # Output status as JSON
            status = {"success": success}
            if not success:
                status["error"] = "Failed to start monitor"
            print(json.dumps(status, indent=2))
            return 0 if success else 1  # Return appropriate exit code
    
    elif args.command == 'stop':
        monitor = ADBStatusMonitor(args.config)
        success = monitor.stop()
        # Output status as JSON
        result = {
            "success": success,
            "message": "Monitor stopped" if success else "No running monitor found"
        }
        print(json.dumps(result, indent=2))
        return 0 if success else 1  # Return appropriate exit code
    
    else:  # status command
        monitor = ADBStatusMonitor(args.config)
        status = monitor.get_status()
        print(json.dumps(status, indent=2))
        return 0 if status["running"] else 1  # Return appropriate exit code


if __name__ == "__main__":
    sys.exit(main()) 