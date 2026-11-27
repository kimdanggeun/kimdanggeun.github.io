#!/usr/bin/env python3
"""매일 자동 갱신 — 새 맛집 발굴 → 대표메뉴·가격 채우기 → 확인일 1년 지난 데이터 정리 → index.html 재빌드.

GitHub Actions(.github/workflows/daily-update.yml)가 매일 06:00 KST 에 이 스크립트를 돌린다.
사람이 손으로 돌릴 때:  python3 scripts/daily_update.py
"""
import argparse, json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build as builder  # noqa: E402


def load(name, default):
    path = os.path.join(ROOT, 'data', name)
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save(name, obj):
    with open(os.path.join(ROOT, 'data', name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(', ', ': '))
        f.write('\n')


def days_old(v):
    if not v:
        return 0
    try:
        t = time.mktime(time.strptime(str(v)[:10], '%Y-%m-%d'))
    except Exception:
        return 0
    return (time.time() - t) / 86400


def purge_stale(days=365):
    """확인일이 1년 넘은 항목을 데이터에서 뺀다(사이트도 빌드 때 같은 기준으로 거른다)."""
    total = 0
    for fname in ('places.json', 'new-places.json'):
        arr = load(fname, [])
        keep = [r for r in arr if days_old(r.get('v')) <= days]
        removed = len(arr) - len(keep)
        total += removed
        if removed:
            save(fname, keep)
    return total


def run(script, *args):
    cmd = [sys.executable, os.path.join(ROOT, 'scripts', script)] + list(args)
    print('\n$ ' + ' '.join(cmd[1:]), flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or '') + (p.stderr or '')
    print(out.strip()[-2000:], flush=True)
    return out


def last_run_hours():
    last = load('last-run.json', {})
    finished = last.get('finished', '')
    if not finished:
        return 1e9
    try:
        t = time.mktime(time.strptime(finished, '%Y-%m-%d %H:%M:%S'))
    except Exception:
        return 1e9
    return (time.time() - t) / 3600


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--if-stale', type=float, default=0,
                    help='마지막 갱신이 이 시간(시간) 안이면 건너뛴다 — 두 러너가 겹치지 않게')
    args = ap.parse_args()
    if args.if_stale and last_run_hours() < args.if_stale:
        print(f'최근 {last_run_hours():.1f}시간 안에 갱신됨 → 이번 실행은 건너뜁니다.')
        return

    menu_limit = os.environ.get('MENU_LIMIT', '1200')
    new_limit = os.environ.get('NEW_LIMIT', '250')
    recheck = os.environ.get('RECHECK_DAYS', '120')

    started = time.strftime('%Y-%m-%d %H:%M:%S')
    dropped = purge_stale(365)
    if dropped:
        print(f'확인일 1년 경과 {dropped}곳 정리')

    out_new = run('fetch_new.py', '--limit', new_limit, '--queries', os.environ.get('NEW_QUERIES', '160'))
    out_menu = run('fetch_menus.py', '--limit', menu_limit, '--recheck', recheck)

    info = builder.build()
    menu_count = 0
    price_level = 0
    for rec in load('places.json', []) + load('new-places.json', []):
        p = rec.get('p', '')
        if p and re.search(r'\d', p):
            menu_count += 1
        if rec.get('pl'):
            price_level += 1

    report = {
        'started': started,
        'finished': time.strftime('%Y-%m-%d %H:%M:%S'),
        'dropped_stale': dropped,
        'total': info['total'],
        'with_menu': menu_count,
        'price_level': price_level,
        'new_log': out_new.strip().splitlines()[-1] if out_new.strip() else '',
        'menu_log': out_menu.strip().splitlines()[-1] if out_menu.strip() else '',
    }
    save('last-run.json', report)
    print('\n=== 요약 ===')
    print(f"전체 {report['total']:,}곳 · 대표메뉴 {menu_count:,}곳 · 가격대 {price_level:,}곳")
    print(report['new_log'])
    print(report['menu_log'])


if __name__ == '__main__':
    main()
