import argparse
import sys

import cv2
import numpy as np

from sell import color_cover
from stage_select import grab_screen

# Battle action menu (bottom left), measured on 1024x576 and stored as fractions.
ROWS = ("attack", "skills", "scroll", "guard", "meditate", "satchel")
ROW_Y0, ROW_STEP = 453 / 576, 19.3 / 576  # center of ATTACK, gap between rows
ROW_HALF = 5 / 576
# Right part of each row: always empty background, so only the highlight changes it.
HIGHLIGHT_X = (130 / 1024, 165 / 1024)
TEXT_X = 60 / 1024

BORDER_BOX = (11 / 1024, 440 / 576, 13 / 1024, 555 / 576)  # light blue left edge of the panel
BODY_BOX = (130 / 1024, 440 / 576, 165 / 1024, 560 / 576)  # navy panel background
BORDER_RANGE = (((95, 50, 110), (115, 130, 170)),)
BODY_RANGE = (((100, 90, 30), (120, 200, 80)),)
MIN_COVER = 0.6

# Highlighted row background is ~20 brighter than the rest.
MIN_HIGHLIGHT_GAP = 10


def row_y(frame, i):
    return int((ROW_Y0 + i * ROW_STEP) * frame.shape[0])


def row_px(frame, name):
    return int(TEXT_X * frame.shape[1]), row_y(frame, ROWS.index(name))


def highlighted_row(frame):
    """Return the name of the highlighted menu row, or None if there's no clear highlight."""
    h, w = frame.shape[:2]
    x0, x1 = int(HIGHLIGHT_X[0] * w), int(HIGHLIGHT_X[1] * w)
    half = max(1, int(ROW_HALF * h))
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    levels = [float(np.mean(gray[row_y(frame, i) - half:row_y(frame, i) + half, x0:x1])) for i in range(len(ROWS))]
    order = np.argsort(levels)
    if levels[order[-1]] - levels[order[-2]] < MIN_HIGHLIGHT_GAP:
        return None
    return ROWS[order[-1]]


def menu_visible(frame):
    return (
        color_cover(frame, BORDER_BOX, BORDER_RANGE) >= MIN_COVER
        and color_cover(frame, BODY_BOX, BODY_RANGE) >= MIN_COVER
        and highlighted_row(frame) is not None
    )


def main():
    parser = argparse.ArgumentParser(description="Check battle menu detection")
    parser.add_argument("image", nargs="?", help="screenshot to analyze (default: live screen)")
    args = parser.parse_args()

    frame = cv2.imread(args.image) if args.image else grab_screen()
    if frame is None:
        sys.exit(f"Can't read {args.image}")
    print(f"menu visible: {menu_visible(frame)}")
    print(f"highlighted:  {highlighted_row(frame)}")


if __name__ == "__main__":
    main()
