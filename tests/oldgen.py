#!/usr/bin/env python3
import json
import os
import sys
import uuid
import secrets
import tempfile
import base64
import hashlib
import time
import string
import logging
import threading
from typing import Callable, Tuple, Dict, Any, Optional, List

# ── Dependency guard ──────────────────────────────────────────────────────────
try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTO = True
    CRYPTO_ERR = ""
except Exception as _e:
    HAS_CRYPTO = False
    CRYPTO_ERR = str(_e)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib, Gio

# ── Constants ─────────────────────────────────────────────────────────────────
ALPHA_B24 = "BCDFGHJKMPQRTVWXY2346789"
ALPHA_B25 = "BCDFGHJKMNPQRTVWXY2346789"
MOD7_MAX_DIGIT = 8
RETAIL_BLACKLIST = {333, 444, 555, 666, 777, 888, 999}
PBKDF2_ITERATIONS = 200_000
AUTO_LOCK_POLL_SECONDS = 30

# ── Paths ─────────────────────────────────────────────────────────────────────
LOG_FILE      = os.path.join(GLib.get_user_data_dir(),   "sentinel_debug.log")
CONFIG_PATH   = os.path.join(GLib.get_user_config_dir(), "sentinel_config.enc")
DEFAULT_VAULT = os.path.join(GLib.get_user_data_dir(),   "sentinel_vault.dat")

logging.basicConfig(
    filename=LOG_FILE, level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)

# ── App identity ──────────────────────────────────────────────────────────────
APP_REAL = "Key Sentinel Pro"
APP_FAKE = "SysMon Diagnostics"

# ── Engine labels ─────────────────────────────────────────────────────────────
ENGINES_REAL = [
    "Win 10 / 11 / Server  (Base-25)",
    "Win XP / Vista / 7    (Base-24)",
    "Win 95/98/NT4 – Retail",
    "Win 95/98/NT4 – OEM",
    "Custom Key Builder",
    "Structured Mask",
    "High-Entropy Password",
    "PIN / Passcode",
]
ENGINES_FAKE = [
    "Topology Baseline α",
    "Topology Baseline β",
    "Hex Filter Mode A",
    "Hex Filter Mode B",
    "Custom Node Builder",
    "Entropy Mask Protocol",
    "Entropy Node Generator",
    "Interrupt Sequence",
]

# ── Badge CSS classes ────────────────────────────────────────────────────────
TYPE_BADGE = {
    "License":  "badge-blue",
    "OEM":      "badge-blue",
    "Legacy":   "badge-blue",
    "Password": "badge-green",
    "Masked":   "badge-amber",
    "Custom":   "badge-amber",
    "PIN":      "badge-amber",
    "Error":    "badge-red",
}

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS_DATA = b"""
.key-display {
    font-family: 'Monospace', 'Courier New', monospace;
    font-size: 1.3rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    color: @accent_color;
    background: alpha(@accent_color, 0.07);
    border: 2px solid alpha(@accent_color, 0.18);
    padding: 18px 14px;
    border-radius: 14px;
}
.badge {
    font-size: 0.68rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
}
.badge-blue  { background: alpha(@accent_color,   0.14); color: @accent_color;   }
.badge-green { background: alpha(@success_color,  0.16); color: @success_color;  }
.badge-amber { background: alpha(@warning_color,  0.18); color: @warning_color;  }
.badge-red   { background: alpha(@error_color,    0.15); color: @error_color;    }
.error-text  { color: @error_color; font-weight: bold; }
.code-block  {
    font-family: monospace;
    background: alpha(@view_fg_color, 0.08);
    padding: 6px 10px;
    border-radius: 6px;
}
"""


# ══════════════════════════════════════════════════════════════════════════════
#  SECURITY UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def secure_wipe(data: Optional[bytearray]) -> None:
    """Overwrite a bytearray with zeros before letting it be garbage-collected."""
    if data is not None:
        for i in range(len(data)):
            data[i] = 0


def wipe_string(s: str) -> None:
    """Convert a string to a bytearray, wipe it, and let it be GC'd."""
    if s:
        ba = bytearray(s.encode())
        secure_wipe(ba)


# ══════════════════════════════════════════════════════════════════════════════
#  GENERATION ENGINES  –  pure functions, no UI logic
# ══════════════════════════════════════════════════════════════════════════════

def gen_win_modern(state: Dict[str, Any]) -> Tuple[str, str]:
    """Base-25, 5×5 — Windows 8/10/11/Server."""
    val = secrets.randbits(114)
    chars = []
    for _ in range(25):
        val, rem = divmod(val, 25)
        chars.append(ALPHA_B25[rem])
    chars.reverse()

    ed = state.get("b25_edition", 0)
    if ed == 1:
        chars[0] = "N"
    elif ed == 2:
        chars[0] = secrets.choice("NB")
    else:
        chars[0] = secrets.choice("BCDFGHJKM")

    k = "".join(chars)
    return "-".join(k[i:i+5] for i in range(0, 25, 5)), "License"


def gen_win_classic(state: Dict[str, Any]) -> Tuple[str, str]:
    """Base-24, 5×5 — Windows XP/Vista/7."""
    val = secrets.randbits(114)
    chars = []
    for _ in range(25):
        val, rem = divmod(val, 24)
        chars.append(ALPHA_B24[rem])
    chars.reverse()

    arch = state.get("b24_archetype", 0)
    if arch == 2:
        chars[0] = "N"                      # Enterprise
    elif arch == 1:
        chars[0] = secrets.choice("346789") # OEM
    elif arch == 3:
        chars[0] = secrets.choice("BCDF")   # Volume/KMS
    else:
        chars[0] = secrets.choice("RTWXY")  # Retail

    k = "".join(chars)
    return "-".join(k[i:i+5] for i in range(0, 25, 5)), "License"


def gen_win95_retail(_state: Dict[str, Any]) -> Tuple[str, str]:
    """XXX-XXXXXXX  —  Windows 95/98/NT4 Retail CD key."""
    while True:
        site = secrets.randbelow(1000)
        if site not in RETAIL_BLACKLIST:
            break
    while True:
        d = [secrets.randbelow(9) for _ in range(6)]
        chk = (7 - sum(d) % 7) % 7
        if chk <= MOD7_MAX_DIGIT:
            d.append(chk)
            break
    return f"{site:03d}-{''.join(map(str, d))}", "Legacy"


