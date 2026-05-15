# Deployment Quick Guide

This repository contains the PRISM frontend and backend. Use the following quick checklist to deploy to Vercel (frontend), Railway (backend), and MongoDB Atlas (database).

Frontend (Vercel):
- Connect `Frontend` repo to Vercel and set production branch to `main`.
- Set environment variable from `Frontend/.env.example` (VITE_API_URL or NEXT_PUBLIC_API_URL).
- Build command: `npm run build` (Vite/React) or `next build` (Next.js).
- Output directory: `dist` for Vite, Next.js handled automatically.
- Add `Frontend/vercel.json` (already present) for SPA routing if using Vite/CRA.

Backend (Railway):
- Railway will use `prism-backend/Procfile` which runs Gunicorn with Uvicorn worker.
- Add env vars from `prism-backend/.env.example` in Railway project settings.
- Ensure `requirements.txt` is up-to-date and includes `gunicorn` and `uvicorn`.

Database (MongoDB Atlas):
- Create production cluster (M10+), create DB user, whitelist Railway IPs or enable VPC peering.
- Use the provided `MONGO_URI` in Railway environment variables.

Checklist before deploying:
- Remove local secrets and `.env` from repo.
- Commit only `.env.example` files.
- Run `npm run build` locally and test the production build.
- Verify `/health` endpoint on backend after deploy.

Required environment variables (summary)
- Backend (`prism-backend` Railway project):
	- `ENVIRONMENT=production`
	- `PORT` (Railway sets this automatically)
	- `MONGO_URI` (MongoDB Atlas connection string)
	- `JWT_SECRET`
	- `ENCRYPTION_KEY` (32+ chars)
	- `GROQ_API_KEY` / `OPENAI_API_KEY` (if used)
	- `REDIS_URL` (use `rediss://` in production)
	- `CELERY_BROKER_URL` (optional, defaults to `REDIS_URL`)
	- `SESSION_COOKIE_SECURE=true`
	- `CORS_ORIGINS` (comma-separated, include Vercel URL)
	- `SENTRY_DSN` (optional)
	- `STORAGE_PROVIDER` (s3 or cloudinary)
	- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET`, `AWS_REGION` (if using S3)
	- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` (if using Cloudinary)

- Frontend (Vercel project):
	- `VITE_API_URL` or `NEXT_PUBLIC_API_URL` (https://your-backend-url.up.railway.app)

Deployment commands (local verification)
```bash
# Frontend build
cd Frontend
npm ci
npm run build

# Backend local run (use virtualenv)
cd prism-backend
python -m venv .venv
. .venv/Scripts/Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
# Run with gunicorn (matches Procfile)
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 1
```

If you want, I can:
- Add or update CI workflow files, or
- Run a local build and test the backend `/health` endpoint.