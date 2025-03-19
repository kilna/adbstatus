# ADB Status

ADB Status is a set of utilities MacOS for monitoring and managing Android Debug
Bridge (ADB) devices with sleep/wake support.

## Features

- Monitor Android devices connected via ADB
- Automatically restore ADB connections after system sleep/wake cycles
- Provides a secure JSON over HTTPS server for device status
- Run custom scripts when devices connect, disconnect, or the system
  sleeps/wakes
- Integrate with sleepwatcher for system event handling

## Components

This installs three command-line utilities:

- `adbstatus` - Query ADB device information in JSON
- `adbstatus-server` - HTTPS server providing device status via JSON API
- `adbstatus-monitor` - Device monitor with sleep/wake support and custom actions

## Installation

### Using Homebrew (preferred)

```bash
brew tap kilna/adbstatus
brew install adbstatus
```

### Using pip

```bash
pip install adbstatus
```

## Usage

### ADB Status CLI

Query connected ADB devices:

```bash
# Default JSON output
adbstatus

# Text output
adbstatus -t

# Filter by device serial number
adbstatus -s <serial>

# Show version information
adbstatus -v
```

### ADB Status Server

The server provides an HTTPS API for ADB device information:

```bash
# Start the server
adbstatus-server start

# Start in foreground mode (for debugging)
adbstatus-server start -f

# Check server status
adbstatus-server status

# Stop the server
adbstatus-server stop

# Show version information
adbstatus-server -v
```

API Endpoints:
- `GET /devices` - List all connected devices
- `GET /devices/<serial>` - Get information about a specific device

### ADB Status Monitor

The monitor watches for device connections and system sleep/wake events:

```bash
# Start the monitor
adbstatus-monitor start

# Start in foreground mode (for debugging)
adbstatus-monitor start -f

# Check monitor status
adbstatus-monitor status

# Stop the monitor
adbstatus-monitor stop

# Show version information
adbstatus-monitor -v
```

### Using Homebrew Services (macOS)

You can also manage services using Homebrew:

```bash
# Start services
brew services start adbstatus-server
brew services start adbstatus-monitor

# Check service status
brew services list | grep adbstatus

# Stop services
brew services stop adbstatus-server
brew services stop adbstatus-monitor
```

## Configuration

### Server Configuration

The server configuration file (`server.yml`) is located at:
- `/usr/local/etc/adbstatus/server.yml` (Homebrew installation)
- `~/.config/adbstatus/server.yml` (pip installation)

Example configuration:

```yaml
# Server settings
port: 8999
bind_address: "0.0.0.0"

# SSL Configuration
ssl:
  enabled: true
  cert_file: "/usr/local/etc/adbstatus/ssl/adbstatus.crt"
  key_file: "/usr/local/etc/adbstatus/ssl/adbstatus.key"

# Logging
logging:
  file: "~/Library/Logs/adbstatus-server.log"
  level: "info"  # debug, info, warning, error, critical
```

### Monitor Configuration

The monitor configuration file (`monitor.yml`) is located at:
- `/usr/local/etc/adbstatus/monitor.yml` (Homebrew installation)
- `~/.config/adbstatus/monitor.yml` (pip installation)

Example configuration:

```yaml
# Monitor settings
check_interval: 2  # seconds between device checks

# Logging
logging:
  file: "~/Library/Logs/adbstatus-monitor.log"
  level: "info"  # debug, info, warning, error, critical

# Sleep/Wake Settings
sleep_monitor:
  enabled: true
  pid_file: "~/.adbstatus_sleepwatcher.pid"

# Device configurations
devices:
  - device:
      # Filter by device properties (they must all be true)
      # If no filters are provided, actions will apply to all devices
      name: "DeviceName"
    connect: |
      # Shell commands to run when device connects
      echo "Device connected"
    disconnect: |
      # Shell commands to run when device disconnects
      echo "Device disconnected"
    sleep: |
      # Shell commands to run when system sleeps
      echo "System sleeping"
    wake: |
      # Shell commands to run when system wakes
      echo "System waking"
```

### SSL Certificates

SSL certificates are stored at:
- `/usr/local/etc/adbstatus/ssl/adbstatus.crt`
- `/usr/local/etc/adbstatus/ssl/adbstatus.key`

These are automatically generated when the package is installed via Homebrew.

For pip installations, you'll need to generate these certificates manually or provide your own in the configuration.

### Log Files

Default log file locations:
- `~/Library/Logs/adbstatus-server.log`
- `~/Library/Logs/adbstatus-monitor.log`

## Using as a Python Library

ADB Status can also be used as a Python library:

```python
# Get ADB device information
from adbstatus import ADBStatus
# Or use the shorthand alias
from adbstatus import Status

# Get all devices
devices = ADBStatus.get_devices()
# Or filter by serial
devices = ADBStatus.get_devices(serial="ABCD1234")

# Start a server programmatically
from adbstatus import ADBStatusServer
# Or use the shorthand alias
from adbstatus import Server

server = ADBStatusServer()
server.start()

# Use the monitor programmatically
from adbstatus import ADBStatusMonitor
# Or use the shorthand alias
from adbstatus import Monitor

monitor = ADBStatusMonitor()
monitor.start()
```

## Dependencies

- Python 3.8+
- Android Debug Bridge (ADB)
- sleepwatcher (for sleep/wake monitoring on macOS)

## Author

Kilna, Anthony <kilna@kilna.com>

## License

MIT
