#!/usr/bin/env python3
"""다이닝코드에서 가게별 '대표메뉴 + 가격'을 확인해 채운다.

- 검색: https://im.diningcode.com/API/isearch/  (mode=portal, query="이름 구")
- 상세: https://www.diningcode.com/profile.php?rid=…  의 JSON-LD(hasMenu) 에서 메뉴/가격/영업시간/가격대 확인
- 추측 없음: 이름+주소가 맞는 가게의 페이지에서 실제로 읽힌 메뉴만 기록한다.

사용법
  python3 scripts/fetch_menus.py --limit 300 --workers 4
  python3 scripts/fetch_menus.py --all            # 남은 대상 전부
  python3 scripts/fetch_menus.py --recheck 90     # 확인한 지 90일 지난 곳 다시 확인
"""
import argparse, gzip, json, os, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = 'https://im.diningcode.com/API/'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
TODAY = time.strftime('%Y-%m-%d')
MONTH = time.strftime('%Y.%m')


def load(name, default):
    path = os.path.join(ROOT, 'data', name)
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save(name, obj):
    path = os.path.join(ROOT, 'data', name)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(', ', ': '))
        f.write('\n')
    os.replace(tmp, path)


def http(url, data=None, tries=3, timeout=20):
    body = urllib.parse.urlencode(data).encode() if data else None
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, method='POST' if data else 'GET')
            req.add_header('User-Agent', UA)
            req.add_header('Accept', 'application/json, text/html;q=0.9,*/*;q=0.8')
            req.add_header('Accept-Encoding', 'gzip')
            if data:
                req.add_header('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
                req.add_header('Origin', 'https://www.diningcode.com')
                req.add_header('Referer', 'https://www.diningcode.com/')
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    raw = gzip.decompress(raw)
                return raw.decode('utf-8', 'replace')
        except Exception as e:  # 429·타임아웃 등은 조금 쉬었다 다시
            last = e
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(str(last))


# ── 이름·주소 정규화 ─────────────────────────────────────────────
def nn(s):
    return re.sub(r'[\s()\[\]{}·.,\'"`~!?\-_/&+]', '', s or '').lower()


def gu_of(addr):
    for tok in (addr or '').split():
        if tok.endswith('구') or tok.endswith('군'):
            return tok
        if tok.endswith('시') and not re.search(r'특별시|광역시|특별자치시$', tok):
            return tok
    return ''


def dong_of(addr):
    m = re.search(r'([가-힣0-9]+동)(?=\s|,|\d|$)', addr or '')
    return m.group(1) if m else ''


def dc_search(query):
    raw = http(API + 'isearch/', {'mode': 'portal', 'query': query, 'page': 1})
    d = json.loads(raw)
    if str(d.get('result_code')) != '100':
        return []
    ps = (d.get('result_data') or {}).get('poi_section') or {}
    return ps.get('list') or []


def pick_candidate(place, cands):
    name = nn(place.get('n'))
    gu, dong = gu_of(place.get('a', '')), dong_of(place.get('a', ''))
    best, best_score = None, 0
    for c in cands:
        full = nn((c.get('nm') or '') + (c.get('branch') or ''))
        short = nn(c.get('nm') or '')
        score = 0
        if full == name:
            score = 3
        elif len(full) >= 4 and len(name) >= 4 and (name.startswith(full) or full.startswith(name)):
            score = 3
        elif short == name:
            score = 2
        elif len(short) >= 4 and name.startswith(short):
            score = 2
        if not score:
            continue
        caddr = (c.get('addr') or '') + ' ' + (c.get('road_addr') or '')
        if gu and gu in caddr:
            score += 2
        if dong and dong in caddr:
            score += 1
        if score > best_score:
            best, best_score = c, score
    # 구까지 맞는 후보(4점 이상)만 인정 — 동명이인 오매칭 방지
    return best if best_score >= 4 else None


def parse_profile(html):
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(1).strip())
    except Exception:
        return None
    menus = []
    hm = d.get('hasMenu') or {}
    for it in (hm.get('hasMenuItem') or []):
        nm = (it.get('name') or '').strip()
        price = ((it.get('offers') or {}).get('price') or '').strip()
        if not nm:
            continue
        menus.append([nm, price])
    hours = d.get('openingHours')
    if isinstance(hours, list):
        hours = ' · '.join([h for h in hours if h])
    return {
        'name': d.get('name') or '',
        'addr': ((d.get('address') or {}).get('streetAddress') or ''),
        'menus': menus,
        'hours': hours or '',
        'priceRange': d.get('priceRange') or '',
        'cuisine': d.get('servesCuisine') or '',
        'tel': d.get('telephone') or '',
    }


BAD_MENU = re.compile(r'^(포장|배달|콜키지|주차|예약|단체|룸|취식|테이크아웃|반려)')


def menu_line(menus, limit=3):
    out = []
    seen = set()
    for nm, price in menus:
        if not nm or BAD_MENU.match(nm):
            continue
        p = re.sub(r'\s*원$', '', price or '').strip()
        if not re.search(r'\d', p):
            continue
        key = nn(nm)
        if key in seen:
            continue
        seen.add(key)
        out.append(f'{nm} {p}')
        if len(out) >= limit:
            break
    return ' · '.join(out)


