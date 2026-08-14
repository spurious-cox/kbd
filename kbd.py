#!/usr/bin/env python3
"""
KBD - floating numeric keypad for macOS
Version: 1.5.1

A borderless, non-activating floating panel holding a numeric pad: two rows
of digits, a stacked column of space / backspace / return / decimal, and a
vertical DISMISS, all under a credit bar.  Key presses are posted as real
keyboard events to the HID event tap, so they land in whatever text field
currently has keyboard focus -- in any application.

Behaviour:
  * Non-activating panel: clicking a key never steals focus from the text
    field being typed into.
  * Floats above all windows, on every Space, including full-screen apps.
  * Draggable from anywhere on the coloured field, credit bar included.
  * Resizable: drag the corner grip, or option-drag anywhere on the field, or
    pick a size from the right-click menu.  The whole keypad scales as one.
  * Right-click anywhere for the field colour menu (eight preset colours).
  * Persistent until DISMISS is pressed, which quits the app.
  * Panel position, size and field colour are remembered across launches.

Requires Accessibility permission (System Settings > Privacy & Security >
Accessibility) so the app is allowed to post keyboard events.  macOS shows
its own permission prompt only once per app, and never again once answered,
so KBD does its own asking: it checks on launch, offers to open the right
settings pane, says so in the credit bar while the permission is missing, and
watches for the grant so the warning clears the moment it is given.

Geometry is kept as one set of base measurements multiplied by a single
scale factor, rather than as an autoresizing layout.  A keypad wants to keep
its proportions at every size, and one scale factor is also what a future
iOS port would need.

History:
  1.5.1  Symbol keys centred on their ink rather than their text box. AppKit
         centres a title by the line box, which put the low-sitting glyphs
         (. ⎵ ↵) near the bottom of their keys.
  1.5.0  Space and return keys added. The right-hand wide keys are replaced
         by one column of four half-height keys (space, backspace, return,
         decimal) and a vertical DISMISS spanning both rows, to Tim's
         mockup: the stacked keys pair up inside each digit row's height,
         so the two grids stay aligned.
  1.4.0  App icon from Tim's artwork, the same mark centred in the credit
         bar, and an Accessibility permission flow that can ask more than
         once.
  1.3.0  Uniform resizing (corner grip, option-drag, size menu), size saved.
  1.2.0  Half-width decimal key, DISMISS widened to close the row, custom
         colour picker dropped (it was the one action that took focus off
         the target text field).
  1.1.0  Credit bar, decimal-point key, selectable field colour.
  1.0.0  Initial version: 12 keys, drag anywhere, position remembered.
"""

import math
import os

import objc
from Foundation import (
    NSAffineTransform,
    NSBundle,
    NSObject,
    NSMakePoint,
    NSMakeRect,
    NSMakeSize,
    NSNotificationCenter,
    NSPointInRect,
    NSTimer,
    NSURL,
    NSUserDefaults,
    NSZeroRect,
)
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSAttributedString,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSBitmapImageRep,
    NSButton,
    NSColor,
    NSColorSpace,
    NSCompositingOperationSourceAtop,
    NSCompositingOperationSourceOver,
    NSDeviceRGBColorSpace,
    NSEvent,
    NSEventModifierFlagOption,
    NSFont,
    NSFontAttributeName,
    NSFontWeightMedium,
    NSFontWeightRegular,
    NSFontWeightSemibold,
    NSForegroundColorAttributeName,
    NSGraphicsContext,
    NSImage,
    NSImageOnly,
    NSMenu,
    NSMenuItem,
    NSMutableParagraphStyle,
    NSOffState,
    NSOnState,
    NSPanel,
    NSParagraphStyleAttributeName,
    NSRectFillUsingOperation,
    NSScreen,
    NSStatusWindowLevel,
    NSTextAlignmentCenter,
    NSTextAlignmentLeft,
    NSTextAlignmentRight,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowDidMoveNotification,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
    NSWorkspace,
)
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    CGEventSourceCreate,
    kCGEventSourceStateHIDSystemState,
    kCGHIDEventTap,
)
from ApplicationServices import (
    AXIsProcessTrusted,
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)

# ---------------------------------------------------------------- constants

