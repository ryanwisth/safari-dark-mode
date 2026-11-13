#!/bin/bash
# Build "Dark Mode for Safari.app" without Xcode: swiftc, a hand-assembled
# bundle, and an ad-hoc signature. Safari needs the web extension inside an
# app extension (.appex) inside an app, both sandboxed.
#
#   tools/build.sh             build into build/
#   tools/build.sh --install   build, then install to /Applications and register with Safari
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/build"
APP="$OUT/Dark Mode for Safari.app"
EXT="$APP/Contents/PlugIns/DarkModeExtension.appex"
SDK="$(xcrun --show-sdk-path)"
TARGET="arm64-apple-macos13.0"
BUNDLE_ID="com.ryanwisth.DarkMode"
DEST="/Applications/Dark Mode for Safari.app"

[[ -f "$OUT/AppIcon.icns" ]] || python3 "$ROOT/tools/make_icons.py"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$EXT/Contents/MacOS" "$EXT/Contents/Resources"

# --- app extension: native stub + the web extension files as resources
swiftc -O -parse-as-library -application-extension -module-name DarkModeExtension \
  -target "$TARGET" -sdk "$SDK" "$ROOT/app/Handler.swift" -framework SafariServices \
  -Xlinker -e -Xlinker _NSExtensionMain -Xlinker -application_extension \
  -o "$EXT/Contents/MacOS/DarkModeExtension"
cp "$ROOT/app/Ext-Info.plist" "$EXT/Contents/Info.plist"
rsync -a --exclude '.DS_Store' "$ROOT/extension/" "$EXT/Contents/Resources/"

# --- container app
swiftc -O -parse-as-library -module-name DarkMode \
  -target "$TARGET" -sdk "$SDK" "$ROOT/app/App.swift" -framework SafariServices -framework AppKit \
  -o "$APP/Contents/MacOS/DarkMode"
cp "$ROOT/app/App-Info.plist" "$APP/Contents/Info.plist"
cp "$OUT/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
printf 'APPL????' > "$APP/Contents/PkgInfo"

# --- sign inside-out (extension first), ad hoc
codesign --force --sign - --entitlements "$ROOT/app/sandbox.entitlements" "$EXT"
codesign --force --sign - --entitlements "$ROOT/app/sandbox.entitlements" "$APP"
codesign --verify --deep --strict "$APP"
echo "built: $APP"

[[ "${1:-}" == "--install" ]] || exit 0

# Replace only our own earlier install.
if [[ -e "$DEST" ]]; then
  existing="$(/usr/libexec/PlistBuddy -c 'Print CFBundleIdentifier' "$DEST/Contents/Info.plist" 2>/dev/null || true)"
  if [[ "$existing" != "$BUNDLE_ID" ]]; then
    echo "refusing: $DEST exists and is not $BUNDLE_ID (found '$existing')" >&2
    exit 1
  fi
  pkill -x DarkMode 2>/dev/null || true
  rm -rf "$DEST"
fi
ditto "$APP" "$DEST"
# One registered copy only, so Safari never loads a stale build.
LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
"$LSREG" -u "$APP" 2>/dev/null || true
rm -rf "$APP"
"$LSREG" -f "$DEST"
pluginkit -a "$DEST/Contents/PlugIns/DarkModeExtension.appex"
open "$DEST"
echo "installed: $DEST"
