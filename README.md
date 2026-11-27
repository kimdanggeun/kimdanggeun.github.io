# 🥕 김당근 미식 — 미식 지도 & 맛집 검색기

전국 5,000여 곳을 모은 미식 지도. 상호명·동네·메뉴·태그를 **초성까지** 실시간 검색하고,
취향 학습형 **무한 발굴**로 끝없이 새 맛집을 찾습니다.

- 라이브: https://kimdanggeun.github.io/ (저장소 `kimdanggeun/kimdanggeun.github.io`, 공개, main/root, `.nojekyll`)
- 옛 주소: https://kimkamatune.github.io/food/ (그대로 보존)

## 화면에서 보이는 것
- 🍽️ **대표메뉴 · 가격** — 가게마다 확인된 메뉴와 가격(예: `라자냐 13,900 · 뽀모도로 9,900 (2026.11 기준)`)
- 💰 **가격대** — 메뉴를 못 찾은 곳은 '가격대 보통/저렴' 같은 표기
- 🕒 영업시간 · ⭐ 평점 · 📝 메모 · ✅ 확인 근거 · `정보 확인 YYYY-MM-DD`
- 🗺️ 네이버지도 / 🌍 구글지도 바로가기, 가봄 표시 · 별점 · 댓글(브라우저 localStorage에만 저장)

## 데이터 구조
```
data/places.json        지도 리스트(전수) — 신규 발굴분 포함
data/new-places.json    발굴·신상 맛집(2025~26 오픈)
data/dropped.json       지운 곳(폐업·종료) — 여기 있으면 어떤 소스에서 다시 들어와도 빌드가 뺀다
data/dc-rid.json        가게 ↔ 다이닝코드 rid 캐시
data/dc-menu.json       다이닝코드에서 읽은 메뉴 캐시
data/dc-notfound.json   다이닝코드에서 못 찾은 가게(재조회 방지)
data/discover-cursor.json  지역×키워드 검색 진행 위치
data/last-run.json      마지막 자동 갱신 결과 요약
data/verify.json        (선택) 확인 오버라이드
```
공통 필드: `n` 상호 · `c` 분류 · `a` 주소 · `r` 구/시 · `m` 메모 · `p` 대표메뉴+가격 · `pl` 가격대 ·
`hours` 영업시간 · `rating` 평점 · `v` 확인일 · `nw` 신상 오픈 시기 · `src` 출처 · `fine`/`oma`/`mi` 태그

## 매일 자동 갱신 (GitHub Actions)
`.github/workflows/daily-update.yml` — **매일 06:00 KST**(`cron: '0 21 * * *'`)에 자동 실행, 수동 실행(`workflow_dispatch`)도 가능.

1. **신규 발굴** `scripts/fetch_new.py` — 다이닝코드 검색 API 로 `지역(78) × 키워드(69)` 조합을 이어서 훑어
   상호·주소·분류·평점이 확인된 곳만 추가. 프랜차이즈·비음식점 제외, 상호(지점 접미사 제거)+도로명+번지로 중복 제거.
2. **대표메뉴·가격** `scripts/fetch_menus.py` — 가게별 다이닝코드 상세(JSON-LD `hasMenu`)에서 실제 메뉴·가격·영업시간을 읽어 채움.
   이름+구(시)가 맞는 가게만 인정(동명이인 오매칭 방지). 막히면(빈 응답) 스스로 멈추고 다음 실행으로 미룸.
3. **확인일 정리** — `v`가 1년을 넘은 항목은 데이터에서 제거(사이트도 같은 기준으로 거름).
4. **재빌드 · 검사 · 커밋** — `scripts/build.py` → `scripts/check.py`(문법·개인정보·삭제 반영) → 자동 커밋·푸시.

## 빌드 (손으로)
```bash
python3 scripts/build.py        # data/*.json + template.html → index.html
python3 scripts/check.py        # ESprima 문법 검사 + 개인정보 0건 + 삭제 반영 확인
python3 scripts/daily_update.py # 발굴·메뉴·정리·재빌드를 한 번에 (Actions가 돌리는 것과 동일)
python3 scripts/fetch_menus.py --limit 300   # 대표메뉴만 따로 채울 때
python3 scripts/fetch_new.py --limit 300 --queries 200
```

## 지운 곳 / 다시 넣지 않기
`data/dropped.json`에 `{"n": 상호, "a": 주소, "why": 이유, "at": 날짜}`를 적으면
데이터에서 빠지고, 이후 자동 수집에서도 같은 이름은 다시 들어오지 않는다.
(예: `뚜레쥬르 강남직영점` — 2026-11-27 무한리필 빵뷔페 종료로 삭제)

## 그 밖에
- 🆕 신상 맛집(2025~26) · 🕓 확인일(`v`) 기준 1년 지난 항목 자동 제외
- 🗺️ 네이버지도는 '상호명+구/시'로만 검색(주소를 붙이면 업체를 못 찾는 문제 회피)
- 별점·댓글·가봄·취향 학습은 브라우저(localStorage)에만 저장