def gen_win95_oem(_state: Dict[str, Any]) -> Tuple[str, str]:
    """DDDYY-OEM-0NNNNNN-XXXXX  —  Windows 95/98/NT4 OEM."""
    day = secrets.randbelow(366) + 1
    year = secrets.randbelow(9) + 95
    if year >= 100:
        year -= 100

    while True:
        d = [secrets.randbelow(9) for _ in range(5)]
        chk = (7 - sum(d) % 7) % 7
        if chk <= MOD7_MAX_DIGIT:
            d.append(chk)
            break
    mid = "0" + "".join(map(str, d))
    last = "".join(str(secrets.randbelow(10)) for _ in range(5))
    return f"{day:03d}{year:02d}-OEM-{mid}-{last}", "OEM"


def gen_custom_key(state: Dict[str, Any]) -> Tuple[str, str]:
    charset = state.get("ckb_charset", ALPHA_B24)
    groups = state.get("ckb_groups", 5)
    size = state.get("ckb_size", 5)
    sep = state.get("ckb_sep", "-") or "-"
    if not charset:
        return "ERR: character set is empty", "Error"
    blocks = [
        "".join(secrets.choice(charset) for _ in range(size))
        for _ in range(groups)
    ]
    return sep.join(blocks), "Custom"


def gen_mask(state: Dict[str, Any]) -> Tuple[str, str]:
    out = []
    escape = False
    for c in state.get("mask_fmt", "AAAA-####-@@@"):
        if escape:
            out.append(c)
            escape = False
            continue
        if c == "\\":
            escape = True
        elif c == "A":
            out.append(secrets.choice(string.ascii_uppercase))
        elif c == "a":
            out.append(secrets.choice(string.ascii_lowercase))
        elif c == "#":
            out.append(secrets.choice(string.digits))
        elif c == "@":
            out.append(secrets.choice("!@#$%^&*-_+="))
        elif c == "?":
            out.append(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*-_+="))
        else:
            out.append(c)
    return "".join(out), "Masked"


def gen_password(state: Dict[str, Any]) -> Tuple[str, str]:
    charset = (
        (string.ascii_uppercase if state.get("pwd_u", True) else "") +
        (string.ascii_lowercase if state.get("pwd_l", True) else "") +
        (string.digits if state.get("pwd_d", True) else "") +
        ("!@#$%^&*-_+=" if state.get("pwd_s", True) else "")
    )
    if not charset:
        return "ERR: enable at least one character class", "Error"
    length = state.get("pwd_len", 16)
    return "".join(secrets.choice(charset) for _ in range(length)), "Password"


def gen_pin(state: Dict[str, Any]) -> Tuple[str, str]:
    preset = state.get("pin_preset", 0)
    length = {0: 4, 1: 6}.get(preset, state.get("pin_len", 4))
    if preset == 3:
        charset = string.ascii_letters + string.digits
        return "".join(secrets.choice(charset) for _ in range(length)), "PIN"
    return "".join(str(secrets.randbelow(10)) for _ in range(length)), "PIN"


# ── Engine registry ──────────────────────────────────────────────────────────
ENGINE_FUNCS: List[Callable[[Dict[str, Any]], Tuple[str, str]]] = [
    gen_win_modern,      # 0
    gen_win_classic,     # 1
    gen_win95_retail,    # 2
    gen_win95_oem,       # 3
    gen_custom_key,      # 4
    gen_mask,            # 5
    gen_password,        # 6
    gen_pin,             # 7
]


# ══════════════════════════════════════════════════════════════════════════════
#  VAULT MANAGER  –  encryption + persistence + config
# ══════════════════════════════════════════════════════════════════════════════

class VaultManager:
    DEFAULTS: Dict[str, Any] = {
        "vault_path":     DEFAULT_VAULT,
        "stealth":        False,
        "animations":     True,
        "auto_lock_mins": 3,
        "engine_mode":    0,
        "b25_edition":    0,
        "b24_archetype":  0,
        "ckb_charset":    ALPHA_B24,
        "ckb_groups":     5,
        "ckb_size":       5,
        "ckb_sep":        "-",
        "mask_fmt":       "AAAA-####-@@@@",
        "pwd_len":        16,
        "pwd_u":          True,
        "pwd_l":          True,
        "pwd_d":          True,
        "pwd_s":          True,
        "pin_preset":     0,
        "pin_len":        4,
    }

    def __init__(self) -> None:
        self.state: Dict[str, Any] = dict(self.DEFAULTS)
        self.records: List[Dict[str, Any]] = []
        self._fernet: Optional[Fernet] = None
        self._salt: Optional[bytes] = None
        self._master_pwd: Optional[bytearray] = None
        self._load_config()

    # ── Config (encrypted with master password) ──────────────────────────────
    def _load_config(self) -> None:
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, "rb") as fh:
                data = fh.read()
            if self._master_pwd is None:
                return
            salt = data[:16]
            ciphertext = data[16:]
            key = self._derive_key(bytes(self._master_pwd), salt)
            fernet = Fernet(key)
            plaintext = fernet.decrypt(ciphertext)
            self.state.update(json.loads(plaintext.decode()))
            secure_wipe(key)
        except Exception as exc:
            logging.error("Config load: %s", exc)

    def _save_config(self) -> None:
        if self._master_pwd is None:
            return
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            salt = os.urandom(16)
            key = self._derive_key(bytes(self._master_pwd), salt)
            fernet = Fernet(key)
            ciphertext = salt + fernet.encrypt(json.dumps(self.state).encode())
            with tempfile.NamedTemporaryFile("wb", delete=False, dir=os.path.dirname(CONFIG_PATH)) as tf:
                tf.write(ciphertext)
                tmp = tf.name
            os.replace(tmp, CONFIG_PATH)
            secure_wipe(key)
        except Exception as exc:
            logging.error("Config save: %s", exc)

    # ── Key derivation ────────────────────────────────────────────────────────
    def _derive_key(self, password: bytes, salt: bytes) -> bytearray:
        raw = hashlib.pbkdf2_hmac("sha256", password, salt, PBKDF2_ITERATIONS)
        return bytearray(base64.urlsafe_b64encode(raw))

    # ── Vault (encrypted) ─────────────────────────────────────────────────────
    def unlock(self, password: str) -> bool:
        path = self.state["vault_path"]
        pwd_ba = bytearray(password.encode())
        self._master_pwd = pwd_ba

        if not os.path.exists(path):
            self._salt = os.urandom(16)
            key = self._derive_key(bytes(pwd_ba), self._salt)
            self._fernet = Fernet(bytes(key))
            self.records = []
            self._write_vault()
            self._save_config()
            secure_wipe(key)
            logging.info("New vault created: %s", path)
            return True

        try:
            with open(path, "rb") as fh:
                raw = fh.read()
            if len(raw) < 16:
                return False
            salt = raw[:16]
            key = self._derive_key(bytes(pwd_ba), salt)
            fernet = Fernet(bytes(key))
            decrypted = fernet.decrypt(raw[16:])
            self._salt = salt
            self._fernet = fernet
            self.records = json.loads(decrypted.decode())
            self._save_config()
            secure_wipe(key)
            logging.info("Vault unlocked.")
            return True
        except InvalidToken:
            self._fernet = None
            self._master_pwd = None
            return False
        except Exception as exc:
            logging.error("Vault unlock: %s", exc)
            self._fernet = None
            self._master_pwd = None
            return False

    def _write_vault(self) -> None:
        if not self._fernet or self._salt is None:
            return
        try:
            path = self.state["vault_path"]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            payload = self._salt + self._fernet.encrypt(json.dumps(self.records).encode())
            with tempfile.NamedTemporaryFile("wb", delete=False, dir=os.path.dirname(path)) as tf:
                tf.write(payload)
                tmp = tf.name
            os.replace(tmp, path)
        except Exception as exc:
            logging.error("Vault write: %s", exc)

    def add_record(self, label: str, val: str, type_str: str, tag: str = "") -> None:
        self.records.append({
            "id": str(uuid.uuid4()),
            "label": label or "Untitled",
            "val": val,
            "type": type_str,
            "tag": tag,
            "timestamp": time.time(),
        })
        self._write_vault()

    def delete_record(self, uid: str) -> bool:
        before = len(self.records)
        self.records = [r for r in self.records if r["id"] != uid]
        if len(self.records) < before:
            self._write_vault()
            return True
        return False

    def lock(self) -> None:
        self._fernet = None
        self._salt = None
        self.records = []
        if self._master_pwd is not None:
            secure_wipe(self._master_pwd)
            self._master_pwd = None
        logging.info("Vault locked – memory purged.")

    def set(self, key: str, val: Any) -> None:
        self.state[key] = val
        self._save_config()


