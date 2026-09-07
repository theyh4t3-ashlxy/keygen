import os
import re

os.chdir('/home/ashley/Projects/keygen')

with open('constants.py', 'r') as f:
    c = f.read()

c = c.replace('APP_NAME = "VaultForge"', 'APP_NAME = "vaultforge // unhinged"')
c = re.sub(r'ENGINES = \[.*?\]', 'ENGINES = [\n    "pure keyboard mash",\n    "word salad",\n    "smooth brain numbers",\n    "skid network shit",\n    "soulless hex tokens",\n    "custom regex nightmare",\n    "weird blocky keys",\n    "bill gates tax (modern)",\n    "bill gates tax (boomer)",\n    "ancient boomer tax",\n]', c, flags=re.DOTALL)
c = re.sub(r'TYPE_FILTERS = \[.*?\]', 'TYPE_FILTERS = [\n    "all the garbage",\n    "passwords",\n    "passphrases",\n    "pins & passcodes",\n    "stolen licenses",\n    "api tokens",\n    "network configs",\n    "custom blocks",\n    "masked shit",\n]', c, flags=re.DOTALL)

new_css = '''CSS_DATA = b"""
window, dialog {
    background-color: #09090b;
}
.key-display {
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 1.6rem;
    font-weight: 900;
    letter-spacing: 0.1em;
    color: #ff003c;
    background: #180006;
    border: 2px solid #ff003c;
    border-radius: 0px;
    padding: 20px;
    box-shadow: 0 0 10px rgba(255, 0, 60, 0.2);
    text-shadow: 0 0 5px rgba(255, 0, 60, 0.4);
}
.badge {
    font-family: monospace;
    font-size: 0.7rem;
    font-weight: 900;
    padding: 4px 10px;
    border-radius: 0px;
    letter-spacing: 0.05em;
    text-transform: lowercase;
}
.badge-blue   { background: #000; color: #3b82f6; border: 1px solid #3b82f6; }
.badge-green  { background: #000; color: #10b981; border: 1px solid #10b981; }
.badge-amber  { background: #000; color: #f59e0b; border: 1px solid #f59e0b; }
.badge-red    { background: #000; color: #ef4444; border: 1px solid #ef4444; }
.badge-purple { background: #000; color: #a855f7; border: 1px solid #a855f7; }
.badge-cyan   { background: #000; color: #06b6d4; border: 1px solid #06b6d4; }
.dim-label    { opacity: 0.6; font-family: monospace; font-size: 0.9rem; text-transform: lowercase; }
.danger-label { color: #ff003c; font-weight: 900; text-transform: lowercase; }
button {
    text-transform: lowercase;
    font-weight: 900;
    border-radius: 0px;
}
"""'''
c = re.sub(r'CSS_DATA = b""".*?"""', new_css, c, flags=re.DOTALL)

with open('constants.py', 'w') as f:
    f.write(c)

with open('app.py', 'r') as f:
    a = f.read()

replacements = {
    '"Algorithm Selection"': '"choose your poison"',
    '"Generation Engine"': '"chaos engine"',
    '"Configuration"': '"knobs & dials"',
    '"Generated Payload"': '"the loot"',
    '"Vault Storage"': '"the stash"',
    '"Label (Identifier)"': '"what is this trash?"',
    '"Tag or Category"': '"useless tag"',
    '"Commit to Vault"': '"shove it in"',
    '"Regenerate"': '"reroll"',
    '"Copy"': '"yoink"',
    '"Strength: N/A"': '"strength: literally nothing"',
    '"Strength: Invalid"': '"strength: absolutely garbage"',
    '"Strength: Weak (': '"strength: wet paper towel ("',
    '"Strength: Fair (': '"strength: mid ("',
    '"Strength: Good (': '"strength: pretty beefy ("',
    '"Strength: Excellent (': '"strength: gigachad ("',
    '"Missing Cryptography Engine"': '"no crypto module? really?"',
    '"Run: pip install cryptography"': '"run pip install cryptography you absolute melon"',
    '"Lock Vault"': '"lock this shit down"',
    '"Vault automatically locked due to inactivity."': '"you were afk so i locked it. yw."',
    '"Encrypted Datastore"': '"the vault of secrets"',
    '"Authenticate with your master key"': '"type the magic word or get out"',
    '"Master Password"': '"magic word"',
    '"Unlock Vault"': '"break in"',
    '"Vault decrypted."': '"we are in."',
    '"Authentication failed."': '"wrong password bozo."',
    '"Filter and Search"': '"find your garbage"',
    '"Search secret records..."': '"search for shit..."',
    '"Tag..."': '"tag..."',
    '"Records"': '"the hoard"',
    '"Vault Empty"': '"literally nothing here"',
    '"Generated items you save will show up here."': '"generate some shit first."',
    '"Reveal"': '"peek"',
    '"Delete"': '"yeet"',
    '"Record deleted."': '"deleted. it is gone."',
    '"Copied to clipboard."': '"yoinked to clipboard."',
    '"Datastore Security"': '"paranoia settings"',
    '"Auto-Lock Timeout"': '"afk lock timer"',
    '"Minutes of inactivity before vault re-locks"': '"how long before i lock you out"',
    '"Datastore Path"': '"where the bodies are buried"',
    '"Change Path"': '"move the stash"',
    '"Destroy Vault"': '"nuke it from orbit"',
    '"Permanently delete the encrypted datastore"': '"press this to destroy everything forever"',
    '"Shred"': '"yeet everything"',
    '"Vault locked."': '"locked. safely hidden from the feds."',
    '"Datastore wiped from disk."': '"nuked. the feds will find nothing."',
    '"User Interface"': '"eye candy"',
    '"Rolling Decipher Animation"': '"schizo matrix animation"',
    '"Visual effect during payload generation"': '"makes you feel like a hacker"',
    '"Engine Core"': '"the guts"',
    '"Generator"': '"forge"',
    '"Vault"': '"stash"',
    '"Settings"': '"under the hood"',
    '"Length"': '"how long?"',
    '"Uppercase Letters (A-Z)"': '"uppercase (A-Z)"',
    '"Lowercase Letters (a-z)"': '"lowercase (a-z)"',
    '"Numbers (0-9)"': '"numbers (0-9)"',
    '"Special Symbols (!@#$)"': '"weird symbols (!@#$)"',
    '"Exclude Ambiguous (l, 1, O, 0, |)"': '"no ambiguous shit (1, l, 0, O)"',
    '"Exclude Characters"': '"ban these chars"',
    '"Word Count"': '"how many words?"',
    '"Delimiter"': '"separator"',
    '"Capitalize Words"': '"make em capital"',
    '"Append Numbers"': '"slap a number on the end"',
    '"Format Preset"': '"preset flavor"',
    '"Custom Length"': '"custom length"',
    '"Hardware and Protocol"': '"skid type"',
    '"Token Format"': '"token flavor"',
    '"Pattern Syntax"': '"regex nightmare string"',
    '"Mask Guide"': '"wtf do these mean"',
    '"Allowed Charset"': '"allowed chars"',
    '"Groups"': '"how many blocks"',
    '"Chars per Group"': '"chars per block"',
    '"Block Separator"': '"block separator"',
    '"Edition Archetype"': '"windows flavor"',
    '"Distribution Channel"': '"how did you pirate it"',
    '"Key Format"': '"key shape"',
    '"Generate a valid secret first."': '"generate some shit first, idiot."',
    '"Unlock vault to store records."': '"unlock the stash first."',
    '"Stored in encrypted datastore."': '"shoved into the vault."',
    '"Select Encrypted Datastore"': '"pick a datastore file"',
    '"Datastore (*.dat)"': '"datastore (*.dat)"'
}

