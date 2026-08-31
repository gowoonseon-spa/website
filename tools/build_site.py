# -*- coding: utf-8 -*-
"""고운:선 데모 사이트 생성기 — site/*.html 4페이지를 공통 헤더/푸터로 빌드.

카피·가격·시간·연락처는 content/content.json (클라이언트 편집 영역).
레이아웃·이미지·SEO 문구·디자인 라벨은 이 파일 (개발 영역).
파생 문구(할인 티어 금액, "120–180분 · 300,000원부터", 워드 리빌 타이밍)는
저장하지 않고 여기서 계산한다 — 가격은 content.json 한 곳만 고치면 전파됨.
"""
import os
import re
import json
import html
import hashlib

ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'site')


def _esc(o):
    """content.json의 모든 문자열을 HTML 이스케이프 (& < > — 따옴표는 유지)."""
    if isinstance(o, str):
        return html.escape(o, quote=False)
    if isinstance(o, list):
        return [_esc(x) for x in o]
    if isinstance(o, dict):
        return {k: _esc(v) for k, v in o.items()}
    return o


# ---- 구조 동결 (사용자 결정 2026-08-27) ----
# 어드민은 텍스트·사진 교체만 허용. 카테고리/프로그램/칩/갤러리의 추가·삭제·재배열은
# 개발 작업 — 구조를 바꿀 때는 아래 스냅샷도 함께 수정할 것.
STRUCTURE = {
    'category_ids': ['full', 'face', 'body', 'mother', 'focus', 'wedding'],
    'program_counts': {'full': 3, 'face': 3, 'body': 5, 'mother': 4, 'focus': 3, 'wedding': 5},
    'chip_counts': {
        'full': [4, 3, 2], 'face': [4, 4, 4], 'body': [3, 3, 2, 2, 3],
        'mother': [2, 4, 3, 2], 'focus': [2, 3, 3], 'wedding': [4, 3, 3, 4, 4],
    },
    # space.figures는 동결 예외 — 흐르는 갤러리는 장수와 무관하게 안전 (최소 4장만)
    'home_creds': 2,
    'director_creds': 5,
    'membership_tiers': 3,
    'membership_how': 3,
}

# ---- 콘텐츠 검증 — 렌더링을 깨뜨리는 값만 차단(에러), 나머지는 참고용 경고 ----
# 표현 선택은 원장 권한 — 아래 단어는 막지 않고 경고만 한다
# (치료·임상 계열은 비의료기관 광고 시 의료법 리스크가 있어 알림 목적)
ADVISORY = ['100%', '완치', '치료', '임상', '의학적', '부작용']

def _walk_strings(o, path='content'):
    if isinstance(o, str):
        yield path, o
    elif isinstance(o, list):
        for i, x in enumerate(o):
            yield from _walk_strings(x, f'{path}[{i}]')
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from _walk_strings(v, f'{path}.{k}')

