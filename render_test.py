#!/usr/bin/env python3
"""
KBD render test
Version: 1.2.0

Builds the keypad panel, renders its content view straight to a PNG and
exits.  Verifies layout and drawing without leaving an app instance running
and without needing screen-recording permission.

    render_test.py OUT.png [preset-name] [scale]

History:
  1.2.0  Optional scale, to check the resized layout.
  1.1.0  Optional preset name, to check credit-bar contrast per colour.
  1.0.0  Initial version.
"""

import sys

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBitmapImageFileTypePNG,
)

import kbd


def main(out_path, preset=None, scale=None):
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    controller = kbd.KeypadController.alloc().init()
    controller.buildPanel()
    controller.panel.orderOut_(None)

    if preset:
        rgb = dict(kbd.FIELD_PRESETS)[preset]
        controller.field.setFieldColor_(kbd._color(*rgb))
    if scale:
        controller.applyScale_(float(scale))

    view = controller.panel.contentView()
    bounds = view.bounds()
    rep = view.bitmapImageRepForCachingDisplayInRect_(bounds)
    view.cacheDisplayInRect_toBitmapImageRep_(bounds, rep)
    data = rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {})
    data.writeToFile_atomically_(out_path, True)

    print("panel %.0fx%.0f -> %s" % (kbd.PANEL_W, kbd.PANEL_H, out_path))
    print("subviews: %d" % len(view.subviews()))
    for sub in view.subviews():
        print("  %-8s tag=%d" % (sub.attributedTitle().string(), sub.tag()))


if __name__ == "__main__":
    main(sys.argv[1],
         sys.argv[2] if len(sys.argv) > 2 else None,
         sys.argv[3] if len(sys.argv) > 3 else None)
