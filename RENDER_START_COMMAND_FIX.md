# 🔧 RENDER START COMMAND FIX

## Problem
Render is including the `web:` prefix from Procfile in the command:
```
bash: line 1: web:: command not found
```

## Root Cause
Render is reading the Procfile but interpreting it incorrectly. It's including `web:` in the actual command instead of just using the command part.

## Solution
Set the Start Command directly in Render Settings **without** the `web:` prefix.

---

## DO THIS NOW (2 minutes)

### Step 1: Go to Render Settings
1. Go: https://render.com/dashboard
2. Click: prism-api service
3. Click: **Settings** tab
4. Scroll down to: **Start Command**

### Step 2: Set the Correct Command
**Clear the current command** and enter:
```
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --max-requests 500 --max-requests-jitter 50
```

**Important**: Do NOT include `web:` prefix

### Step 3: Save
Click: **Save**

### Step 4: Deploy
1. Click: **Deployments** tab
2. Click: **Manual Deploy**
3. Wait: 10-15 minutes

---

## Expected Success
```
==> Build successful 🎉
==> Deploying...
==> Setting WEB_CONCURRENCY=1 by default
==> Running 'gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --max-requests 500 --max-requests-jitter 50'
[SUCCESS] Application startup complete
```

---

## Why This Happens

Render has two ways to configure the start command:

1. **Procfile** - For Heroku-style deployments
2. **Settings** - For direct configuration

When both exist, Render sometimes gets confused and includes the Procfile prefix in the command.

The solution is to explicitly set it in Settings.

---

## Procfile vs Settings

| Method | Format | Render Behavior |
|--------|--------|-----------------|
| Procfile | `web: command` | Sometimes includes `web:` in command |
| Settings | `command` | Always correct |

**Recommendation**: Use Settings for Render

---

## Status
✅ **READY TO DEPLOY** - Just set the start command in Settings

---

## Quick Checklist

- [ ] Go to Render Settings
- [ ] Find Start Command field
- [ ] Clear current value
- [ ] Enter: `gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --max-requests 500 --max-requests-jitter 50`
- [ ] Click Save
- [ ] Click Manual Deploy
- [ ] Wait 10-15 minutes
- [ ] Verify: `curl https://prism-api.onrender.com/health`

---

## If It Still Fails

### Check 1: Verify Command is Set
1. Go to Settings
2. Scroll to Start Command
3. Verify it shows the full command WITHOUT `web:`

### Check 2: Clear Build Cache
1. Go to Settings
2. Scroll to "Clear build cache"
3. Click it
4. Manual Deploy again

### Check 3: Check Environment Variables
1. Go to Settings → Environment Variables
2. Verify all variables are set:
   - MONGODB_URI
   - REDIS_URL
   - GROQ_API_KEY
   - OPENAI_API_KEY
   - etc.

---

## Time Estimate
- Set command: 1 minute
- Deploy: 10-15 minutes
- Verify: 1 minute
- **Total: 15 minutes**

---

## Next Steps

1. **Set the start command** in Render Settings (without `web:` prefix)
2. **Click Manual Deploy**
3. **Wait for deployment**
4. **Verify with curl**

That's it! Backend will be live! 🚀