# ══════════════════════════════════════════════════════════════════════════════
#  KEY SENTINEL UI  –  GTK4 / Libadwaita front-end
# ══════════════════════════════════════════════════════════════════════════════

class KeySentinelUI(Adw.Application):
    def __init__(self, **kwargs) -> None:
        super().__init__(application_id="com.sentinel.v21", **kwargs)
        self.vault = VaultManager() if HAS_CRYPTO else None
        self.is_animating = False
        self._anim_timer = None
        self._anim_target = ""
        self._anim_frame = 0
        self._cpu_timer = None
        self._auto_lock_tmr = None
        self._last_activity = time.time()
        self._current_type = "Key"

    # ── Helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _m(w: Gtk.Widget, t=0, b=0, s=0, e=0) -> None:
        w.set_margin_top(t)
        w.set_margin_bottom(b)
        w.set_margin_start(s)
        w.set_margin_end(e)

    def _toast(self, msg: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=msg))

    def _set(self, key: str, val: Any) -> None:
        self.vault.set(key, val)

    def _badge(self, text: str, css_class: str) -> Gtk.Label:
        lbl = Gtk.Label(label=text)
        lbl.add_css_class("badge")
        lbl.add_css_class(css_class)
        lbl.set_valign(Gtk.Align.CENTER)
        return lbl

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def do_activate(self) -> None:
        # CSS
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS_DATA)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.win = Adw.ApplicationWindow(application=self)
        self.win.set_default_size(540, 840)
        self.win.connect("close-request", self._on_shutdown)

        # Activity tracking for auto-lock – attach to the window itself
        motion_ctrl = Gtk.EventControllerMotion.new()
        motion_ctrl.connect("motion", self._register_activity)
        self.win.add_controller(motion_ctrl)

        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._register_activity)
        self.win.add_controller(key_ctrl)

        # Click controller for button presses
        click_ctrl = Gtk.GestureClick.new()
        click_ctrl.connect("pressed", self._register_activity)
        self.win.add_controller(click_ctrl)

        self.toast_overlay = Adw.ToastOverlay()
        self.win.set_content(self.toast_overlay)

        if not HAS_CRYPTO:
            self.toast_overlay.set_child(self._page_crypto_error())
            self.win.present()
            return

        self.root_stack = Gtk.Stack()
        self.root_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.root_stack.add_named(self._page_unlock(), "unlock")
        self.root_stack.add_named(self._page_main(), "main")
        self.toast_overlay.set_child(self.root_stack)
        self._apply_stealth()
        self.win.present()

    def _register_activity(self, *_) -> None:
        self._last_activity = time.time()

    def _check_auto_lock(self) -> bool:
        if self.root_stack.get_visible_child_name() == "main":
            mins = self.vault.state.get("auto_lock_mins", 3)
            if time.time() - self._last_activity > mins * 60:
                self._action_lock(None)
                self._toast("Auto-locked due to inactivity.")
        return True

    def _on_shutdown(self, *_) -> bool:
        if self.vault:
            self.vault.lock()
        for tid in (self._cpu_timer, self._anim_timer, self._auto_lock_tmr):
            if tid:
                GLib.source_remove(tid)
        return False

    # ─────────────────────────────────────────────────────────────────────────
    #  PAGE: crypto-error screen
    # ─────────────────────────────────────────────────────────────────────────
    def _page_crypto_error(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        self._m(box, s=40, e=40)

        icon = Gtk.Image.new_from_icon_name("dialog-error")
        icon.set_pixel_size(80)
        box.append(icon)

        h = Gtk.Label(label="Dependency Missing")
        h.add_css_class("title-1")
        box.append(h)

        s = Gtk.Label(label="The 'cryptography' library could not be loaded.")
        s.add_css_class("error-text")
        box.append(s)

        err = Gtk.Label(label=CRYPTO_ERR)
        err.add_css_class("code-block")
        err.set_wrap(True)
        box.append(err)
        return box

    # ─────────────────────────────────────────────────────────────────────────
    #  PAGE: unlock
    # ─────────────────────────────────────────────────────────────────────────
    def _page_unlock(self) -> Gtk.Widget:
        clamp = Adw.Clamp()
        clamp.set_maximum_size(380)
        clamp.set_valign(Gtk.Align.CENTER)
        self._m(clamp, s=20, e=20)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)

        icon = Gtk.Image.new_from_icon_name("dialog-password")
        icon.set_pixel_size(72)
        box.append(icon)

        title = Gtk.Label(label="Encrypted Datastore")
        title.add_css_class("title-2")
        box.append(title)

        sub = Gtk.Label(
            label="Enter your master password to decrypt and mount the vault."
        )
        sub.add_css_class("dim-label")
        sub.set_wrap(True)
        sub.set_justify(Gtk.Justification.CENTER)
        box.append(sub)

        grp = Adw.PreferencesGroup()
        self.unlock_pwd = Adw.PasswordEntryRow(title="Master Password")
        self.unlock_pwd.connect("apply", self._on_unlock_attempt)
        self.unlock_pwd.connect("changed", self._eval_pwd_strength)
        grp.add(self.unlock_pwd)

        self.unlock_strength = Gtk.LevelBar()
        self.unlock_strength.set_max_value(4)
        self._m(self.unlock_strength, t=4)

        grp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        grp_box.append(grp)
        grp_box.append(self.unlock_strength)
        box.append(grp_box)

        row = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        self.unlock_btn = Gtk.Button(label="Decrypt & Mount")
        self.unlock_btn.add_css_class("suggested-action")
        self.unlock_btn.add_css_class("pill")
        self.unlock_btn.connect("clicked", self._on_unlock_attempt)
        self.unlock_spinner = Gtk.Spinner()
        row.append(self.unlock_btn)
        row.append(self.unlock_spinner)
        box.append(row)

        clamp.set_child(box)
        return clamp

    def _eval_pwd_strength(self, entry: Adw.PasswordEntryRow) -> None:
        p = entry.get_text()
        score = sum([
            len(p) >= 8,
            any(c.isupper() for c in p),
            any(c.isdigit() for c in p),
            any(not c.isalnum() for c in p),
        ])
        self.unlock_strength.set_value(score)

    def _on_unlock_attempt(self, *_) -> None:
        pwd = self.unlock_pwd.get_text()
        if not pwd:
            return
        self.unlock_pwd.set_sensitive(False)
        self.unlock_btn.set_sensitive(False)
        self.unlock_spinner.start()

        def _worker():
            ok = self.vault.unlock(pwd)
            GLib.idle_add(self._finish_unlock, ok, pwd)

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_unlock(self, success: bool, pwd: str) -> bool:
        self.unlock_pwd.set_sensitive(True)
        self.unlock_btn.set_sensitive(True)
        self.unlock_spinner.stop()

        # Wipe the password from memory
        wipe_string(pwd)

        if success:
            self.root_stack.set_visible_child_name("main")
            self._refresh_vault_list()
            self.unlock_pwd.set_text("")
            self.unlock_strength.set_value(0)
            self._last_activity = time.time()
            if not self._auto_lock_tmr:
                self._auto_lock_tmr = GLib.timeout_add_seconds(
                    AUTO_LOCK_POLL_SECONDS, self._check_auto_lock
                )
        else:
            self.unlock_pwd.set_text("")
            self.unlock_pwd.add_css_class("error")
            self._toast("Invalid password – decryption failed.")
            GLib.timeout_add(
                1200,
                lambda: self.unlock_pwd.remove_css_class("error") or False,
            )
        return False

    # ─────────────────────────────────────────────────────────────────────────
    #  PAGE: main app shell
    # ─────────────────────────────────────────────────────────────────────────
    def _page_main(self) -> Gtk.Widget:
        self.app_stack = Adw.ViewStack()

        p_gen = self.app_stack.add_titled(self._tab_generator(), "gen", "Generator")
        p_gen.set_icon_name("system-run")

        p_vlt = self.app_stack.add_titled(self._tab_vault(), "vault", "Vault")
        p_vlt.set_icon_name("folder-encrypted")

        p_set = self.app_stack.add_titled(self._tab_settings(), "settings", "Settings")
        p_set.set_icon_name("preferences-system")

        self.header = Adw.HeaderBar()
        switcher = Adw.ViewSwitcher(stack=self.app_stack)
        self.header.set_title_widget(switcher)

        self.btn_lock = Gtk.Button(
            icon_name="system-lock-screen",
            tooltip_text="Lock Vault",
        )
        self.btn_lock.connect("clicked", self._action_lock)
        self.header.pack_start(self.btn_lock)

        self.fake_cpu = Gtk.ProgressBar()
        self.fake_cpu.set_size_request(90, -1)
        self.fake_cpu.set_valign(Gtk.Align.CENTER)
        self.fake_cpu.set_tooltip_text("CPU Usage")
        self.header.pack_end(self.fake_cpu)

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        shell.append(self.header)
        shell.append(self.app_stack)

        # Additional activity tracking on the shell
        shell_motion = Gtk.EventControllerMotion.new()
        shell_motion.connect("motion", self._register_activity)
        shell.add_controller(shell_motion)

        shell_click = Gtk.GestureClick.new()
        shell_click.connect("pressed", self._register_activity)
        shell.add_controller(shell_click)

        return shell

    # ─────────────────────────────────────────────────────────────────────────
    #  TAB: Generator
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_generator(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(560)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self._m(box, t=20, b=32, s=20, e=20)

        # ── Engine selector ──────────────────────────────────────────────────
        eng_grp = Adw.PreferencesGroup(title="Generation Engine")
        self.row_engine = Adw.ComboRow(title="Mode")
        self.row_engine.set_model(Gtk.StringList.new(ENGINES_REAL))
        self.row_engine.set_selected(self.vault.state["engine_mode"])
        self.row_engine.connect("notify::selected", self._on_engine_changed)
        eng_grp.add(self.row_engine)
        box.append(eng_grp)

        # ── Engine-options stack ─────────────────────────────────────────────
        self.gen_stack = Gtk.Stack()
        self.gen_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.gen_stack.set_transition_duration(120)
        self._build_engine_pages()
        box.append(self.gen_stack)

        # ── Output display ───────────────────────────────────────────────────
        out_grp = Adw.PreferencesGroup(title="Output")

        self.lbl_output = Gtk.Label(label="─── AWAITING GENERATION ───")
        self.lbl_output.add_css_class("key-display")
        self.lbl_output.set_selectable(True)

        btn_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            halign=Gtk.Align.CENTER,
        )

        self.btn_gen = Gtk.Button(label="Generate")
        self.btn_gen.add_css_class("suggested-action")
        self.btn_gen.add_css_class("pill")
        self.btn_gen.connect("clicked", self._on_generate)

        btn_copy = Gtk.Button(icon_name="edit-copy", tooltip_text="Copy")
        btn_copy.add_css_class("pill")
        btn_copy.connect("clicked", lambda _: self._copy_val(self.lbl_output.get_label()))

        btn_row.append(self.btn_gen)
        btn_row.append(btn_copy)

        out_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        out_inner.append(self.lbl_output)
        out_inner.append(btn_row)

        out_card = Gtk.ListBox()
        out_card.add_css_class("boxed-list")
        out_card.set_selection_mode(Gtk.SelectionMode.NONE)
        self._m(out_inner, t=12, b=12, s=16, e=16)
        out_card.append(out_inner)

        out_grp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        lbl_out_title = Gtk.Label(label="Output", halign=Gtk.Align.START)
        lbl_out_title.add_css_class("heading")
        out_grp_box.append(lbl_out_title)
        out_grp_box.append(out_card)
        box.append(out_grp_box)

        # ── Save to vault ────────────────────────────────────────────────────
        save_grp = Adw.PreferencesGroup(title="Save to Vault")

        self.entry_label = Adw.EntryRow(title="Reference Name")
        self.entry_tag = Adw.EntryRow(title="Tag / Category  (optional)")
        save_grp.add(self.entry_label)
        save_grp.add(self.entry_tag)
        box.append(save_grp)

        self.btn_save = Gtk.Button(label="Commit to Vault")
        self.btn_save.add_css_class("pill")
        self.btn_save.set_halign(Gtk.Align.CENTER)
        self.btn_save.connect("clicked", self._on_save)
        box.append(self.btn_save)

        clamp.set_child(box)
        scroll.set_child(clamp)
        return scroll

    # ── Engine option pages ───────────────────────────────────────────────────
    def _build_engine_pages(self) -> None:
        # Mode 0: Win Modern Base-25
        g0 = Adw.PreferencesGroup()
        self.row_b25_ed = Adw.ComboRow(title="Edition / Channel")
        self.row_b25_ed.set_model(Gtk.StringList.new([
            "Standard (Home / Pro)", "N Edition", "Server / Datacenter",
        ]))
        self.row_b25_ed.set_selected(self.vault.state["b25_edition"])
        self.row_b25_ed.connect(
            "notify::selected",
            lambda o, _: self._set("b25_edition", o.get_selected()),
        )
        g0.add(self.row_b25_ed)
        hint0 = Adw.ActionRow(
            title="Windows 8, 10, 11 and Server",
            subtitle="25-char Base-25 key (adds N to the classic alphabet)",
        )
        hint0.set_activatable(False)
        g0.add(hint0)
        self.gen_stack.add_named(g0, "mode_0")

        # Mode 1: Win Classic Base-24
        g1 = Adw.PreferencesGroup()
        self.row_b24_arch = Adw.ComboRow(title="Key Type")
        self.row_b24_arch.set_model(Gtk.StringList.new([
            "Retail", "OEM", "Enterprise", "Volume / KMS",
        ]))
        self.row_b24_arch.set_selected(self.vault.state["b24_archetype"])
        self.row_b24_arch.connect(
            "notify::selected",
            lambda o, _: self._set("b24_archetype", o.get_selected()),
        )
        g1.add(self.row_b24_arch)
        hint1 = Adw.ActionRow(
            title="Windows XP, Vista, 7 – and Office 2003/2007",
            subtitle="25-char Base-24 key; first char encodes the channel",
        )
        hint1.set_activatable(False)
        g1.add(hint1)
        self.gen_stack.add_named(g1, "mode_1")

        # Mode 2: Win Legacy Retail
        g2 = Adw.PreferencesGroup()
        info2 = Adw.ActionRow(
            title="Windows 95 / 98 / NT 4  –  Retail",
            subtitle="Format: XXX-XXXXXXX  ·  Mod-7 digit checksum",
        )
        info2.set_activatable(False)
        hint2 = Adw.ActionRow(
            title="Algorithm",
            subtitle="First 3 digits = site code  ·  Last 7 digits (0–8) sum ≡ 0 mod 7",
        )
        hint2.set_activatable(False)
        g2.add(info2)
        g2.add(hint2)
        self.gen_stack.add_named(g2, "mode_2")

        # Mode 3: Win Legacy OEM
        g3 = Adw.PreferencesGroup()
        info3 = Adw.ActionRow(
            title="Windows 95 / 98 / NT 4  –  OEM",
            subtitle="Format: DDDYY-OEM-0NNNNNN-XXXXX",
        )
        info3.set_activatable(False)
        hint3 = Adw.ActionRow(
            title="Algorithm",
            subtitle=(
                "DDD = Julian day 001–366  ·  YY = year 95–03  ·  "
                "Middle starts with 0; 7 digits sum ≡ 0 mod 7"
            ),
        )
        hint3.set_activatable(False)
        g3.add(info3)
        g3.add(hint3)
        self.gen_stack.add_named(g3, "mode_3")

        # Mode 4: Custom Key Builder
        g4 = Adw.PreferencesGroup()
        self.ckb_charset = Adw.EntryRow(title="Character Set")
        self.ckb_charset.set_text(self.vault.state["ckb_charset"])
        self.ckb_charset.connect(
            "changed", lambda e: self._set("ckb_charset", e.get_text())
        )
        g4.add(self.ckb_charset)

        row_grps = Adw.ActionRow(title="Groups", subtitle="Number of character blocks")
        self.spin_ckb_groups = Gtk.SpinButton.new_with_range(2, 10, 1)
        self.spin_ckb_groups.set_value(self.vault.state["ckb_groups"])
        self.spin_ckb_groups.set_valign(Gtk.Align.CENTER)
        self.spin_ckb_groups.connect(
            "value-changed",
            lambda s: self._set("ckb_groups", int(s.get_value())),
        )
        row_grps.add_suffix(self.spin_ckb_groups)
        row_grps.set_activatable_widget(self.spin_ckb_groups)
        g4.add(row_grps)

        row_sz = Adw.ActionRow(title="Group Size", subtitle="Characters per block")
        self.spin_ckb_size = Gtk.SpinButton.new_with_range(1, 12, 1)
        self.spin_ckb_size.set_value(self.vault.state["ckb_size"])
        self.spin_ckb_size.set_valign(Gtk.Align.CENTER)
        self.spin_ckb_size.connect(
            "value-changed",
            lambda s: self._set("ckb_size", int(s.get_value())),
        )
        row_sz.add_suffix(self.spin_ckb_size)
        row_sz.set_activatable_widget(self.spin_ckb_size)
        g4.add(row_sz)

        self.ckb_sep = Adw.EntryRow(title="Separator Character")
        self.ckb_sep.set_text(self.vault.state["ckb_sep"])
        self.ckb_sep.connect(
            "changed", lambda e: self._set("ckb_sep", e.get_text())
        )
        g4.add(self.ckb_sep)
        self.gen_stack.add_named(g4, "mode_4")

        # Mode 5: Structured Mask
        g5 = Adw.PreferencesGroup()
        self.entry_mask = Adw.EntryRow(title="Mask Pattern")
        self.entry_mask.set_text(self.vault.state["mask_fmt"])
        self.entry_mask.connect(
            "changed", lambda e: self._set("mask_fmt", e.get_text())
        )
        g5.add(self.entry_mask)
        hint5 = Adw.ActionRow(
            title="Token reference",
            subtitle="A = uppercase  ·  a = lower  ·  # = digit  ·  @ = symbol  ·  ? = any  ·  \\ = escape",
        )
        hint5.set_activatable(False)
        g5.add(hint5)
        self.gen_stack.add_named(g5, "mode_5")

        # Mode 6: Password
        g6 = Adw.PreferencesGroup()

        row_len = Adw.ActionRow(title="Length")
        self.lbl_pwd_len = Gtk.Label(label=str(self.vault.state["pwd_len"]))
        self.lbl_pwd_len.add_css_class("dim-label")
        self.lbl_pwd_len.set_valign(Gtk.Align.CENTER)
        self.lbl_pwd_len.set_width_chars(4)

        self.scale_pwd = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 8, 128, 1)
        self.scale_pwd.set_value(self.vault.state["pwd_len"])
        self.scale_pwd.set_hexpand(True)
        self.scale_pwd.set_valign(Gtk.Align.CENTER)
        self.scale_pwd.set_size_request(160, -1)
        self.scale_pwd.set_draw_value(False)
        self.scale_pwd.connect("value-changed", self._on_pwd_len_changed)

        row_len.add_suffix(self.lbl_pwd_len)
        row_len.add_suffix(self.scale_pwd)
        g6.add(row_len)

        for key, label in (
            ("pwd_u", "Uppercase  A–Z"),
            ("pwd_l", "Lowercase  a–z"),
            ("pwd_d", "Digits  0–9"),
            ("pwd_s", "Symbols  !@#$%^&*"),
        ):
            row = Adw.ActionRow(title=label)
            sw = Gtk.Switch(active=self.vault.state[key], valign=Gtk.Align.CENTER)
            sw.connect(
                "state-set",
                lambda _, st, k=key: self._set(k, st) or False,
            )
            row.add_suffix(sw)
            row.set_activatable_widget(sw)
            g6.add(row)

        self.gen_stack.add_named(g6, "mode_6")

        # Mode 7: PIN / Passcode
        g7 = Adw.PreferencesGroup()

        self.row_pin_preset = Adw.ComboRow(title="Preset")
        self.row_pin_preset.set_model(Gtk.StringList.new([
            "4-digit numeric   (ATM / Android legacy)",
            "6-digit numeric   (iPhone default, iOS 9+)",
            "Custom-length numeric",
            "Custom alphanumeric",
        ]))
        self.row_pin_preset.set_selected(self.vault.state["pin_preset"])
        self.row_pin_preset.connect(
            "notify::selected", self._on_pin_preset_changed
        )
        g7.add(self.row_pin_preset)

        self.row_pin_len = Adw.ActionRow(
            title="Custom Length", subtitle="Number of characters"
        )
        self.spin_pin_len = Gtk.SpinButton.new_with_range(4, 32, 1)
        self.spin_pin_len.set_value(self.vault.state["pin_len"])
        self.spin_pin_len.set_valign(Gtk.Align.CENTER)
        self.spin_pin_len.connect(
            "value-changed",
            lambda s: self._set("pin_len", int(s.get_value())),
        )
        self.row_pin_len.add_suffix(self.spin_pin_len)
        self.row_pin_len.set_activatable_widget(self.spin_pin_len)
        g7.add(self.row_pin_len)

        self._sync_pin_len_row()
        self.gen_stack.add_named(g7, "mode_7")

        self.gen_stack.set_visible_child_name(f"mode_{self.vault.state['engine_mode']}")

    def _on_pwd_len_changed(self, scale: Gtk.Scale) -> None:
        v = int(scale.get_value())
        self._set("pwd_len", v)
        self.lbl_pwd_len.set_label(str(v))

    def _on_pin_preset_changed(self, obj: Adw.ComboRow, _pspec) -> None:
        self._set("pin_preset", obj.get_selected())
        self._sync_pin_len_row()

    def _sync_pin_len_row(self) -> None:
        preset = self.vault.state["pin_preset"]
        self.row_pin_len.set_visible(preset in (2, 3))

    def _on_engine_changed(self, obj: Adw.ComboRow, _pspec) -> None:
        idx = obj.get_selected()
        self._set("engine_mode", idx)
        self.gen_stack.set_visible_child_name(f"mode_{idx}")

    # ─────────────────────────────────────────────────────────────────────────
    #  Generator logic
    # ─────────────────────────────────────────────────────────────────────────
    def _on_generate(self, _btn: Gtk.Button) -> None:
        if self.is_animating:
            return
        mode = self.vault.state["engine_mode"]
        result, kind = ENGINE_FUNCS[mode](self.vault.state)
        self._current_type = kind

        if self.vault.state["animations"] and "ERR" not in result:
            self.is_animating = True
            self.btn_gen.set_sensitive(False)
            self.btn_save.set_sensitive(False)
            self._anim_target = result
            self._anim_frame = 0
            self._anim_timer = GLib.timeout_add(45, self._anim_tick)
        else:
            self.lbl_output.set_label(result)

    def _anim_tick(self) -> bool:
        target = self._anim_target
        if self._anim_frame < len(target):
            revealed = target[:self._anim_frame]
            remaining = target[self._anim_frame:]
            pool = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*!"
            scrambled = "".join(
                secrets.choice(pool) if c not in "- ." else c
                for c in remaining
            )
            self.lbl_output.set_label(revealed + scrambled)
            self._anim_frame += secrets.randbelow(3) + 1
            return True
        else:
            self.lbl_output.set_label(target)
            self.is_animating = False
            self.btn_gen.set_sensitive(True)
            self.btn_save.set_sensitive(True)
            self._anim_timer = None
            return False

    def _on_save(self, _btn: Gtk.Button) -> None:
        val = self.lbl_output.get_label()
        if "ERR" in val or "AWAITING" in val:
            self._toast("Generate a value first.")
            return
        label = self.entry_label.get_text().strip()
        tag = self.entry_tag.get_text().strip()
        self.vault.add_record(label, val, self._current_type, tag)
        self._refresh_vault_list()
        self.entry_label.set_text("")
        self.entry_tag.set_text("")
        self._toast("Committed to vault.")

    # ─────────────────────────────────────────────────────────────────────────
    #  TAB: Vault
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_vault(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._m(box, t=12, b=12, s=12, e=12)

        top = Gtk.Box(spacing=8)
        self.vault_search = Gtk.SearchEntry(
            placeholder_text="Search name or value…",
            hexpand=True,
        )
        self.vault_search.connect(
            "search-changed",
            lambda _: self.vault_list.invalidate_filter(),
        )

        self.vault_tag_filter = Gtk.SearchEntry(
            placeholder_text="Filter by tag…",
        )
        self.vault_tag_filter.set_size_request(130, -1)
        self.vault_tag_filter.connect(
            "search-changed",
            lambda _: self.vault_list.invalidate_filter(),
        )

        top.append(self.vault_search)
        top.append(self.vault_tag_filter)
        box.append(top)

        self.vault_view_stack = Gtk.Stack()

        empty = Adw.StatusPage()
        empty.set_title("Vault is Empty")
        empty.set_description("Generate a value in the Generator tab, then commit it.")
        empty.set_icon_name("folder-encrypted")
        self.vault_view_stack.add_named(empty, "empty")

        self.vault_list = Gtk.ListBox()
        self.vault_list.add_css_class("boxed-list")
        self.vault_list.set_filter_func(self._vault_filter)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self.vault_list)
        self.vault_view_stack.add_named(scroll, "list")

        box.append(self.vault_view_stack)
        return box

    def _vault_filter(self, row: Gtk.ListBoxRow) -> bool:
        q = self.vault_search.get_text().lower()
        tag = self.vault_tag_filter.get_text().lower()
        child = row.get_child()
        if not isinstance(child, Adw.ActionRow):
            return True
        t = (child.get_title() or "").lower()
        s = (child.get_subtitle() or "").lower()
        rt = getattr(child, "_s_tag", "").lower()
        return (not q or q in t or q in s) and (not tag or tag in rt)

    def _refresh_vault_list(self) -> None:
        child = self.vault_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.vault_list.remove(child)
            child = nxt

        if not self.vault.records:
            self.vault_view_stack.set_visible_child_name("empty")
            return

        self.vault_view_stack.set_visible_child_name("list")
        for item in reversed(self.vault.records):
            self._append_vault_row(item)
        self.vault_list.invalidate_filter()

    def _append_vault_row(self, item: Dict[str, Any]) -> None:
        row = Adw.ActionRow(
            title=item["label"],
            subtitle=item["val"],
        )
        row._s_tag = item.get("tag", "")

        badge_css = TYPE_BADGE.get(item["type"], "badge-blue")
        row.add_prefix(self._badge(item["type"], badge_css))

        tag = item.get("tag", "")
        if tag:
            row.add_prefix(self._badge(tag, "badge-amber"))

        cp = Gtk.Button(
            icon_name="edit-copy",
            tooltip_text="Copy value",
            valign=Gtk.Align.CENTER,
        )
        cp.add_css_class("flat")
        cp.connect("clicked", lambda _, v=item["val"]: self._copy_val(v))
        row.add_suffix(cp)

        dl = Gtk.Button(
            icon_name="user-trash",
            tooltip_text="Delete",
            valign=Gtk.Align.CENTER,
        )
        dl.add_css_class("flat")
        dl.add_css_class("destructive-action")
        dl.connect(
            "clicked",
            lambda _, uid=item["id"], rw=row: self._delete_vault_row(uid, rw),
        )
        row.add_suffix(dl)

        self.vault_list.append(row)

    def _copy_val(self, txt: str) -> None:
        cb = Gdk.Display.get_default().get_clipboard()
        if cb:
            cb.set(txt)
            self._toast("Copied to clipboard.")

    def _delete_vault_row(self, uid: str, row: Adw.ActionRow) -> None:
        if self.vault.delete_record(uid):
            self.vault_list.remove(row)
            if not self.vault.records:
                self.vault_view_stack.set_visible_child_name("empty")

    # ─────────────────────────────────────────────────────────────────────────
    #  TAB: Settings
    # ─────────────────────────────────────────────────────────────────────────
    def _tab_settings(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()

        g_sec = Adw.PreferencesGroup(title="Vault & Security")

        row_al = Adw.ActionRow(
            title="Auto-Lock Timeout",
            subtitle="Minutes of inactivity before the vault locks",
        )
        self.spin_auto_lock = Gtk.SpinButton.new_with_range(1, 60, 1)
        self.spin_auto_lock.set_value(self.vault.state.get("auto_lock_mins", 3))
        self.spin_auto_lock.set_valign(Gtk.Align.CENTER)
        self.spin_auto_lock.connect(
            "value-changed",
            lambda s: self._set("auto_lock_mins", int(s.get_value())),
        )
        row_al.add_suffix(self.spin_auto_lock)
        row_al.set_activatable_widget(self.spin_auto_lock)
        g_sec.add(row_al)

        row_stealth = Adw.ActionRow(
            title="Stealth Mode",
            subtitle="Disguise as 'SysMon Diagnostics'; hides nav and relabels controls",
        )
        sw_stealth = Gtk.Switch(
            active=self.vault.state["stealth"],
            valign=Gtk.Align.CENTER,
        )
        sw_stealth.connect(
            "state-set",
            lambda _, st: self._update_stealth(st) or False,
        )
        row_stealth.add_suffix(sw_stealth)
        row_stealth.set_activatable_widget(sw_stealth)
        g_sec.add(row_stealth)

        self.row_vault_path = Adw.ActionRow(
            title="Encrypted Database Path",
            subtitle=self.vault.state["vault_path"],
        )
        btn_browse = Gtk.Button(
            icon_name="folder-open",
            tooltip_text="Change path",
            valign=Gtk.Align.CENTER,
        )
        btn_browse.add_css_class("flat")
        btn_browse.connect("clicked", self._on_browse_path)
        self.row_vault_path.add_suffix(btn_browse)
        g_sec.add(self.row_vault_path)

        row_nuke = Adw.ActionRow(
            title="Destroy Datastore",
            subtitle="Permanently wipe the encrypted vault file from disk",
        )
        btn_nuke = Gtk.Button(label="Nuke", valign=Gtk.Align.CENTER)
        btn_nuke.add_css_class("destructive-action")
        btn_nuke.add_css_class("pill")
        btn_nuke.connect("clicked", self._action_nuke)
        row_nuke.add_suffix(btn_nuke)
        g_sec.add(row_nuke)

        page.add(g_sec)

        g_app = Adw.PreferencesGroup(title="Appearance")

        row_ani = Adw.ActionRow(
            title="Generation Animation",
            subtitle="Brief scramble effect when a value is generated",
        )
        sw_ani = Gtk.Switch(
            active=self.vault.state["animations"],
            valign=Gtk.Align.CENTER,
        )
        sw_ani.connect(
            "state-set",
            lambda _, st: self._set("animations", st) or False,
        )
        row_ani.add_suffix(sw_ani)
        row_ani.set_activatable_widget(sw_ani)
        g_app.add(row_ani)

        page.add(g_app)

        g_about = Adw.PreferencesGroup(title="About")
        row_ver = Adw.ActionRow(
            title=APP_REAL,
            subtitle="Version 2.1  ·  GTK 4 / Libadwaita  ·  Python 3",
        )
        row_ver.set_activatable(False)
        g_about.add(row_ver)
        page.add(g_about)

        return page

    # ─────────────────────────────────────────────────────────────────────────
    #  App-wide actions
    # ─────────────────────────────────────────────────────────────────────────
    def _action_lock(self, _btn) -> None:
        self.vault.lock()
        self._refresh_vault_list()
        self.root_stack.set_visible_child_name("unlock")
        if self._auto_lock_tmr:
            GLib.source_remove(self._auto_lock_tmr)
            self._auto_lock_tmr = None

    def _action_nuke(self, _btn) -> None:
        path = self.vault.state["vault_path"]
        if os.path.exists(path):
            os.remove(path)
            logging.warning("Vault nuked by user.")
        self._toast("Datastore permanently destroyed.")
        GLib.timeout_add(900, lambda: self._action_lock(None) or False)

    def _update_stealth(self, active: bool) -> None:
        self._set("stealth", active)
        self._apply_stealth()

    def _apply_stealth(self) -> None:
        st = self.vault.state["stealth"]
        self.win.set_title(APP_FAKE if st else APP_REAL)
        self.btn_lock.set_visible(not st)
        self.fake_cpu.set_visible(st)

        if st:
            self.row_engine.set_model(Gtk.StringList.new(ENGINES_FAKE))
            self.btn_gen.set_label("Execute Diagnostic Routine")
        else:
            self.row_engine.set_model(Gtk.StringList.new(ENGINES_REAL))
            self.btn_gen.set_label("Generate")

        self.row_engine.set_selected(self.vault.state["engine_mode"])

        if st and not self._cpu_timer:
            self._cpu_timer = GLib.timeout_add_seconds(1, self._tick_cpu)
        elif not st and self._cpu_timer:
            GLib.source_remove(self._cpu_timer)
            self._cpu_timer = None

    def _tick_cpu(self) -> bool:
        self.fake_cpu.set_fraction((secrets.randbelow(30) + 5) / 100.0)
        return True

    def _on_browse_path(self, _btn) -> None:
        dlg = Gtk.FileDialog(title="Select or Create Encrypted Datastore")
        ff = Gtk.FileFilter()
        ff.set_name("Datastore (*.dat)")
        ff.add_pattern("*.dat")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(ff)
        dlg.set_filters(filters)
        dlg.set_default_filter(ff)
        dlg.save(self.win, None, self._finish_browse)

    def _finish_browse(self, dlg: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
        try:
            f = dlg.save_finish(res)
            if not f:
                return
            new_path = f.get_path()
            if not os.path.isdir(os.path.dirname(new_path)):
                self._toast("Invalid directory.")
                return
            self._set("vault_path", new_path)
            self.row_vault_path.set_subtitle(new_path)
            self._action_lock(None)
        except Exception:
            pass


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = KeySentinelUI()
    sys.exit(app.run(sys.argv))