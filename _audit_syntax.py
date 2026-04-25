import ast, os, sys
errors = []
count = 0
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'node_modules', 'cache', 'db', 'logs', 'assets')]
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        count += 1
        try:
            ast.parse(open(path, encoding='utf-8', errors='replace').read())
        except SyntaxError as e:
            errors.append('%s: %s' % (path, e))
if errors:
    for e in errors:
        print('SYNTAX ERROR:', e)
else:
    print('All Python files: SYNTAX OK')
print('Scanned:', count, 'files')
