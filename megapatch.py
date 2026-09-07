import os

os.chdir('/home/ashley/Projects/keygen')

# 1. Update constants.py
with open('constants.py', 'r') as f:
    c = f.read()
c = c.replace('"ancient boomer tax",\n]', '"ancient boomer tax",\n    "unhinged emoji soup",\n]')
with open('constants.py', 'w') as f:
    f.write(c)

# 2. Update engines.py
with open('engines.py', 'r') as f:
    e = f.read()
emoji_code = """
def gen_emoji(state: Dict[str, Any]) -> Tuple[str, str, float]:
    pool = "💀👽👾🤖🎃🤬🤡👺👹💩🔥🔪🩸💣🦠🪓🧿🔮"
    length = max(4, min(64, state.get("pwd_len", 16)))
    res = "".join(secrets.choice(pool) for _ in range(length))
    return res, "Cursed Emoji", length * 2.0
"""
e = e.replace('ENGINE_FUNCS: List[Callable', emoji_code + '\nENGINE_FUNCS: List[Callable')
e = e.replace('gen_win95_retro\n]', 'gen_win95_retro, gen_emoji\n]')
with open('engines.py', 'w') as f:
    f.write(e)

# 3. Update crypto.py
with open('crypto.py', 'r') as f:
    cr = f.read()
cr = cr.replace('"ui_theme": 0,', '"ui_opacity": 1.0, "clipboard_ttl": 0, "anim_speed": 6, "drunk_mode": False, "ui_theme": 0,')
with open('crypto.py', 'w') as f:
    f.write(cr)

# 4. Update app.py
with open('app.py', 'r') as f:
    a = f.read()

drunk_funcs = """
    def _on_drunk_toggled(self, sw, state):
        if self.vault: self.vault.set("drunk_mode", state)
        if state:
            GLib.timeout_add(50, self._drunk_tick)
        else:
            self.lbl_output.set_margin_start(0)
            self.lbl_output.set_margin_top(0)
        return False

    def _drunk_tick(self):
        if not getattr(self, 'vault', None) or not self.vault.state.get("drunk_mode", False):
            self.lbl_output.set_margin_start(0)
            self.lbl_output.set_margin_top(0)
            return False
        self.lbl_output.set_margin_start(random.randint(0, 20))
        self.lbl_output.set_margin_top(random.randint(0, 20))
        return True
"""
a = a.replace('    def _apply_theme(self) -> None:', drunk_funcs + '\n    def _apply_theme(self) -> None:')

op_apply = """        if hasattr(self, 'win') and getattr(self, 'vault', None):
            self.win.set_opacity(self.vault.state.get("ui_opacity", 1.0))
"""
a = a.replace('        Adw.StyleManager.get_default().set_color_scheme(', op_apply + '        Adw.StyleManager.get_default().set_color_scheme(')

a = a.replace('self.win.connect("close-request", self._on_shutdown)', 'self.win.connect("close-request", self._on_shutdown)\n        self.win.set_opacity(self.vault.state.get("ui_opacity", 1.0) if getattr(self, "vault", None) else 1.0)')

a = a.replace('self._on_rgb_toggled(None, True)', 'self._on_rgb_toggled(None, True)\n        if getattr(self, \'vault\', None) and self.vault.state.get("drunk_mode", False):\n            self._on_drunk_toggled(None, True)')


extra_vibes = """
        row_opacity = Adw.ActionRow(title="ghost mode (opacity)", subtitle="make the window transparent to hide from your boss")
        spin_op = Gtk.SpinButton.new_with_range(0.1, 1.0, 0.05)
        spin_op.set_value(self.vault.state.get("ui_opacity", 1.0))
        spin_op.set_valign(Gtk.Align.CENTER)
        spin_op.connect("value-changed", lambda s: self.vault.set("ui_opacity", s.get_value()) or self._apply_theme())
        row_opacity.add_suffix(spin_op)
        g_vibes.add(row_opacity)

        row_drunk = Adw.ActionRow(title="drunk ui mode", subtitle="the layout jiggles uncontrollably")
        sw_drunk = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.state.get("drunk_mode", False))
        sw_drunk.connect("state-set", self._on_drunk_toggled)
        row_drunk.add_suffix(sw_drunk)
        g_vibes.add(row_drunk)
"""
a = a.replace('        page.add(g_vibes)', extra_vibes + '\n        page.add(g_vibes)')

extra_sec = """
        row_clip = Adw.ActionRow(title="clipboard auto-nuke (seconds)", subtitle="0 to disable. self-destructs your clipboard.")
        spin_clip = Gtk.SpinButton.new_with_range(0, 60, 1)
        spin_clip.set_value(self.vault.state.get("clipboard_ttl", 0))
        spin_clip.set_valign(Gtk.Align.CENTER)
        spin_clip.connect("value-changed", lambda s: self.vault.set("clipboard_ttl", int(s.get_value())))
        row_clip.add_suffix(spin_clip)
        g_sec.add(row_clip)
        
        row_panic = Adw.ActionRow(title="PANIC BUTTON", subtitle="instantly locks and shreds the vault from memory")
        btn_panic = Gtk.Button(label="NUKE NOW", valign=Gtk.Align.CENTER, css_classes=["destructive-action", "pill"])
        btn_panic.connect("clicked", self._action_nuke)
        row_panic.add_suffix(btn_panic)
        g_sec.add(row_panic)
"""
a = a.replace('        g_sec.add(row_paranoid)', '        g_sec.add(row_paranoid)' + extra_sec)

extra_app = """
        row_anim_speed = Adw.ActionRow(title="schizo animation speed", subtitle="lower is faster. breaks the matrix.")
        spin_anim = Gtk.SpinButton.new_with_range(1, 50, 1)
        spin_anim.set_value(self.vault.state.get("anim_speed", 6))
        spin_anim.set_valign(Gtk.Align.CENTER)
        spin_anim.connect("value-changed", lambda s: self.vault.set("anim_speed", int(s.get_value())))
        row_anim_speed.add_suffix(spin_anim)
        g_app.add(row_anim_speed)
"""
a = a.replace('        g_app.add(row_toxic)', '        g_app.add(row_toxic)' + extra_app)

a = a.replace('self._anim_frame += max(1, len(self._anim_target) // 6)', 'speed = self.vault.state.get("anim_speed", 6)\n            self._anim_frame += max(1, len(self._anim_target) // speed)')

old_copy = """        if cb := Gdk.Display.get_default().get_clipboard():
            cb.set(txt)
            if self.vault.state.get("toxic_mode", False):
                self._toast(random.choice(["yoinked. try not to paste it in general chat.", "copied. you're gonna lose it anyway.", "stolen. hope nobody is looking.", "clipboard tainted."]))
            else:
                self._toast("yoinked to clipboard.")"""
new_copy = """        if cb := Gdk.Display.get_default().get_clipboard():
            cb.set(txt)
            ttl = self.vault.state.get("clipboard_ttl", 0)
            if ttl > 0:
                GLib.timeout_add_seconds(ttl, lambda: Gdk.Display.get_default().get_clipboard().set("") or False)
            if self.vault.state.get("toxic_mode", False):
                self._toast(random.choice(["yoinked. try not to paste it in general chat.", "copied. you're gonna lose it anyway.", "stolen. hope nobody is looking.", "clipboard tainted."]) + (f" (nuking in {ttl}s)" if ttl else ""))
            else:
                self._toast(f"yoinked to clipboard." + (f" (self-destructs in {ttl}s)" if ttl else ""))"""
a = a.replace(old_copy, new_copy)

with open('app.py', 'w') as f:
    f.write(a)