BASE_SUFFIX = re.compile(r'\s*(본점|직영점|[가-힣0-9]*점|[A-Za-z]*호점)$')


def base_name(n):
    return BASE_SUFFIX.sub('', n or '').strip() or n


def work_one(place, ridmap, cache, nf=None):
    """returns (status, rid, patch) — status: 'menu'|'no-menu'|'not-found'"""
    key = nn(place.get('n')) + '|' + nn(place.get('a', ''))[:24]
    rid = ridmap.get(key)
    if not rid and nf is not None and key in nf:
        return 'not-found', None, None
    if not rid:
        gu = gu_of(place.get('a', ''))
        name = place.get('n', '')
        cands = []
        for q in (name, (name + ' ' + gu).strip(), base_name(name)):
            cands = dc_search(q)
            c = pick_candidate(place, cands)
            if c:
                break
        if not c:
            if nf is not None:
                nf[key] = TODAY
            return 'not-found', None, None
        rid = c.get('v_rid')
        ridmap[key] = rid
    info = cache.get(rid)
    if not info:
        html = http('https://www.diningcode.com/profile.php?rid=' + rid)
        if len(html) < 500:
            # 빈 응답(202) = 사이트가 잠시 막은 상태. 확인 실패로 기록하지 않고 중단한다.
            raise Blocked(len(html))
        info = parse_profile(html) or {'menus': []}
        cache[rid] = info
        time.sleep(0.15)
    line = menu_line(info.get('menus') or [])
    patch = {}
    if line:
        patch['p'] = f'{line} ({MONTH} 기준)'
    if info.get('hours'):
        patch['hours'] = info['hours']
    if info.get('priceRange'):
        patch['pl'] = info['priceRange']
    patch['v'] = TODAY
    return ('menu' if line else 'no-menu'), rid, patch


class Blocked(Exception):
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--recheck', type=int, default=0, help='N일 지난 확인 건도 다시 확인')
    ap.add_argument('--max-blocked', type=int, default=25, help='빈 응답이 이만큼 나오면 중단')
    args = ap.parse_args()

    places = load('places.json', [])
    newp = load('new-places.json', [])
    ridmap = load('dc-rid.json', {})
    cache = load('dc-menu.json', {})
    nf = load('dc-notfound.json', {})

    def menu_ok(rec):
        return bool(rec.get('p') and re.search(r'\d', rec.get('p', '')))

    def stale(rec):
        if not args.recheck:
            return False
        return days_old(rec.get('v', '')) >= args.recheck

    targets = []
    for rec in places + newp:
        if not rec.get('n'):
            continue
        if menu_ok(rec) and not stale(rec):
            continue
        targets.append(rec)
    # 확인한 지 오래된 곳 → 메뉴 없는 곳 순으로
    targets.sort(key=lambda r: (menu_ok(r), r.get('v', '')))
    if not args.all and args.limit:
        targets = targets[:args.limit]

    stats = {'menu': 0, 'no-menu': 0, 'not-found': 0, 'error': 0, 'blocked': 0}
    done = 0
    blocked = 0
    stop = False

    def save_all():
        save('dc-rid.json', ridmap)
        save('dc-menu.json', cache)
        save('dc-notfound.json', nf)
        save('places.json', places)
        save('new-places.json', newp)

    t0 = time.time()
    it = iter(targets)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        inflight = {}
        while not stop:
            while len(inflight) < args.workers:
                try:
                    rec = next(it)
                except StopIteration:
                    break
                inflight[ex.submit(safe_run, rec, ridmap, cache, nf)] = rec
            if not inflight:
                break
            done_set, _ = wait(list(inflight), return_when=FIRST_COMPLETED)
            for fut in done_set:
                rec = inflight.pop(fut)
                status, rid, patch = fut.result()
                done += 1
                if status.startswith('blocked'):
                    blocked += 1
                    stats['blocked'] += 1
                    if blocked >= args.max_blocked:
                        stop = True
                elif status.startswith('error'):
                    stats['error'] += 1
                else:
                    stats[status] += 1
                if patch:
                    rec.update(patch)
                if done % 25 == 0:
                    save_all()
                    print('  … %d/%d  메뉴 %d · 메뉴없음 %d · 미발견 %d · 오류 %d · 차단 %d (%ds)' % (
                        done, len(targets), stats['menu'], stats['no-menu'], stats['not-found'],
                        stats['error'], stats['blocked'], time.time() - t0), flush=True)

    save_all()
    print('완료 %d곳 · 메뉴 %d · 메뉴없음 %d · 미발견 %d · 오류 %d · 차단 %d · %ds' % (
        done, stats['menu'], stats['no-menu'], stats['not-found'], stats['error'],
        stats['blocked'], time.time() - t0))
    if stop:
        print('※ 사이트가 응답을 비웠습니다(차단). 남은 %d곳은 다음 실행으로 미룹니다.' % (len(targets) - done))


def safe_run(rec, ridmap, cache, nf):
    try:
        return work_one(rec, ridmap, cache, nf)
    except Blocked as e:
        return 'blocked' + str(e), None, None
    except Exception as e:
        return 'error:' + str(e)[:60], None, None


def days_old(v):
    if not v:
        return 0
    try:
        t = time.mktime(time.strptime(v, '%Y-%m-%d'))
    except Exception:
        return 0
    return (time.time() - t) / 86400


if __name__ == '__main__':
    main()
