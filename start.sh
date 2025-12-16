#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if command -v git >/dev/null 2>&1 && git -C "${SCRIPT_DIR}" rev-parse --show-toplevel >/dev/null 2>&1; then
  ROOT_DIR="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel)"
else
  ROOT_DIR="${SCRIPT_DIR}"
fi

BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"

LOG_DIR="${ROOT_DIR}/.logs"
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
BACKEND_PID_FILE="${LOG_DIR}/backend.pid"
FRONTEND_PID_FILE="${LOG_DIR}/frontend.pid"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8011}"
FRONTEND_PORT="${FRONTEND_PORT:-5176}"
AUTO_KILL_PORTS="${AUTO_KILL_PORTS:-true}"

backend_pid=""
frontend_pid=""
tail_backend_pid=""
tail_frontend_pid=""
use_setsid="false"

die() {
  echo "Error: $*" >&2
  exit 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

ensure_port_free() {
  local port="$1"
  local label="${2:-service}"
  local allow_regex="${3:-}"
  if ! have_cmd lsof; then
    return 0
  fi
  if ! lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    return 0
  fi

  if [[ "${AUTO_KILL_PORTS}" != "true" ]]; then
    die "Port ${port} is already in use. Free it or change BACKEND_PORT/FRONTEND_PORT."
  fi

  local pids=""
  pids="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ' || true)"
  if [[ -z "${pids}" ]]; then
    die "Port ${port} is already in use. Free it or change BACKEND_PORT/FRONTEND_PORT."
  fi

  local pid cmd killed_any="false"
  for pid in ${pids}; do
    cmd="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
    if [[ -n "${allow_regex}" ]] && [[ "${cmd}" =~ ${allow_regex} ]]; then
      echo "Port ${port} is in use; stopping existing ${label} (pid=${pid}) ..."
      kill_tree "${pid}"
      killed_any="true"
    fi
  done

  if [[ "${killed_any}" != "true" ]]; then
    echo "Port ${port} is in use by:" >&2
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >&2 || true
    die "Port ${port} is already in use. Free it or change BACKEND_PORT/FRONTEND_PORT."
  fi

  # Wait a bit for graceful shutdown; force kill if still holding the port.
  local i
  for i in {1..50}; do
    if ! lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.1
  done

  local still_pids=""
  still_pids="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ' || true)"
  if [[ -n "${still_pids}" ]]; then
    for pid in ${still_pids}; do
      cmd="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
      if [[ -n "${allow_regex}" ]] && [[ "${cmd}" =~ ${allow_regex} ]]; then
        echo "Port ${port} still in use; force killing ${label} (pid=${pid}) ..." >&2
        kill -KILL "${pid}" >/dev/null 2>&1 || true
      fi
    done
  fi

  sleep 0.2
  if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port ${port} is still in use by:" >&2
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >&2 || true
    die "Port ${port} is still in use after attempting to stop existing processes."
  fi
}

is_running() {
  local pid="${1:-}"
  [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

read_pid_file() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]]; then
    tr -d ' \t\r\n' <"${pid_file}" || true
  fi
}

write_pid_file() {
  local pid_file="$1"
  local pid="$2"
  printf '%s' "${pid}" >"${pid_file}"
}

remove_pid_file() {
  local pid_file="$1"
  rm -f "${pid_file}" >/dev/null 2>&1 || true
}

kill_tree() {
  local pid="${1:-}"
  if [[ -z "${pid}" ]]; then
    return 0
  fi
  if ! is_running "${pid}"; then
    return 0
  fi

  local children=""
  if have_cmd pgrep; then
    children="$(pgrep -P "${pid}" 2>/dev/null || true)"
  else
    children="$(ps -eo pid=,ppid= | awk -v p="${pid}" '$2==p {print $1}')"
  fi

  local child
  for child in ${children}; do
    kill_tree "${child}"
  done

  kill -TERM "${pid}" >/dev/null 2>&1 || true
}

stop_service_if_running() {
  local label="$1"
  local pid_file="$2"
  local pid
  pid="$(read_pid_file "${pid_file}")"
  if [[ -z "${pid}" ]]; then
    return 0
  fi
  if ! is_running "${pid}"; then
    remove_pid_file "${pid_file}"
    return 0
  fi

  echo "Stopping existing ${label} (pid=${pid}) ..."
  kill_tree "${pid}"

  local i
  for i in {1..50}; do
    if ! is_running "${pid}"; then
      remove_pid_file "${pid_file}"
      return 0
    fi
    sleep 0.1
  done

  echo "Force killing ${label} (pid=${pid}) ..." >&2
  kill -KILL "${pid}" >/dev/null 2>&1 || true
  remove_pid_file "${pid_file}"
}

