#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import ssl
import json
import os
from adb_info import ADBInfo

port = int(os.environ.get('ADB_STATUS_PORT', '8751'))
cert_file = os.environ.get(
  'ADB_STATUS_CERT',
  "/usr/local/etc/adb-status/cert.pem"
)
key_file = os.environ.get(
  'ADB_STATUS_KEY',
  "/usr/local/etc/adb-status/key.pem"
)

class ADBDevicesHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        devices = ADBInfo.get_devices()
        if self.path == '/':
            contents = devices
        elif self.path.startswith('/'):
            # Split path into field and value, skipping empty strings
            parts = [p for p in self.path[1:].split('/') if p]
            if len(parts) == 2:
                field, value = parts
                contents = [d for d in devices if str(d.get(field, '')).lower() == value.lower()]
        if contents is None:
            self.send_response(404)
            contents = {"error": "Not found"}
        else:
            self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(contents).encode())

if __name__ == "__main__":
    server_address = ("0.0.0.0", port)  # Serve on all addresses, port 8751
    httpd = HTTPServer(server_address, ADBDevicesHandler)
    # Create SSL context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=cert_file, keyfile=key_file)    
    # Wrap the socket with SSL
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    print(f"Serving ADB status on port {port} with HTTPS...")
    httpd.serve_forever()
