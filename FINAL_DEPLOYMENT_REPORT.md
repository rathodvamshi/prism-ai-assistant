# Final Production Deployment Report

## 1) Architecture overview
- Frontend: React + Vite hosted on Vercel.
- Backend: FastAPI app hosted on Railway (Gunicorn + Uvicorn worker from Procfile).
- Database: MongoDB Atlas (primary data).
- Cache/queues: Redis (production should be rediss://), Celery worker + beat.
- Upload storage: Cloudinary or AWS S3 via `app/utils/storage.py` abstraction.
- Monitoring: Sentry (optional) via `SENTRY_DSN`.

## 2) Required environment variables

### Frontend (Vercel)
- `VITE_API_URL` (or `NEXT_PUBLIC_API_URL` for Next.js)

### Backend (Railway)
- `ENVIRONMENT=production`
- `MONGO_URI`
- `JWT_SECRET`
- `ENCRYPTION_KEY` (32+ chars)
- `CORS_ORIGINS` (must include Vercel URL)
- `SESSION_COOKIE_SECURE=true`
- `SESSION_COOKIE_SAMESITE=lax` (or `strict` if compatible)
- `REDIS_URL` (use `rediss://` in production)
- `CELERY_BROKER_URL` (optional; defaults to `REDIS_URL`)
- `GROQ_API_KEY` / `OPENAI_API_KEY` (if used)
- `SENTRY_DSN` (optional)
- Storage:
  - S3: `STORAGE_PROVIDER=s3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET`, `AWS_REGION`
  - Cloudinary: `STORAGE_PROVIDER=cloudinary`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`

## 3) Deployment steps
1. Deploy backend to Railway with env vars from `prism-backend/.env.example`.
2. Deploy frontend to Vercel with `VITE_API_URL` pointing to Railway backend URL.
3. Configure MongoDB Atlas user/network access and set `MONGO_URI` in Railway.
4. Configure Redis (managed) and set `REDIS_URL`/`CELERY_BROKER_URL`.
5. Enable GitHub Actions CI and set secrets `PROD_BACKEND_URL`, `PROD_FRONTEND_URL`.

## 4) Railway service setup
- Web: from `Procfile` web process (Gunicorn+Uvicorn).
- Worker: Celery worker process.
- Beat: Celery scheduler process.
- Recommended: separate Railway services for web and workers for better scaling.

## 5) Vercel setup
- Build command: `npm run build`.
- Output: `dist`.
- SPA routing: `Frontend/vercel.json` rewrite to `index.html`.

## 6) Redis setup
- Use managed Redis with TLS (`rediss://`).
- Ensure Celery broker and backend use same managed Redis unless dedicated queues are required.

## 7) Atlas setup
- Use production cluster (M10+ recommended).
- Create least-privilege DB user.
- Restrict network access to Railway egress / approved IP ranges.

## 8) Troubleshooting guide
- Frontend white screen: verify `VITE_API_URL` points to Railway URL and build logs are clean.
- CORS blocked: ensure `CORS_ORIGINS` includes exact Vercel domain.
- Celery unhealthy: production requires `rediss://` URL.
- Mongo issues: verify Atlas credentials, network access, and retryWrites params.
- 404 on refresh: verify `Frontend/vercel.json` rewrite exists.

## 9) Scaling recommendations
- Scale Railway web and worker separately.
- Add read-heavy caches in Redis with TTL.
- Track slow endpoints and Mongo query latency using APM + logs.
- Keep background jobs off web process.
