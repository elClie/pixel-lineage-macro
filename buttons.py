import argparse
import sys

import cv2

from stage_select import grab_screen

TAN_LOW = (10, 60, 150)
TAN_HIGH = (35, 255, 255)

MIN_ASPECT, MAX_ASPECT = 3.5, 8.0
MIN_FILL = 0.85

# Areas are (x0, y0, x1, y1) and widths are fractions of screen size, measured on 1024x576.
# CONTINUE: 106x19 popup button in the middle. Area excludes the tan sidebar buttons.
CONTINUE_AREA = (0.3, 0.25, 0.7, 0.85)
CONTINUE_WIDTH = (0.07, 0.14)
# Big "TO BATTLE" button: 112x21 at x 685-797, any height. The BUY buttons share
# this column but are ~45px wide, so the width range filters them out.
BATTLE_AREA = (0.64, 0.1, 0.81, 0.95)
BATTLE_WIDTH = (0.08, 0.14)
# PLAY AGAIN: 105x19 at x 515-620, y 348-367 on the run complete popup, never moves.
PLAY_AGAIN_AREA = (0.49, 0.58, 0.62, 0.66)
PLAY_AGAIN_WIDTH = (0.08, 0.12)


def find_button(frame, area, width_range):
    """Return (x, y) center of the first solid tan button in area, or None."""
    h, w = frame.shape[:2]
    x0, y0 = int(area[0] * w), int(area[1] * h)
    x1, y1 = int(area[2] * w), int(area[3] * h)
    hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, TAN_LOW, TAN_HIGH)

    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    for i in range(1, n):
        x, y, bw, bh, px = stats[i]
        if not (width_range[0] * w <= bw <= width_range[1] * w):
            continue
        if not (MIN_ASPECT <= bw / bh <= MAX_ASPECT):
            continue
        if px / (bw * bh) < MIN_FILL:
            continue
        return int(x0 + x + bw // 2), int(y0 + y + bh // 2)
    return None


def find_continue(frame):
    return find_button(frame, CONTINUE_AREA, CONTINUE_WIDTH)


def find_battle(frame):
    return find_button(frame, BATTLE_AREA, BATTLE_WIDTH)


def find_play_again(frame):
    return find_button(frame, PLAY_AGAIN_AREA, PLAY_AGAIN_WIDTH)


def main():
    parser = argparse.ArgumentParser(description="Find the PLAY AGAIN / CONTINUE / TO BATTLE buttons")
    parser.add_argument("image", nargs="?", help="screenshot to analyze (default: live screen)")
    args = parser.parse_args()

    frame = cv2.imread(args.image) if args.image else grab_screen()
    if frame is None:
        sys.exit(f"Can't read {args.image}")

    print(f"play again: {find_play_again(frame)}")
    print(f"continue:   {find_continue(frame)}")
    print(f"battle:     {find_battle(frame)}")


if __name__ == "__main__":
    main()
