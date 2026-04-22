# 🚀 DEPLOYMENT CHECKLIST - FINAL STEPS

## Status: READY FOR PRODUCTION

All code is clean, optimized, and tested. Follow these steps to deploy.

---

## STEP 1: Backend Deployment (Render) - 15 minutes

### 1.1 Set Start Command in Render
```
URL: https://render.com/dashboard
Service: prism-api
Tab: Settings
Field: Start Command

PASTE THIS:
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --max-requests 500 --max-requests-jitter 50 --preload-app

Click: Save
```

### 1.2 Verify Environment Variables
Go to Render Settings → Environment Variables. Ensure these are set:
- `MONGODB_URI` ✓
- `REDIS_URL` ✓
- `GROQ_API_KEY` ✓
- `OPENAI_API_KEY` ✓
- `SENDGRID_API_KEY` ✓
- `PINECONE_API_KEY` ✓
- `NEO4J_URI` ✓
- `NEO4J_USERNAME` ✓
- `NEO4J_PASSWORD` ✓
- `JWT_SECRET_KEY` ✓
- `ENVIRONMENT` = `production` ✓

### 1.3 Trigger Manual Deploy
```
URL: https://render.com/dashboard
Service: prism-api
Tab: Deployments
Click: Manual Deploy
Wait: 10-15 minutes
```

### 1.4 Monitor Build
Watch the logs for:
- ✅ Build successful
- ✅ Deployment started
- ✅ App running on port $PORT
- ✅ MongoDB connected
- ✅ Redis connected

### 1.5 Verify Backend is Live
```bash
curl https://prism-api.onrender.com/health
# Expected: 200 OK with JSON response
```

---

## STEP 2: Frontend Deployment (Vercel) - 5 minutes

### 2.1 Set Environment Variables in Vercel
```
URL: https://vercel.com/dashboard
Project: prism-ai-studio
Tab: Settings → Environment Variables

Add/Update:
VITE_API_URL = https://prism-api.onrender.com
```

### 2.2 Deploy to Vercel
```bash
# Option 1: Push to main branch (auto-deploys)
git push origin main

# Option 2: Manual deploy from Vercel dashboard
URL: https://vercel.com/dashboard
Project: prism-ai-studio
Click: Deployments
Click: Deploy
```

### 2.3 Verify Frontend is Live
```
URL: https://prism-ai-studio.vercel.app
Expected: App loads, can chat, media displays correctly
```

---

## STEP 3: Connect Services - 2 minutes

### 3.1 Update CORS in Render
```
URL: https://render.com/dashboard
Service: prism-api
Tab: Settings
Environment Variables

Update:
CORS_ORIGINS = https://prism-ai-studio.vercel.app
```

### 3.2 Verify Connection
```bash
# Test from frontend
1. Open https://prism-ai-studio.vercel.app
2. Send a message
3. Check browser console for errors
4. Expected: Message sent successfully
```

---

## STEP 4: Test Critical Features

### 4.1 Chat & Streaming
- [ ] Send message
- [ ] Receive streaming response
- [ ] Message saves to database

### 4.2 Media Display
- [ ] Request video search
- [ ] Video card displays
- [ ] Click play button
- [ ] Video plays in iframe
- [ ] Refresh page
- [ ] Video card still displays (FIXED!)

### 4.3 Authentication
- [ ] Sign up new user
- [ ] Login
- [ ] Logout
- [ ] Session persists

### 4.4 Performance
- [ ] First message < 3 seconds
- [ ] Streaming smooth
- [ ] No console errors
- [ ] Memory usage stable

---

## STEP 5: Monitor & Verify

### 5.1 Backend Logs
```
URL: https://render.com/dashboard
Service: prism-api
Tab: Logs

Look for:
✅ Configuration validation passed
✅ MongoDB connected
✅ Redis warmed up
✅ Groq Pool pre-initialized
✅ No duplicate logs
✅ No errors
```

### 5.2 Frontend Console
```
Open: https://prism-ai-studio.vercel.app
Press: F12 (Developer Tools)
Tab: Console

Look for:
✅ No errors
✅ No CORS warnings
✅ API calls successful
```

### 5.3 Database
```
MongoDB Atlas:
- Check collections exist
- Check data is being saved
- Check indexes are created

Redis:
- Check connection is active
- Check cache is working
```

---

## TROUBLESHOOTING

### Backend won't start
```
Check:
1. Start command is set correctly in Render Settings
2. All environment variables are set
3. Build logs for errors
4. MongoDB connection string is valid
5. Redis connection string is valid
```

### Media cards don't display
```
Check:
1. Frontend is deployed with VITE_API_URL set
2. CORS_ORIGINS includes frontend URL
3. Browser console for errors
4. Network tab for failed requests
```

### Slow performance
```
Check:
1. Render instance has enough memory
2. MongoDB indexes are created
3. Redis is connected
4. Groq API is responding
5. Network latency
```

---

## FINAL CHECKLIST

- [ ] Backend start command set in Render
- [ ] All environment variables verified
- [ ] Manual deploy triggered
- [ ] Backend health check passes
- [ ] Frontend VITE_API_URL set
- [ ] Frontend deployed to Vercel
- [ ] CORS_ORIGINS updated in Render
- [ ] Chat works end-to-end
- [ ] Media displays correctly
- [ ] No console errors
- [ ] Performance is good
- [ ] Database has data
- [ ] Logs look clean

---

## ESTIMATED TIME

- Backend deployment: 15 minutes
- Frontend deployment: 5 minutes
- Verification: 5 minutes
- **Total: 25 minutes**

---

## SUCCESS CRITERIA

✅ Backend running at https://prism-api.onrender.com
✅ Frontend running at https://prism-ai-studio.vercel.app
✅ Chat works end-to-end
✅ Media displays correctly on refresh
✅ No errors in logs
✅ Performance is good

**You're ready to deploy!** 🚀
