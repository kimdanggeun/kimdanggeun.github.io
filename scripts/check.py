#!/usr/bin/env python3
"""배포 전 검사 — ① 인라인 JS 문법(esprima) ② 개인정보 0건 ③ 데이터 위생."""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regions

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')

FORBIDDEN = ['안성택', 'sabsab762', 'ahnseongtaeg', 'kimkama', '@BJ김카마']


def load(name, default):
    path = os.path.join(ROOT, 'data', name)
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    html = open(INDEX, encoding='utf-8').read()
    ok = True

    # ① JS 문법
    scripts = re.findall(r'<script(?![^>]*type="application/ld\+json")[^>]*>(.*?)</script>', html, re.S)
    body = max(scripts, key=len)
    try:
        import esprima
        esprima.parseScript(body)
        print('① JS 문법: OK (%d bytes)' % len(body))
    except ImportError:
        print('① JS 문법: esprima 없음 → 건너뜀 (pip install esprima)')
    except Exception as e:
        ok = False
        print('① JS 문법: 실패 →', e)

    # ② 개인정보
    hits = []
    for word in FORBIDDEN:
        n = html.count(word)
        if n:
            hits.append((word, n))
    if hits:
        ok = False
        print('② 개인정보: 발견!', hits)
    else:
        print('② 개인정보: 0건 (' + ', '.join(FORBIDDEN) + ')')

    # ③ 데이터 위생
    places = load('places.json', [])
    newp = load('new-places.json', [])
    dropped = load('dropped.json', [])
    drop_names = {re.sub(r'\s+', '', d.get('n', '')) for d in dropped}
    alive = [r for r in places + newp if re.sub(r'\s+', '', r.get('n', '')) in drop_names]
    if alive:
        ok = False
        print('③ 데이터: 지운 곳이 남아 있음 →', [r['n'] for r in alive])
    else:
        print('③ 데이터: 삭제 요청 %d곳 모두 빠짐 · 전체 %s곳' % (len(dropped), format(len(places) + len(newp), ',')))

    # ④ 지역 값이 주소와 맞는지 (지역 필터 오작동의 원인이었음)
    mismatch = []
    for r in places + newp:
        sido, _ = regions.split_sido(r.get('a', ''))
        if sido and not (r.get('r', '') or '').startswith(sido):
            mismatch.append((r.get('n'), r.get('r'), r.get('a', '')[:30]))
    if mismatch:
        ok = False
        print('④ 지역 불일치 %d곳 (예: %s)' % (len(mismatch), mismatch[:3]))
    else:
        print('④ 지역: 주소와 지역 값 모두 일치')

    menus = sum(1 for r in places + newp if r.get('p') and re.search(r'\d', r.get('p', '')))
    print('   대표메뉴·가격 표기: %s곳' % format(menus, ','))

    if not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
