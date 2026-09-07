import os
import re

os.chdir('/home/ashley/Projects/keygen')

with open('constants.py', 'r') as f:
    c = f.read()

css_func = '''def get_css(accent, glow, font, radius):
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
    .dim-label    {{ opacity: 0.6; font-family: '{font}', monospace; text-transform: lowercase; }}
    .danger-label {{ color: {accent}; font-weight: 900; text-transform: lowercase; }}
    button {{
        text-transform: lowercase;
        font-weight: bold;
        border-radius: {max(0, radius-4)}px;
    }}
    """.encode('utf-8')
'''

c = re.sub(r'CSS_DATA = b""".*?"""', css_func, c, flags=re.DOTALL)
with open('constants.py', 'w') as f:
    f.write(c)


with open('crypto.py', 'r') as f:
    crypto = f.read()
new_defaults = '"legacy_mode": 0,\n        "ui_theme": 0, "ui_accent": "#ff2a5f", "ui_glow": 8, "ui_font": 0, "ui_radius": 12,'
crypto = crypto.replace('"legacy_mode": 0,', new_defaults)
with open('crypto.py', 'w') as f:
    f.write(crypto)


with open('app.py', 'r') as f:
    a = f.read()

a = a.replace('CSS_DATA, ENGINES', 'get_css, ENGINES')

old_activate = """    def do_activate(self) -> None:
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS_DATA)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)"""

new_activate = """    def do_activate(self) -> None:
        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._apply_theme()"""
a = a.replace(old_activate, new_activate)

apply_theme_code = """
    def _apply_theme(self) -> None:
        if not hasattr(self, 'css_provider'): return
        theme_map = {0: Adw.ColorScheme.FORCE_DARK, 1: Adw.ColorScheme.FORCE_LIGHT, 2: Adw.ColorScheme.DEFAULT}
        if self.vault:
            theme_idx = self.vault.state.get("ui_theme", 0)
            font_idx = self.vault.state.get("ui_font", 0)
            accent = self.vault.state.get("ui_accent", "#ff2a5f")
            glow = self.vault.state.get("ui_glow", 8)
            rad = self.vault.state.get("ui_radius", 12)
        else:
            theme_idx, font_idx, accent, glow, rad = 0, 0, "#ff2a5f", 8, 12

        Adw.StyleManager.get_default().set_color_scheme(theme_map.get(theme_idx, Adw.ColorScheme.FORCE_DARK))
        fonts = ["JetBrains Mono", "Fira Code", "Cascadia Code", "monospace", "Comic Sans MS"]
        font = fonts[font_idx] if 0 <= font_idx < len(fonts) else "monospace"
        
        try:
            self.css_provider.load_from_data(get_css(accent, glow, font, rad))
        except Exception as e:
            self.css_provider.load_from_data(get_css("#ff2a5f", 8, "monospace", 12))
"""
a = a.replace('    def _check_auto_lock(self) -> bool:', apply_theme_code + '\n    def _check_auto_lock(self) -> bool:')

aesthetics_ui = """
        g_vibes = Adw.PreferencesGroup(title="aesthetics & vibes")
        
        row_theme = Adw.ComboRow(title="theme flavor", model=Gtk.StringList.new(["dark mode (based)", "light mode (flashbang)", "system default"]))
        row_theme.set_selected(self.vault.state.get("ui_theme", 0))
        row_theme.connect("notify::selected", lambda o, _: self.vault.set("ui_theme", o.get_selected()) or self._apply_theme())
        g_vibes.add(row_theme)

        row_font = Adw.ComboRow(title="hacker font", model=Gtk.StringList.new(["jetbrains mono", "fira code", "cascadia code", "generic monospace", "comic sans (unhinged)"]))
        row_font.set_selected(self.vault.state.get("ui_font", 0))
        row_font.connect("notify::selected", lambda o, _: self.vault.set("ui_font", o.get_selected()) or self._apply_theme())
        g_vibes.add(row_font)

        row_accent = Adw.EntryRow(title="accent color (hex)")
        row_accent.set_text(self.vault.state.get("ui_accent", "#ff2a5f"))
        row_accent.connect("changed", lambda e: self.vault.set("ui_accent", e.get_text()) or self._apply_theme())
        g_vibes.add(row_accent)

        row_glow = Adw.ActionRow(title="neon glow intensity", subtitle="crank it up so it hurts")
        spin_glow = Gtk.SpinButton.new_with_range(0, 50, 1)
        spin_glow.set_value(self.vault.state.get("ui_glow", 8))
        spin_glow.set_valign(Gtk.Align.CENTER)
        spin_glow.connect("value-changed", lambda s: self.vault.set("ui_glow", int(s.get_value())) or self._apply_theme())
        row_glow.add_suffix(spin_glow)
        g_vibes.add(row_glow)

        row_rad = Adw.ActionRow(title="border radius", subtitle="0px = edgy, 12px = standard, 24px = bubble")
        spin_rad = Gtk.SpinButton.new_with_range(0, 40, 1)
        spin_rad.set_value(self.vault.state.get("ui_radius", 12))
        spin_rad.set_valign(Gtk.Align.CENTER)
        spin_rad.connect("value-changed", lambda s: self.vault.set("ui_radius", int(s.get_value())) or self._apply_theme())
        row_rad.add_suffix(spin_rad)
        g_vibes.add(row_rad)

        page.add(g_vibes)
"""
a = a.replace('        g_app = Adw.PreferencesGroup(title="eye candy")', aesthetics_ui + '\n        g_app = Adw.PreferencesGroup(title="eye candy")')

with open('app.py', 'w') as f:
    f.write(a)

