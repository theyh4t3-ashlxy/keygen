import os
import re

with open('/home/ashley/Projects/keygen/keygen.py.bak', 'r') as f:
    lines = f.readlines()

def write_lines(filename, start, end, imports=""):
    with open(f"/home/ashley/Projects/keygen/{filename}", 'w') as f:
        f.write(imports)
        f.writelines(lines[start:end])

# constants.py
imports_const = """import os
import string
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib

"""
write_lines('constants.py', 33, 119, imports_const)

# engines.py
imports_eng = """import math
import string
import secrets
import uuid
from typing import Dict, Any, Tuple, List, Callable
from .constants import ALPHA_B24, ALPHA_B25, AMBIGUOUS, WORDLIST

"""
write_lines('engines.py', 136, 281, imports_eng)

# crypto.py
imports_crypto = """import os
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

from .constants import CONFIG_PATH, DEFAULT_VAULT, PBKDF2_ITERATIONS, ALPHA_B24, LOG_FILE

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

"""
write_lines('crypto.py', 120, 136, imports_crypto)
with open("/home/ashley/Projects/keygen/crypto.py", 'a') as f:
    f.writelines(lines[281:393])

# app.py
imports_app = """import sys
import time
import os
import threading
import secrets
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib, Gio

from .constants import APP_NAME, APP_VERSION, CSS_DATA, ENGINES, TYPE_FILTERS, AUTO_LOCK_POLL_SECONDS, DEFAULT_VAULT, CRYPTO_ERR, HAS_CRYPTO
from .engines import ENGINE_FUNCS
from .crypto import wipe_string, format_relative_time

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from .crypto import VaultManager
except ImportError:
    VaultManager = None

"""
write_lines('app.py', 393, 982, imports_app)

# __main__.py
with open("/home/ashley/Projects/keygen/__main__.py", 'w') as f:
    f.write('''import sys
from .app import VaultForgeUI

def main():
    app = VaultForgeUI()
    sys.exit(app.run(sys.argv))

if __name__ == "__main__":
    main()
''')

# __init__.py
with open("/home/ashley/Projects/keygen/__init__.py", 'w') as f:
    f.write('')
