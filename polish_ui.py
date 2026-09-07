import re
with open('app.py', 'r') as f:
    text = f.read()

replacements = {
    'g_vibes.add(row_theme)': 'row_theme.add_prefix(Gtk.Image.new_from_icon_name("format-text-color-symbolic"))\n        g_vibes.add(row_theme)',
    'g_vibes.add(row_font)': 'row_font.add_prefix(Gtk.Image.new_from_icon_name("preferences-desktop-font-symbolic"))\n        g_vibes.add(row_font)',
    'g_vibes.add(row_accent)': 'row_accent.add_prefix(Gtk.Image.new_from_icon_name("color-select-symbolic"))\n        g_vibes.add(row_accent)',
    'g_vibes.add(row_rgb)': 'row_rgb.add_prefix(Gtk.Image.new_from_icon_name("video-display-symbolic"))\n        g_vibes.add(row_rgb)',
    'g_vibes.add(row_opacity)': 'row_opacity.add_prefix(Gtk.Image.new_from_icon_name("weather-clear-symbolic"))\n        g_vibes.add(row_opacity)',
    'g_vibes.add(row_drunk)': 'row_drunk.add_prefix(Gtk.Image.new_from_icon_name("face-sick-symbolic"))\n        g_vibes.add(row_drunk)',
    
    'g_sec.add(row_clip)': 'row_clip.add_prefix(Gtk.Image.new_from_icon_name("edit-clear-all-symbolic"))\n        g_sec.add(row_clip)',
    'g_sec.add(row_panic)': 'row_panic.add_prefix(Gtk.Image.new_from_icon_name("system-shutdown-symbolic"))\n        g_sec.add(row_panic)',
    
    'g_app.add(row_anim_speed)': 'row_anim_speed.add_prefix(Gtk.Image.new_from_icon_name("preferences-system-time-symbolic"))\n        g_app.add(row_anim_speed)',
    'g_app.add(row_toxic)': 'row_toxic.add_prefix(Gtk.Image.new_from_icon_name("face-smirk-symbolic"))\n        g_app.add(row_toxic)',
    
    'g_eng.add(row_eng)': 'row_eng.add_prefix(Gtk.Image.new_from_icon_name("applications-engineering-symbolic"))\n        g_eng.add(row_eng)'
}

for k, v in replacements.items():
    text = text.replace(k, v)

# Also let's make the "shove it in" and "reroll" buttons have icons
text = text.replace('self.btn_gen = Gtk.Button(label="reroll", css_classes=["suggested-action", "pill"])', 'self.btn_gen = Gtk.Button(label="reroll", icon_name="view-refresh-symbolic", css_classes=["suggested-action", "pill"])')
text = text.replace('self.btn_save = Gtk.Button(label="shove it in", css_classes=["pill"])', 'self.btn_save = Gtk.Button(label="shove it in", icon_name="document-save-symbolic", css_classes=["pill"])')
text = text.replace('self.btn_copy = Gtk.Button(label="yoink", css_classes=["pill"])', 'self.btn_copy = Gtk.Button(label="yoink", icon_name="edit-copy-symbolic", css_classes=["pill"])')

# And lock button in the header bar instead of nothing
header_code = """
        # Let's add a lock button to the headerbar
        self.btn_header_lock = Gtk.Button(icon_name="system-lock-screen-symbolic", tooltip_text="lock vault")
        self.btn_header_lock.connect("clicked", self._action_lock)
"""

with open('app.py', 'w') as f:
    f.write(text)

