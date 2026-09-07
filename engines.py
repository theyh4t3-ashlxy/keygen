import math
import string
import secrets
import uuid
from typing import Dict, Any, Tuple, List, Callable
try:
    from .constants import ALPHA_B24, ALPHA_B25, AMBIGUOUS, WORDLIST
except (ImportError, ValueError):
    from constants import ALPHA_B24, ALPHA_B25, AMBIGUOUS, WORDLIST

def estimate_crack_time(entropy: float) -> str:
    # 100 billion guesses / sec
    guesses_per_sec = 1e11
    if entropy <= 0:
        return "0 seconds (instantly folded)"
    seconds = (2 ** (entropy - 1)) / guesses_per_sec
    if seconds < 1:
        return "<1 second"
    if seconds < 60:
        return f"{int(seconds)} seconds"
    if seconds < 3600:
        return f"{int(seconds // 60)} minutes"
    if seconds < 86400:
        return f"{int(seconds // 3600)} hours"
    if seconds < 31536000:
        return f"{int(seconds // 86400)} days"
    years = seconds / 31536000
    if years < 1000:
        return f"{int(years)} years"
    if years < 1_000_000:
        return f"{int(years // 1000)}k years"
    if years < 1_000_000_000:
        return f"{int(years // 1_000_000)}m years"
    return "heat death of universe"


def gen_password(state: Dict[str, Any]) -> Tuple[str, str, float]:
    pool = ""
    if state.get("pwd_u", True): pool += string.ascii_uppercase
    if state.get("pwd_l", True): pool += string.ascii_lowercase
    if state.get("pwd_d", True): pool += string.digits
    if state.get("pwd_s", True): pool += "!@#$%^&*-_+=~?"
    if state.get("pwd_ambig", False):
        pool = "".join(c for c in pool if c not in AMBIGUOUS)
    if exc := state.get("pwd_exclude", ""):
        pool = "".join(c for c in pool if c not in exc)
    if not pool:
        return "ERR: character pool is empty", "Error", 0.0
    length = max(4, min(256, state.get("pwd_len", 20)))
    res = "".join(secrets.choice(pool) for _ in range(length))
    return res, "Password", length * math.log2(len(pool))

def gen_passphrase(state: Dict[str, Any]) -> Tuple[str, str, float]:
    count = max(2, min(20, state.get("phrase_words", 4)))
    sep = state.get("phrase_sep", "-")
    capitalize = state.get("phrase_cap", True)
    add_num = state.get("phrase_num", True)
    words = [secrets.choice(WORDLIST) for _ in range(count)]
    if capitalize:
        words = [w.capitalize() for w in words]
    if add_num:
        words[-1] += str(secrets.randbelow(90) + 10)
    bits = count * math.log2(len(WORDLIST)) + (math.log2(90) if add_num else 0)
    return sep.join(words), "Passphrase", bits

def gen_pin(state: Dict[str, Any]) -> Tuple[str, str, float]:
    preset = state.get("pin_preset", 0)
    if preset == 0: length, alpha = 4, False
    elif preset == 1: length, alpha = 6, False
    elif preset == 2: length, alpha = state.get("pin_len", 8), False
    else: length, alpha = state.get("pin_len", 8), True
    length = max(2, min(64, length))
    if alpha:
        pool = string.ascii_letters + string.digits
        return "".join(secrets.choice(pool) for _ in range(length)), "Passcode", length * math.log2(len(pool))
    return "".join(str(secrets.randbelow(10)) for _ in range(length)), "PIN", length * math.log2(10)

def gen_network(state: Dict[str, Any]) -> Tuple[str, str, float]:
    mode = state.get("net_mode", 0)
    if mode == 0:
        mac = [secrets.randbelow(256) for _ in range(6)]
        mac[0] = (mac[0] & 0xFC) | 0x02
        return ":".join(f"{b:02X}" for b in mac), "Hardware MAC", 46.0
    elif mode == 1:
        return f"fd{secrets.randbits(40):010x}::1", "IPv6 ULA", 40.0
    elif mode == 2:
        return secrets.token_hex(32).upper(), "WPA PSK", 256.0
    return secrets.token_urlsafe(32), "WireGuard Secret", 256.0

def gen_uuid(state: Dict[str, Any]) -> Tuple[str, str, float]:
    mode = state.get("uuid_mode", 0)
    if mode == 0:
        return str(uuid.uuid4()), "UUIDv4", 122.0
    elif mode == 1:
        prefix = secrets.choice(["sk_live_", "pk_live_", "sec_"])
        token = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        return f"{prefix}{token}", "API Key", 32 * math.log2(62)
    return secrets.token_hex(32), "Hex Secret", 256.0

