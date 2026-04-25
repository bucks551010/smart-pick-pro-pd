"""Fix orphan line and phase numbers in Live Games page."""
import re

path = r'pages/1_\U0001f4e1_Live_Games.py'

with open(path, encoding='utf-8') as f:
    content = f.read()

# Remove orphan line left from multi-replace
# The orphan looks like: `3 — {len(_oc_games)} game(s) loaded. Loading player data…")`
orphan = '3 \u2014 {len(_oc_games)} game(s) loaded. Loading player data\u2026")\n'
content = content.replace(orphan, '')

# Fix remaining phase numbers
content = content.replace(
    '\u23f3 Phase 1/4 \u2014 {len(_oc_games)}',
    '\u23f3 Phase 1/3 \u2014 {len(_oc_games)}'
)
content = content.replace(
    '\u23f3 Phase 2/4 \u2014 Loading team stats',
    '\u23f3 Phase 2/3 \u2014 Loading team stats'
)
content = content.replace(
    '\u23f3 Phase 3/4 \u2014 Retrieving live',
    '\u23f3 Phase 3/3 \u2014 Retrieving live'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done. Verifying...')
# Verify no orphan remains
if '3 \u2014 {len(_oc_games)} game(s)' in content and 'Phase 1/3' not in content:
    print('ERROR: still has issues')
else:
    print('OK')

# Verify syntax
import ast
try:
    ast.parse(content)
    print('SYNTAX OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
