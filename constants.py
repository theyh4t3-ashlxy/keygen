import os
import logging
import string
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib

APP_NAME = "vaultforge // unhinged"
APP_VERSION = "5.0"

ALPHA_B24 = "BCDFGHJKMPQRTVWXY2346789"
ALPHA_B25 = "BCDFGHJKMNPQRTVWXY2346789"
AMBIGUOUS = "Il1O0|"
PBKDF2_ITERATIONS = 600_000
AUTO_LOCK_POLL_SECONDS = 15

WORDLIST = (
    "absurd", "acid", "alien", "amber", "anchor", "arcade", "arrow", "atomic", "bandit", "beacon",
    "binary", "blaze", "bullet", "bypass", "cactus", "carbon", "cipher", "cobalt", "cosmic", "crater",
    "crypto", "cypher", "dagger", "danger", "diesel", "dragon", "dynamo", "echo", "eclipse", "engine",
    "falcon", "filter", "flame", "fossil", "fusion", "galaxy", "ghost", "glitch", "gravity", "hazard",
    "helium", "horizon", "hybrid", "hyper", "impact", "inferno", "iron", "jaguar", "joker", "jungle",
    "karma", "kinetic", "krypton", "laser", "legacy", "liquid", "lunar", "magma", "matrix", "meteor",
    "mutant", "nebula", "neon", "nexus", "ninja", "nitro", "nuclear", "obsidian", "omega", "orbit",
    "outlaw", "oxygen", "phantom", "phoenix", "pixel", "plasma", "poison", "pulsar", "quantum", "radar",
    "radium", "raptor", "rebel", "relic", "rocket", "rogue", "savage", "shadow", "signal", "silver",
    "sniper", "solar", "specter", "static", "stealth", "strike", "syntax", "target", "titan", "toxic",
    "turbo", "ultra", "vacuum", "vapor", "vector", "velocity", "venom", "viper", "virus", "vortex",
    "vulcan", "warp", "weapon", "wraith", "xenon", "zenith", "zero", "zombie"
)

DATA_DIR      = GLib.get_user_data_dir()
CONF_DIR      = GLib.get_user_config_dir()
LOG_FILE      = os.path.join(DATA_DIR, "vaultforge.log")
CONFIG_PATH   = os.path.join(CONF_DIR, "vaultforge_settings.enc")
DEFAULT_VAULT = os.path.join(DATA_DIR, "vaultforge_db.dat")

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ENGINES = [
    "pure keyboard mash",
    "word salad",
    "smooth brain numbers",
    "skid network shit",
    "soulless hex tokens",
    "custom regex nightmare",
    "weird blocky keys",
    "bill gates tax (modern)",
    "bill gates tax (boomer)",
    "ancient boomer tax",
    "unhinged emoji soup",
]

PALETTES = [
    ("custom hex", ""),
    ("synthwave neon", "#ff2a5f"),
    ("matrix terminal", "#00ff66"),
    ("cyber cyan", "#00f0ff"),
    ("dracula violet", "#bd93f9"),
    ("nord ice", "#88c0d0"),
    ("monokai gold", "#e6db74"),
    ("toxic acid", "#a6e22e"),
    ("blood moon", "#ff3333"),
    ("monochrome hacker", "#d4d4d4"),
]

TYPE_FILTERS = [
    "all the garbage",
    "favorites ⭐",
    "passwords",
    "passphrases",
    "pins &amp; passcodes",
    "stolen licenses",
    "api tokens",
    "network configs",
    "custom blocks",
    "masked shit",
]

def get_css(accent, glow, font, radius):
    try:
        accent = accent.strip()
        if len(accent) == 4:
            r, g, b = tuple(int(accent[i]*2, 16) for i in (1, 2, 3))
        else:
            r, g, b = tuple(int(accent.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    except:
        r, g, b = 255, 42, 95
        accent = "#ff2a5f"
        
    return f"""
    .key-display {{
        font-family: '{font}', monospace;
        font-size: 1.6rem;
        font-weight: 900;
        letter-spacing: 0.1em;
        color: {accent};
        background: rgba({r}, {g}, {b}, 0.08);
        border: 1px solid rgba({r}, {g}, {b}, 0.3);
        border-radius: {radius}px;
        padding: 24px;
        text-shadow: 0 0 {glow}px rgba({r}, {g}, {b}, 0.4);
    }}
    .badge {{
        font-family: '{font}', monospace;
        font-size: 0.75rem;
        font-weight: 800;
        padding: 4px 8px;
        border-radius: {max(0, radius-6)}px;
        text-transform: lowercase;
    }}
    .badge-blue   {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.5); }}
    .badge-green  {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.5); }}
    .badge-amber  {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.5); }}
    .badge-red    {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.5); }}
    .badge-purple {{ background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.5); }}
    .badge-cyan   {{ background: rgba(6, 182, 212, 0.15); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.5); }}
    .badge-gold   {{ background: rgba(234, 179, 8, 0.2); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.6); }}
    .dim-label    {{ opacity: 0.65; font-family: '{font}', monospace; text-transform: lowercase; font-size: 0.85rem; }}
    .crack-label  {{ opacity: 0.85; font-family: '{font}', monospace; text-transform: lowercase; font-size: 0.8rem; color: {accent}; }}
    .danger-label {{ color: {accent}; font-weight: 900; text-transform: lowercase; }}
    .fav-star     {{ color: #facc15; }}
    .bulk-mono    {{ font-family: '{font}', monospace; font-size: 0.9rem; }}
    button {{
        text-transform: lowercase;
        font-weight: bold;
        border-radius: {max(0, radius-4)}px;
    }}
    """.encode('utf-8')



