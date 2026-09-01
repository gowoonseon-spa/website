#!/bin/zsh
# 개발 repo → 프로덕션 repo(gowoonseon-spa/website) 동기화 + 푸시.
# 사용: bash tools/sync_prod.sh "커밋 메시지"
# 하는 일: content/tools/site/netlify.toml rsync → prod config를 프로덕션형으로 변환
# (backend 주석 정리 + local_backend 제거) → prod에서 빌드 검증 → 커밋 → push (Netlify 자동 배포).
set -e
cd "$(dirname "$0")/.."
MSG="${1:?커밋 메시지를 넘겨주세요}"
PROD="$HOME/orca/projects/gowonsun-prod"

rsync -a --delete --exclude '.DS_Store' --exclude '__pycache__' --exclude 'deploy.sh' \
  --exclude '.git' --exclude 'README.md' --exclude '.gitignore' \
  content tools site netlify.toml "$PROD/"

python3 - "$PROD/site/admin/config.yml" <<'EOF'
import re, sys
p = sys.argv[1]
s = open(p).read()
s = re.sub(
    r'# 고운:선 콘텐츠 관리 \(Decap CMS\)\n(#[^\n]*\n)*',
    '# 고운:선 콘텐츠 관리 (Decap CMS) — 프로덕션 설정\n'
    '# 개발용 로컬 시연 설정(local_backend)은 개발 repo 쪽 config.yml에만 있음\n', s, count=1)
s = re.sub(r'^  repo: gowoonseon-spa/website.*$', '  repo: gowoonseon-spa/website', s, flags=re.M)
s = re.sub(r'\nlocal_backend: true\n', '\n', s)
assert not re.search(r'^local_backend', s, re.M), 'local_backend가 남아 있음'
assert 'repo: gowoonseon-spa/website' in s
open(p, 'w').write(s)
EOF

cd "$PROD"
python3 tools/build_site.py >/dev/null
git add -A
if git diff --cached --quiet; then echo "변경 없음"; exit 0; fi
git -c user.name='Jinyoung Jang' -c user.email='sinclairjang@gmail.com' commit -q -m "$MSG"
git push -q origin main
echo "푸시됨 → Netlify가 gowoonseon.com에 자동 배포합니다 (1~2분)"
