import subprocess
import os

class ADBInfo:
    @staticmethod
    def get_devices(device_id=None):
        # Start with the current environment
        env = os.environ.copy()
        if device_id:
            env['ANDROID_SERIAL'] = device_id
        
        adb_output = subprocess.run(
            ["adb", "devices", "-l"],
            capture_output=True, text=True,
            env=env
        )
        
        # Parse adb devices output into list of device details
        devices = []
        for line in adb_output.stdout.splitlines()[1:]:  # Skip empty lines
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