import threading

from pynput import keyboard

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


def start_listener():
    keyboard.Listener(on_press=on_press, on_release=on_release, daemon=True).start()


def wait(seconds):
    """Sleep, but return early (True) if Ctrl+3 was pressed."""
    return stopping.wait(seconds)