APP_VERSION = "1.5.1"
CREDIT_TEXT = "© 2026 Tim McCoy"
DEFAULTS_ORIGIN_KEY = "KBDPanelOrigin"
DEFAULTS_COLOR_KEY = "KBDFieldColor"
DEFAULTS_SCALE_KEY = "KBDScale"

# Virtual keycodes (ANSI layout).  47 is the ordinary period, not the numeric
# keypad's decimal key, so it types a "." into any field regardless of layout.
KEYCODES = {
    "0": 29, "1": 18, "2": 19, "3": 20, "4": 21,
    "5": 23, "6": 22, "7": 26, "8": 28, "9": 25,
    ".": 47,
}
KEYCODE_DELETE = 51
KEYCODE_SPACE = 49
KEYCODE_RETURN = 36
TAG_DISMISS = -1  # sentinel: no keycode can collide with it

# Menu tags: colour presets take their list index, size presets are offset so
# the two sets can never collide.
TAG_SIZE_BASE = 100

# Base geometry, in points, at 100%.  Five digit keys wide by two rows, then
# a column of four half-height keys, then DISMISS standing on end across both
# rows.  The stacked keys pair up within each digit row's height -- a tight
# gap inside a pair, the ordinary row gap between pairs -- so the stack reads
# as two halves of two keys rather than four evenly spaced ones.
MARGIN = 10.0
GAP = 8.0
KEY_W = 56.0
KEY_H = 46.0
STACK_W = 56.0
STACK_GAP = 3.0                                 # inside a pair
STACK_H = (KEY_H - STACK_GAP) / 2.0             # 21.5
DISMISS_W = 42.0
DISMISS_H = KEY_H * 2 + GAP                     # 100
DIGITS_W = KEY_W * 5 + GAP * 4                  # five digit keys: 312
ROW_W = DIGITS_W + GAP + STACK_W + GAP + DISMISS_W      # 426
HEADER_H = 20.0
HEADER_GAP = 6.0
PANEL_W = ROW_W + MARGIN * 2                                        # 508
PANEL_H = MARGIN * 2 + KEY_H * 2 + GAP + HEADER_GAP + HEADER_H      # 146
FIELD_RADIUS = 8.0
KEY_RADIUS = 7.0
GRIP_SIZE = 18.0
CREDIT_FONT_SIZE = 11.0
GLYPH_H = 19.0              # the KBD mark, centred in the credit bar

# Where System Settings keeps the switch KBD needs.
ACCESSIBILITY_PANE = (
    "x-apple.systempreferences:com.apple.preference.security"
    "?Privacy_Accessibility"
)
TRUST_POLL_SECONDS = 2.0

# Resize limits, as a multiple of the base size.
MIN_SCALE = 0.6
MAX_SCALE = 3.0
SIZE_PRESETS = [("Small", 0.75), ("Default", 1.0), ("Large", 1.25),
                ("Larger", 1.5), ("Largest", 2.0)]


def _color(r, g, b):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0)


# Field colour presets offered on the right-click menu.
DEFAULT_FIELD_COLOR = (0.12, 0.56, 1.00)
FIELD_PRESETS = [
    ("Blue", DEFAULT_FIELD_COLOR),
    ("Indigo", (0.35, 0.34, 0.84)),
    ("Teal", (0.11, 0.60, 0.62)),
    ("Green", (0.20, 0.64, 0.35)),
    ("Orange", (0.95, 0.55, 0.15)),
    ("Red", (0.83, 0.26, 0.26)),
    ("Graphite", (0.38, 0.39, 0.42)),
    ("Charcoal", (0.16, 0.17, 0.19)),
]

KEY_FACE = _color(0.98, 0.98, 0.98)       # key face, at rest
KEY_FACE_DOWN = _color(0.80, 0.80, 0.82)  # key face, while held
KEY_BORDER = _color(0.72, 0.72, 0.74)
KEY_TEXT = _color(0.20, 0.20, 0.22)


def rgb_components(color):
    """(r, g, b) in device RGB, safe for any colour value."""
    converted = color.colorUsingColorSpace_(NSColorSpace.deviceRGBColorSpace())
    if converted is None:
        return DEFAULT_FIELD_COLOR
    return (converted.redComponent(),
            converted.greenComponent(),
            converted.blueComponent())


