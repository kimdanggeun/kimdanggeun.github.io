#!/usr/bin/env python3
"""새 맛집 발굴 — 다이닝코드 검색 API 로 지역×키워드를 훑어 후보를 모으고,
이름+주소가 겹치지 않는 곳만 data/places.json 에 추가한다.

- 추측 없음: API가 돌려준 상호·주소·카테고리·평점만 저장한다(메뉴는 fetch_menus.py 담당).
- 프랜차이즈·비음식점은 제외해 목록 품질을 지킨다.

사용법
  python3 scripts/fetch_new.py --limit 200
  python3 scripts/fetch_new.py --queries 400 --min-score 0
"""
import argparse, html as html_lib, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_menus as F  # http/load/save/nn/gu_of 재사용
import regions

ROOT = F.ROOT

KEYWORDS = [
    '맛집', '노포', '국밥', '순대국', '설렁탕', '곰탕', '칼국수', '냉면', '밀면', '막국수',
    '한식', '백반', '찌개', '전골', '감자탕', '고기', '삼겹살', '갈비', '곱창', '족발', '보쌈',
    '닭갈비', '찜닭', '닭볶음탕', '양꼬치', '훠궈', '마라탕', '중식', '짜장면', '짬뽕', '딤섬',
    '일식', '초밥', '스시', '라멘', '우동', '돈까스', '덮밥', '카레', '오마카세',
    '양식', '파스타', '스테이크', '리조또', '브런치', '쌀국수', '베트남', '태국', '커리',
    '분식', '떡볶이', '김밥', '회', '횟집', '해물', '조개', '장어', '추어탕', '복국',
    '치킨', '호프', '이자카야', '술집', '와인바', '뷔페', '카페', '디저트', '빵', '베이커리',
]

CHAIN = re.compile(
    r'스타벅스|투썸|이디야|메가커피|컴포즈|빽다방|커피빈|할리스|폴바셋|탐앤탐스|엔제리너스|파스쿠찌|'
    r'뚜레쥬르|파리바게뜨|던킨|배스킨|크리스피|노티드|설빙|'
    r'맥도날드|롯데리아|버거킹|KFC|맘스터치|서브웨이|쉐이크쉑|'
    r'교촌|BBQ|비비큐|BHC|굽네|푸라닭|네네치킨|처갓집|도미노|파파존스|미스터피자|피자헛|'
    r'김밥천국|본죽|한솥|이삭토스트|명랑|죠스떡볶이|신전떡볶이|'
    r'맥주창고|와바|프랭크버거|이마트|홈플러스|롯데마트|코스트코|편의점|GS25|CU|세븐일레븐'
)

BAD_CAT = re.compile(r'편의점|마트|병원|약국|은행|부동산|학원|미용|네일|세탁|주유|노래|PC방|만화')

DISTRICTS_SEOUL = ['강남구', '강동구', '강북구', '강서구', '관악구', '광진구', '구로구', '금천구',
                   '노원구', '도봉구', '동대문구', '동작구', '마포구', '서대문구', '서초구', '성동구',
                   '성북구', '송파구', '양천구', '영등포구', '용산구', '은평구', '종로구', '중구', '중랑구']

DISTRICTS_LOCAL = ['수원시', '성남시', '고양시', '용인시', '부천시', '안산시', '안양시', '남양주시',
                   '화성시', '평택시', '의정부시', '시흥시', '파주시', '김포시', '광주시', '하남시',
                   '인천', '부산', '대구', '대전', '광주', '울산', '세종', '춘천시', '원주시', '강릉시',
                   '청주시', '천안시', '전주시', '목포시', '여수시', '순천시', '포항시', '경주시',
                   '구미시', '창원시', '진주시', '김해시', '제주시', '서귀포시']


def sig(rec):
    """중복 판정 서명 — 지점 접미사를 뗀 상호 + 도로명 + 번지."""
    base = F.nn(F.base_name(rec.get('n', '')))
    addr = rec.get('a', '') or ''
    street = re.search(r'([가-힣]+(?:로|길)\s*\d*)', addr)
    num = re.search(r'(\d+(?:-\d+)?)', addr)
    return (base,
            re.sub(r'\s+', '', street.group(1)) if street else '',
            num.group(1) if num else '')


