"""Check CSS syntax and HTML attribute issues in auth_gate.py"""
import re

with open("utils/auth_gate.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

errors = []

# Track if we're in the CSS block
in_css = False
brace_depth = 0

for i, line in enumerate(lines, 1):
    stripped = line.strip()
    
    # Check for common HTML attribute issues in HTML lines
    if '<div' in line or '<span' in line or '<td' in line or '<th' in line:
        # Unclosed quotes in attributes
        in_str = stripped.find('"""')
        if in_str == -1:  # not a Python triple-quote line
            # Count quotes in tag
            tags = re.findall(r'<[^>]+>', stripped)
            for tag in tags:
                dq = tag.count('"')
                if dq % 2 != 0:
                    errors.append(f"Line {i}: Odd number of quotes in tag: {tag[:80]}")
    
    # Check for unclosed style tags
    if '<style' in line.lower():
        style_opens = line.lower().count('<style')
        style_closes = line.lower().count('</style>')
        if style_opens > style_closes:
            # Check subsequent lines for close
            pass
    
    # Check for broken class attributes
    if 'class=' in line:
        matches = re.findall(r'class="([^"]*)"', line)
        # Check for class names with typos (double spaces, etc.)
        for m in matches:
            if '  ' in m:
                errors.append(f"Line {i}: Double space in class: '{m}'")
    
    # Check for empty href
    if 'href=""' in line:
        errors.append(f"Line {i}: Empty href attribute")
    
    # Check for unclosed inline styles
    style_matches = re.findall(r'style="([^"]*)"', line)
    for sm in style_matches:
        # Check for missing semicolons between properties
        props = sm.split(';')
        for p in props:
            p = p.strip()
            if p and ':' not in p:
                errors.append(f"Line {i}: Style property missing colon: '{p}' in style='{sm}'")

if errors:
    print(f"Found {len(errors)} issues:")
    for e in errors:
        print(f"  {e}")
else:
    print("No HTML attribute errors found.")

# Also check for duplicate CSS class definitions
print("\n=== DUPLICATE CSS SELECTORS ===")
css_block = ""
capture = False
for line in lines:
    if "_GATE_CSS" in line and '"""' in line:
        capture = True
        continue
    if capture and '"""' in line:
        break
    if capture:
        css_block += line

selectors = re.findall(r'^([.#][\w-]+(?:\s*[.#>~+][\w-]*)*)\s*\{', css_block, re.MULTILINE)
from collections import Counter
dupes = {k: v for k, v in Counter(selectors).items() if v > 1}
if dupes:
    print(f"Duplicate selectors: {dupes}")
else:
    print("No duplicate selectors.")

# Check for unclosed CSS braces
open_b = css_block.count('{')
close_b = css_block.count('}')
print(f"\nCSS braces: {{ = {open_b}, }} = {close_b}, diff = {open_b - close_b}")

print("\nDone.")