cleanup() {
  if is_running "${tail_frontend_pid}"; then
    kill -TERM "${tail_frontend_pid}" >/dev/null 2>&1 || true
  fi
  if is_running "${tail_backend_pid}"; then
    kill -TERM "${tail_backend_pid}" >/dev/null 2>&1 || true
  fi

  if is_running "${frontend_pid}"; then
    kill_tree "${frontend_pid}"
    remove_pid_file "${FRONTEND_PID_FILE}"
  fi
  if is_running "${backend_pid}"; then
    kill_tree "${backend_pid}"
    remove_pid_file "${BACKEND_PID_FILE}"
  fi
}

trap cleanup EXIT INT TERM

have_cmd npm || die "npm not found. Install Node.js first."
have_cmd python3 || die "python3 not found."

mkdir -p "${LOG_DIR}"

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  echo "Warning: ${ROOT_DIR}/.env not found (backend may fail to connect to DB)." >&2
fi

if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  die "Missing ${FRONTEND_DIR}/node_modules. Run: (cd \"${FRONTEND_DIR}\" && npm install)"
fi

venv_python=""
if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
  venv_python="${BACKEND_DIR}/.venv/bin/python"
elif [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  venv_python="${ROOT_DIR}/.venv/bin/python"
fi

if [[ -z "${venv_python}" ]]; then
  die "Python venv not found at ${BACKEND_DIR}/.venv or ${ROOT_DIR}/.venv. Create one and install backend deps."
fi

if [[ "${1:-}" == "stop" ]]; then
  stop_service_if_running "backend" "${BACKEND_PID_FILE}"
  stop_service_if_running "frontend" "${FRONTEND_PID_FILE}"
  exit 0
fi

stop_service_if_running "backend" "${BACKEND_PID_FILE}"
stop_service_if_running "frontend" "${FRONTEND_PID_FILE}"

ensure_port_free "${BACKEND_PORT}" "backend" "uvicorn[[:space:]].*backend\\.app\\.main:app"
ensure_port_free "${FRONTEND_PORT}" "frontend" "(npm[[:space:]].*run[[:space:]]dev|vite[[:space:]]|node[[:space:]].*vite)"

if have_cmd setsid; then
  use_setsid="true"
fi

echo "Logs:"
echo "  backend : ${BACKEND_LOG}"
echo "  frontend: ${FRONTEND_LOG}"
echo

echo "Starting backend on http://localhost:${BACKEND_PORT} ..."
if [[ "${use_setsid}" == "true" ]]; then
  setsid bash -lc "cd \"${ROOT_DIR}\" && exec \"${venv_python}\" -m uvicorn backend.app.main:app --host \"${BACKEND_HOST}\" --port \"${BACKEND_PORT}\" --reload" \
    >"${BACKEND_LOG}" 2>&1 &
else
  bash -lc "cd \"${ROOT_DIR}\" && exec \"${venv_python}\" -m uvicorn backend.app.main:app --host \"${BACKEND_HOST}\" --port \"${BACKEND_PORT}\" --reload" \
    >"${BACKEND_LOG}" 2>&1 &
fi
backend_pid="$!"
write_pid_file "${BACKEND_PID_FILE}" "${backend_pid}"

echo "Starting frontend on http://localhost:${FRONTEND_PORT} ..."
if [[ "${use_setsid}" == "true" ]]; then
  setsid bash -lc "cd \"${FRONTEND_DIR}\" && exec npm run dev -- --port \"${FRONTEND_PORT}\"" \
    >"${FRONTEND_LOG}" 2>&1 &
else
  bash -lc "cd \"${FRONTEND_DIR}\" && exec npm run dev -- --port \"${FRONTEND_PORT}\"" \
    >"${FRONTEND_LOG}" 2>&1 &
fi
frontend_pid="$!"
write_pid_file "${FRONTEND_PID_FILE}" "${frontend_pid}"

# Stream logs to terminal (and keep writing to the log files above).
tail -n 0 -F "${BACKEND_LOG}" 2>/dev/null | awk '{print "[backend] " $0; fflush();}' &
tail_backend_pid="$!"
tail -n 0 -F "${FRONTEND_LOG}" 2>/dev/null | awk '{print "[frontend] " $0; fflush();}' &
tail_frontend_pid="$!"

echo
echo "Started."
echo "  backend pid : ${backend_pid}"
echo "  frontend pid: ${frontend_pid}"
echo "Press Ctrl+C to stop both."

while :; do
  if ! kill -0 "${backend_pid}" >/dev/null 2>&1; then
    echo "Backend exited. See ${BACKEND_LOG}" >&2
    exit 1
  fi
  if ! kill -0 "${frontend_pid}" >/dev/null 2>&1; then
    echo "Frontend exited. See ${FRONTEND_LOG}" >&2
    exit 1
  fi
  sleep 1
done
