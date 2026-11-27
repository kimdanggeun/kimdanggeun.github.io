#!/usr/bin/env python3
"""주소 → 지역(시도 + 구/시) 정규화.

이 파일이 있는 이유: 발굴 목록(new-places.json)의 `reg` 값이 실제 주소와 다른 경우가 있어
(예: 강릉 카페인데 reg 가 '서울특별시 마포구') 지역 필터에 엉뚱한 동네가 섞여 나왔다.
빌드할 때마다 주소를 기준으로 지역을 다시 계산해 그런 불일치를 없앤다.
"""
import re

# 긴 이름부터 검사해야 '전남광주통합특별시' 가 '전남' 으로 잘리지 않는다.
SIDO = [
    ('전남광주통합특별시', '전남광주통합특별시'),
    ('서울특별시', '서울특별시'), ('서울', '서울특별시'),
    ('부산광역시', '부산광역시'), ('부산', '부산광역시'),
    ('대구광역시', '대구광역시'), ('대구', '대구광역시'),
    ('인천광역시', '인천광역시'), ('인천', '인천광역시'),
    ('광주광역시', '광주광역시'),
    ('대전광역시', '대전광역시'), ('대전', '대전광역시'),
    ('울산광역시', '울산광역시'), ('울산', '울산광역시'),
    ('세종특별자치시', '세종특별자치시'), ('세종', '세종특별자치시'),
    ('경기도', '경기도'), ('경기', '경기도'),
    ('강원특별자치도', '강원특별자치도'), ('강원도', '강원특별자치도'), ('강원', '강원특별자치도'),
    ('충청북도', '충청북도'), ('충북', '충청북도'),
    ('충청남도', '충청남도'), ('충남', '충청남도'),
    ('전북특별자치도', '전북특별자치도'), ('전라북도', '전북특별자치도'), ('전북', '전북특별자치도'),
    ('전라남도', '전라남도'), ('전남', '전라남도'),
    ('경상북도', '경상북도'), ('경북', '경상북도'),
    ('경상남도', '경상남도'), ('경남', '경상남도'),
    ('제주특별자치도', '제주특별자치도'), ('제주도', '제주특별자치도'), ('제주', '제주특별자치도'),
]
SIDO_NAMES = {full for _, full in SIDO}

GU_RE = re.compile(r'^[가-힣]+(?:구|군)$')
SI_RE = re.compile(r'^[가-힣]+시$')


def split_sido(addr):
    addr = (addr or '').strip()
    for key, full in SIDO:
        if addr.startswith(key):
            return full, addr[len(key):].strip()
    return '', addr


def district_of(addr):
    """주소에서 구/시/군 하나를 뽑는다(시도 다음 토큰)."""
    _, rest = split_sido(addr)
    toks = rest.split()
    for i, t in enumerate(toks[:3]):
        if GU_RE.match(t):
            return t
        if SI_RE.match(t):
            return t
    return ''


def canonical(addr, current=''):
    """주소를 기준으로 '시도 구/시' 를 만든다. 주소에서 못 알아내면 기존 값을 그대로 둔다."""
    sido, _ = split_sido(addr)
    if not sido:
        return current or ''
    gu = district_of(addr)
    return (sido + ' ' + gu).strip()


def apply(rec, key='r'):
    """레코드 하나의 지역 값을 주소에 맞춘다. (mismatch 였으면 True)"""
    addr = rec.get('a', '') or ''
    old = rec.get(key, '') or ''
    new = canonical(addr, old)
    # 기존 값이 이미 같은 시도이고 구/시까지 맞으면 그대로 (전남광주통합 등 표기 보존)
    old_sido, old_rest = split_sido(old)
    if old_sido in SIDO_NAMES and old_rest and new.startswith(old_sido):
        return False
    if not new or new == old:
        return False
    rec[key] = new
    return True