def is_dup(rec, sigs, names):
    b, st, num = sig(rec)
    if not b:
        return True
    if F.nn(rec.get('n', '')) in names:
        return True
    if st and num and (b, st, num) in sigs:
        return True
    if not st and (b, '', '') in sigs:
        return True
    return False


def remember(rec, sigs, names):
    b, st, num = sig(rec)
    sigs.add((b, st, num))
    names.add(F.nn(rec.get('n', '')))


def clean(s):
    s = re.sub(r'<[^>]+>', '', s or '')
    return html_lib.unescape(s).strip()


def candidate_to_record(c):
    nm = clean(c.get('nm'))
    branch = clean(c.get('branch'))
    if not nm:
        return None
    name = nm if (not branch or F.nn(branch) in F.nn(nm)) else f'{nm} {branch}'
    addr = clean(c.get('road_addr') or c.get('addr'))
    if not addr:
        return None
    cat = clean(c.get('category'))
    if BAD_CAT.search(cat):
        return None
    if CHAIN.search(name):
        return None
    gu = F.gu_of(addr)
    rec = {
        'n': name, 'c': cat, 'a': addr, 'r': regions.canonical(addr, gu), 'd': '', 'm': '',
        's': '', 't': [], 'ls': [], 'fine': False, 'oma': False, 'mi': '',
        'v': F.TODAY, 'src': 'diningcode', 'drid': c.get('v_rid') or '',
    }
    lat, lng = c.get('lat'), c.get('lng')
    if lat and lng:
        rec['lat'], rec['lon'] = lat, lng
    score = c.get('user_score')
    if score:
        rec['rating'] = str(score)
    cnt = c.get('review_cnt')
    if cnt:
        rec['rc'] = cnt
    return rec


def run_queries(queries, workers=4):
    out = []

    def one(q):
        try:
            return q, F.dc_search(q)
        except Exception as e:
            return q, []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for q, cands in ex.map(one, queries):
            for c in cands:
                out.append((q, c))
            time.sleep(0.05)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=300, help='이번 실행에서 추가할 최대 곳')
    ap.add_argument('--queries', type=int, default=200, help='이번 실행에서 던질 검색어 수')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--min-reviews', type=int, default=0, help='리뷰 수 하한(0=제한 없음)')
    args = ap.parse_args()

    places = F.load('places.json', [])
    newp = F.load('new-places.json', [])
    dropped = F.load('dropped.json', [])
    cursor = F.load('discover-cursor.json', {'next': 0})

    sigs = set()
    names = set()
    for rec in places + newp:
        remember(rec, sigs, names)
    for d in dropped:
        names.add(F.nn(d.get('n', '')))

    # 지역×키워드 조합을 이어서 소비한다 (매일 조금씩, 끝나면 처음부터 다시)
    districts = DISTRICTS_SEOUL + DISTRICTS_LOCAL
    combos = [(d, k) for d in districts for k in KEYWORDS]
    start = cursor.get('next', 0) % len(combos)
    picked = []
    i = start
    while len(picked) < args.queries:
        d, k = combos[i % len(combos)]
        picked.append(f'{d} {k}')
        i += 1
    cursor['next'] = i % len(combos)

    rows = run_queries(picked, args.workers)
    added = []
    for q, c in rows:
        rec = candidate_to_record(c)
        if not rec:
            continue
        if is_dup(rec, sigs, names):
            continue
        if args.min_reviews and (rec.get('rc') or 0) < args.min_reviews:
            continue
        remember(rec, sigs, names)
        added.append(rec)
        if len(added) >= args.limit:
            break

    places.extend(added)
    F.save('places.json', places)
    F.save('discover-cursor.json', cursor)
    print(f'검색어 {len(picked)}개 · 후보 {len(rows)}곳 → 새로 추가 {len(added)}곳 (누적 {len(places) + len(newp):,}곳)')


if __name__ == '__main__':
    main()
