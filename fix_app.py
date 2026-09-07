with open('app.py', 'r') as f:
    text = f.read()

bad_snippet = """self._apply_theme()
        if self.vault and self.vault.state.get("rgb_mode", False):
            self._on_rgb_toggled(None, True)"""
text = text.replace(bad_snippet, "self._apply_theme()")
with open('app.py', 'w') as f:
    f.write(text)
