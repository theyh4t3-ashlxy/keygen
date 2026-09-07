with open('app.py', 'r') as f:
    text = f.read()

bad_snippet = """            self._last_activity = time.time()
        self.bad_auth_count = 0
        self._live_accent = None
            if not self._auto_lock_tmr:"""
good_snippet = """            self._last_activity = time.time()
            if not self._auto_lock_tmr:"""

text = text.replace(bad_snippet, good_snippet)
with open('app.py', 'w') as f:
    f.write(text)