def is_light(color):
    """True when the field colour is bright enough to need dark credit text."""
    r, g, b = rgb_components(color)
    return (0.299 * r + 0.587 * g + 0.114 * b) > 0.62


def clamp_scale(scale):
    return max(MIN_SCALE, min(MAX_SCALE, scale))


# ------------------------------------------------------------- the KBD mark

def glyph_path():
    """KBD_glyph.png, whether running from the bundle or from source."""
    packaged = NSBundle.mainBundle().pathForResource_ofType_("KBD_glyph", "png")
    if packaged:
        return packaged
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "icon", "KBD_glyph.png")
    return local if os.path.exists(local) else None


def load_glyph():
    path = glyph_path()
    if path is None:
        return None
    return NSImage.alloc().initWithContentsOfFile_(path)


def ink_image(text, font, color):
    """`text` as an image cropped to the pixels it actually inks.

    A button centres its title on the text line box, which includes the
    ascender and descender whether or not the glyph uses them: `.`, `⎵` and
    `↵` all sit at the bottom of that box and so land low on the key.
    Cropping to the ink and letting the button centre the image instead puts
    the mark where the eye expects it."""
    attributes = {
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: color,
    }
    string = NSAttributedString.alloc().initWithString_attributes_(
        text, attributes)
    box = string.size()
    inset = 4
    width = int(math.ceil(box.width)) + inset * 2
    height = int(math.ceil(box.height)) + inset * 2

    rep = NSBitmapImageRep.alloc()
    rep = rep.initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, width, height, 8, 4, True, False, NSDeviceRGBColorSpace, 0, 0)
    context = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(context)
    string.drawAtPoint_(NSMakePoint(inset, inset))
    NSGraphicsContext.restoreGraphicsState()

    # Scan the alpha channel for the ink's bounding box. Rows run top-down
    # in the bitmap and bottom-up in AppKit, hence the flip below.
    data = rep.bitmapData()
    row_bytes = rep.bytesPerRow()
    min_x, min_y, max_x, max_y = width, height, -1, -1
    for row in range(height):
        base = row * row_bytes
        for column in range(width):
            if data[base + column * 4 + 3]:
                min_x = min(min_x, column)
                max_x = max(max_x, column)
                min_y = min(min_y, row)
                max_y = max(max_y, row)
    if max_x < 0:
        return None

    image = NSImage.alloc().initWithSize_(
        NSMakeSize(max_x - min_x + 1, max_y - min_y + 1))
    image.lockFocus()
    string.drawAtPoint_(NSMakePoint(
        inset - min_x, inset - (height - 1 - max_y)))
    image.unlockFocus()
    return image


def rotated_text_image(text, font, color):
    """`text` drawn on its side, reading top to bottom.

    AppKit has no vertical button title, so DISMISS is rendered into an image
    and handed to the button as its picture instead."""
    attributes = {
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: color,
    }
    string = NSAttributedString.alloc().initWithString_attributes_(
        text, attributes)
    size = string.size()
    image = NSImage.alloc().initWithSize_(NSMakeSize(size.height, size.width))
    image.lockFocus()
    transform = NSAffineTransform.transform()
    # Composed as translate(rotate(p)): a point is turned a quarter turn
    # clockwise, then pushed back up into the image.
    transform.translateXBy_yBy_(0.0, size.width)
    transform.rotateByDegrees_(-90.0)
    transform.concat()
    string.drawAtPoint_(NSMakePoint(0.0, 0.0))
    image.unlockFocus()
    return image


def tinted_glyph(glyph, color, height):
    """The mark recoloured to `color`, drawn into its own image so the tint
    lands on the artwork's alpha and not on the field behind it."""
    if glyph is None or height <= 0:
        return None
    source = glyph.size()
    if source.height <= 0:
        return None
    width = source.width * height / source.height
    tinted = NSImage.alloc().initWithSize_(NSMakeSize(width, height))
    rect = NSMakeRect(0, 0, width, height)
    tinted.lockFocus()
    glyph.drawInRect_fromRect_operation_fraction_(
        rect, NSZeroRect, NSCompositingOperationSourceOver, 1.0)
    color.set()
    NSRectFillUsingOperation(rect, NSCompositingOperationSourceAtop)
    tinted.unlockFocus()
    return tinted


# ------------------------------------------------------------ event posting