def validate(c):
    errors, warnings = [], []
    for path, s in _walk_strings(c):
        for word in ADVISORY:
            if word in s:
                warnings.append(f'{path}: "{word}" — 절대 표현/의료 뉘앙스는 의료법·광고법 리스크가 있을 수 있음 (참고용, 빌드는 진행)')
    if not re.fullmatch(r'01[0-9]-\d{3,4}-\d{4}', c['global']['phone']):
        errors.append(f'global.phone: 전화번호 형식이 아닙니다 — "{c["global"]["phone"]}"')
    for cat in c['categories']:
        if not re.fullmatch(r'[a-z]+', cat.get('id', '')):
            errors.append(f'카테고리 "{cat.get("name")}": id는 영문 소문자여야 합니다')
        for p in cat['programs']:
            where = f'{cat.get("name")} > {p.get("name")}'
            if not p.get('name'):
                errors.append(f'{cat.get("name")}: 이름 없는 프로그램이 있습니다')
            if not isinstance(p.get('minutes'), int) or not 10 <= p['minutes'] <= 360:
                errors.append(f'{where}: 관리 시간은 10–360분 사이 숫자여야 합니다')
            if not isinstance(p.get('price'), int) or p['price'] < 10000 or p['price'] % 1000:
                errors.append(f'{where}: 가격은 10,000원 이상, 천원 단위여야 합니다')
            if not p.get('components'):
                errors.append(f'{where}: 구성(칩)이 비어 있습니다')
            if len(p.get('name') or '') > 16:
                warnings.append(f'{where}: 프로그램 이름이 16자를 넘습니다 — 카드에서 줄바꿈될 수 있음')
    # 멤버십 — 선불 충전형 (2026-08-31 미팅에서 확정된 모델)
    _frozen_mem = ' 항목 추가·삭제는 개발 작업입니다 — 삭제(X)했다면 되돌려 주세요'
    mts = c['memberships'].get('tiers', [])
    if len(mts) != STRUCTURE['membership_tiers']:
        errors.append(f'memberships.tiers: 멤버십은 {STRUCTURE["membership_tiers"]}종이어야 합니다 — 현재 {len(mts)}종.{_frozen_mem}')
    for t in mts:
        mwhere = f'멤버십 "{t.get("name") or "(이름 없음)"}"'
        if not t.get('name'):
            errors.append('memberships.tiers: 이름 없는 멤버십이 있습니다')
        if not isinstance(t.get('amount'), int) or t['amount'] < 100000 or t['amount'] % 10000:
            errors.append(f'{mwhere}: 충전 금액은 100,000원 이상, 만원 단위여야 합니다')
        if not isinstance(t.get('discount'), int) or not 1 <= t['discount'] <= 60:
            errors.append(f'{mwhere}: 할인율은 1–60 사이 숫자(%)여야 합니다')
    if len(c['memberships'].get('how', [])) != STRUCTURE['membership_how']:
        errors.append(f'memberships.how: 이용 안내 단계는 {STRUCTURE["membership_how"]}줄이어야 합니다.{_frozen_mem}')
    names = [p['name'] for cat in c['categories'] for p in cat['programs']]
    for ref in c['home']['sig_cards']:
        if ref['program'] not in names:
            errors.append(f'home.sig_cards: "{ref["program"]}" 프로그램이 없습니다 — 프로그램 이름을 바꿨다면 여기도 같이 바꿔야 합니다')
    # 콘텐츠가 가리키는 이미지 파일이 실제로 존재해야 한다 (없으면 빌드가 죽으므로 에러)
    fc = c['home']['for_cards']
    image_refs = (
        [(f'home.sig_cards[{i}]', r.get('image')) for i, r in enumerate(c['home']['sig_cards'])]
        + [(f'home.for_cards.{k}', fc[k].get('image')) for k in ('mother', 'face', 'focus')]
        + [(f'home.for_cards.scalp.images[{i}]', r.get('image')) for i, r in enumerate(fc['scalp'].get('images', []))]
        + [(f'home.space.figures[{i}]', r.get('image')) for i, r in enumerate(c['home']['space'].get('figures', []))]
        + [(f'about.journey[{i}]', r.get('image')) for i, r in enumerate(c['about']['journey'])]
        + ([('about.director.photo', c['about']['director']['photo'])] if c['about']['director'].get('photo') else [])
    )
    for where, ref in image_refs:
        rel = (ref or '').removeprefix('assets/img/')
        if not rel or not os.path.exists(os.path.join(OUT, 'assets', 'img', rel)):
            errors.append(f'{where}: 이미지 파일이 없습니다 — "{ref}"')
    # 구조 동결 검사 — 항목 추가/삭제/순서 변경은 개발 작업
    _frozen = ' 항목 추가·삭제는 개발 작업입니다 — 삭제(X)했다면 되돌려 주세요'
    ids = [cat.get('id') for cat in c['categories']]
    if ids != STRUCTURE['category_ids']:
        errors.append(f'categories: 카테고리 구성/순서가 바뀌었습니다 (기대 {STRUCTURE["category_ids"]} → 현재 {ids}).{_frozen}')
    else:
        for cat in c['categories']:
            n_expect = STRUCTURE['program_counts'][cat['id']]
            if len(cat['programs']) != n_expect:
                errors.append(f'{cat["name"]}: 프로그램은 {n_expect}개여야 합니다 — 현재 {len(cat["programs"])}개.{_frozen}')
            else:
                for p, n_chip in zip(cat['programs'], STRUCTURE['chip_counts'][cat['id']]):
                    if len(p.get('components') or []) != n_chip:
                        errors.append(f'{cat["name"]} > {p.get("name")}: 구성(칩)은 {n_chip}개여야 합니다 — 현재 {len(p.get("components") or [])}개.{_frozen}')
    if len(c['home']['space'].get('figures', [])) < 4:
        errors.append('home.space.figures: 흐르는 갤러리는 사진이 최소 4장 필요합니다')
    if len(c['home']['product'].get('creds', [])) != STRUCTURE['home_creds']:
        errors.append(f'home.product.creds: 경력 줄은 {STRUCTURE["home_creds"]}줄이어야 합니다.{_frozen}')
    if len(c['about']['director'].get('creds', [])) != STRUCTURE['director_creds']:
        errors.append(f'about.director.creds: 약력은 {STRUCTURE["director_creds"]}줄이어야 합니다.{_frozen}')
    # 고정 개수 섹션 — CMS의 min/max가 Add 버튼을 막아주지 않으므로 여기서 강제
    for path, items, n in [
        ('home.sig_cards (시그니처 카드)', c['home']['sig_cards'], 2),
        ('home.for_cards.scalp.images (두피 카드 사진)', c['home']['for_cards']['scalp'].get('images', []), 2),
        ('about.journey (고운:선에서의 시간)', c['about']['journey'], 4),
        ('visit.first_visit (처음 오시는 분께)', c['visit']['first_visit'], 3),
    ]:
        if len(items) != n:
            errors.append(f'{path}: 정확히 {n}개여야 합니다 — 현재 {len(items)}개. 추가한 항목을 삭제(X)해 주세요')
    for i, j in enumerate(c['about']['journey']):
        if not j.get('title') or not j.get('text'):
            errors.append(f'about.journey[{i + 1}번째]: 단계 제목과 설명을 채워주세요')
    for i, s_ in enumerate(c['visit']['first_visit']):
        if not s_.get('title') or not s_.get('text'):
            errors.append(f'visit.first_visit[{i + 1}번째]: 단계 제목과 설명을 채워주세요')
    if len(c['home']['reveal_sentence'].split()) < 2:
        errors.append('home.reveal_sentence: 두 단어 이상이어야 합니다')
    for w_ in c['home']['reveal_sentence'].split():
        if len(w_) > 8:
            warnings.append(f'home.reveal_sentence: "{w_}" — 긴 단어는 모바일에서 줄바꿈될 수 있음')
    for path, s in _walk_strings(c):
        if len(s) > 400:
            warnings.append(f'{path}: {len(s)}자 — 지나치게 긴 문단은 레이아웃 균형을 해칠 수 있음')
    for msg in warnings:
        print(f'⚠️  {msg}')
    if errors:
        print('\n콘텐츠 검증 실패 — 사이트를 빌드하지 않았습니다. content/content.json을 고쳐주세요:')
        for msg in errors:
            print(f'  ✕ {msg}')
        raise SystemExit(1)

