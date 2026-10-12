import time

from battle import BACK_BTN, ROWS, highlighted_row, menu_visible, row_px, skill_list_open, to_px

# W presses in the skill list for each skill cast at the start of a battle, in order.
# After these, every turn is ATTACK.
SKILL_PICKS = (3, 2)

KEY_GAP = 0.05
# The two Spaces after picking: one confirms the skill/attack, one confirms the target.
# With a single enemy the second one is simply ignored.
DOUBLE_TAP_GAP = 0.03
NAV_SETTLE = 0.15
# Battle menu must be up this long before acting, so the turn has really started.
MENU_SETTLE = 0.2
LIST_TIMEOUT = 0.5
# No minigame and the menu still up after this long means the action didn't go through.
CAST_TIMEOUT = 2.0
MAX_CAST_TRIES = 3
# The solver saw a minigame this recently: it's handling input, so don't press anything.
MINIGAME_QUIET = 0.5


class SkillBattle:
    """Battle turns for skill mode: cast SKILL_PICKS in order, then ATTACK for the rest of the battle."""

    def __init__(self, press, click, grab, wait, minigame_seen):
        self.press = press
        self.click = click
        self.grab = grab
        self.wait = wait
        self.minigame_seen = minigame_seen
        self.new_battle()

    def new_battle(self):
        self.casts = 0
        self.menu_since = None
        # Set after acting; cleared once the menu goes away, so each turn is played once.
        self.acted = False

    def step(self, frame):
        """Play the turn if the battle menu is up. Returns True if this was a battle frame."""
        if not menu_visible(frame):
            self.menu_since = None
            self.acted = False
            return False
        now = time.perf_counter()
        if self.acted or now - self.minigame_seen() < MINIGAME_QUIET:
            return True
        self.menu_since = self.menu_since or now
        if now - self.menu_since < MENU_SETTLE:
            return True

        if skill_list_open(frame):
            print("[skills] skill list left open, BACK")
            self.click(to_px(frame, BACK_BTN))
            self.wait(NAV_SETTLE)
            return True

        want = "skills" if self.casts < len(SKILL_PICKS) else "attack"
        row = highlighted_row(frame)
        if row != want:
            key = "w" if ROWS.index(row) > ROWS.index(want) else "s"
            print(f"[skills] pointer on {row.upper()}, want {want.upper()}: {key.upper()}")
            self.press(key)
            self.wait(NAV_SETTLE)
            return True

        if want == "skills":
            n = self.casts + 1
            done = self.cast_skill(SKILL_PICKS[self.casts])
            if done:
                print(f"[skills] skill {n} cast")
                self.casts = n
                self.acted = True
            elif done is False:
                print(f"[skills] skill {n} failed {MAX_CAST_TRIES} times, attacking for the rest of this battle")
                self.casts = len(SKILL_PICKS)
                self.click(to_px(self.grab(), BACK_BTN))
                self.wait(NAV_SETTLE)
        elif self.attack():
            self.acted = True
        return True

    def double_space(self):
        self.press("space")
        self.wait(DOUBLE_TAP_GAP)
        self.press("space")

    # These return None when Ctrl+3 stops the bot mid-action, so a stop isn't mistaken for a failure.

    def wait_for(self, check, timeout):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            if check(self.grab()):
                return True
            if self.wait(0.03):
                return None
        return False

    def went_through(self):
        """After an action: True once a minigame shows or the battle menu goes away."""
        start = time.perf_counter()
        gone = 0
        while time.perf_counter() - start < CAST_TIMEOUT:
            if self.wait(0.05):
                return None
            if self.minigame_seen() > start:
                return True
            gone = 0 if menu_visible(self.grab()) else gone + 1
            if gone >= 2:
                return True
        return False

    def cast_skill(self, picks):
        for attempt in range(MAX_CAST_TRIES):
            if attempt == 0:
                print(f"[skills] SPACE, W x{picks}, SPACE x2")
                self.press("space")
            else:
                # Clicking SKILLS opens the list itself, so no opening Space this time.
                print(f"[skills] didn't go through, BACK > SKILLS, W x{picks}, SPACE x2 (retry {attempt})")
                frame = self.grab()
                self.click(to_px(frame, BACK_BTN))
                self.wait(NAV_SETTLE)
                self.click(row_px(frame, "skills"))
            opened = self.wait_for(skill_list_open, LIST_TIMEOUT)
            if opened is None:
                return None
            if not opened:
                continue
            for _ in range(picks):
                self.press("w")
                self.wait(KEY_GAP)
            self.double_space()
            done = self.went_through()
            if done is not False:
                return done
        return False

    def attack(self):
        print("[attack] SPACE x2")
        self.double_space()
        done = self.went_through()
        if done is False:
            print("[attack] didn't go through, retrying next scan")
        return done
