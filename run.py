"""StockView 실행 헬퍼 — 백엔드(FastAPI) + 프론트엔드(Vite) 동시 실행/종료.

Windows의 make 셸 문제(bash vs cmd)를 피하려고 실행 로직을 파이썬으로 옮겼다.
OS·셸에 상관없이 동작한다.

  python run.py        # 동시 실행 (Ctrl-C로 둘 다 종료)
  python run.py down   # 포트(:8000,:5173) 점유 프로세스 종료
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORTS = [8000, 5173]

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _backend_python() -> str:
    venv_py = ROOT / "backend" / "venv" / "Scripts" / "python.exe"
    return str(venv_py) if venv_py.exists() else sys.executable


def up() -> None:
    print("백엔드 :8000  +  프론트엔드 :5173  동시 실행  (종료: Ctrl-C)")
    backend = subprocess.Popen(
        [_backend_python(), "-m", "uvicorn", "main:app",
         "--port", "8000", "--host", "127.0.0.1"],
        cwd=str(ROOT / "backend"),
    )
    frontend = subprocess.Popen(
        "npm run dev", cwd=str(ROOT / "frontend"), shell=True,
    )
    try:
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in (frontend, backend):
            try:
                p.terminate()
            except Exception:
                pass
        down()  # 남은 포트 점유 프로세스까지 확실히 정리


def down() -> None:
    print("서버 종료 중  (:8000, :5173)")
    if os.name == "nt":
        try:
            out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
        except Exception as e:
            print("  netstat 실패:", e)
            return
        killed = False
        for port in PORTS:
            pids = {
                line.split()[-1]
                for line in out.splitlines()
                if f":{port} " in line and "LISTENING" in line
            }
            for pid in pids:
                subprocess.run(["taskkill", "/PID", pid, "/F"],
                               capture_output=True)
                print(f"  :{port} 종료 (PID {pid})")
                killed = True
        if not killed:
            print("  실행 중인 서버가 없습니다")
    else:
        subprocess.run(
            "kill $(lsof -t -i:8000 -i:5173) 2>/dev/null", shell=True
        )


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "up"
    (down if cmd == "down" else up)()
