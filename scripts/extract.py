#!/usr/bin/env python3
"""index.html 한 파일에 들어 있던 NEW_PLACES / PLACES 배열을 data/*.json 으로 꺼낸다.
template.html 은 두 배열 자리를 __NEW_PLACES__ / __PLACES__ 로 비워 둔다.
(처음 한 번만 쓰는 이관 스크립트. 이후에는 build.py 가 data → index.html 방향으로만 만든다.)
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'index.html')


def grab_array(text, name):
    i = text.find('const ' + name + ' = [')
    if i < 0:
        raise SystemExit('배열을 찾지 못했습니다: ' + name)
    start = text.index('[', i)
    depth = 0
    instr = False
    esc = False
    for k in range(start, len(text)):
        ch = text[k]
        if instr:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                instr = False
        else:
            if ch == '"':
                instr = True
            elif ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    return start, k + 1, json.loads(text[start:k + 1])
    raise SystemExit('배열 끝을 찾지 못했습니다: ' + name)


def main():
    text = open(SRC, encoding='utf-8').read()
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)

    out = text
    for name, fname in (('PLACES', 'places.json'), ('NEW_PLACES', 'new-places.json')):
        start, end, arr = grab_array(text, name)
        with open(os.path.join(ROOT, 'data', fname), 'w', encoding='utf-8') as f:
            json.dump(arr, f, ensure_ascii=False, separators=(', ', ': '))
            f.write('\n')
        print(name, len(arr), '→ data/' + fname)

    # template: 두 배열을 자리표시자로 바꾼다 (뒤에서부터 바꿔야 인덱스가 안 밀린다)
    spans = []
    for name in ('PLACES', 'NEW_PLACES'):
        s, e, _ = grab_array(out, name)
        spans.append((s, e, '__' + name + '__'))
    for s, e, token in sorted(spans, reverse=True):
        out = out[:s] + token + out[e:]
    with open(os.path.join(ROOT, 'template.html'), 'w', encoding='utf-8') as f:
        f.write(out)
    print('template.html 작성 완료', len(out), 'bytes')


if __name__ == '__main__':
    main()
