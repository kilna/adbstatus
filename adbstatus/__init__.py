"""ADB Status - Android Debug Bridge (ADB) device monitor with sleep/wake support."""

import sys
from pathlib import Path

# Define these variables first
__version__ = None
__author__ = None
__email__ = None

for path in [
  Path(__file__).parent.parent / "pyproject.toml",  # Development location
  Path(__file__).parent / "pyproject.toml",  # Copied during install
]:
  if path.exists():
    with open(path, "rb") as f:
      pyproject = tomli.load(f)
      __version__ = pyproject["project"]["version"]
      __version_info__ = tuple(int(part) for part in __version__.split('.') if part.isdigit())
      __author__ = pyproject["project"]["authors"][0].get("name")
      __email__ = pyproject["project"]["authors"][0].get("email")
      break

if __version__ is None or __author__ is None or __email__ is None:
    sys.stderr.write("FATAL ERROR: Could not determine package version\n")
    sys.exit(1)

# Import all classes with their original names
from .core import ADBStatus
from .service import ADBStatusService
from .server import ADBStatusServer
from .monitor import ADBStatusMonitor
from .sleep_monitor import ADBStatusSleepMonitor

# Create shorter aliases
Status = ADBStatus
Service = ADBStatusService
Server = ADBStatusServer
Monitor = ADBStatusMonitor
SleepMonitor = ADBStatusSleepMonitor

# Version information function
def version_info(program_name="ADBStatus"):
    """Print version information for the program."""
    print(f"{program_name} {__version__}")
    print(f"Author: {__author__} <{__email__}>")

__all__ = [
    # Full names
    'ADBStatus',
    'ADBStatusService', 
    'ADBStatusServer',
    'ADBStatusMonitor',
    'ADBStatusSleepMonitor',
    # Aliases
    'Status',
    'Service',
    'Server',
    'Monitor',
    'SleepMonitor',
    # Utility functions
    'version_info',
] 