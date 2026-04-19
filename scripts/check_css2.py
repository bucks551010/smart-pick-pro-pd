"""Check for CSS corruption in player_card_renderer.py and QEG section of theme.py."""
import re

# Check player_card_renderer.py
print("=== player_card_renderer.py ===")
with open('utils/player_card_renderer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_css = False
depth = 0
css_start = 0
for i, line in enumerate(lines, 1):
    s = line.strip()
    if 'PLAYER_CARD_CSS' in s and '=' in s:
        in_css = True
        depth = 0
        css_start = i
        continue
    if in_css and ('"""' in s or "'''" in s):
        if depth != 0:
            print(f"  BRACE MISMATCH: CSS block {css_start}-{i} ends with depth={depth}")
        else:
            print(f"  CSS block {css_start}-{i}: braces OK")
        in_css = False
        continue
    if not in_css:
        continue
    opens = line.count('{')
    closes = line.count('}')
    depth += opens - closes
    if depth < 0:
        print(f"  EXTRA CLOSE at line {i}: {s[:80]}")
        depth = 0

# Check for specific patterns in theme.py that indicate corruption
print("\n=== theme.py: checking QEG prop CSS ===")
with open('styles/theme.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    s = line.strip()
    # Check for selector-value fusion (like "}8deg")
    if re.search(r'\}[a-zA-Z0-9]', s) and 'f"' not in s and "f'" not in s and '{' not in s.split('}')[0]:
        if not any(x in s for x in ['/*', '//', '#', 'def ', 'class ', 'return', 'if ', 'else']):
            print(f"  Line {i}: Possible fused selector/value: {s[:80]}")
    # Check for property without semicolon before next property
    if re.search(r'rgba\(\d+,\d+,\d+,[\d.]+\s*$', s):
        print(f"  Line {i}: Line ends inside rgba(): {s[:80]}")

print("\nDone.")
