"""Check for mismatched CSS braces in theme.py style blocks."""
import re, sys

with open('styles/theme.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find triple-quoted CSS string blocks
in_css = False
css_start = None
depth = 0
problems = []

for i, line in enumerate(lines, 1):
    stripped = line.strip()
    
    # Track triple-quoted strings that look like CSS
    if '"""' in stripped or "'''" in stripped:
        quotes = stripped.count('"""') + stripped.count("'''")
        if quotes == 1:
            if not in_css:
                in_css = True
                css_start = i
                depth = 0
            else:
                in_css = False
                if depth != 0:
                    problems.append(f"CSS block starting at line {css_start} ends at line {i} with brace depth={depth}")
                css_start = None
        continue
    
    if not in_css:
        continue
    
    # Count braces (skip f-string expressions like {var})
    # Simple approach: count all { and } 
    opens = line.count('{')
    closes = line.count('}')
    old_depth = depth
    depth += opens - closes
    
    if depth < 0:
        problems.append(f"Line {i}: Extra closing brace (depth went to {depth}): {stripped[:100]}")
        depth = 0

if problems:
    print("PROBLEMS FOUND:")
    for p in problems:
        print(f"  {p}")
else:
    print("No brace mismatch issues found in CSS blocks.")

# Also check for specific corruption patterns
print("\n--- Checking corruption patterns ---")
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    # Line starting with CSS value instead of selector
    if stripped.startswith('linear-gradient(') and not any(stripped.startswith(x) for x in ['/*', '.', '#', '[', '@', '"', "'"]):
        print(f"Line {i}: Orphaned value (no selector): {stripped[:80]}")
    # Broken box-shadow with stray ", inset"
    if ', inset 0 1px 0 rgba(255,255,255' in stripped and stripped.startswith(', inset'):
        print(f"Line {i}: Stray inset shadow fragment: {stripped[:80]}")
    # Unclosed parenthesis at end of line
    if stripped.endswith('(') or (stripped.count('(') > stripped.count(')') and not stripped.endswith(',')):
        if 'def ' not in stripped and 'if ' not in stripped and 'for ' not in stripped and 'return' not in stripped and '#' not in stripped and 'f"' not in stripped and "f'" not in stripped:
            # Only flag if it looks like a CSS property
            if any(x in stripped for x in ['box-shadow', 'background', 'border', 'linear-gradient', 'rgba']):
                print(f"Line {i}: Possible unclosed paren: {stripped[:100]}")

print("\nDone.")
