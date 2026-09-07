with open('app.py', 'r') as f:
    text = f.read()
text = text.replace('f"strength: wet paper towel ("', 'f"strength: wet paper towel (')
text = text.replace('f"strength: mid ("', 'f"strength: mid (')
text = text.replace('f"strength: pretty beefy ("', 'f"strength: pretty beefy (')
text = text.replace('f"strength: gigachad ("', 'f"strength: gigachad (')
with open('app.py', 'w') as f:
    f.write(text)
