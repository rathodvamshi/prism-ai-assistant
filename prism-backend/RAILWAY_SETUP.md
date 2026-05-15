# Railway deployment setup

1. Create a new Railway project and connect your GitHub repository (backend folder `prism-backend`).

2. In Railway Project Settings -> Environment, add the following variables (from `prism-backend/.env.example`):

- `ENVIRONMENT=production`
- `MONGO_URI` (MongoDB Atlas connection string)
- `JWT_SECRET` (strong random value)
- `ENCRYPTION_KEY` (32+ chars)
- `REDIS_URL` (use `rediss://` for production)
- `CELERY_BROKER_URL` (optional, can be same as `REDIS_URL`)
- `SENTRY_DSN` (optional)
- `CORS_ORIGINS` (comma-separated list; include your Vercel frontend URL)
- `STORAGE_PROVIDER` (s3 or cloudinary)

3. Start command: Railway will use `Procfile` which defines:

```
web: gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --max-requests 500 --max-requests-jitter 50
worker: celery -A app.core.celery_app worker --loglevel=info --queues=email,default --concurrency=1
beat: celery -A app.core.celery_app beat --loglevel=info
```

4. Services:
- Add a Redis add-on (managed) and ensure it provides a `rediss://` URL.
- Add MongoDB Atlas (separate) and use the connection string for `MONGO_URI`.

5. Workers:
- Railway can run multiple services; configure separate service instances for `web` and `worker` if desired.

6. Verify after deploy:
- Visit `https://your-backend-url.up.railway.app/health` (should return 200)
- Check logs for Celery worker connection to Redis and tasks registration
