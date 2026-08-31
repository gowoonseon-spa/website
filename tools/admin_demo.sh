#!/bin/zsh
# 고운:선 어드민 로컬 시연 — 계정·인증 없이 그 자리에서 콘텐츠 수정을 보여준다.
#   실행: bash tools/admin_demo.sh
#   어드민: http://localhost:8741/admin/   (저장 → 자동 재빌드 → 사이트 새로고침)
#   사이트: http://localhost:8741/
set -e
cd "$(dirname "$0")/.."

python3 tools/build_site.py

cleanup() { kill 0 2>/dev/null; }
trap cleanup EXIT INT TERM

# Decap 로컬 백엔드 프록시 (8081) — 저장 시 content/content.json에 직접 쓴다
npx -y decap-server &

# 사이트 서버
python3 -m http.server 8741 -d site &

sleep 1
echo ""
echo "  어드민 → http://localhost:8741/admin/"
echo "  사이트 → http://localhost:8741/"
echo "  (Ctrl+C로 종료)"
echo ""

# content.json 저장 감지 → 자동 재빌드 (검증 실패 시 사이트는 이전 상태 유지)
python3 - <<'EOF'
import os, time, subprocess
p = 'content/content.json'
m = os.path.getmtime(p)
while True:
    time.sleep(1)
    try:
        n = os.path.getmtime(p)
    except FileNotFoundError:
        continue
    if n != m:
        m = n
        print('--- content.json 변경 감지 → 재빌드 ---')
        subprocess.run(['python3', 'tools/build_site.py'])
EOF
