import re, ast

path = u'pages/1_\U0001f4e1_Live_Games.py'

with open(path, encoding='utf-8') as f:
    content = f.read()

orphan = '3 \u2014 {len(_oc_games)} game(s) loaded. Loading player data\u2026\")\n'
before = content
content = content.replace(orphan, '')
print('Orphan removed:', content != before)

r1 = content.replace('\u23f3 Phase 1/4 \u2014 {len(_oc_games)}', '\u23f3 Phase 1/3 \u2014 {len(_oc_games)}')
r2 = r1.replace('\u23f3 Phase 2/4 \u2014 Loading team stats', '\u23f3 Phase 2/3 \u2014 Loading team stats')
r3 = r2.replace('\u23f3 Phase 3/4 \u2014 Retrieving live', '\u23f3 Phase 3/3 \u2014 Retrieving live')
print('Phase replacements made:', r3 != content)
content = r3

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done. Verifying...')
if '3 \u2014 {len(_oc_games)} game(s)' in content and 'Phase 1/3' not in content:
    print('ERROR: still has issues')
else:
    print('OK')

try:
    ast.parse(content)
    print('SYNTAX OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
