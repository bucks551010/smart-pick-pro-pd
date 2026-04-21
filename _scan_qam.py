import os, re, sys
os.chdir(r'C:\Users\v-jmoten\smart-pick-pro-pd')
src = open('pages/3_⚡_Quantum_Analysis_Matrix.py', encoding='utf-8').read()

terms = ['QEG', 'blur', 'upgrade', 'platform_pick', 'Platform Pick', '_PREM_PATH', 'tier_gate', 'locked', '_QAM_PROP_LIMIT', 'PLATFORM_PICK', 'free_picks', 'top_picks', 'AI PICKS', 'render_tier']
for term in terms:
    m = re.search(term, src, re.IGNORECASE)
    if m:
        snippet = src[m.start():m.start()+200].replace('\n', '\\n')
        sys.stdout.buffer.write(f'{term} at {m.start()}: {snippet[:180]}\n\n'.encode('utf-8'))
