"""py2app build for KBD.app

    ./venv/bin/python make_icon.py      (icon/ must be built first)
    ./venv/bin/python setup.py py2app

LSUIElement is what makes this work: the app has no Dock icon and no menu
bar, so it never becomes the active application and never pulls focus out of
the text field the keys are being typed into.

KBD_glyph.png ships in Resources because the app draws the same mark as its
icon in its own credit bar, recolouring it to suit the field colour.
"""

import re
from pathlib import Path

from setuptools import setup

APP = ["kbd.py"]
DATA_FILES = [("", ["icon/KBD_glyph.png"])]


def app_version():
    """The single source of truth: APP_VERSION in kbd.py.

    These were separate numbers until 1.5.2, and they drifted the first time
    it mattered — kbd.py said 1.5.2 and drew "KBD 1.5.2" in its own credit
    bar while the bundle it shipped in still declared 1.5.1. Reading it from
    the source means the two cannot disagree again. Bump APP_VERSION in
    kbd.py and nowhere else.
    """
    source = Path(__file__).with_name("kbd.py").read_text()
    match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', source, re.MULTILINE)
    if not match:
        raise SystemExit("setup.py: APP_VERSION not found in kbd.py")
    return match.group(1)


VERSION = app_version()

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "icon/KBD.icns",
    "plist": {
        "CFBundleName": "KBD",
        "CFBundleDisplayName": "KBD",
        "CFBundleIdentifier": "com.timmccoy.kbd",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
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
