# StockView — 백엔드(FastAPI) + 프론트엔드(Vite) 실행용 Makefile
# Windows에서도 동작하도록 셸을 Git Bash로 고정한다.
SHELL := bash

.DEFAULT_GOAL := dev
.PHONY: dev down backend frontend install help clean

PY := ./venv/Scripts/python.exe

## dev: 백엔드(:8000) + 프론트엔드(:5173) 동시 실행 (Ctrl-C로 둘 다 종료)
dev:
	@echo "▶ 백엔드 :8000  +  프론트엔드 :5173  동시 실행  (종료: Ctrl-C)"
	@trap 'kill 0' INT TERM; \
	( cd backend  && $(PY) -m uvicorn main:app --port 8000 --host 127.0.0.1 ) & \
	( cd frontend && npm run dev ) & \
	wait

## down: 실행 중인 백엔드(:8000)·프론트(:5173) 종료 (포트 점유 프로세스 kill)
down:
	@echo "▶ 서버 종료 중  (:8000, :5173)"
	@powershell -NoProfile -Command 'foreach ($$p in 8000,5173) { $$ids = Get-NetTCPConnection -LocalPort $$p -State Listen -ErrorAction SilentlyContinue | Select-Object -Expand OwningProcess -Unique; if ($$ids) { $$ids | ForEach-Object { Stop-Process -Id $$_ -Force -ErrorAction SilentlyContinue; Write-Host "  port $$p -> killed PID $$_" } } else { Write-Host "  port $$p : not running" } }'

## backend: 백엔드만 실행 (코드 변경 시 자동 리로드)
backend:
	cd backend && $(PY) -m uvicorn main:app --port 8000 --host 127.0.0.1 --reload

## frontend: 프론트엔드만 실행
frontend:
	cd frontend && npm run dev

## install: 백엔드 venv + 의존성, 프론트 node_modules 설치
install:
	cd backend  && python -m venv venv && $(PY) -m pip install -r requirements.txt
	cd frontend && npm install

## clean: 설치된 의존성(venv, node_modules) 삭제
clean:
	rm -rf backend/venv frontend/node_modules

## help: 사용 가능한 명령 목록
help:
	@echo "사용법:"
	@echo "  make           백엔드+프론트 동시 실행 (= make dev)"
	@echo "  make down      실행 중인 서버 종료 (:8000, :5173)"
	@echo "  make backend   백엔드만 (자동 리로드)"
	@echo "  make frontend  프론트만"
	@echo "  make install   의존성 설치 (최초 1회)"
	@echo "  make clean     venv/node_modules 삭제"
