# 🔄 CLEAR RENDER BUILD CACHE

## Problem
Render is still using old code even though we fixed it. The fix is committed but Render's cache is serving the old version.

## Solution
Clear the Render build cache and redeploy.

---

## DO THIS NOW (3 minutes)

### Step 1: Go to Render Settings
1. Go: https://render.com/dashboard
2. Click: prism-api service
3. Click: **Settings** tab

### Step 2: Clear Build Cache
1. Scroll down to: **Clear build cache**
2. Click: **Clear build cache** button
3. Confirm if prompted

### Step 3: Deploy
1. Click: **Deployments** tab
2. Click: **Manual Deploy**
3. Wait: 10-15 minutes

### Step 4: Verify
```bash
curl https://prism-api.onrender.com/health
# Expected: 200 OK
```

---

## Expected Success
```
==> Build successful 🎉
==> Deploying...
==> Running 'gunicorn app.main:app...'
[SUCCESS] Application startup complete
```

---

## Why This Happens

Render caches builds to speed up deployments. When we fix code locally and commit it, Render sometimes uses the cached version instead of rebuilding.

**Solution**: Clear the cache to force a fresh build.

---

## Checklist
- [ ] Went to Render Settings
- [ ] Clicked "Clear build cache"
- [ ] Clicked Manual Deploy
- [ ] Waited 10-15 minutes
- [ ] Verified with curl (got 200 OK)

---

## Status
✅ **READY TO DEPLOY** - Just clear cache and redeploy

---

## Time Estimate
- Clear cache: 1 minute
- Deploy: 10-15 minutes
- Verify: 1 minute
- **Total: 15 minutes**

---

## Done! 🚀

Backend will be live in 15 minutes!
