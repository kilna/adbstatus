# Configuration
PREFIX ?= /usr/local
LIBEXEC ?= $(PREFIX)/libexec/adbstatus
ETC ?= $(PREFIX)/etc/adbstatus
PYTHON ?= /usr/bin/env python3

.PHONY: all install clean

all: install

install:
	@echo "Installing ADBStatus..."
	@mkdir -p $(LIBEXEC)
	@mkdir -p $(ETC)/ssl
	@mkdir -p $(PREFIX)/bin
	
	# Copy source files
	@cp -r adbstatus $(LIBEXEC)/
	
	# Create executable scripts
	@echo '#!/usr/bin/env python3' > $(PREFIX)/bin/adbstatus
	@echo 'import sys; sys.path.insert(0, "$(LIBEXEC)"); from adbstatus.core import ADBStatus; sys.exit(ADBStatus.main())' >> $(PREFIX)/bin/adbstatus
	@chmod 755 $(PREFIX)/bin/adbstatus
	
	@echo '#!/usr/bin/env python3' > $(PREFIX)/bin/adbstatus-server
	@echo 'import sys; sys.path.insert(0, "$(LIBEXEC)"); from adbstatus.server import ADBStatusServer; sys.exit(ADBStatusServer.main())' >> $(PREFIX)/bin/adbstatus-server
	@chmod 755 $(PREFIX)/bin/adbstatus-server
	
	@echo '#!/usr/bin/env python3' > $(PREFIX)/bin/adbstatus-monitor
	@echo 'import sys; sys.path.insert(0, "$(LIBEXEC)"); from adbstatus.monitor import ADBStatusMonitor; sys.exit(ADBStatusMonitor.main())' >> $(PREFIX)/bin/adbstatus-monitor
	@chmod 755 $(PREFIX)/bin/adbstatus-monitor
	
	# Install config files if they don't exist
	@if [ ! -f $(ETC)/server.yml ]; then cp -f etc/server.yml $(ETC)/; fi
	@if [ ! -f $(ETC)/monitor.yml ]; then cp -f etc/monitor.yml $(ETC)/; fi
	
	# Generate SSL certificates if they don't exist
	@if [ ! -f $(ETC)/ssl/adbstatus.crt ] || [ ! -f $(ETC)/ssl/adbstatus.key ]; then \
		openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj "/CN=adbstatus" \
			-keyout $(ETC)/ssl/adbstatus.key -out $(ETC)/ssl/adbstatus.crt; \
		chmod 644 $(ETC)/ssl/adbstatus.crt; \
		chmod 600 $(ETC)/ssl/adbstatus.key; \
	fi
	
	@echo
	@echo "ADBStatus has been installed."
	@echo "Python dependencies: tomli (for Python <3.11), psutil, pyyaml"
	@echo "If needed: pip install tomli psutil pyyaml"

clean:
	@echo "Cleaning up..."
	@rm -rf $(LIBEXEC)
	@rm -f $(PREFIX)/bin/adbstatus
	@rm -f $(PREFIX)/bin/adbstatus-server
	@rm -f $(PREFIX)/bin/adbstatus-monitor
	@echo "Cleanup complete. Config files and SSL certificates were not removed." 