#!/bin/bash
# RepairFully - Hot Reload (when app is already running with debug)
# Usage: ./hot_reload.sh

PROJECT_DIR="C:/Projects/Amazon Systems Design/RepairFully Camera App Project/mobile"
FLUTTER="/c/Flutter/bin/flutter"

echo "=== HOT RELOAD ==="
echo "Make code changes, then this script will hot-reload the running app."
echo ""

cd "$PROJECT_DIR"

# Try hot reload
$FLUTTER attach --device-id SM_S938B 2>&1