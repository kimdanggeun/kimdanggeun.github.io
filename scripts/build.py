#!/usr/bin/env python3
"""data/*.json + template.html → index.html

- data/places.json       지도 리스트(전수) 맛집
- data/new-places.json   발굴·신상 맛집
- data/dropped.json      지운 곳(폐업·종료) — 여기 있으면 어떤 소스에서 다시 들어와도 빌드가 뺀다
- data/verify.json       확인 오버라이드(선택): {"가게이름|주소": {"p": "대표메뉴 …", "v": "2026-11-27"}}
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, default):
    path = os.path.join(ROOT, 'data', name)
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save(name, obj):
    path = os.path.join(ROOT, 'data', name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(', ', ': '))
        f.write('\n')


def key_of(rec):
    return re.sub(r'\s+', '', (rec.get('n', '') + '|' + rec.get('a', ''))).lower()


def drop_removed(places, dropped):
    """drops: [{"n":…, "a":…, "why":…, "at":…}] — 이름이 같고 주소가 비슷하거나 이름만 같으면 제거."""
    keys = set()
    names = set()
    for d in dropped:
        keys.add(key_of(d))
        names.add(re.sub(r'\s+', '', d.get('n', '')))
    keep = []
    removed = []
    for p in places:
        nm = re.sub(r'\s+', '', p.get('n', ''))
        if key_of(p) in keys or (nm and nm in names):
            removed.append(p)
            continue
        keep.append(p)
    return keep, removed


def build(write=True):
    template = open(os.path.join(ROOT, 'template.html'), encoding='utf-8').read()
    places = load('places.json', [])
    new_places = load('new-places.json', [])
    dropped = load('dropped.json', [])
    verify = load('verify.json', {}).get('overrides', {})

    places, rm1 = drop_removed(places, dropped)
    new_places, rm2 = drop_removed(new_places, dropped)
    removed = rm1 + rm2

    for rec in places + new_places:
        ov = verify.get(key_of(rec))
        if ov:
            rec.update(ov)

    total = len(places) + len(new_places)
    html = template.replace('__NEW_PLACES__', json.dumps(new_places, ensure_ascii=False))
    html = html.replace('__PLACES__', json.dumps(places, ensure_ascii=False))
    # 머리말·설명의 "N여 곳" 숫자를 데이터에 맞춘다
    html = re.sub(r'(id="subTotal">)[\d,]+', lambda m: m.group(1) + f'{total:,}', html)
    html = re.sub(r'전국 [\d,]+여 곳', f'전국 {total:,}여 곳', html)

    if write:
        with open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html)
    return {'total': total, 'places': len(places), 'new': len(new_places), 'removed': removed}


if __name__ == '__main__':
    info = build()
    print(f"index.html 생성 · 전체 {info['total']:,}곳 (지도 {info['places']:,} + 발굴 {info['new']:,})")
    if info['removed']:
        for p in info['removed']:
            print('  제외:', p.get('n'), '|', p.get('a', ''))