def gen_mask(state: Dict[str, Any]) -> Tuple[str, str, float]:
    out, escape, total_bits = [], False, 0.0
    for c in state.get("mask_fmt", "AAAA-####-@@@@"):
        if escape:
            out.append(c); escape = False; continue
        if c == "\\": escape = True
        elif c == "A": out.append(secrets.choice(string.ascii_uppercase)); total_bits += math.log2(26)
        elif c == "a": out.append(secrets.choice(string.ascii_lowercase)); total_bits += math.log2(26)
        elif c == "#": out.append(secrets.choice(string.digits)); total_bits += math.log2(10)
        elif c == "@": out.append(secrets.choice("!@#$%^&*-_+=")); total_bits += math.log2(12)
        elif c == "?":
            pool = string.ascii_letters + string.digits + "!@#$%^&*-_+="
            out.append(secrets.choice(pool)); total_bits += math.log2(len(pool))
        else:
            out.append(c)
    return "".join(out), "Masked Key", total_bits

def gen_custom_key(state: Dict[str, Any]) -> Tuple[str, str, float]:
    charset = state.get("ckb_charset", ALPHA_B24)
    groups = max(1, min(16, state.get("ckb_groups", 5)))
    size = max(1, min(16, state.get("ckb_size", 5)))
    sep = state.get("ckb_sep", "-")
    if not charset:
        return "ERR: charset cannot be empty", "Error", 0.0
    blocks = ["".join(secrets.choice(charset) for _ in range(size)) for _ in range(groups)]
    bits = (groups * size) * math.log2(len(charset))
    return sep.join(blocks), "Custom Key", bits

def gen_win_modern(state: Dict[str, Any]) -> Tuple[str, str, float]:
    val = secrets.randbits(114)
    chars = []
    t = val
    for _ in range(25):
        t, rem = divmod(t, 25)
        chars.append(ALPHA_B25[rem])
    chars.reverse()
    chars[0] = {0: secrets.choice("BCDFGHJKM"), 1: "N", 2: secrets.choice("WXY89")}.get(state.get("b25_edition", 0), "B")
    k = "".join(chars)
    return "-".join(k[i:i+5] for i in range(0, 25, 5)), "Win Modern Key", 114.0

def gen_win_classic(state: Dict[str, Any]) -> Tuple[str, str, float]:
    val = secrets.randbits(114)
    chars = []
    t = val
    for _ in range(25):
        t, rem = divmod(t, 24)
        chars.append(ALPHA_B24[rem])
    chars.reverse()
    chars[0] = {0: secrets.choice("RTWXYP"), 1: secrets.choice("346789"), 2: secrets.choice("BCDFGH")}.get(state.get("b24_archetype", 0), "R")
    k = "".join(chars)
    return "-".join(k[i:i+5] for i in range(0, 25, 5)), "Win Classic Key", 114.0

def gen_win95_retro(state: Dict[str, Any]) -> Tuple[str, str, float]:
    # math goes brrr
    if state.get("legacy_mode", 0) == 0:
        while True:
            site = secrets.randbelow(998) + 1
            if site not in (333, 444, 555, 666, 777, 888, 999):
                break
        while True:
            d = [secrets.randbelow(10) for _ in range(6)]
            last = (7 - (sum(d) % 7)) % 7
            if 1 <= last <= 7:
                d.append(last)
                break
        return f"{site:03d}-{''.join(map(str, d))}", "Win95 Retail", 30.0

    day = secrets.randbelow(366) + 1
    year = secrets.choice([95, 96, 97, 98, 99, 0, 1, 2, 3])
    while True:
        d = [0, 0] + [secrets.randbelow(10) for _ in range(4)]
        last = (7 - (sum(d) % 7)) % 7
        if 1 <= last <= 7:
            d.append(last)
            break
    tail = f"{secrets.randbelow(100000):05d}"
    return f"{day:03d}{year:02d}-OEM-{''.join(map(str, d))}-{tail}", "Win95 OEM", 32.0


def gen_emoji(state: Dict[str, Any]) -> Tuple[str, str, float]:
    pool = "💀👽👾🤖🎃🤬🤡👺👹💩🔥🔪🩸💣🦠🪓🧿🔮"
    length = max(4, min(64, state.get("pwd_len", 16)))
    res = "".join(secrets.choice(pool) for _ in range(length))
    return res, "Cursed Emoji", length * 2.0

ENGINE_FUNCS: List[Callable[[Dict[str, Any]], Tuple[str, str, float]]] = [
    gen_password, gen_passphrase, gen_pin, gen_network, gen_uuid, gen_mask, gen_custom_key, gen_win_modern, gen_win_classic, gen_win95_retro, gen_emoji
]

