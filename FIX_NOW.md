# ⚡ FIX NOW - 2 MINUTES

## Problem
Render showing: `bash: line 1: web:: command not found`

## Solution
Set Start Command in Render Settings (without `web:` prefix)

---

## DO THIS NOW

### Step 1: Open Render Settings (30 seconds)
- Go: https://render.com/dashboard
- Click: prism-api
- Click: Settings

### Step 2: Set Start Command (1 minute)
Find: **Start Command** field

Clear it and paste:
```
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --max-requests 500 --max-requests-jitter 50
```

Click: **Save**

### Step 3: Deploy (30 seconds)
- Click: Deployments
- Click: Manual Deploy
- Wait: 10-15 minutes

---

## Expected Output
```
==> Build successful 🎉
==> Running 'gunicorn app.main:app...'
[SUCCESS] Application startup complete
```

---

## Verify
```bash
curl https://prism-api.onrender.com/health
# Expected: 200 OK
```

---

## Done! 🚀

Backend will be live in 15 minutes!
