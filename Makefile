SHELL := /bin/bash

VENDOR  := vendor
HEADERS := $(VENDOR)/Headers
DYLIB   := $(VENDOR)/libneurosdk2.dylib
BUILD   := build
BIN     := $(BUILD)/eegcli

SRCS := $(wildcard Sources/*.swift)
SHIM := Sources/shim.h
PLIST := Info.plist

SWIFTC ?= swiftc

.PHONY: all clean run

all: $(BIN)

$(BIN): $(SRCS) $(SHIM) $(PLIST) | $(BUILD)
	@if [ ! -f "$(DYLIB)" ]; then \
	  echo "Missing $(DYLIB). Run ./setup.sh first."; exit 1; \
	fi
	$(SWIFTC) \
	  -import-objc-header $(SHIM) \
	  -I $(HEADERS) \
	  -L $(VENDOR) -lneurosdk2 \
	  -Xlinker -rpath -Xlinker @executable_path/../$(VENDOR) \
	  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker $(PLIST) \
	  -o $(BIN) $(SRCS)

$(BUILD):
	@mkdir -p $(BUILD)

clean:
	rm -rf $(BUILD)

run: $(BIN)
	./$(BIN) $(ARGS)
