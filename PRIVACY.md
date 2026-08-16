# Privacy Policy

**KBD — numeric keypad for iOS, iPadOS and macOS**

Last updated: 16 August 2026

## The short version

KBD collects nothing, sends nothing, and stores nothing about you.

There is no account to create, no analytics, no advertising, no tracking, and
no third-party code of any kind in either app.

## The iOS and iPadOS keyboard

KBD is a custom keyboard extension. It types digits, a decimal point, space,
return and backspace into whatever text field you have open.

**It does not request Full Access.** This is the important part, and it is a
structural guarantee rather than a promise. iOS grants a custom keyboard
network access and shared storage only when the user turns on Full Access.
KBD's `RequestsOpenAccess` flag is set to `false`, so iOS never offers that
switch and never grants those capabilities. The app therefore has:

- **No network access.** It cannot transmit anything, to us or to anyone else.
- **No shared container.** It cannot pass data to any other app, including its
  own containing app.
- **No visibility into other keyboards.** It cannot see anything you type when
  a different keyboard is active.

What you type on KBD is delivered directly to the text field you are typing
into, by iOS, and is not retained afterwards.

The only thing KBD saves is your chosen keypad colour, held in the app's own
private storage on that device. It never leaves the device, and it is removed
when you delete the app.

## The macOS app

KBD.app for macOS is a floating keypad that sends ordinary keystrokes to
whichever application has keyboard focus. To do that, macOS requires you to
grant Accessibility permission, which you can revoke at any time in System
Settings → Privacy & Security → Accessibility.

That permission allows the app to post keyboard events. KBD uses it for
nothing else: it does not read the contents of any window, does not observe
what other applications are doing, and does not record keystrokes.

The macOS app saves its window position, size and colour in your own user
preferences on that Mac. Nothing is transmitted anywhere.

## Children

KBD is suitable for all ages and collects no data from anyone, including
children.

## Changes

Any change to this policy will be published in this file, in the public
repository, with the date above updated.

## Contact

Questions about privacy in KBD can be raised as an issue at
<https://github.com/spurious-cox/kbd/issues>.

---

Copyright © 2026 Tim McCoy. KBD is released under the MIT Licence.
