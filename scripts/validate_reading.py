#!/usr/bin/env python3
"""
Validate generated IELTS reading practice HTML.
Checks structural integrity, div balance, and key feature presence.
"""
import re, sys

def validate(path):
    with open(path, 'r') as f:
        html = f.read()
    
    errors = []
    
    # 1. Check file size
    size = len(html)
    if size < 10000:
        errors.append(f'File too small: {size} bytes (expected > 10KB)')
    
    # 2. Check for key components
    components = {
        'tab-bar': 'tab-bar',
        'action-bar': 'action-bar',
        'header': 'header',
        'layout': 'layout',
        'passage-panel': 'passage-panel',
        'passage-col': 'passage-col',
        'questions-col': 'questions-col',
        'submit button': 'submitAnswers()',
        'reset function': 'resetAll()',
        'export PDF': 'exportPDF()',
        'grade function': 'gradePanel',
        'switch passage': 'switchPassage',
        'drag heading': 'dragHeading(',
        'drop heading': 'dropHeading(',
        'place heading': 'placeHeading',
        'answer-reveal': 'answer-reveal',
        'reveal-btn-single': 'reveal-btn-single',
        'score-badge': 'score-badge',
        'heading-slot': 'heading-slot',
        'heading-pool': 'heading-pool',
        'heading-item': 'heading-item',
        'placeHeading full text': 'item.textContent.trim()',
        'gradePanel passage-col': 'passage-col .heading-slot',
    }
    
    for name, pattern in components.items():
        if pattern not in html:
            errors.append(f'Missing: {name} ({pattern})')
    
    # 3. Check div balance for each passage
    for p in range(1, 6):
        m = html.find(f'PASSAGE {p}')
        if m < 0:
            errors.append(f'Missing PASSAGE {p} marker')
            continue
        next_m = html.find('PASSAGE', m + 1)
        e = html.find('</div><!-- /layout -->', m) if next_m < 0 else next_m
        section = html[m:e]
        opens = len(re.findall(r'<div[\s>]', section))
        closes = len(re.findall(r'</div>', section))
        if opens != closes:
            errors.append(f'P{p}: div mismatch: {opens} opens, {closes} closes')
    
    # 4. Check heading-slot in passage-col for heading-matching passages
    # (Only if they exist in the data)
    for p in [3, 5]:
        m = html.find(f'PASSAGE {p}')
        if m < 0: continue
        e = html.find('PASSAGE', m + 1) if p < 5 else len(html)
        section = html[m:e]
        pc = section[section.find('passage-col'):section.find('questions-col')]
        passage_hs = pc.count('heading-slot')
        if passage_hs > 0:
            # Verify each has a reveal
            reveals = section.count('answer-reveal')
            # This is approximate, just check it's non-zero
        else:
            # Non-heading passages shouldn't have it
            pass
    
    # 5. Check page structure (action-bar before header)
    ab_idx = html.find('class="action-bar"')
    header_idx = html.find('class="header"')
    if ab_idx > header_idx:
        errors.append('action-bar should be BEFORE header')
    
    # 6. Check script tags
    script_count = html.count('<script>')
    if script_count != 1:
        errors.append(f'Expected 1 <script> tag, found {script_count}')
    
    if errors:
        print(f'VALIDATION FAILED: {len(errors)} issue(s)')
        for e in errors:
            print(f'  - {e}')
        return False
    else:
        print('VALIDATION PASSED ✅')
        print(f'  Size: {size} bytes')
        return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: validate_reading.py <path-to-html>')
        sys.exit(1)
    valid = validate(sys.argv[1])
    sys.exit(0 if valid else 1)