def post_keycode(keycode):
    """Post a key down/up pair to the HID tap, i.e. to the focused field."""
    source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)
    for is_down in (True, False):
        event = CGEventCreateKeyboardEvent(source, keycode, is_down)
        if event is None:
            continue
        CGEventSetFlags(event, 0)  # never inherit a stuck modifier
        CGEventPost(kCGHIDEventTap, event)


# --------------------------------------------------------------- ui classes

class KeypadPanel(NSPanel):
    """A panel that refuses to become key, so focus stays in the text field."""

    def canBecomeKeyWindow(self):
        return False

    def canBecomeMainWindow(self):
        return False


class FieldView(NSView):
    """The coloured field: drag handle, credit bar, and resize grip."""

    def initWithFrame_(self, frame):
        self = objc.super(FieldView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.fieldColor = _color(*DEFAULT_FIELD_COLOR)
        self.scale = 1.0
        self.controller = None
        self.resizing = False
        self.resizeStartX = 0.0
        self.resizeStartWidth = PANEL_W
        self.glyph = load_glyph()
        self.tintedGlyph = None      # cached, rebuilt when colour or size change
        self.tintedKey = None
        return self

    def setFieldColor_(self, color):
        self.fieldColor = color
        self.setNeedsDisplay_(True)

    def setScale_(self, scale):
        self.scale = scale
        self.setNeedsDisplay_(True)

    # -- drawing ----------------------------------------------------------

    def creditColors(self):
        """Credit text: dark on a light field, white on a dark one."""
        if is_light(self.fieldColor):
            return (NSColor.colorWithCalibratedWhite_alpha_(0.10, 0.85),
                    NSColor.colorWithCalibratedWhite_alpha_(0.10, 0.65))
        return (NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.95),
                NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.75))

    def drawRect_(self, dirty_rect):
        self.fieldColor.set()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), FIELD_RADIUS * self.scale, FIELD_RADIUS * self.scale
        ).fill()
        self.drawCreditBar()
        self.drawGrip()

    def drawCreditBar(self):
        name_color, credit_color = self.creditColors()
        scale = self.scale
        y = (MARGIN + KEY_H * 2 + GAP + HEADER_GAP) * scale
        rect = NSMakeRect(MARGIN * scale, y, ROW_W * scale, HEADER_H * scale)
        size = CREDIT_FONT_SIZE * scale

        # While the permission is missing, the left slot says so instead of
        # naming the version -- the one place the user is already looking.
        if self.controller is not None and not self.controller.trusted:
            left_text = "KBD — needs Accessibility"
        else:
            left_text = "KBD %s" % APP_VERSION

        self.drawText_inRect_color_size_weight_alignment_(
            left_text, rect, name_color,
            size, NSFontWeightSemibold, NSTextAlignmentLeft)
        self.drawText_inRect_color_size_weight_alignment_(
            CREDIT_TEXT, rect, credit_color,
            size, NSFontWeightRegular, NSTextAlignmentRight)
        self.drawGlyphInRect_color_(rect, name_color)

    def drawGlyphInRect_color_(self, rect, color):
        """The KBD mark, centred between the two credit texts."""
        height = GLYPH_H * self.scale
        key = (color.description(), round(height, 2))
        if self.tintedGlyph is None or self.tintedKey != key:
            self.tintedGlyph = tinted_glyph(self.glyph, color, height)
            self.tintedKey = key
        if self.tintedGlyph is None:
            return
        size = self.tintedGlyph.size()
        origin = NSMakePoint(
            rect.origin.x + (rect.size.width - size.width) / 2.0,
            rect.origin.y + (rect.size.height - size.height) / 2.0)
        self.tintedGlyph.drawInRect_fromRect_operation_fraction_(
            NSMakeRect(origin.x, origin.y, size.width, size.height),
            NSZeroRect, NSCompositingOperationSourceOver, 1.0)

    def drawText_inRect_color_size_weight_alignment_(self, text, rect, color,
                                                     size, weight, alignment):
        paragraph = NSMutableParagraphStyle.alloc().init()
        paragraph.setAlignment_(alignment)
        font = NSFont.systemFontOfSize_weight_(size, weight)
        attributes = {
            NSFontAttributeName: font,
            NSForegroundColorAttributeName: color,
            NSParagraphStyleAttributeName: paragraph,
        }
        # Vertically centre the single line inside the credit bar.
        inset = (rect.size.height - font.ascender() + font.descender()) / 2.0
        text_rect = NSMakeRect(rect.origin.x, rect.origin.y,
                               rect.size.width, rect.size.height - inset)
        NSAttributedString.alloc().initWithString_attributes_(
            text, attributes
        ).drawInRect_(text_rect)

    def gripRect(self):
        size = GRIP_SIZE * self.scale
        return NSMakeRect(self.bounds().size.width - size, 0.0, size, size)

    def drawGrip(self):
        """Three diagonals in the bottom-right corner, the resize affordance."""
        _name_color, credit_color = self.creditColors()
        credit_color.set()
        rect = self.gripRect()
        step = 4.0 * self.scale
        path = NSBezierPath.bezierPath()
        path.setLineWidth_(1.0 * self.scale)
        for index in (1, 2, 3):
            offset = step * index
            path.moveToPoint_(NSMakePoint(
                rect.origin.x + rect.size.width - offset, rect.origin.y + 2.0))
            path.lineToPoint_(NSMakePoint(
                rect.origin.x + rect.size.width - 2.0, rect.origin.y + offset))
        path.stroke()

    # -- mouse ------------------------------------------------------------

    def mouseDown_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        option_held = bool(event.modifierFlags() & NSEventModifierFlagOption)
        if option_held or NSPointInRect(point, self.gripRect()):
            # Resize: track in screen coordinates, which stay meaningful even
            # as the view resizes underneath the pointer.
            self.resizing = True
            self.resizeStartX = NSEvent.mouseLocation().x
            self.resizeStartWidth = self.window().frame().size.width
            return
        # Any other mouse-down on the field (keys swallow their own) drags it.
        self.window().performWindowDragWithEvent_(event)

    def mouseDragged_(self, event):
        if not self.resizing or self.controller is None:
            return
        delta = NSEvent.mouseLocation().x - self.resizeStartX
        self.controller.applyScale_((self.resizeStartWidth + delta) / PANEL_W)

    def mouseUp_(self, event):
        if self.resizing and self.controller is not None:
            self.controller.saveGeometry()
        self.resizing = False


