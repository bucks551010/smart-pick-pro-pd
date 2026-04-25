content = open('pages/3_\u26a1_Quantum_Analysis_Matrix.py', encoding='utf-8').read()
lines = content.split('\n')
for i, l in enumerate(lines):
    if any(k in l.lower() for k in ['broadcast', 'desk', 'joseph_desk', 'JOSEPH_DESK', 'render_joseph_broadcast']):
        print(i+1, l)
