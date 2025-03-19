#!/usr/bin/env python3
"""ADBStatusServer - HTTP server for ADB device status information."""

import argparse
import json
import logging
import os
import psutil
import signal
import ssl
import sys
import time
import yaml
import http.server
import socketserver
import threading
from typing import Dict, Any, Optional, List, Tuple, Type, ClassVar, Union
from . import version_info
from .core import ADBStatus
from .service import ADBStatusService

class ADBStatusRequestHandler(http.server.BaseHTTPRequestHandler):
    """Handler for ADB Status HTTP requests."""
  
  def do_GET(self) -> None:
    """Handle GET requests."""
        if self.path == '/':
      self.send_response(200)
      self.send_header('Content-type', 'application/json')
      self.end_headers()
      
            # Get device information
            devices = ADBStatus.get_devices()
            response = {
                'devices': devices,
                'count': len(devices)
            }
            
            self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))
    else:
      self.send_response(404)
            self.send_header('Content-type', 'application/json')
      self.end_headers()
            self.wfile.write(json.dumps({'error': 'Not found'}).encode('utf-8'))
    
    def log_request(self, code: Union[int, str] = '-', size: Union[int, str] = '-') -> None:
        """Log HTTP requests."""
        if hasattr(self.server, 'logger'):
            self.server.logger.info(f"{self.client_address[0]} - {self.command} {self.path} {code}")


class ADBStatusServer(ADBStatusService):
    """ADB Status HTTP server class."""
    
    def __init__(self, config_path: Optional[str] = None, 
                 logger: Optional[logging.Logger] = None) -> None:
        """Initialize the server with the given configuration."""
        super().__init__('server', config_path, logger)
        self.httpd = None
    
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load server configuration from YAML file.
        
        Loads base configuration using the parent class method, then
        adds server-specific defaults.
  
  Args:
            config_path (str, optional): Path to configuration file.
  
  Returns:
            dict: Server configuration.
        """
        # Get base configuration
        config = super().load_config(config_path)
        
        # Find appropriate SSL paths based on platform
        ssl_paths = [
            '/usr/local/etc/adbstatus/ssl',  # Intel Mac/Linux
            '/opt/homebrew/etc/adbstatus/ssl'  # Apple Silicon Mac
        ]
        
        ssl_dir = None
        for path in ssl_paths:
            if os.path.exists(path):
                ssl_dir = path
                break
        
        if not ssl_dir:
            ssl_dir = '/usr/local/etc/adbstatus/ssl'  # Default fallback
        
        # Add server-specific defaults
        server_defaults = {
            'port': 8999,
            'bind_address': '0.0.0.0',
            'ssl': {
                'enabled': True,
                'cert_file': f'{ssl_dir}/adbstatus.crt',
                'key_file': f'{ssl_dir}/adbstatus.key'
            }
        }
        
        # Merge with server defaults
        for k, v in server_defaults.items():
            if k not in config:
                config[k] = v
        
        return config
    
    def _run_service(self):
        """Run the HTTP server."""
        try:
            port = self.config.get('port', 8999)
            bind_address = self.config.get('bind_address', '0.0.0.0')
            
            # Create server
            class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
                pass
            
            self.httpd = ThreadedHTTPServer((bind_address, port), ADBStatusRequestHandler)
            self.httpd.logger = self.logger
            
            # Configure SSL if enabled
            ssl_config = self.config.get('ssl', {})
            if ssl_config.get('enabled', True):
                cert_file = os.path.expanduser(ssl_config.get('cert_file', '/usr/local/etc/adbstatus/ssl/adbstatus.crt'))
                key_file = os.path.expanduser(ssl_config.get('key_file', '/usr/local/etc/adbstatus/ssl/adbstatus.key'))
                
                if os.path.exists(cert_file) and os.path.exists(key_file):
  context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    context.load_cert_chain(cert_file, key_file)
                    self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)
                    server_type = "HTTPS"
                else:
                    self.logger.warning(f"SSL certificate or key not found. Using HTTP instead.")
                    server_type = "HTTP"
            else:
                server_type = "HTTP"
            
            # Set running flags
            self.running = True
            self.start_time = self.httpd.server_activate()
            
            self.logger.info(f"{server_type} server started on {bind_address}:{port}")
            
            # Start server in a separate thread
            server_thread = threading.Thread(target=self.httpd.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            # Wait for server thread or until stopped
            try:
                while self.running:
                    server_thread.join(1.0)  # Check every second if we should stop
  except KeyboardInterrupt:
                self.logger.info("Shutting down server...")
            finally:
                if self.httpd:
                    self.httpd.shutdown()
                    self.httpd.server_close()
                self.running = False
            
            return True
        except Exception as e:
            self.logger.error(f"Error starting server: {e}")
            self.running = False
            return False
    
    def stop(self):
        """Stop the HTTP server."""
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
                self.httpd = None
                self.running = False
                return True
            except Exception as e:
                self.logger.error(f"Error stopping server: {e}")
                return False
        else:
            return super().stop()
    
    def get_status(self):
        """Get current server status."""
        # Get base status
        status = super().get_status()
        
        # Add server-specific info
        status.update({
            "port": self.config.get('port', 8999),
            "bind_address": self.config.get('bind_address', '0.0.0.0'),
            "ssl_enabled": self.config.get('ssl', {}).get('enabled', True)
        })
        
        return status

def main():
    """CLI entry point for the server."""
    from . import version_info
    
    # Parse arguments with program-specific settings
    args = ADBStatusService.parse_args(
        description='ADBStatus Server - HTTPS server for ADB device status',
        prog='adbstatus-server'
    )
    
    # Handle version flag or command
    if args.version or args.command == 'version':
        version_info("ADBStatus Server")
        return 0  # Success exit code
    
    if args.command == 'start':
        server = ADBStatusServer(args.config)
        success = server.start(foreground=args.foreground)
        if success and args.foreground:
            # This will block until server is stopped
            pass
      else:
            # Output status as JSON
            status = {"success": success}
            if not success:
                status["error"] = "Failed to start server"
            print(json.dumps(status, indent=2))
            return 0 if success else 1  # Return appropriate exit code
  
  elif args.command == 'stop':
        server = ADBStatusServer(args.config)
        success = server.stop()
        # Output status as JSON
        result = {
            "success": success,
            "message": "Server stopped" if success else "No running server found"
        }
        print(json.dumps(result, indent=2))
        return 0 if success else 1  # Return appropriate exit code
    
    else:  # status command
        server = ADBStatusServer(args.config)
        status = server.get_status()
        print(json.dumps(status, indent=2))
        return 0 if status["running"] else 1  # Return appropriate exit code


if __name__ == "__main__":
    sys.exit(main()) 