_raw = json.load(open(os.path.join(ROOT, 'content', 'content.json'), encoding='utf-8'))
validate(_raw)
# 영업시간 구분 기호 정규화 — 어드민에서 하이픈으로 입력해도 엔대시로 통일
for _k in ('hours_weekday', 'hours_sat'):
    _raw['global'][_k] = re.sub(r'\s*[–—-]\s*', ' – ', _raw['global'][_k])
CONTENT = _esc(_raw)
G = CONTENT['global']
PRICING = CONTENT['pricing']
MEMBERSHIPS = CONTENT['memberships']
CATEGORIES = CONTENT['categories']
HOME = CONTENT['home']
PROGRAMS_PAGE = CONTENT['programs_page']
ABOUT = CONTENT['about']
VISIT = CONTENT['visit']

PHONE = G['phone']
TEL = f'tel:{PHONE}'

SITE_URL = 'https://gowoonseon.com'  # 2026-08-31 확정 — canonical/og/sitemap 절대경로의 원천

# 네이버 서치어드바이저 소유 확인 태그 (2026-09-01 발급). 구글 서치콘솔은 DNS 인증 — 태그 불필요.
NAVER_SITE_VERIFICATION = 'a88976b47489438adaa9e9af877df7ad980a9fa9'

# ---- 파생 문구 ----------------------------------------------------------
w = lambda n: f'{n:,}'

def tier_amount(price, discount):
    """멤버십 차감 금액 — 천원 단위 내림 (예: 450,000 · −20% → 360,000)."""
    return price * (100 - discount) // 100 // 1000 * 1000

def mem_short(name):
    """티어 라벨 축약 — '고운 멤버십' → '고운'. 이름을 바꿔도 자동 추종."""
    s = name.replace('멤버십', '').strip()
    return s or name

def tier_prices(price):
    """프로그램 카드 멤버십 차감가 라인 — '고운 405,000 · 깊은 382,000 · 온전 360,000'."""
    return ' · '.join(f'{mem_short(t["name"])} {w(tier_amount(price, t["discount"]))}'
                      for t in MEMBERSHIPS['tiers'])

# 파인프린트용 할인 요약 — 전 티어 동일하면 '−20%', 다르면 '−10~20%'
_mds = [t['discount'] for t in MEMBERSHIPS['tiers']]
MEM_DISCOUNT_SUMMARY = f'−{_mds[0]}%' if len(set(_mds)) == 1 else f'−{min(_mds)}~{max(_mds)}%'

def find_prog(name):
    for cat in CATEGORIES:
        for p in cat['programs']:
            if p['name'] == name:
                return p
    raise SystemExit(f'content.json 오류: 프로그램 "{name}"을(를) 찾을 수 없습니다 (home.sig_cards 연결 이름 확인)')

def cat_range_meta(cat):
    """홈 미리보기 메타 — '120–180분 · 300,000원부터'."""
    mins = [p['minutes'] for p in cat['programs']]
    return f'{min(mins)}–{max(mins)}분 · {w(min(p["price"] for p in cat["programs"]))}원부터'

# 시간 문구 변형들 — content의 시간 필드에서 파생
HOURS_LINE = f"월–금 {G['hours_weekday']} · 토 {G['hours_sat']} · 일 {G['hours_sun']}"
_sun_short = '휴무' if G['hours_sun'] == '정기휴무' else G['hours_sun']
HOURS_COMPACT = (f"월–금 {G['hours_weekday'].replace(' ', '')}"
                 f" · 토 {G['hours_sat'].replace(' ', '')} · 일 {_sun_short}")

ADDRESS_FULL = f"{G['address_road']}\n{G['address_building']} {G['address_room']}"
FOOTER_ADDR = f"{G['address_road']}, {G['address_room']}"

_SNS_GLYPH = {
    'insta': '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="5.2"/><circle cx="12" cy="12" r="4.1"/><circle cx="17.1" cy="6.9" r="1.15" fill="currentColor" stroke="none"/></svg>',
    'blog': '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"><path d="M15.5 5.1l3.4 3.4L8.4 19H5v-3.4L15.5 5.1z"/><path d="M13.4 7.2l3.4 3.4"/></svg>',
    'tel': '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.08 4.18 2 2 0 0 1 4.06 2h3a2 2 0 0 1 2 1.72c.13.96.35 1.9.66 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.31 1.85.53 2.81.66A2 2 0 0 1 22 16.92z"/></svg>',
}

def sns_icon(url, kind, label):
    """원형 라인 아이콘 — URL이 있으면 링크, 없으면 흐린 자리표시."""
    if url:
        return (f'<a class="sns-ic" href="{url}" target="_blank" rel="noopener"'
                f' aria-label="{label}" title="{label}">{_SNS_GLYPH[kind]}</a>')
    return f'<span class="sns-ic off" title="{label} — 준비 중" aria-hidden="true">{_SNS_GLYPH[kind]}</span>'


def _v(rel):
    """css/js 캐시버스터 — 파일 내용 해시 8자리."""
    fp = os.path.join(OUT, rel)
    return hashlib.md5(open(fp, 'rb').read()).hexdigest()[:8]

def _hours_spec(days, text):
    """'10:30 – 21:30' 형태에서 시각 2개를 추출. '정기휴무' 등 시각이 없으면 None(= 영업일 아님)."""
    times = re.findall(r'\d{1,2}:\d{2}', text)
    if len(times) < 2:
        return None
    return {'@type': 'OpeningHoursSpecification', 'dayOfWeek': days,
            'opens': times[0], 'closes': times[1]}

