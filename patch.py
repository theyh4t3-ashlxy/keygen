import os

os.chdir('/home/ashley/Projects/keygen')

with open('crypto.py', 'r') as f:
    c = f.read()
c = c.replace('"ui_theme": 0,', '"rgb_mode": False, "toxic_mode": False, "paranoia_mode": False, "ui_theme": 0,')
with open('crypto.py', 'w') as f:
    f.write(c)

with open('app.py', 'r') as f:
    a = f.read()

# Imports
a = a.replace('import secrets', 'import secrets\nimport random\nimport colorsys')

# __init__
a = a.replace('self._last_activity = time.time()', 'self._last_activity = time.time()\n        self.bad_auth_count = 0\n        self._live_accent = None')

# do_activate
a = a.replace('self._apply_theme()', 'self._apply_theme()\n        if self.vault and self.vault.state.get("rgb_mode", False):\n            self._on_rgb_toggled(None, True)')

# RGB functions
rgb_funcs = """
    def _on_rgb_toggled(self, sw, state):
        if self.vault: self.vault.set("rgb_mode", state)
        if state:
            self._rgb_hue = 0.0
            GLib.timeout_add(100, self._rgb_tick)
        else:
            self._live_accent = None
            self._apply_theme()
        return False

    def _rgb_tick(self):
        if not getattr(self, 'vault', None) or not self.vault.state.get("rgb_mode", False):
            return False
        self._rgb_hue = (getattr(self, '_rgb_hue', 0) + 0.05) % 1.0
        r, g, b = colorsys.hsv_to_rgb(self._rgb_hue, 1.0, 1.0)
        self._live_accent = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        self._apply_theme()
        return True
"""
a = a.replace('    def _apply_theme(self) -> None:', rgb_funcs + '\n    def _apply_theme(self) -> None:')

# _apply_theme override
a = a.replace('accent = self.vault.state.get("ui_accent", "#ff2a5f")', 'accent = getattr(self, "_live_accent", None) or self.vault.state.get("ui_accent", "#ff2a5f")')

# UI injections
rgb_ui = """
        row_rgb = Adw.ActionRow(title="rgb gamer mode", subtitle="epilepsy warning")
        sw_rgb = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.state.get("rgb_mode", False))
        sw_rgb.connect("state-set", self._on_rgb_toggled)
        row_rgb.add_suffix(sw_rgb)
        g_vibes.add(row_rgb)
"""
a = a.replace('        page.add(g_vibes)', rgb_ui + '        page.add(g_vibes)')

para_ui = """
        row_paranoid = Adw.ActionRow(title="dead man's switch", subtitle="nuke vault after 3 wrong passwords")
        sw_paranoid = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.state.get("paranoia_mode", False))
        sw_paranoid.connect("state-set", lambda _, st: self.vault.set("paranoia_mode", st) or False)
        row_paranoid.add_suffix(sw_paranoid)
        g_sec.add(row_paranoid)
"""
a = a.replace('        g_sec.add(row_nuke)', '        g_sec.add(row_nuke)' + para_ui)

toxic_ui = """
        row_toxic = Adw.ActionRow(title="toxic mode", subtitle="the app actively disrespects you")
        sw_toxic = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.state.get("toxic_mode", False))
        sw_toxic.connect("state-set", lambda _, st: self.vault.set("toxic_mode", st) or False)
        row_toxic.add_suffix(sw_toxic)
        g_app.add(row_toxic)
"""
a = a.replace('        g_app.add(row_ani)', '        g_app.add(row_ani)' + toxic_ui)

# Unlock logic
old_unlock = """            self.vault_unlock_entry.add_css_class("error")
            self._toast("wrong password bozo.")"""
new_unlock = """            self.vault_unlock_entry.add_css_class("error")
            if self.vault.state.get("paranoia_mode", False):
                self.bad_auth_count += 1
                if self.bad_auth_count >= 3:
                    self._action_nuke(None)
                    self._toast("3 strikes. VAULT NUKED. goodbye.")
                    self.bad_auth_count = 0
                    return False
            toxic_msg = random.choice(["wrong password bozo.", "do you even remember it?", "typing is hard, huh?", "skill issue."])
            self._toast(toxic_msg if self.vault.state.get("toxic_mode", False) else "wrong password bozo.")"""
a = a.replace(old_unlock, new_unlock)

# Copy logic
old_copy = """        if cb := Gdk.Display.get_default().get_clipboard():
            cb.set(txt)
            self._toast("yoinked to clipboard.")"""
new_copy = """        if cb := Gdk.Display.get_default().get_clipboard():
            cb.set(txt)
            if self.vault.state.get("toxic_mode", False):
                self._toast(random.choice(["yoinked. try not to paste it in general chat.", "copied. you're gonna lose it anyway.", "stolen. hope nobody is looking.", "clipboard tainted."]))
            else:
                self._toast("yoinked to clipboard.")"""
a = a.replace(old_copy, new_copy)

# Weak password toxic toast
old_lbl = "self.entropy_lbl.set_label(label)"
new_lbl = 'self.entropy_lbl.set_label(label)\n        if score <= 1 and self.vault.state.get("toxic_mode", False):\n            self._toast(random.choice(["are you actually going to use this trash?", "wow. very secure.", "my grandma makes better passwords."]))'
a = a.replace(old_lbl, new_lbl)

with open('app.py', 'w') as f:
    f.write(a)
