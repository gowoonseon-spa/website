# 고운:선 — 웹사이트

용인 수지 프리미엄 웰니스 스파 **고운:선 윤곽&산모관리** 공식 웹사이트.

## 구조

- `content/content.json` — 사이트의 모든 카피·가격·영업시간·연락처. **/admin(Decap CMS)에서 편집.**
- `tools/build_site.py` — 정적 빌더. content.json → `site/*.html` (레이아웃·파생 문구·검증 담당).
- `site/` — 배포 산출물 + 정적 자산 + `/admin`.
- `netlify.toml` — 빌드 명령. push 되면 Netlify가 자동 빌드·배포.

## 운영 규칙

- `site/*.html`은 빌드 산출물 — **직접 수정 금지**, 항상 빌더·css·js를 수정.
- 콘텐츠 수정은 /admin에서. 빌더 검증이 에러를 내면 배포가 거부되고 사이트는 이전 상태 유지.
- 구조 변경(카테고리·프로그램 수 등)은 개발 작업: 빌더 `STRUCTURE` + `site/admin/config.yml` 필드 선언 + 프리뷰 템플릿 3곳 동기화 필요.

로컬 빌드: `python3 tools/build_site.py` (외부 의존성 없음, Python 3.12)
