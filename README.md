# pixel-lineage-macro

A screen-reading macro that plays a 2D Roblox roguelike RPG on its own. It watches the screen, decides what's showing, and clicks buttons, picks stages, sells gear, and taps Space to fight.

Windows only. It assumes the game runs fullscreen on the primary monitor.

## Quick start

| File | What it does |
|---|---|
| `run.bat` | Starts the bot. Creates `.venv` and installs the requirements on first run. |
| `sell_test.bat` | Runs the gear sell routine once, then exits. |

Hotkeys work from any window: **Ctrl+2** starts, **Ctrl+3** stops and exits. Moving the mouse into a screen corner is an emergency stop.

`run.bat --dry-run` logs what the bot would do without clicking or pressing keys.

## How it works

### Screen capture and coordinates

- Each loop takes a screenshot of the primary monitor with `mss`. One capture object is reused, and a full scan takes about 40–50 ms.
- The process is set DPI-aware, so screenshot pixels and mouse coordinates line up even with Windows display scaling.
- Every position and search area is stored as a fraction of the screen size. They were measured on 1024×576 screenshots and work at any resolution, including 1920×1080.
- Nothing uses image templates. Each detector checks colors in HSV inside a fixed area, then looks for blobs with the right size, aspect ratio, and fill.

### Input

- Clicks and key presses go through `pydirectinput`, which uses `SendInput` with scan codes, so the game registers them reliably.
- Before every click, the cursor moves 1 px. Roblox sometimes ignores a click when the cursor hasn't just moved.
- A background thread presses Space every 0.1 s while the bot runs. It pauses while selling and while the battle pointer is being reset.
- Hotkeys come from a `pynput` low-level keyboard hook and are matched by virtual-key code. Holding Ctrl changes the character Python sees for 2 and 3, so the code checks the key itself.

### Main loop (`bot.py`)

Each scan checks the screen in this order. The first match acts, and the loop starts over.

1. **Gear menu left open:** if its red X is visible, click X.
2. **Battle menu**
   - When the scroll hits, Space spam handles it and the menu goes away.
   - If the menu stays on screen for 2 s or more, the bot assumes the scroll missed and clicks **GUARD**.
   - After a battle where it guarded, the pointer is left on GUARD. In the next battle, Space stays paused. Once the menu has been up 0.5 s, it presses **W** (or **S**) until the **SCROLL** row is highlighted, then resumes Space.
3. **Popup buttons**, checked in this order:
   - **PLAY AGAIN**, at a fixed spot on the run complete popup.
   - **CONTINUE**, the popup button in the middle of the screen.
   - **TO BATTLE**, the large yellow button in the shop column. Its height can change.
4. **Settle check:** cards are only picked after 1 s with no button click, and 3 s after the last card click.
5. **Sell gear** after every `SELL_EVERY` PLAY AGAIN clicks, once the GEAR button is bright, meaning no popup covers it.
6. **Stage pick:** pick a card on the stage select screen.

After any click, there's a 0.5 s cooldown before the next one.

### Stage selection (`stage_select.py`)

- In the reward star strip on the right of the cards, it masks gold pixels. Red danger stars and grey empty stars are ignored.
- Gold blobs of star size are grouped into one row per card. Size limits keep gold buttons such as BUY from counting.
- Each row's star count is that card's reward.
- It picks the first card with **reward 5**, otherwise the first with **reward 3**. Cards with reward 4 or 2 are never picked.
- Before clicking, it waits 0.3 s and checks again. If a button appeared or the stars changed, it skips the click.

### Popup buttons (`buttons.py`)

- All three buttons are solid tan rectangles: HSV hue 10–35, high value.
- In each button's search area, the bot looks for a tan blob with the right width, an aspect ratio of 3.5–8, and at least 85% fill.
- The search areas leave out the tan CHARACTER and GEAR buttons in the sidebar. The width limits leave out the BUY buttons, which are in the same column as TO BATTLE.

### Gear selling (`sell.py`)

1. Click **GEAR**, then wait up to 3 s for the gear menu's red X to appear.
2. Click **SELL MANY**, wait 0.5 s, and check that the red X is still there.
3. Click **COMMON**, **UNCOMMON**, **RARE**, and **EPIC**, 0.25 s apart. **CLEAR** is never clicked.
4. Click the red **SELL** button twice, 0.5 s apart.
5. Click **X** to close, up to 3 times until the red X is gone. This also runs if an earlier step fails.

Space is paused for the whole routine. If it fails, the bot tries again 5 s later.

### Battle menu (`battle.py`)

- The menu counts as visible when three things are all true:
  - Its light-blue left border is present.
  - Its navy background is present.
  - Exactly one row is highlighted.
- The highlighted row is the one whose empty background area is clearly brighter than the rest, by at least 10 grey levels. That gives the pointer's position: ATTACK, SKILLS, SCROLL, GUARD, MEDITATE, or SATCHEL.

## Tuning

Timings are constants at the top of `bot.py`:

| Constant | Default | Meaning |
|---|---|---|
| `SCAN_INTERVAL` | 0.1 s | Pause between screen scans |
| `CLICK_COOLDOWN` | 0.5 s | Minimum gap between clicks |
| `SETTLE_DELAY` | 1.0 s | Time with no button click needed before a card can be picked |
| `CONFIRM_DELAY` | 0.3 s | Wait before the second look at the cards |
| `CARD_REPICK_DELAY` | 3.0 s | No second card pick within this window |
| `SPACE_INTERVAL` | 0.1 s | Time between Space presses |
| `SELL_EVERY` | 1 | PLAY AGAIN clicks between gear sells |
| `GUARD_AFTER` | 2.0 s | How long the battle menu can stay up before GUARD is clicked |
| `MENU_LOAD_DELAY` | 0.5 s | Wait before moving the pointer in the next battle |

Sell step delays are at the top of `sell.py`.

## Debug tools

Each detector can be run by itself, on the live screen or on a saved screenshot:

```powershell
.\.venv\Scripts\python stage_select.py samples\stage_select.png
.\.venv\Scripts\python buttons.py samples\shop.png
.\.venv\Scripts\python sell.py samples\sell_menu.png
.\.venv\Scripts\python battle.py samples\battle.png
.\.venv\Scripts\python mouse_pos.py   # live cursor X/Y
```

`samples/` contains the reference screenshots the detectors were measured on.

## Other files

`macro.py`, `capture.py`, `screen.py`, and `config.json` make up the original general-purpose macro: it matches images listed in `config.json` and clicks them. `bot.py` only borrows its click helper from `macro.py`.
