import argparse
import threading
import time

import pydirectinput
from pynput import keyboard

from buttons import find_battle, find_continue, find_play_again
from macro import click
from stage_select import grab_screen, pick_stage

SCAN_INTERVAL = 0.1
# Minimum gap between any two clicks, so one button isn't clicked twice.
CLICK_COOLDOWN = 0.5
# Cards are only picked after this long with no button click.
SETTLE_DELAY = 1.0
# Second look before clicking a card, in case a popup was still fading in.
CONFIRM_DELAY = 0.3
# The stage select can linger while the next screen loads; don't pick a card again in that window.
CARD_REPICK_DELAY = 3.0
SPACE_INTERVAL = 0.1

# PLAY AGAIN first: its popup also passes the CONTINUE size/position check.
BUTTONS = (
    ("play again", find_play_again),
    ("continue", find_continue),
    ("battle", find_battle),
)

# Virtual key codes for the top-row 2 and 3. Matched by vk because holding Ctrl
# turns the key's char into a control code.
VK_START, VK_STOP = 0x32, 0x33
CTRL_KEYS = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}

running = threading.Event()
stopping = threading.Event()
ctrl_held = set()


def on_press(key):
    if key in CTRL_KEYS:
        ctrl_held.add(key)
        return
    if not ctrl_held:
        return
    vk = getattr(key, "vk", None)
    if vk == VK_START and not running.is_set():
        running.set()
        print("[started]")
    elif vk == VK_STOP:
        stopping.set()
        print("[stopping]")
        return False


def on_release(key):
    ctrl_held.discard(key)


def find_any_button(frame):
    for name, finder in BUTTONS:
        pos = finder(frame)
        if pos:
            return name, pos
    return None


def wait(seconds):
    """Sleep, but return early (True) if Ctrl+3 was pressed."""
    return stopping.wait(seconds)


def spam_space():
    while not stopping.is_set():
        if not running.is_set():
            wait(0.1)
            continue
        try:
            pydirectinput.press("space", _pause=False)
        except pydirectinput.FailSafeException:
            print("[failsafe] mouse in screen corner, stopping")
            stopping.set()
            return
        wait(SPACE_INTERVAL)


def main():
    parser = argparse.ArgumentParser(description="Clicks popup buttons and picks the best stage")
    parser.add_argument("--dry-run", action="store_true", help="log actions without clicking")
    args = parser.parse_args()

    def do_click(pos):
        if not args.dry_run and not stopping.is_set():
            click(*pos, "left")

    keyboard.Listener(on_press=on_press, on_release=on_release, daemon=True).start()
    if not args.dry_run:
        threading.Thread(target=spam_space, daemon=True).start()
    print("Ctrl+2 = start, Ctrl+3 = stop." + (" [dry run]" if args.dry_run else ""))

    last_button = 0.0
    last_card = 0.0
    while not stopping.is_set():
        if not running.is_set():
            wait(0.1)
            continue

        frame = grab_screen()
        btn = find_any_button(frame)
        if btn:
            name, pos = btn
            print(f"[{name}] click {pos}")
            do_click(pos)
            last_button = time.time()
            wait(CLICK_COOLDOWN)
            continue

        now = time.time()
        if now - last_button < SETTLE_DELAY or now - last_card < CARD_REPICK_DELAY:
            wait(SCAN_INTERVAL)
            continue

        choice = pick_stage(frame)
        if choice:
            if wait(CONFIRM_DELAY):
                break
            frame = grab_screen()
            if find_any_button(frame) or pick_stage(frame) != choice:
                print("[stage] screen changed, rechecking")
                continue
            i, stars, pos = choice
            print(f"[stage] card {i + 1} (reward {stars}) click {pos}")
            do_click(pos)
            last_card = time.time()
            wait(CLICK_COOLDOWN)
            continue

        wait(SCAN_INTERVAL)

    print("bye")


if __name__ == "__main__":
    main()
