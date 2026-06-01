# StockView — 백엔드(FastAPI) + 프론트엔드(Vite) 실행용 Makefile
# 실행 로직은 run.py(파이썬)에 있어 OS·셸에 상관없이 동작한다.

.DEFAULT_GOAL := dev
.PHONY: dev down backend frontend install help

# 기본 명령: 그냥 `make` 만 치면 백엔드+프론트가 동시에 실행된다.
## dev: 백엔드(:8000) + 프론트엔드(:5173) 동시 실행 (Ctrl-C로 둘 다 종료)
dev:
	python run.py up

## down: 실행 중인 백엔드(:8000)·프론트(:5173) 종료
down:
	python run.py down

## recommend: 오늘의 추천 배치 즉시 실행 (recommendations.json 갱신)
recommend:
	cd backend && venv\Scripts\python.exe recommend.py

## backend: 백엔드만 실행 (코드 변경 시 자동 리로드)
backend:
	cd backend && venv\Scripts\python.exe -m uvicorn main:app --port 8000 --host 127.0.0.1 --reload

## frontend: 프론트엔드만 실행
frontend:
	cd frontend && npm run dev

## install: 백엔드 venv + 의존성, 프론트 node_modules 설치
install:
	cd backend && python -m venv venv && venv\Scripts\python.exe -m pip install -r requirements.txt
	cd frontend && npm install

## help: 사용 가능한 명령 목록
help:
	@echo make           백엔드+프론트 동시 실행
	@echo make down      실행 중인 서버 종료 (:8000, :5173)
	@echo make backend   백엔드만 (자동 리로드)
	@echo make frontend  프론트만
	@echo make install   의존성 설치 (최초 1회)
