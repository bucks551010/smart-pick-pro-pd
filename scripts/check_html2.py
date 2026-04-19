"""Deep HTML validation for auth_gate.py"""
import re
from html.parser import HTMLParser

class Validator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []
        self.line = 0

    def handle_starttag(self, tag, attrs):
        void_tags = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}
        if tag not in void_tags:
            self.stack.append((tag, self.getpos()))

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        elif self.stack:
            # Search back for matching open
            for i in range(len(self.stack)-1, -1, -1):
                if self.stack[i][0] == tag:
                    # Everything between is unclosed
                    unclosed = self.stack[i+1:]
                    for u_tag, u_pos in unclosed:
                        self.errors.append(f"Unclosed <{u_tag}> opened at line {u_pos[0]}")
                    self.stack = self.stack[:i]
                    return
            self.errors.append(f"Extra </{tag}> at line {self.getpos()[0]} with no matching open")

with open("utils/auth_gate.py", "r", encoding="utf-8") as f:
    content = f.read()

blocks = re.findall(r'st\.markdown\s*\(\s*[f]?"""(.*?)"""', content, re.DOTALL)
all_html = "\n".join(blocks)

v = Validator()
v.feed(all_html)

if v.errors:
    print(f"Found {len(v.errors)} HTML errors:")
    for e in v.errors:
        print(f"  {e}")
else:
    print("No HTML structure errors found.")

if v.stack:
    print(f"\n{len(v.stack)} tags still open at end:")
    for tag, pos in v.stack:
        print(f"  <{tag}> opened at line {pos[0]}")
else:
    print("All tags properly closed.")

# Check for common Streamlit-stripped tags
print("\n=== STREAMLIT-STRIPPED TAGS ===")
stripped = re.findall(r"<(input|button|form|textarea|select|iframe|script|object)\b", all_html)
if stripped:
    print(f"WARNING: Found tags Streamlit will strip: {stripped}")
else:
    print("No stripped tags found.")

# Check for broken entities
print("\n=== ENTITY CHECK ===")
bad_ents = re.findall(r"&[a-zA-Z0-9#]+[^;]", all_html)
# Filter out false positives
real_bad = [e for e in bad_ents if not e.endswith(";") and "&amp" not in e[:5]]
if real_bad:
    print(f"Possibly broken entities: {real_bad[:10]}")
else:
    print("Entities look OK.")

print("\nDone.")
