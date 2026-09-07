import re
with open('constants.py', 'r') as f:
    c = f.read()

new_css = '''CSS_DATA = b"""
.key-display {
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 1.6rem;
    font-weight: 900;
    letter-spacing: 0.1em;
    color: #ff2a5f;
    background: rgba(255, 42, 95, 0.08);
    border: 1px solid rgba(255, 42, 95, 0.3);
    border-radius: 12px;
    padding: 24px;
    text-shadow: 0 0 8px rgba(255, 42, 95, 0.4);
}
.badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 800;
    padding: 4px 8px;
    border-radius: 6px;
    text-transform: lowercase;
}
.badge-blue   { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.badge-green  { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.badge-amber  { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.badge-red    { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.badge-purple { background: rgba(168, 85, 247, 0.15); color: #c084fc; }
.badge-cyan   { background: rgba(6, 182, 212, 0.15); color: #22d3ee; }
.dim-label    { opacity: 0.6; font-family: 'JetBrains Mono', monospace; text-transform: lowercase; }
.danger-label { color: #ff2a5f; font-weight: 900; text-transform: lowercase; }
button {
    text-transform: lowercase;
    font-weight: bold;
}
"""'''

c = re.sub(r'CSS_DATA = b""".*?"""', new_css, c, flags=re.DOTALL)
with open('constants.py', 'w') as f:
    f.write(c)
