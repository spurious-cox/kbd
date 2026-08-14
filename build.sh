#!/bin/zsh
# Build, sign and install KBD.app — v1.1.0
#
# v1.1.0 replaced `codesign --deep` with a per-binary pass under the hardened
# runtime. --deep silently skipped the .so files py2app buries under
# Resources and the extension-less Mach-O at Contents/MacOS/python, and
# Apple rejected the notarization for exactly those:
#   "The executable does not have the hardened runtime enabled."
#   "The binary is not signed with a valid Developer ID certificate."
# `file` is the only reliable test for what is a Mach-O; filenames are not.
#
# Signing uses the Developer ID Application certificate (valid to 2027-02-01),
# selected by SHA-1 HASH rather than by name: expired certificates with similar
# names are still in the keychain and signing by name can pick a dead one.
# --timestamp is not optional — a timestamped signature stays valid after the
# certificate expires.
#
# A STABLE signature matters more here than usual: macOS ties the Accessibility
# permission to the app's code signature. Ad-hoc signing changes identity on
# every rebuild, which would make macOS forget the grant and silently stop the
# keys from typing until the permission was granted again.
#
#   ./build.sh              build and sign into dist/
#   ./build.sh --install    also install to /Applications
set -e
cd "${0:A:h}"

SIGN_ID="4208ABA3EC12F24C1F09C7BB624EFF68B44259DB"

if ! security find-identity -p codesigning | grep -q "$SIGN_ID"; then
    echo "error: signing identity $SIGN_ID not in keychain — see header of this script" >&2
    exit 1
fi

echo "==> killing any running instance"
pkill -x KBD 2>/dev/null || true
sleep 1

echo "==> building"
rm -rf build dist
./venv/bin/python setup.py py2app >/dev/null

echo "==> signing inner binaries with the hardened runtime"
find dist/KBD.app -type f -print0 2>/dev/null | while IFS= read -r -d $'\0' f; do
    if file -b "$f" 2>/dev/null | grep -q 'Mach-O'; then
        codesign --force --timestamp --options runtime --sign "$SIGN_ID" "$f" 2>/dev/null || true
    fi
done

echo "==> sealing nested frameworks, then the app"
# Nested bundles are sealed as units, after their contents; the app last, or
# its own signature is invalidated by everything signed inside it.
find dist/KBD.app -name '*.framework' -print0 2>/dev/null \
    | xargs -0 -n1 -I{} codesign --force --timestamp --options runtime --sign "$SIGN_ID" {} 2>/dev/null || true
codesign --force --timestamp --options runtime \
    --entitlements kbd.entitlements --sign "$SIGN_ID" dist/KBD.app
codesign --verify --deep --strict dist/KBD.app

if [[ "$1" == "--install" ]]; then
    echo "==> installing to /Applications"
    rm -rf /Applications/KBD.app
    cp -R dist/KBD.app /Applications/
    xattr -dr com.apple.quarantine /Applications/KBD.app 2>/dev/null || true
    codesign -dv /Applications/KBD.app 2>&1 | grep -E "Identifier=|Authority="
    plutil -extract CFBundleShortVersionString raw /Applications/KBD.app/Contents/Info.plist
fi

echo "==> running instances: $(pgrep -x KBD | wc -l | tr -d ' ')"
