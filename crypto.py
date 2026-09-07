import os
import json
import time
import uuid
import logging
import hashlib
import tempfile
from typing import Dict, Any, List, Optional
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
except ImportError:
    pass

try:
    from .constants import CONFIG_PATH, DEFAULT_VAULT, PBKDF2_ITERATIONS, ALPHA_B24, LOG_FILE
except (ImportError, ValueError):
    from constants import CONFIG_PATH, DEFAULT_VAULT, PBKDF2_ITERATIONS, ALPHA_B24, LOG_FILE

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def secure_wipe(data: Optional[bytearray]) -> None:
    if data is not None:
        for i in range(len(data)):
            data[i] = 0

def wipe_string(s: str) -> None:
    if s:
        secure_wipe(bytearray(s.encode("utf-8")))

def format_relative_time(ts: float) -> str:
    diff = max(0, int(time.time() - ts))
    if diff < 60: return "just now"
    if diff < 3600: return f"{diff // 60}m ago"
    if diff < 86400: return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"

class VaultManager:
    DEFAULTS: Dict[str, Any] = {
        "vault_path": DEFAULT_VAULT, "animations": True, "auto_lock_mins": 3, "engine_mode": 0,
        "pwd_len": 20, "pwd_u": True, "pwd_l": True, "pwd_d": True, "pwd_s": True, "pwd_ambig": False, "pwd_exclude": "",
        "phrase_words": 4, "phrase_sep": "-", "phrase_cap": True, "phrase_num": True,
        "pin_preset": 0, "pin_len": 6, "net_mode": 0, "uuid_mode": 0, "mask_fmt": "AAAA-####-@@@@",
        "ckb_charset": ALPHA_B24, "ckb_groups": 5, "ckb_size": 5, "ckb_sep": "-",
        "b25_edition": 0, "b24_archetype": 0, "legacy_mode": 0,
        "rgb_mode": False, "toxic_mode": False, "paranoia_mode": False, "ui_opacity": 1.0, "clipboard_ttl": 0, "anim_speed": 6, "drunk_mode": False, "ui_theme": 0, "ui_accent": "#ff2a5f", "ui_glow": 8, "ui_font": 0, "ui_radius": 12,
        "auto_copy": False, "palette_preset": 1, "bulk_count": 10,
    }

    def __init__(self) -> None:
        self.state: Dict[str, Any] = dict(self.DEFAULTS)
        self.records: List[Dict[str, Any]] = []
        self._master_pwd: Optional[bytearray] = None
        self._aesgcm: Optional[AESGCM] = None
        self._vault_salt: Optional[bytes] = None
        self.is_unlocked: bool = False
        self._load_config()

    def _derive_key(self, password: bytes, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password, salt, PBKDF2_ITERATIONS)

    def _load_config(self) -> None:
        if not os.path.exists(CONFIG_PATH) or not self._master_pwd: return
        try:
            with open(CONFIG_PATH, "rb") as fh: payload = fh.read()
            if len(payload) < 28: return
            plaintext = AESGCM(self._derive_key(bytes(self._master_pwd), payload[:16])).decrypt(payload[16:28], payload[28:], None)
            self.state.update(json.loads(plaintext.decode()))
        except Exception as exc:
            logging.error(f"config decrypt error: {exc}")

    def _save_config(self) -> None:
        if not self._master_pwd: return
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            salt, nonce = os.urandom(16), os.urandom(12)
            ciphertext = AESGCM(self._derive_key(bytes(self._master_pwd), salt)).encrypt(nonce, json.dumps(self.state).encode(), None)
            with tempfile.NamedTemporaryFile("wb", delete=False, dir=os.path.dirname(CONFIG_PATH)) as tf:
                tf.write(salt + nonce + ciphertext)
            os.replace(tf.name, CONFIG_PATH)
        except Exception as exc:
            logging.error(f"config save error: {exc}")

    def unlock(self, password: str) -> bool:
        path = self.state["vault_path"]
        pwd_ba = bytearray(password.encode("utf-8"))
        self._master_pwd = pwd_ba

        if not os.path.exists(path):
            self._vault_salt = os.urandom(16)
            self._aesgcm = AESGCM(self._derive_key(bytes(pwd_ba), self._vault_salt))
            self.records = []
            self.is_unlocked = True
            self._write_vault()
            self._save_config()
            return True

        try:
            with open(path, "rb") as fh: payload = fh.read()
            if len(payload) < 28: return False
            salt, nonce, ciphertext = payload[:16], payload[16:28], payload[28:]
            aesgcm = AESGCM(self._derive_key(bytes(pwd_ba), salt))
            self.records = json.loads(aesgcm.decrypt(nonce, ciphertext, None).decode())
            self._vault_salt, self._aesgcm = salt, aesgcm
            self.is_unlocked = True
            self._load_config()
            return True
        except (InvalidTag, ValueError):
            self.lock()
            return False

    def _write_vault(self) -> None:
        if not self._aesgcm or not self._vault_salt or not self.is_unlocked: return
        try:
            os.makedirs(os.path.dirname(self.state["vault_path"]), exist_ok=True)
            nonce = os.urandom(12)
            ciphertext = self._aesgcm.encrypt(nonce, json.dumps(self.records).encode(), None)
            with tempfile.NamedTemporaryFile("wb", delete=False, dir=os.path.dirname(self.state["vault_path"])) as tf:
                tf.write(self._vault_salt + nonce + ciphertext)
            os.replace(tf.name, self.state["vault_path"])
        except Exception as exc:
            logging.error(f"vault write error: {exc}")

    def add_record(self, label: str, val: str, type_str: str, tag: str = "", fav: bool = False) -> Dict[str, Any]:
        rec = {
            "id": str(uuid.uuid4()), "label": label or "Untitled", "val": val,
            "type": type_str, "tag": tag, "timestamp": time.time(), "fav": fav
        }
        self.records.append(rec)
        self._write_vault()
        return rec

    def update_record(self, uid: str, label: str, tag: str, fav: Optional[bool] = None) -> bool:
        for r in self.records:
            if r["id"] == uid:
                r["label"] = label or r["label"]
                r["tag"] = tag
                if fav is not None:
                    r["fav"] = fav
                self._write_vault()
                return True
        return False

    def toggle_fav(self, uid: str) -> bool:
        for r in self.records:
            if r["id"] == uid:
                r["fav"] = not r.get("fav", False)
                self._write_vault()
                return r["fav"]
        return False

    def export_vault_json(self) -> str:
        return json.dumps(self.records, indent=2)

    def import_vault_json(self, raw_json: str) -> int:
        try:
            parsed = json.loads(raw_json)
            if not isinstance(parsed, list): return 0
            count = 0
            existing_ids = {r.get("id") for r in self.records}
            for item in parsed:
                if isinstance(item, dict) and "val" in item:
                    item_id = item.get("id")
                    if not item_id or item_id in existing_ids:
                        item_id = str(uuid.uuid4())
                    self.records.append({
                        "id": item_id,
                        "label": item.get("label", "Imported Key"),
                        "val": item["val"],
                        "type": item.get("type", "Imported"),
                        "tag": item.get("tag", "imported"),
                        "timestamp": item.get("timestamp", time.time()),
                        "fav": bool(item.get("fav", False))
                    })
                    existing_ids.add(item_id)
                    count += 1
            if count > 0:
                self._write_vault()
            return count
        except Exception as exc:
            logging.error(f"vault import error: {exc}")
            return 0

    def delete_record(self, uid: str) -> bool:
        filtered = [r for r in self.records if r["id"] != uid]
        if len(self.records) > len(filtered):
            self.records = filtered
            self._write_vault()
            return True
        return False

    def lock(self) -> None:
        self._aesgcm = self._vault_salt = None
        self.records = []
        self.is_unlocked = False
        if self._master_pwd:
            secure_wipe(self._master_pwd)
            self._master_pwd = None

    def set(self, key: str, val: Any) -> None:
        self.state[key] = val
        if self.is_unlocked:
            self._save_config()

HAS_CRYPTO = 'AESGCM' in globals()
CRYPTO_ERR = "" if HAS_CRYPTO else "python3-cryptography is missing"
