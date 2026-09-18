#!/usr/bin/env bash
# 로컬에서 A/B/C/D + 화면(eodiego)을 한 번에 띄운다.
#
# 시크릿은 인자로 넘기지 않고 .env(=.gitignore 대상)에서만 읽는다.
# 명령줄이나 ps 출력에 서비스키가 남지 않도록 export 로만 전달한다.
#
#   cp .env.example .env   # 값 채우기
#   bash scripts/run_local.sh
#   bash scripts/run_local.sh --stop
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${ENV_FILE:-${root}/.env}"
run_dir="${root}/.run"
python_bin="${PYTHON_BIN:-python}"
node_bin_dir="${NODE_BIN_DIR:-}"

stop_all() {
  for name in A B C D web; do
    pid_file="${run_dir}/${name}.pid"
    [[ -f "${pid_file}" ]] || continue
    pid="$(cat "${pid_file}")"
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      echo "stopped ${name} (pid ${pid})"
    fi
    rm -f "${pid_file}"
  done
}

if [[ "${1:-}" == "--stop" ]]; then
  stop_all
  exit 0
fi

if [[ ! -f "${env_file}" ]]; then
  echo "환경변수 파일이 없습니다: ${env_file}" >&2
  echo "  cp .env.example .env  후 값을 채워주세요." >&2
  exit 78
fi

# .env 로드. 주석/빈 줄은 건너뛰고, 값은 그대로(따옴표 없이) 넣는다.
set -a
# shellcheck disable=SC1090
source "${env_file}"
set +a

if [[ "${USE_MOCK:-true}" == "false" && -z "${KTO_SERVICE_KEY:-}" ]]; then
  echo "USE_MOCK=false 인데 KTO_SERVICE_KEY 가 비어 있습니다." >&2
  exit 78
fi

mkdir -p "${run_dir}"
export PYTHONPATH="${root}"
# DB는 MySQL이고 접속 정보는 .env(DB_HOST/DB_NAME/DB_USER/DB_PASSWORD)에서만
# 읽는다. 여기서 따로 덮어쓰지 않는다.

start_service() {
  local name="$1" module="$2" port="$3"
  "${python_bin}" -m uvicorn "${module}" --host 127.0.0.1 --port "${port}" \
    --log-level "${LOG_LEVEL:-info}" > "${run_dir}/${name}.log" 2>&1 &
  echo $! > "${run_dir}/${name}.pid"
  echo "  ${name}  http://127.0.0.1:${port}"
}

echo "USE_MOCK=${USE_MOCK:-true} (false = 실제 한국관광공사 API 호출)"
echo "서버 기동:"
start_service A A_backend.main:app "${A_PORT:-8000}"
start_service B B_openapi.main:app "${B_PORT:-8001}"
start_service C C_ai_planner.main:app "${C_PORT:-8002}"
start_service D D_frontend.main:app "${D_PORT:-8003}"

# 화면(eodiego) 위치. 백엔드가 저장소 안(eodiego/PythonServer)으로 들어오면서
# 화면은 이 폴더의 상위가 됐다. 예전처럼 하위에 둔 구조도 계속 지원한다.
web_dir="${WEB_DIR:-}"
if [[ -z "${web_dir}" ]]; then
  for candidate in "${root}/.." "${root}/eodiego"; do
    if [[ -f "${candidate}/package.json" ]]; then
      web_dir="$(cd "${candidate}" && pwd)"
      break
    fi
  done
fi

if [[ -n "${web_dir}" && -x "${web_dir}/node_modules/.bin/vite" ]]; then
  [[ -n "${node_bin_dir}" ]] && export PATH="${node_bin_dir}:${PATH}"
  (
    cd "${web_dir}"
    export WRANGLER_LOG_PATH=".wrangler/logs" WRANGLER_WRITE_LOGS=false
    ./node_modules/.bin/vite --port "${WEB_PORT:-5173}" --strictPort \
      > "${run_dir}/web.log" 2>&1 &
    echo $! > "${run_dir}/web.pid"
  )
  echo "  화면 http://localhost:${WEB_PORT:-5173}  (${web_dir})"
elif [[ -n "${web_dir}" ]]; then
  echo "  (${web_dir}/node_modules 가 없어 화면은 건너뜁니다: 그 폴더에서 npm ci)"
else
  echo "  (화면 폴더를 찾지 못해 건너뜁니다. WEB_DIR 로 지정하세요)"
fi

echo
echo "로그: ${run_dir}/*.log     내리기: bash scripts/run_local.sh --stop"
