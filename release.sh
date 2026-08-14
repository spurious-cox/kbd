#!/bin/zsh
# Notarize KBD.app and wrap it in a distributable DMG — v1.0.0
#
# Run ./build.sh first; this takes dist/KBD.app as it finds it.
#
# Notarization uses the same keychain profile as the PixPro apps, so no
# password lives here or gets typed. If the profile is ever lost:
#   xcrun notarytool store-credentials "PixProNotary" \
#       --apple-id <appleid> --team-id RUDN8D7ZN9
#
# Both the app and the DMG are notarized and stapled. Stapling the app
# matters because that is what the user drags out of the DMG; stapling the
# DMG matters because that is what they download. Notarizing only one of the
# two leaves a Gatekeeper warning on the other.
set -e
cd "${0:A:h}"

SIGN_ID="4208ABA3EC12F24C1F09C7BB624EFF68B44259DB"
PROFILE="PixProNotary"
APP="dist/KBD.app"
VOLNAME="KBD"

[[ -d "$APP" ]] || { echo "error: $APP not found — run ./build.sh first" >&2; exit 1; }

VERSION=$(plutil -extract CFBundleShortVersionString raw "$APP/Contents/Info.plist")
DMG="dist/KBD-${VERSION}.dmg"

xcrun notarytool history --keychain-profile "$PROFILE" >/dev/null 2>&1 \
    || { echo "error: no notary profile '$PROFILE' in keychain" >&2; exit 1; }

echo "==> notarizing the app (KBD $VERSION)"
rm -f dist/KBD_notarize.zip
ditto -c -k --keepParent "$APP" dist/KBD_notarize.zip
xcrun notarytool submit dist/KBD_notarize.zip --keychain-profile "$PROFILE" --wait
xcrun stapler staple "$APP"

echo "==> building the disk image"
rm -rf dist/dmg "$DMG"
mkdir -p dist/dmg
cp -R "$APP" dist/dmg/
ln -s /Applications dist/dmg/Applications
hdiutil create -volname "$VOLNAME" -srcfolder dist/dmg -ov -format UDZO "$DMG" >/dev/null
rm -rf dist/dmg

echo "==> signing and notarizing the disk image"
codesign --force --timestamp --sign "$SIGN_ID" "$DMG"
xcrun notarytool submit "$DMG" --keychain-profile "$PROFILE" --wait
xcrun stapler staple "$DMG"

echo "==> installing the stapled app to /Applications"
pkill -x KBD 2>/dev/null || true
rm -rf /Applications/KBD.app
cp -R "$APP" /Applications/
xattr -dr com.apple.quarantine /Applications/KBD.app 2>/dev/null || true

echo "==> results"
echo "    dmg:      $DMG  ($(du -h "$DMG" | cut -f1))"
echo "    stapled:  app $(xcrun stapler validate "$APP" >/dev/null 2>&1 && echo YES || echo no), dmg $(xcrun stapler validate "$DMG" >/dev/null 2>&1 && echo YES || echo no)"
spctl -a -t open --context context:primary-signature -v "$DMG" 2>&1 | sed 's/^/    gatekeeper: /'
echo "    running instances: $(pgrep -x KBD | wc -l | tr -d ' ')"
