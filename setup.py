"""py2app build for KBD.app — v1.4.0

    ./venv/bin/python make_icon.py      (icon/ must be built first)
    ./venv/bin/python setup.py py2app

LSUIElement is what makes this work: the app has no Dock icon and no menu
bar, so it never becomes the active application and never pulls focus out of
the text field the keys are being typed into.

KBD_glyph.png ships in Resources because the app draws the same mark as its
icon in its own credit bar, recolouring it to suit the field colour.
"""

from setuptools import setup

APP = ["kbd.py"]
DATA_FILES = [("", ["icon/KBD_glyph.png"])]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "icon/KBD.icns",
    "plist": {
        "CFBundleName": "KBD",
        "CFBundleDisplayName": "KBD",
        "CFBundleIdentifier": "com.timmccoy.kbd",
        "CFBundleShortVersionString": "1.4.0",
        "CFBundleVersion": "1.4.0",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        # Accessory app: no Dock icon, no menu bar, never activates.
        "LSUIElement": True,
        "NSHumanReadableCopyright":
            "Copyright © 2026 Tim McCoy. All rights reserved.",
        "CFBundleGetInfoString":
            "KBD — floating numeric keypad that types into any app's text field.",
    },
}

setup(
    name="KBD",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
