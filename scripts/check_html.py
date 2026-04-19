"""Temporary HTML tag balance checker for auth_gate.py"""
import re

with open("utils/auth_gate.py", "r", encoding="utf-8") as f:
    content = f.read()

# Extract HTML from triple-quoted strings in st.markdown calls
blocks = re.findall(r'st\.markdown\s*\(\s*[f]?"""(.*?)"""', content, re.DOTALL)
all_html = "\n".join(blocks)

# Tag balance
print("=== TAG BALANCE ===")
for tag in ["div", "span", "ul", "li", "p", "h2", "h3", "h4", "table", "tr", "td", "th",
            "details", "summary", "a", "strong", "em", "thead", "tbody", "section"]:
    opens = len(re.findall(rf"<{tag}[\s>/]", all_html))
    closes = len(re.findall(rf"</{tag}>", all_html))
    if opens != closes:
        print(f"  MISMATCH <{tag}>: {opens} opens vs {closes} closes (diff {opens - closes})")

# Track div depth line-by-line to find where imbalance occurs
print("\n=== DIV DEPTH TRACE (per block) ===")
for i, block in enumerate(blocks):
    lines = block.split("\n")
    depth = 0
    for j, line in enumerate(lines):
        opens = len(re.findall(r"<div[\s>]", line))
        closes = len(re.findall(r"</div>", line))
        depth += opens - closes
        if depth < 0:
            print(f"  Block {i}, line {j}: depth went NEGATIVE ({depth}): {line.strip()[:90]}")
    if depth != 0:
        print(f"  Block {i} ends with depth={depth} (unclosed divs)")

# Check for unclosed quotes in attributes
print("\n=== UNCLOSED ATTRIBUTES ===")
for i, block in enumerate(blocks):
    lines = block.split("\n")
    for j, line in enumerate(lines):
        # Count quotes in tag contexts
        in_tag = False
        for m in re.finditer(r'<[^/!][^>]*$', line):
            print(f"  Block {i}, line {j}: possible unclosed tag: {line.strip()[:90]}")

print("\nDone.")
