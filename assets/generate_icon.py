#!/usr/bin/env python3
"""Generate an AudioRec icon — a red circle on transparent background."""

import AppKit
import os

SIZES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}

OUT_DIR = os.path.join(os.path.dirname(__file__), "AudioRec.iconset")
os.makedirs(OUT_DIR, exist_ok=True)

RED = (1.0, 0.2, 0.2, 1.0)

for filename, size in SIZES.items():
    image = AppKit.NSImage.alloc().initWithSize_((size, size))
    image.lockFocus()
    rect = AppKit.NSMakeRect(0, 0, size, size)
    path = AppKit.NSBezierPath.bezierPathWithOvalInRect_(rect)
    AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*RED).set()
    path.fill()
    image.unlockFocus()

    tiff = image.TIFFRepresentation()
    rep = AppKit.NSBitmapImageRep.imageRepWithData_(tiff)
    png = rep.representationUsingType_properties_(
        AppKit.NSBitmapImageFileTypePNG, {}
    )
    out_path = os.path.join(OUT_DIR, filename)
    png.writeToFile_atomically_(out_path, False)

print("Imageset generated:", OUT_DIR)
