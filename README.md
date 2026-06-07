# APTRADES v2

Breeze-only APTRADES v2 monorepo.

## Stack

- Backend: Flask 3
- Frontend: React + Vite + TypeScript
- Broker: ICICI Breeze only

## Phase 1

This repository currently contains:

- Flask app factory
- `GET /api/health`
- `GET /api/health/readiness`
- Placeholder Breeze service modules
- React application shell with MVP navigation
- Dashboard backend health panel

## Local Commands

### Backend

```powershell
cd backend
python -m pip install -e .[dev]
python -m pytest
python run.py
```

### Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run build
```
