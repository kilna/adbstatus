#!/usr/bin/env python3
"""ADBStatus - ADB device information class."""

import argparse
import json
import os
import subprocess
import sys
from . import version_info

class ADBStatus:
    """ADB device information class."""
    
    @staticmethod
    def get_devices(device_id=None):
        """Get list of connected ADB devices.
        
        Args:
            device_id (str, optional): Filter for a specific device ID.
            
        Returns:
            list: List of device dictionaries with details.
        """
        try:
            # Start with the current environment
            env = os.environ.copy()
            if device_id:
                env['ANDROID_SERIAL'] = device_id
            
            adb_output = subprocess.run(
                ["adb", "devices", "-l"],
                capture_output=True, text=True,
                env=env
            )
            
            # Check for errors
            if adb_output.returncode != 0:
                return []  # Return empty list instead of failing
            
            # Parse adb devices output into list of device details
            devices = []
            for line in adb_output.stdout.splitlines()[1:]:  # Skip first line (header)
                if line.strip():  # Skip empty lines
                    parts = line.split()
                    device_info = {
                        "serial": parts[0],
                        "state": parts[1]
                    }
                    # Parse additional properties directly into top level
                    for part in parts[2:]:
                        if ':' in part:
                            key, value = part.split(':', 1)
                            device_info[key] = value
                    devices.append(device_info)
            
            return devices
        except subprocess.SubprocessError:
            # Log the error and return empty list
            return []

def main():
    """Run the ADBStatus command-line utility."""
    parser = argparse.ArgumentParser(description='ADBStatus utility')
    parser.add_argument('-j', '--json', action='store_true',
                      help='Output in JSON format (default)')
    parser.add_argument('-t', '--text', action='store_true',
                      help='Output in text format')
    parser.add_argument('-s', '--serial', 
                      help='Filter devices by serial number')
    parser.add_argument('-v', '--version', action='store_true',
                      help='Show version and exit')
    args = parser.parse_args()
    
    # Handle version request
    if args.version:
        version_info()
        return 0  # Success exit code
    
    # Get devices
    devices = ADBStatus.get_devices(args.serial)
    
    # Output devices
    if args.text:
        # Text output
        if not devices:
            print("No ADB devices connected")
        else:
            print(f"ADB Devices ({len(devices)}):")
            for device in devices:
                print(f"  {device['serial']} - {device['state']}")
                for key, value in device.items():
                    if key not in ['serial', 'state']:
                        print(f"    {key}: {value}")
    else:
        # JSON output (default)
        print(json.dumps(devices, indent=2))
    
    return 0  # Success exit code

if __name__ == "__main__":
    sys.exit(main()) 