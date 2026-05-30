#!/bin/bash
# RepairFully - Quick Fix Loop
# Usage: ./quick_fix.sh

cd "C:/Projects/Amazon Systems Design/RepairFully Camera App Project/mobile"

echo "=== Building APK ==="
/c/Flutter/bin/flutter build apk --debug 2>&1

if [ $? -eq 0 ]; then
    echo "=== Installing on device ==="
    /c/Flutter/bin/flutter install --debug
    echo "=== Done! Check app on phone ==="
else
    echo "Build failed!"
fi