for k, v in replacements.items():
    a = a.replace(k, v)

old_filter = """        type_match = True
        if type_choice == "Password": type_match = item_type == "Password"
        elif type_choice == "Passphrase": type_match = item_type == "Passphrase"
        elif type_choice == "PIN and Passcode": type_match = item_type in ("PIN", "Passcode")
        elif type_choice == "Licenses": type_match = "Win" in item_type or "License" in item_type
        elif type_choice == "Auth Tokens": type_match = "Token" in item_type or "UUID" in item_type or "Secret" in item_type or "Key" in item_type
        elif type_choice == "Hardware and Network": type_match = item_type in ("Hardware", "Network", "Hardware MAC", "IPv6 ULA", "WPA PSK", "WireGuard Secret")
        elif type_choice == "Custom Block": type_match = "Custom" in item_type
        elif type_choice == "Masked": type_match = "Masked" in item_type"""

new_filter = """        type_match = True
        if type_choice == "passwords": type_match = item_type == "Password"
        elif type_choice == "passphrases": type_match = item_type == "Passphrase"
        elif type_choice == "pins & passcodes": type_match = item_type in ("PIN", "Passcode")
        elif type_choice == "stolen licenses": type_match = "Win" in item_type or "License" in item_type
        elif type_choice == "api tokens": type_match = "Token" in item_type or "UUID" in item_type or "Secret" in item_type or "Key" in item_type
        elif type_choice == "network configs": type_match = item_type in ("Hardware", "Network", "Hardware MAC", "IPv6 ULA", "WPA PSK", "WireGuard Secret")
        elif type_choice == "custom blocks": type_match = "Custom" in item_type
        elif type_choice == "masked shit": type_match = "Masked" in item_type"""

a = a.replace(old_filter, new_filter)

a = a.replace('["4-Digit PIN", "6-Digit PIN", "Custom Numeric Length", "Custom Alphanumeric"]', '["4-digit pin", "6-digit pin", "custom numbers", "custom everything"]')
a = a.replace('["MAC Address", "IPv6 Unique Local (ULA)", "WPA2/3 Hex Key (256-bit)", "WireGuard Key"]', '["mac address", "ipv6 ula", "wpa2/3 hex key", "wireguard key"]')
a = a.replace('["UUIDv4 Standard", "Mock API Secret", "Hex Secret (256-bit)"]', '["uuidv4 standard", "fake api secret", "hex secret"]')
a = a.replace('["Standard", "N Edition", "Server"]', '["standard", "n edition", "server"]')
a = a.replace('["Retail / MSDN", "OEM", "Volume / KMS"]', '["retail / msdn", "oem", "volume / kms"]')
a = a.replace('["Retail (10-Digit)", "OEM (23-Digit)"]', '["retail (10-digit)", "oem (23-digit)"]')

a = a.replace('def _on_generate(self, _btn) -> None:', 'def _on_generate(self, _btn) -> None:\\n        # if this breaks again im quitting')
a = a.replace('def _action_nuke(self, _btn) -> None:', 'def _action_nuke(self, _btn) -> None:\\n        # fixing this garbage layout with fire')

with open('app.py', 'w') as f:
    f.write(a)
