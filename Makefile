# J&J GraphRAG Nexus - developer workflow
PYTHON ?= python3
VENV := backend/.venv
ifeq ($(OS),Windows_NT)
  VENV_BIN := $(VENV)/Scripts
else
  VENV_BIN := $(VENV)/bin
endif
PY := $(VENV_BIN)/python

.PHONY: help install install-backend install-frontend test backend frontend dev build reseed clean

help:
	@echo "make install   - create backend venv + install Python deps, npm install frontend"
	@echo "make test      - run the full backend pytest suite"
	@echo "make backend   - run FastAPI on http://localhost:8000"
	@echo "make frontend  - run Vite dev server on http://localhost:5173"
	@echo "make dev       - run backend + frontend together (./start.sh)"
	@echo "make build     - type-check and build the production frontend bundle"
	@echo "make reseed    - wipe the persisted graph and reload the golden J&J dataset"

install: install-backend install-frontend

install-backend:
	test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r backend/requirements.txt

install-frontend:
	cd frontend && npm install

test:
	cd backend && $(abspath $(PY)) -m pytest tests -v

backend:
	cd backend && ../$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev

dev:
	bash ./start.sh

build:
	cd frontend && npm run build

reseed:
	rm -f backend/data/jnj_graph.json
	@echo "Graph will be re-seeded from the golden dataset on next backend start."

clean:
	rm -rf frontend/dist frontend/node_modules .pytest_cache backend/.pytest_cache
