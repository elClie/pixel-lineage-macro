import argparse
import threading
import time

import pydirectinput
from pynput import keyboard

from battle import ROWS, highlighted_row, menu_visible, row_px
from buttons import find_battle, find_continue, find_play_again
from macro import click
from sell import CLOSE_BTN, gear_ready, menu_open, run_sell, to_px
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
# Sell gear after this many PLAY AGAIN clicks, once the GEAR button is usable.
SELL_EVERY = 1
SELL_RETRY_DELAY = 5.0
# Battle menu still up this long means the scroll missed/was used: click GUARD.
GUARD_AFTER = 2.0
# Next battle after a GUARD: menu must be up this long before moving the pointer.
MENU_LOAD_DELAY = 0.5
KEY_SETTLE = 0.3

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
# Space could press things inside the gear menu, so spamming pauses while this is set.
selling = threading.Event()
# Set after a battle where GUARD was clicked: the pointer is left on GUARD, so Space stays
# paused until the next battle's pointer is moved back to SCROLL.
fixing_pointer = threading.Event()
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
        if not running.is_set() or selling.is_set() or fixing_pointer.is_set():
            wait(0.1)
            continue
        try:
            pydirectinput.press("space", _pause=False)
        except pydirectinput.FailSafeException:
            print("[failsafe] mouse in screen corner, stopping")
            stopping.set()
            return
        wait(SPACE_INTERVAL)


def sell_test(do_click):
    print("[sell test] Ctrl+2 = sell once, Ctrl+3 = cancel.")
    while not running.is_set():
        if wait(0.1):
            return
    while not gear_ready(grab_screen()):
        print("[sell test] GEAR button not visible (popup open?), retrying...")
        if wait(1.0):
            return
    ok = run_sell(do_click, grab_screen, wait)
    print("[sell test] success" if ok else "[sell test] failed")


def main():
    parser = argparse.ArgumentParser(description="Clicks popup buttons and picks the best stage")
    parser.add_argument("--dry-run", action="store_true", help="log actions without clicking")
    parser.add_argument("--sell-test", action="store_true", help="run the gear sell routine once, then exit")
    args = parser.parse_args()

    def do_click(pos):
        if not args.dry_run and not stopping.is_set():
            click(*pos, "left")

    def do_key(key):
        if not args.dry_run and not stopping.is_set():
            pydirectinput.press(key)

    keyboard.Listener(on_press=on_press, on_release=on_release, daemon=True).start()
    if args.sell_test:
        sell_test(do_click)
        return
    if not args.dry_run:
        threading.Thread(target=spam_space, daemon=True).start()
    print("Ctrl+2 = start, Ctrl+3 = stop." + (" [dry run]" if args.dry_run else ""))

    last_button = 0.0
    last_card = 0.0
    play_agains = 0
    last_sell_try = 0.0
    menu_since = None
    guarded = False

    def left_battle():
        nonlocal guarded
        if guarded:
            guarded = False
            fixing_pointer.set()
            print("[battle] left a GUARD battle, space paused until pointer is back on SCROLL")

    while not stopping.is_set():
        if not running.is_set():
            wait(0.1)
            continue

        frame = grab_screen()
        # A gear menu left open would hide everything else, and its stars/items could be misread.
        if menu_open(frame):
            print("[gear] menu open, closing")
            do_click(to_px(frame, CLOSE_BTN))
            last_button = time.time()
            wait(CLICK_COOLDOWN)
            continue

        if menu_visible(frame):
            now = time.time()
            menu_since = menu_since or now
            shown = now - menu_since
            if fixing_pointer.is_set():
                if shown < MENU_LOAD_DELAY:
                    wait(SCAN_INTERVAL)
                    continue
                row = highlighted_row(frame)
                if row == "scroll":
                    print("[battle] pointer on SCROLL, space resumed")
                    fixing_pointer.clear()
                    continue
                key = "w" if ROWS.index(row) > ROWS.index("scroll") else "s"
                print(f"[battle] pointer on {row.upper()}, press {key.upper()}")
                do_key(key)
                wait(KEY_SETTLE)
                continue
            if shown >= GUARD_AFTER:
                pos = row_px(frame, "guard")
                print(f"[battle] menu up {shown:.1f}s, click GUARD {pos}")
                do_click(pos)
                guarded = True
                menu_since = None
                wait(CLICK_COOLDOWN)
                continue
            wait(SCAN_INTERVAL)
            continue
        menu_since = None

        btn = find_any_button(frame)
        if btn:
            name, pos = btn
            print(f"[{name}] click {pos}")
            do_click(pos)
            left_battle()
            last_button = time.time()
            if name == "play again":
                play_agains += 1
            wait(CLICK_COOLDOWN)
            continue

        now = time.time()
        if now - last_button < SETTLE_DELAY or now - last_card < CARD_REPICK_DELAY:
            wait(SCAN_INTERVAL)
            continue

        if play_agains >= SELL_EVERY and gear_ready(frame) and now - last_sell_try >= SELL_RETRY_DELAY:
            if args.dry_run:
                print("[sell] would sell gear now")
                ok = True
            else:
                selling.set()
                try:
                    ok = run_sell(do_click, grab_screen, wait)
                finally:
                    selling.clear()
            if ok:
                print("[sell] done")
                play_agains = 0
            else:
                last_sell_try = time.time()
            last_button = time.time()
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
            left_battle()
            last_card = time.time()
            wait(CLICK_COOLDOWN)
            continue

        wait(SCAN_INTERVAL)

    print("bye")


if __name__ == "__main__":
    main()