def jsonld(desc):
    data = {
        '@context': 'https://schema.org',
        '@type': 'DaySpa',
        'name': '고운:선',
        'url': SITE_URL,
        'description': desc,
        'image': f'{SITE_URL}/assets/img/hero.jpg',
        'telephone': '+82-' + PHONE[1:],
        'address': {
            '@type': 'PostalAddress',
            'streetAddress': f"{G['address_road']} {G['address_building']} {G['address_room']}",
            'addressLocality': '용인시 수지구',
            'addressRegion': '경기도',
            'addressCountry': 'KR',
        },
        'geo': {'@type': 'GeoCoordinates', 'latitude': 37.2977154, 'longitude': 127.0694204},
        'openingHoursSpecification': [s for s in (
            _hours_spec(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'], G['hours_weekday']),
            _hours_spec(['Saturday'], G['hours_sat']),
            _hours_spec(['Sunday'], G['hours_sun']),
        ) if s],
        'sameAs': [u for u in (G['insta_url'], G['blog_url']) if u],
    }
    if not data['sameAs']:
        del data['sameAs']
    return ('<script type="application/ld+json">'
            + json.dumps(data, ensure_ascii=False) + '</script>')

def canonical_url(path):
    """'index.html' → 'https://gowoonseon.com/', 그 외 → '/<파일명>'."""
    return SITE_URL + '/' + ('' if path == 'index.html' else path)

def head(title, desc, page, path=None):
    ld = ('\n' + jsonld(desc)) if page == 'home' else ''
    if NAVER_SITE_VERIFICATION:
        ld += f'\n<meta name="naver-site-verification" content="{NAVER_SITE_VERIFICATION}">'
    # 404 등 path 없는 페이지는 canonical/og:url 없이 + noindex
    if path:
        canon = (f'\n<link rel="canonical" href="{canonical_url(path)}">'
                 f'\n<meta property="og:url" content="{canonical_url(path)}">')
        robots = ''
    else:
        canon = ''
        robots = '\n<meta name="robots" content="noindex">'
    title, desc = html.escape(title, quote=False), html.escape(desc, quote=False)
    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">{robots}{canon}
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{SITE_URL}/assets/img/hero.jpg">
<meta property="og:type" content="website">
<meta property="og:site_name" content="고운:선">{ld}
<link rel="icon" type="image/png" href="assets/img/favicon.png?v={_v("assets/img/favicon.png")}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;500;600&family=Noto+Sans+KR:wght@300;400;500&family=Cormorant+Garamond:wght@500;600&display=swap">
<link rel="stylesheet" href="assets/css/style.css?v={_v("assets/css/style.css")}">
</head>
<body data-page="{page}">'''

def header(active, overlay=False):
    cls = 'site-header overlay' if overlay else 'site-header solid'
    def a(href, label, key):
        act = ' class="active"' if key == active else ''
        return f'<a href="{href}"{act}>{label}</a>'
    return f'''
<header class="{cls}">
  <div class="bar">
    <a href="index.html" class="wordmark" aria-label="고운:선 홈">
      <img class="mark" src="assets/img/logo.png" alt="">
      <span class="wtext">
        <span class="name">고운<span class="breath">:</span>선</span>
        <span class="sub">윤곽&amp;산모관리</span>
      </span>
    </a>
    <nav class="nav-links" aria-label="주 메뉴">
      {a('programs.html', '프로그램', 'programs')}
      {a('about.html', '고운:선 이야기', 'about')}
      {a('visit.html', '오시는 길', 'visit')}
      <a class="btn-reserve" href="{TEL}">전화 예약</a>
    </nav>
    <button class="menu-btn" id="menuOpen" aria-label="메뉴 열기">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M3 7h18M3 12h18M3 17h18"/></svg>
    </button>
  </div>
</header>
<div class="mobile-menu" id="mmenu">
  <div class="top">
    <span class="wordmark"><img class="mark" src="assets/img/logo.png" alt=""><span class="name">고운<span class="breath">:</span>선</span></span>
    <button class="menu-btn" id="menuClose" aria-label="메뉴 닫기">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M5 5l14 14M19 5L5 19"/></svg>
    </button>
  </div>
  <nav aria-label="모바일 메뉴">
    <a href="index.html"{' aria-current="page"' if active == 'index' else ''} style="--d: 0">홈</a>
    <span class="tick" aria-hidden="true" style="--d: 1"></span>
    <a href="programs.html"{' aria-current="page"' if active == 'programs' else ''} style="--d: 1">프로그램</a>
    <span class="tick" aria-hidden="true" style="--d: 2"></span>
    <a href="about.html"{' aria-current="page"' if active == 'about' else ''} style="--d: 2">고운:선 이야기</a>
    <span class="tick" aria-hidden="true" style="--d: 3"></span>
    <a href="visit.html"{' aria-current="page"' if active == 'visit' else ''} style="--d: 3">오시는 길</a>
  </nav>
  <div class="mfoot">
    <img src="assets/img/philosophy-hands.png" alt="" aria-hidden="true">
    <div class="hours">{HOURS_COMPACT}</div>
    <a class="call" href="{TEL}">전화 예약</a>
  </div>
</div>'''

FOOTER = f'''
<footer class="site-footer">
  <div class="container inner">
    <div class="id">
      <img src="assets/img/logo.png" alt="고운:선 엠블럼">
      <div>
        <div class="t">고운:선 윤곽&amp;산모관리</div>
        <div class="legal">{G['biz_no']} · {G['owner_name']} · {FOOTER_ADDR}</div>
      </div>
    </div>
    <div class="links">
      <a class="sns-ic" href="{TEL}" aria-label="전화 예약" title="전화 예약">{_SNS_GLYPH['tel']}</a>
      {sns_icon(G['blog_url'], 'blog', '네이버 블로그')}
      {sns_icon(G['insta_url'], 'insta', '인스타그램')}
    </div>
  </div>
</footer>
<dialog id="telDialog" class="tel-dialog" aria-labelledby="telDialogNum">
  <div class="eyebrow">RESERVATION</div>
  <div class="num" id="telDialogNum">{PHONE}</div>
  <div class="hrs">{HOURS_COMPACT}</div>
  <p>{G['notice_reservation']}
휴대폰에서는 전화 예약 버튼을 누르면 바로 연결됩니다.</p>
  <div class="row">
    <button id="telCopy" type="button">번호 복사</button>
    <button id="telClose" type="button">닫기</button>
  </div>
</dialog>
<button id="toTop" aria-label="맨 위로">↑</button>
<script src="assets/js/main.js?v={_v("assets/js/main.js")}"></script>
</body>
</html>'''

def chips(items):
    return '<div class="chips">' + ''.join(f'<span>{i}</span>' for i in items) + '</div>'

def price_block(minutes, price):
    return f'''<div class="price-block">
        <div class="dline" style="--min:{minutes}"></div>
        <div class="pb-row"><span class="min">{minutes}분</span><span class="price">{w(price)}원</span></div>
        <div class="tierline">{tier_prices(price)}</div>
      </div>'''

def prog(p):
    tag_html = f' <span class="tag">{p["tag"]}</span>' if p.get('tag') else ''
    desc_html = f'<p>{p["desc"]}</p>' if p.get('desc') else ''
    return f'''<article class="prog">
      <div class="head"><div class="name-row"><h3>{p['name']}</h3>{tag_html}</div></div>
      <div class="mid">{desc_html}{chips(p['components'])}</div>
      {price_block(p['minutes'], p['price'])}
    </article>'''

def reveal_spans(sentence):
    """진심의 문장 — 단어 수에 맞춰 view-timeline 구간을 균등 분배."""
    words = sentence.split()
    n = len(words)
    step = 66 / (n - 1) if n > 1 else 0
    spans = []
    for i, word in enumerate(words):
        s = round(4 + i * step)
        spans.append(f'<span class="w" style="animation-range: contain {s}% contain {s + 24}%;">{word}</span>')
    return '\n    '.join(spans)

def img_rel(path):
    """콘텐츠의 이미지 값('assets/img/x.jpg' 또는 'x.jpg') → 파일명."""
    return path.removeprefix('assets/img/')

def sig_card(ref):
    p = find_prog(ref['program'])
    return f'''<article class="sig-card">
        <img src="assets/img/{img_rel(ref['image'])}" alt="{ref.get('alt', '')}" loading="lazy">
        <div class="pad">
          <div class="row"><h3>{p['name']}</h3><span class="meta">{p['minutes']}분 · {w(p['price'])}원</span></div>
          <p>{p['desc']}</p>
          {chips(p['components'])}
        </div>
      </article>'''

def for_card(key, href):
    c = HOME['for_cards'][key]
    if key == 'scalp':
        slides = '\n            '.join(
            f'<img src="assets/img/{img_rel(s["image"])}" alt="{s.get("alt", "")}" loading="lazy">'
            for s in c['images'])
        imgs_html = f'''<div class="carousel">
            {slides}
          </div>
          <div class="dots" aria-hidden="true"><i class="active"></i><i></i></div>'''
    else:
        imgs_html = f'<img src="assets/img/{img_rel(c["image"])}" alt="{c.get("alt", "")}" loading="lazy">'
    return f'''<a class="for-card" href="{href}"{' data-carousel' if key == 'scalp' else ''}>
        <div class="imgwrap">{imgs_html}</div>
        <div class="pad"><h3>{c['title']}</h3><p>{c['desc']}</p><span class="more">{c['more']}</span></div>
      </a>'''

def drift_figures():
    figs, ghosts = [], []
    for f_ in HOME['space']['figures']:
        src = f'assets/img/{img_rel(f_["image"])}'
        figs.append(f'<figure><img src="{src}" alt="{f_.get("alt", "")}"><figcaption>{f_["caption"]}</figcaption></figure>')
        ghosts.append(f'<figure aria-hidden="true"><img src="{src}" alt=""><figcaption>{f_["caption"]}</figcaption></figure>')
    return '\n      '.join(figs + ghosts)

# ============================================================ index
_cat_by_id = {c['id']: c for c in CATEGORIES}
prev_items = []
for cat in CATEGORIES:
    eng_short = cat['eng'].split('·')[-1].strip()
    prev_items.append(
        f'<a class="prev-item" href="programs.html#{cat["id"]}"><span class="name">{cat["name"]}</span>'
        f'<span class="eng">{eng_short}</span><span class="desc">{cat["short_desc"]}</span>'
        f'<span class="meta">{cat_range_meta(cat)}</span><span class="arrow">›</span></a>')

home_fineprint = f"{PRICING['vat_note']} · 멤버십 충전 시 {MEM_DISCOUNT_SUMMARY} 혜택 · 예약제 운영"

index_body = f'''

<section class="hero">
  <img class="bg" src="assets/img/hero.jpg"
    srcset="assets/img/hero.jpg?v={_v("assets/img/hero.jpg")} 1024w, assets/img/hero-2x.jpg?v={_v("assets/img/hero-2x.jpg")} 2048w"
    sizes="100vw" alt="은은한 조명 아래 정돈된 고운:선의 스파 룸">
  <div class="shade" aria-hidden="true"></div>
  <div class="vertical-caption" aria-hidden="true">쉼 · 균형 · 본연의 선</div>
  <div class="copy container">
    <div class="eyebrow">PREMIUM WELLNESS SPA · YONGIN SUJI</div>
    <h1>{HOME['hero']['headline']}</h1>
    <p class="sub">{HOME['hero']['sub']}</p>
    <div class="actions">
      <a class="btn btn-light" href="programs.html">프로그램 보기</a>
      <a class="btn btn-ghost-light" href="{TEL}">전화 예약</a>
    </div>
  </div>
</section>

<section class="section">
  <div class="container story">
    <div class="eyebrow">OUR PHILOSOPHY</div>
    <h2 class="headline">{HOME['philosophy']['headline']}</h2>
    <div class="divider" aria-hidden="true"></div>
    <p class="body">{HOME['philosophy']['body']}</p>
    <img class="story-illust" src="assets/img/philosophy-hands.png" alt="어깨를 감싸는 따뜻한 손길 일러스트">
  </div>
</section>

<section class="reveal">
  <div class="pin">
    <p class="line">{reveal_spans(HOME['reveal_sentence'])}</p>
  </div>
</section>

<section class="section on-cream" style="background: var(--card);">
  <div class="container">
    <div class="section-head">
      <div class="eyebrow">SIGNATURE RITUALS</div>
      <h2 class="section-title">고운:선의 시그니처</h2>
    </div>
    <div class="sig-grid">
      {sig_card(HOME['sig_cards'][0])}
      {sig_card(HOME['sig_cards'][1])}
    </div>
  </div>
</section>

<section class="section">
  <div class="container">
    <div class="section-head center">
      <div class="eyebrow">FOR YOU</div>
      <h2 class="section-title">지금, 당신에게 필요한 쉼</h2>
    </div>
    <div class="for-grid">
      {for_card('mother', 'programs.html#mother')}
      {for_card('face', 'programs.html#face')}
      {for_card('focus', 'programs.html#focus')}
      {for_card('scalp', 'programs.html#face')}
    </div>
  </div>
</section>

<section class="section on-dark space-sec">
  <div class="container">
    <div class="space-head">
      <div class="section-head" style="margin: 0;">
        <div class="eyebrow">THE SPACE</div>
        <h2 class="section-title">{HOME['space']['title']}</h2>
      </div>
      <p>{HOME['space']['desc']}</p>
    </div>
  </div>
  <!-- 동선의 결 — 천천히 흐르는 무한 루프. 호버/터치 시 멈추고, 밀어서 직접 둘러볼 수 있다 -->
  <div class="drift" data-drift>
    <div class="drift-track">
      {drift_figures()}
    </div>
  </div>
</section>

<section class="section" style="background: var(--card);">
  <div class="container product-split">
    <img class="main" src="assets/img/products-set.jpg" alt="조시안로르 제품 라인" loading="lazy">
    <div class="text">
      <div class="eyebrow">JOSIANE LAURE, PARIS</div>
      <h2>{HOME['product']['headline']}</h2>
      <p class="desc">{HOME['product']['desc']}</p>
      <div class="cred">
        {''.join(f'<span>{c}</span>' for c in HOME['product']['creds'])}
      </div>
    </div>
  </div>
</section>

<section class="section">
  <div class="container">
    <div class="section-head">
      <div class="eyebrow">PROGRAMS</div>
      <h2 class="section-title">프로그램 안내</h2>
    </div>
    <div class="prev-list">
      {chr(10).join(prev_items)}
    </div>
    <p class="fineprint">{home_fineprint}</p>
  </div>
</section>

<section class="section visit-band on-dark">
  <div class="container inner">
    <div style="display: flex; flex-direction: column; gap: 18px;">
      <div class="eyebrow">VISIT US</div>
      <h2>{HOME['visit_band']['headline']}</h2>
      <p class="addr">{ADDRESS_FULL}</p>
      <div class="actions">
        <a class="btn btn-amber" href="{TEL}">전화 예약</a>
        <a class="btn btn-ghost-light" href="visit.html">오시는 길</a>
      </div>
    </div>
    <div class="hours">
      <span class="benefit">{HOME['visit_band']['benefit']}</span>
      <div class="row"><span>월 – 금</span><span>{G['hours_weekday']}</span></div>
      <div class="row"><span>토요일</span><span>{G['hours_sat']}</span></div>
      <div class="row off"><span>일요일</span><span>{G['hours_sun']}</span></div>
      <div class="note">{G['notice_reservation']}
{G['notice_pregnant']}
{G['notice_parking']}</div>
    </div>
  </div>
</section>'''

# ============================================================ programs
cat_sections = []
for cat in CATEGORIES:
    cards = '\n'.join(prog(p) for p in cat['programs'])
    cat_sections.append(f'''
<section class="category" id="{cat['id']}">
  <div class="watermark" aria-hidden="true">{cat['watermark']}</div>
  <div class="container">
    <div class="cat-head"><h2>{cat['name']}</h2><span class="eng">{cat['eng']}</span></div>
    <p class="cat-desc">{cat['desc']}</p>
    <div class="prog-list">{cards}</div>
  </div>
</section>''')

cat_nav = (''.join(f'<a href="#{c["id"]}">{c["nav_label"]}</a>' for c in CATEGORIES)
           + '<a href="#membership">멤버십</a>')

mem_how = ''.join(
    f'<li><span class="n">{i + 1:02d}</span><p>{s}</p></li>'
    for i, s in enumerate(MEMBERSHIPS['how']))
mem_cards = ''.join(f'''
      <div class="mem-card">
        <h3>{t['name']}</h3>
        <div class="amount">{w(t['amount'])}<span class="won">원</span></div>
        <div class="benefit">모든 프로그램 −{t['discount']}% 혜택</div>
        <p class="mdesc">{t['desc']}</p>
      </div>''' for t in MEMBERSHIPS['tiers'])
membership_section = f'''
<section class="section membership" id="membership">
  <div class="container">
    <div class="eyebrow">MEMBERSHIP</div>
    <h2 class="section-title">{MEMBERSHIPS['headline']}</h2>
    <p class="mem-lede">{MEMBERSHIPS['lede']}</p>
    <ol class="mem-how">{mem_how}</ol>
    <div class="mem-tiers">{mem_cards}
    </div>
    <p class="mem-note">{MEMBERSHIPS['note']}</p>
  </div>
</section>'''

cta_note = (f"{G['notice_reservation'].rstrip('.')} · {G['notice_pregnant'].rstrip('.')}")

programs_body = f'''
<div class="page-head container">
  <div class="eyebrow">PROGRAMS &amp; PRICING</div>
  <h1>프로그램 안내</h1>
  <p class="lede">{PROGRAMS_PAGE['lede']}</p>
</div>
<nav class="cat-nav" aria-label="프로그램 카테고리"><div class="row container">{cat_nav}</div></nav>
<div class="container" style="padding-top: 40px; padding-bottom: 46px;">
  <div class="tiers">
    {''.join(f'<a href="#membership"><span class="l">{t["name"]}</span><span class="v">−{t["discount"]}%</span></a>' for t in MEMBERSHIPS['tiers'])}
  </div>
  <div class="legend"><span class="dline" aria-hidden="true"></span><span>가는 선의 길이는 관리 시간을 뜻합니다 — 90분</span></div>
</div>
{''.join(cat_sections)}
{membership_section}
<div class="container"><p class="fineprint" style="padding: 34px 0 44px 0; margin: 0;">{PRICING['vat_note']}</p></div>
<section class="section cta-band on-dark">
  <div class="container inner">
    <div class="stem" aria-hidden="true"></div>
    <h2>{PROGRAMS_PAGE['cta_headline']}</h2>
    <div class="hours-line">{HOURS_LINE}</div>
    <a class="btn btn-amber" href="{TEL}">전화 예약</a>
    <p class="note">{cta_note}</p>
  </div>
</section>'''

# ============================================================ about
about_creds = ABOUT['director']['creds']
creds_html = '\n        '.join(
    f'<span class="c{" now" if i == len(about_creds) - 1 else ""}">{c}</span>'
    for i, c in enumerate(about_creds))

journey_html = '\n      '.join(
    f'<figure><img src="assets/img/{img_rel(j["image"])}" alt="{j.get("alt", "")}"><figcaption><span class="step">{j["title"]}</span><p>{j["text"]}</p></figcaption></figure>'
    for j in ABOUT['journey'])

_dir_photo = ABOUT['director'].get('photo') or ''
if _dir_photo:
    director_photo_html = (f'<img class="photo" src="assets/img/{img_rel(_dir_photo)}"'
                           f' alt="{ABOUT["director"].get("photo_alt") or "고운:선 원장"}">')
else:
    director_photo_html = '''<div class="photo-slot">
      <div class="ring" aria-hidden="true">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#84652F" stroke-width="1.2"><circle cx="12" cy="8.5" r="3.6"/><path d="M4.5 20c1.4-3.6 4.2-5.4 7.5-5.4s6.1 1.8 7.5 5.4"/></svg>
      </div>
      <span>원장 프로필 사진</span>
    </div>'''

about_body = f'''
<div class="page-head container">
  <div class="eyebrow">OUR STORY</div>
  <h1>고운:선 이야기</h1>
</div>
<section class="section container name-story" style="padding-top: 20px;">
  <img class="emblem" src="assets/img/logo.png" alt="고운:선 엠블럼">
  <h2>{ABOUT['name_story']['title']}</h2>
  <p class="body" style="max-width: 600px; font-weight: 300; line-height: 2.05; color: var(--body); white-space: pre-line;">{ABOUT['name_story']['body']}</p>
</section>

<section class="section" style="background: var(--card);">
  <div class="container director">
    {director_photo_html}
    <div style="display: flex; flex-direction: column; gap: 18px;">
      <div class="eyebrow">DIRECTOR</div>
      <h2>{ABOUT['director']['headline']}</h2>
      <p style="font-weight: 300; line-height: 2; color: var(--body); margin: 0;">{ABOUT['director']['body']}</p>
      <div class="creds">
        {creds_html}
      </div>
    </div>
  </div>
</section>

<section class="section">
  <div class="container product-split">
    <div class="text">
      <div class="eyebrow">JOSIANE LAURE, PARIS</div>
      <h2>{ABOUT['product']['headline']}</h2>
      <p class="desc">{ABOUT['product']['desc']}</p>
      <div class="thumb-row">
        <img src="assets/img/product-hand.jpg" alt="손 위의 조시안로르 세럼" loading="lazy">
        <img src="assets/img/product-macro.jpg" alt="캔들 곁의 오일 보틀" loading="lazy">
        <img src="assets/img/massage1.jpg" alt="제품을 사용하는 관리 장면" loading="lazy">
      </div>
    </div>
    <img class="main" src="assets/img/products-set.jpg" alt="조시안로르 제품 라인" loading="lazy">
  </div>
</section>

<section class="section on-dark">
  <div class="container">
    <div class="section-head center">
      <div class="eyebrow">THE JOURNEY</div>
      <h2 class="section-title">고운:선에서의 시간</h2>
    </div>
    <div class="journey-grid">
      {journey_html}
    </div>
  </div>
</section>'''

# ============================================================ visit
first_visit_html = '\n      '.join(
    f'<div class="step-card"><span class="n">{i + 1:02d}</span><h3>{s["title"]}</h3><p>{s["text"]}</p></div>'
    for i, s in enumerate(VISIT['first_visit']))

visit_body = f'''
<div class="page-head container">
  <div class="eyebrow">VISIT US</div>
  <h1>오시는 길</h1>
  <p class="lede">{VISIT['lede']}</p>
</div>
<section class="container visit-grid" style="padding-bottom: 72px;">
  <div class="map-embed">
    <iframe src="https://maps.google.com/maps?q=37.2977154,127.0694204&z=17&hl=ko&output=embed" title="고운:선 위치 — 경기 용인시 수지구 광교중앙로 310 신명프라자" loading="lazy" referrerpolicy="no-referrer-when-downgrade" allowfullscreen></iframe>
    <div class="map-links">
      <a href="https://naver.me/FriOoDXD" target="_blank" rel="noopener">네이버 지도에서 보기</a>
      <a href="https://place.map.kakao.com/1736168956" target="_blank" rel="noopener">카카오맵에서 보기</a>
    </div>
  </div>
  <div class="info-col">
    <div class="info-block">
      <span class="lbl">ADDRESS</span>
      <span class="big">{ADDRESS_FULL}</span>
      <span class="small">지번 · {G['address_jibun']}</span>
    </div>
    <div class="info-block">
      <span class="lbl">HOURS</span>
      <div class="hrow"><span>월 – 금</span><span>{G['hours_weekday']}</span></div>
      <div class="hrow"><span>토요일</span><span>{G['hours_sat']}</span></div>
      <div class="hrow off"><span>일요일</span><span>{G['hours_sun']}</span></div>
      <span class="benefit">{VISIT['hours_benefit']}</span>
    </div>
    <div class="info-block">
      <span class="lbl">PARKING</span>
      <span class="body-sm">{VISIT['parking']}</span>
    </div>
    <div class="info-block">
      <span class="lbl">RESERVATION</span>
      <span class="body-sm">{G['notice_reservation']}
{G['notice_pregnant']}</span>
      <a class="tel-btn" href="{TEL}">전화 예약 · {PHONE}</a>
      <div class="sns-row">
        {sns_icon(G['blog_url'], 'blog', '네이버 블로그')}
        {sns_icon(G['insta_url'], 'insta', '인스타그램')}
      </div>
    </div>
  </div>
</section>
<section class="section" style="background: var(--card);">
  <div class="container">
    <div class="section-head center">
      <div class="eyebrow">FIRST VISIT</div>
      <h2 class="section-title">처음 오시는 분께</h2>
    </div>
    <div class="steps-grid">
      {first_visit_html}
    </div>
  </div>
</section>'''

PAGES = [
    ('index.html', '고운:선 | 프리미엄 웰니스 스파 · 용인 수지 윤곽&산모관리',
     '몸과 마음의 균형을 되찾는 프라이빗 웰니스 스파. 윤곽관리 · 산모관리 · 헤드스파 · 수험생 케어 — 용인 수지구 상현동.',
     'home', True, index_body),
    ('programs.html', '프로그램 안내 | 고운:선',
     '전신·얼굴&헤드·부분바디·산모·수험생·웨딩 — 고운:선의 모든 프로그램과 가격 안내. 모든 가격은 부가세 포함입니다.',
     'programs', False, programs_body),
    ('about.html', '고운:선 이야기',
     '곱다, 그리고 선(線) — 고운:선의 철학, 원장, 조시안로르 제품, 그리고 공간의 이야기.',
     'about', False, about_body),
    ('visit.html', '오시는 길 | 고운:선',
     '경기 용인시 수지구 광교중앙로 310 신명프라자 4층 404호 · 예약제 운영 · 지하주차장 주차등록 지원.',
     'visit', False, visit_body),
]

notfound_body = '''
<div class="page-head container">
  <div class="eyebrow">404</div>
  <h1>찾으시는 페이지가 없습니다</h1>
  <p class="lede">주소가 바뀌었거나 잘못 입력된 것 같습니다.
아래에서 원하시는 곳으로 이동해 주세요.</p>
  <div class="map-links" style="justify-content: center; margin-top: 26px;">
    <a href="index.html">홈으로</a>
    <a href="programs.html">프로그램 안내</a>
  </div>
</div>'''
PAGES.append(('404.html', '페이지를 찾을 수 없습니다 | 고운:선',
              '요청하신 페이지가 존재하지 않습니다.', 'home', False, notfound_body))

for fname, title, desc, key, overlay, body in PAGES:
    path = None if fname == '404.html' else fname
    html_out = head(title, desc, key, path) + header(key, overlay) + '\n<main>' + body + '\n</main>\n' + FOOTER
    # 이미지도 내용 해시로 캐시버스팅 — 같은 파일명으로 교체해도 CDN/브라우저 캐시에 안 잡히게
    html_out = re.sub(r'src="assets/img/([^"?]+)"',
                      lambda m: f'src="assets/img/{m.group(1)}?v={_v("assets/img/" + m.group(1))}"', html_out)
    with open(os.path.join(OUT, fname), 'w', encoding='utf-8') as f:
        f.write(html_out)
    print('wrote', fname, len(html_out), 'bytes')

with open(os.path.join(OUT, 'robots.txt'), 'w', encoding='utf-8') as f:
    f.write(f'''User-agent: *
Disallow: /admin/

Sitemap: {SITE_URL}/sitemap.xml
''')
with open(os.path.join(OUT, 'sitemap.xml'), 'w', encoding='utf-8') as f:
    urls = '\n'.join(f'  <url><loc>{canonical_url(p[0])}</loc></url>'
                     for p in PAGES if p[0] != '404.html')
    f.write(f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>
''')
print('wrote robots.txt, sitemap.xml')
