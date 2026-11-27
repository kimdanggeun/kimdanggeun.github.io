#!/usr/bin/env python3
"""기존 데이터 필드 정리 (한 번만).

- p 필드가 '가격대 …' 같은 가격대 설명이면 pl 로 옮긴다 → p 는 '대표메뉴+가격' 전용
- 메뉴+가격이 들어 있는 p 는 그대로 둔다 (신상 카드가 쓰던 형식)
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICE_LEVEL = re.compile(r'^가격대|^저렴|^보통|^비쌈')


def main():
    moved = 0
    for fname in ('places.json', 'new-places.json'):
        path = os.path.join(ROOT, 'data', fname)
        arr = json.load(open(path, encoding='utf-8'))
        for rec in arr:
            p = rec.get('p', '')
            if p and PRICE_LEVEL.match(p):
                rec['pl'] = p
                rec['p'] = ''
                moved += 1
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(arr, f, ensure_ascii=False, separators=(', ', ': '))
            f.write('\n')
    print('가격대 문구를 pl 로 옮김:', moved)


if __name__ == '__main__':
    main()
