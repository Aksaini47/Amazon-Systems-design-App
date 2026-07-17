#!/bin/bash
# RepairFully - Quick Fix Flow
# Code change > install debug > live debug logs

PROJECT_DIR="C:/Projects/Amazon Systems Design/RepairFully Camera App Project/mobile"
FLUTTER="/c/Flutter/bin/flutter"
DEVICE="SM_S938B"

echo "=== QUICK FIX FLOW ==="
echo ""

cd "$PROJECT_DIR"

# Step 1: Build and Install
echo ">>> [1/3] Building APK..."
$FLUTTER build apk --debug 2>&1 | tail -5

if [ $? -eq 0 ]; then
    echo ">>> [2/3] Installing on device..."
    $FLUTTER install --debug 2>&1
else
    echo "Build failed! Fix code and retry."
    exit 1
fi

echo ""
echo ">>> [3/3] Starting live debug logs (Ctrl+C to stop)..."
echo "    Watch for: RepairFully, flutter, error, Exception"
echo ""
adb logcat | grep -iE "repairfully|flutter|error|exception"