class KeyButton(NSButton):
    """A rounded key with a pressed state, drawn from its layer."""

    def initWithFrame_(self, frame):
        self = objc.super(KeyButton, self).initWithFrame_(frame)
        if self is None:
            return None
        self.baseFrame = frame
        self.baseFontSize = 24.0
        self.fontWeight = NSFontWeightMedium
        self.titleText = ""
        self.vertical = False       # DISMISS reads top to bottom
        self.centerInk = False      # centre the glyph, not its text box
        self.setBordered_(False)
        self.setWantsLayer_(True)
        layer = self.layer()
        layer.setCornerRadius_(KEY_RADIUS)
        layer.setBorderWidth_(1.0)
        layer.setBorderColor_(KEY_BORDER.CGColor())
        layer.setBackgroundColor_(KEY_FACE.CGColor())
        return self

    def mouseDown_(self, event):
        self.layer().setBackgroundColor_(KEY_FACE_DOWN.CGColor())
        objc.super(KeyButton, self).mouseDown_(event)  # tracks until mouse up
        self.layer().setBackgroundColor_(KEY_FACE.CGColor())


class KeypadController(NSObject):
    """Owns the panel, routes key taps, remembers position, size and colour."""

    def init(self):
        self = objc.super(KeypadController, self).init()
        if self is None:
            return None
        self.panel = None
        self.field = None
        self.menu = None
        self.keys = []
        self.fieldColor = self.savedColor() or _color(*DEFAULT_FIELD_COLOR)
        self.scale = self.savedScale()
        self.trusted = True     # assume yes until the launch check says otherwise
        self.trustTimer = None
        return self

    # -- accessibility permission -----------------------------------------

    def checkAccessibility(self):
        """Ask once at launch, then keep watching until the switch is on."""
        self.trusted = bool(AXIsProcessTrusted())
        if self.trusted:
            return
        self.field.setNeedsDisplay_(True)

        # Registers KBD in the Accessibility list and shows the system prompt
        # if macOS has not already asked for this app.  It only ever asks
        # once, which is why the alert below does the asking from then on.
        AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})

        alert = NSAlert.alloc().init()
        alert.setMessageText_("KBD needs Accessibility permission")
        alert.setInformativeText_(
            "macOS only lets an app send keystrokes to other applications "
            "once you allow it.\n\n"
            "Open Privacy & Security > Accessibility and switch KBD on. The "
            "keys start working as soon as you do — the keypad stays open "
            "and notices the change on its own.")
        alert.addButtonWithTitle_("Open Accessibility Settings")
        alert.addButtonWithTitle_("Later")
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        if alert.runModal() == NSAlertFirstButtonReturn:
            self.openAccessibilitySettings_(None)
        self.startTrustTimer()

    def openAccessibilitySettings_(self, sender):
        NSWorkspace.sharedWorkspace().openURL_(
            NSURL.URLWithString_(ACCESSIBILITY_PANE))
        if not self.trusted:
            self.startTrustTimer()

    def startTrustTimer(self):
        if self.trustTimer is not None:
            return
        self.trustTimer = (
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                TRUST_POLL_SECONDS, self, "trustTick:", None, True))

    def trustTick_(self, timer):
        """Clear the warning the moment the permission is granted."""
        if not AXIsProcessTrusted():
            return
        self.trusted = True
        timer.invalidate()
        self.trustTimer = None
        self.field.setNeedsDisplay_(True)

    # -- key actions ------------------------------------------------------

    def keyTapped_(self, sender):
        post_keycode(sender.tag())

    def dismiss_(self, sender):
        self.saveGeometry()
        NSApplication.sharedApplication().terminate_(None)

    def windowMoved_(self, notification):
        self.saveGeometry()

    # -- colour -----------------------------------------------------------

    def applyColor_(self, color):
        self.fieldColor = color
        if self.field is not None:
            self.field.setFieldColor_(color)
        r, g, b = rgb_components(color)
        NSUserDefaults.standardUserDefaults().setObject_forKey_(
            "%.4f,%.4f,%.4f" % (r, g, b), DEFAULTS_COLOR_KEY
        )
        self.refreshMenuState()

    def savedColor(self):
        stored = NSUserDefaults.standardUserDefaults().stringForKey_(
            DEFAULTS_COLOR_KEY
        )
        if not stored:
            return None
        try:
            r, g, b = [float(part) for part in str(stored).split(",")]
        except ValueError:
            return None
        return _color(r, g, b)

    def presetChosen_(self, sender):
        self.applyColor_(_color(*FIELD_PRESETS[sender.tag()][1]))

    # -- size -------------------------------------------------------------

    def applyScale_(self, scale):
        """Resize the whole keypad, keeping its top-left corner anchored."""
        scale = clamp_scale(scale)
        self.scale = scale
        if self.panel is None:
            return

        frame = self.panel.frame()
        top = frame.origin.y + frame.size.height
        width, height = PANEL_W * scale, PANEL_H * scale
        self.panel.setFrame_display_(
            NSMakeRect(frame.origin.x, top - height, width, height), True
        )

        self.field.setFrameSize_(NSMakeSize(width, height))
        self.field.setScale_(scale)
        for button in self.keys:
            base = button.baseFrame
            button.setFrame_(NSMakeRect(
                base.origin.x * scale, base.origin.y * scale,
                base.size.width * scale, base.size.height * scale))
            button.layer().setCornerRadius_(KEY_RADIUS * scale)
            self.styleKey_(button)
        self.refreshMenuState()

    def sizeChosen_(self, sender):
        self.applyScale_(SIZE_PRESETS[sender.tag() - TAG_SIZE_BASE][1])
        self.saveGeometry()

    def savedScale(self):
        stored = NSUserDefaults.standardUserDefaults().stringForKey_(
            DEFAULTS_SCALE_KEY
        )
        if not stored:
            return 1.0
        try:
            return clamp_scale(float(str(stored)))
        except ValueError:
            return 1.0

    # -- context menu -----------------------------------------------------

    def buildMenu(self):
        menu = NSMenu.alloc().initWithTitle_("KBD")

        menu.addItem_(self.sectionHeader_("Keypad Colour"))
        for index, (name, rgb) in enumerate(FIELD_PRESETS):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                name, "presetChosen:", "")
            item.setTarget_(self)
            item.setTag_(index)
            item.setImage_(self.swatchForColor_(_color(*rgb)))
            menu.addItem_(item)

        menu.addItem_(NSMenuItem.separatorItem())
        menu.addItem_(self.sectionHeader_("Keypad Size"))
        for index, (name, scale) in enumerate(SIZE_PRESETS):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "%s (%d%%)" % (name, round(scale * 100)), "sizeChosen:", "")
            item.setTarget_(self)
            item.setTag_(TAG_SIZE_BASE + index)
            menu.addItem_(item)

        menu.addItem_(NSMenuItem.separatorItem())
        for title, action in (
            ("Accessibility Permission…", "openAccessibilitySettings:"),
            ("Dismiss KBD", "dismiss:"),
        ):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                title, action, "")
            item.setTarget_(self)
            menu.addItem_(item)

        self.menu = menu
        self.refreshMenuState()
        return menu

    def sectionHeader_(self, title):
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, None, "")
        item.setEnabled_(False)
        return item

    def swatchForColor_(self, color):
        image = NSImage.alloc().initWithSize_(NSMakeSize(14, 14))
        image.lockFocus()
        color.set()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(0, 0, 14, 14), 3, 3).fill()
        image.unlockFocus()
        return image

    def refreshMenuState(self):
        """Tick the colour and size currently in effect."""
        if self.menu is None:
            return
        current = rgb_components(self.fieldColor)
        for index, (_name, rgb) in enumerate(FIELD_PRESETS):
            item = self.menu.itemWithTag_(index)
            if item is not None:
                matches = all(abs(a - b) < 0.01 for a, b in zip(current, rgb))
                item.setState_(NSOnState if matches else NSOffState)
        for index, (_name, scale) in enumerate(SIZE_PRESETS):
            item = self.menu.itemWithTag_(TAG_SIZE_BASE + index)
            if item is not None:
                matches = abs(self.scale - scale) < 0.005
                item.setState_(NSOnState if matches else NSOffState)

    # -- position and size on disk ----------------------------------------

    def saveGeometry(self):
        if self.panel is None:
            return
        defaults = NSUserDefaults.standardUserDefaults()
        origin = self.panel.frame().origin
        defaults.setObject_forKey_(
            "%.1f,%.1f" % (origin.x, origin.y), DEFAULTS_ORIGIN_KEY)
        defaults.setObject_forKey_("%.4f" % self.scale, DEFAULTS_SCALE_KEY)

    def savedOrigin(self):
        """Last saved origin, if it still lands on an attached screen."""
        stored = NSUserDefaults.standardUserDefaults().stringForKey_(
            DEFAULTS_ORIGIN_KEY
        )
        if not stored:
            return None
        try:
            x_str, y_str = str(stored).split(",")
            x, y = float(x_str), float(y_str)
        except ValueError:
            return None
        width, height = PANEL_W * self.scale, PANEL_H * self.scale
        for screen in NSScreen.screens():
            frame = screen.frame()
            if (x + width > frame.origin.x
                    and x < frame.origin.x + frame.size.width
                    and y + height > frame.origin.y
                    and y < frame.origin.y + frame.size.height):
                return NSMakePoint(x, y)
        return None

    def defaultOrigin(self):
        visible = NSScreen.mainScreen().visibleFrame()
        x = visible.origin.x + (visible.size.width - PANEL_W * self.scale) / 2.0
        y = visible.origin.y + 120.0
        return NSMakePoint(x, y)

    # -- construction -----------------------------------------------------

    def buildPanel(self):
        panel = KeypadPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, PANEL_W, PANEL_H),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(True)
        panel.setLevel_(NSStatusWindowLevel)       # above ordinary windows
        panel.setFloatingPanel_(True)
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setHidesOnDeactivate_(False)         # persistent across apps
        panel.setMovableByWindowBackground_(True)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        field = FieldView.alloc().initWithFrame_(
            NSMakeRect(0, 0, PANEL_W, PANEL_H)
        )
        field.setWantsLayer_(True)
        field.controller = self
        field.setFieldColor_(self.fieldColor)
        panel.setContentView_(field)
        self.field = field

        menu = self.buildMenu()
        field.setMenu_(menu)

        top_y = MARGIN + KEY_H + GAP
        bottom_y = MARGIN
        self.addKeys_toView_atY_(["1", "2", "3", "4", "5"], field, top_y)
        self.addKeys_toView_atY_(["6", "7", "8", "9", "0"], field, bottom_y)

        # The stacked column, top to bottom: space and backspace share the
        # top row's height, return and decimal share the bottom row's.
        stack_x = MARGIN + DIGITS_W + GAP
        upper = STACK_H + STACK_GAP
        for title, y, tag in (
            (u"⎵", top_y + upper, KEYCODE_SPACE),
            (u"⌫", top_y, KEYCODE_DELETE),
            (u"↵", bottom_y + upper, KEYCODE_RETURN),
            (".", bottom_y, KEYCODES["."]),
        ):
            key = self.makeKey_frame_size_weight_tag_action_(
                title, NSMakeRect(stack_x, y, STACK_W, STACK_H),
                15.0, NSFontWeightMedium, tag, "keyTapped:")
            key.centerInk = True
            self.styleKey_(key)
            field.addSubview_(key)

        # DISMISS stands on end beside them, spanning both rows.
        dismiss = self.makeKey_frame_size_weight_tag_action_(
            "DISMISS",
            NSMakeRect(MARGIN + ROW_W - DISMISS_W, bottom_y,
                       DISMISS_W, DISMISS_H),
            13.0, NSFontWeightSemibold, TAG_DISMISS, "dismiss:")
        dismiss.vertical = True
        self.styleKey_(dismiss)
        field.addSubview_(dismiss)

        for subview in field.subviews():
            subview.setMenu_(menu)  # right-click works over the keys too

        panel.setFrameOrigin_(self.savedOrigin() or self.defaultOrigin())
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, "windowMoved:", NSWindowDidMoveNotification, panel
        )

        self.panel = panel
        if abs(self.scale - 1.0) > 0.005:
            self.applyScale_(self.scale)   # restore the size last used
        panel.orderFrontRegardless()

    def addKeys_toView_atY_(self, digits, view, y):
        for index, digit in enumerate(digits):
            frame = NSMakeRect(MARGIN + (KEY_W + GAP) * index, y, KEY_W, KEY_H)
            view.addSubview_(self.makeKey_frame_size_weight_tag_action_(
                digit, frame, 24.0, NSFontWeightMedium,
                KEYCODES[digit], "keyTapped:",
            ))

    def makeKey_frame_size_weight_tag_action_(self, title, frame, size,
                                              weight, tag, action):
        button = KeyButton.alloc().initWithFrame_(frame)
        button.baseFrame = frame
        button.baseFontSize = size
        button.fontWeight = weight
        button.titleText = title
        button.setTag_(tag)
        button.setTarget_(self)
        button.setAction_(action)
        self.styleKey_(button)
        self.keys.append(button)
        return button

    def styleKey_(self, button):
        """(Re)apply the key's title at the current scale."""
        font = NSFont.systemFontOfSize_weight_(
            button.baseFontSize * self.scale, button.fontWeight)
        if button.vertical or button.centerInk:
            image = (rotated_text_image(button.titleText, font, KEY_TEXT)
                     if button.vertical
                     else ink_image(button.titleText, font, KEY_TEXT))
            if image is not None:
                button.setImage_(image)
                button.setImagePosition_(NSImageOnly)
                return

        paragraph = NSMutableParagraphStyle.alloc().init()
        paragraph.setAlignment_(NSTextAlignmentCenter)
        attributes = {
            NSFontAttributeName: font,
            NSForegroundColorAttributeName: KEY_TEXT,
            NSParagraphStyleAttributeName: paragraph,
        }
        button.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                button.titleText, attributes
            )
        )


class AppDelegate(NSObject):

    def applicationWillTerminate_(self, notification):
        if self.controller is not None:
            self.controller.saveGeometry()


# --------------------------------------------------------------------- main

def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    controller = KeypadController.alloc().init()
    controller.buildPanel()

    delegate = AppDelegate.alloc().init()
    delegate.controller = controller
    app.setDelegate_(delegate)

    # Checked after the panel is up, so the keypad is visible behind the
    # alert.  KBD_SKIP_AX_PROMPT=1 skips it (used by the render test).
    if os.environ.get("KBD_SKIP_AX_PROMPT") != "1":
        controller.checkAccessibility()

    app.run()


if __name__ == "__main__":
    main()
