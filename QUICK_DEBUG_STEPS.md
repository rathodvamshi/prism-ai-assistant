# ⚡ QUICK DEBUG STEPS - MEDIA DISPLAY

## Do This Now

### Step 1: Request a Video (2 minutes)
1. Open chat
2. Type: "play devera song"
3. Open DevTools (F12)
4. Go to Console tab
5. **Copy all logs that start with:**
   - 🎬 Extracted action
   - 💾 Captured action
   - 📤 Finalizing with metadata

### Step 2: Check Backend Logs (2 minutes)
1. Go to: https://render.com/dashboard
2. Click: prism-api service
3. Click: Logs tab
4. Search for: "💾 Saving message"
5. **Copy the log that shows:**
   - ✅ Action payload found OR
   - ⚠️ No action_payload in metadata

### Step 3: Refresh Page (2 minutes)
1. Press F5 to refresh
2. Open DevTools Console
3. **Copy logs that show:**
   - 📥 Loading message from DB
   - 🎬 MediaActionCard render check

### Step 4: Check Network (2 minutes)
1. Open DevTools → Network tab
2. Request video again
3. Look for request: `/api/streaming/chat/.../finalize/...`
4. Click on it
5. Go to "Payload" tab
6. **Check if metadata has action_payload**

---

## What Each Log Means

| Log | Means | Status |
|-----|-------|--------|
| 🎬 Extracted action | Action found in stream | ✅ Good |
| 💾 Captured action | Action saved | ✅ Good |
| 📤 Finalizing with metadata | Sending to backend | ✅ Good |
| 💾 Saving message with metadata | Backend received | ✅ Good |
| ✅ Action payload found | Backend saving | ✅ Good |
| ⚠️ No action_payload | Metadata empty | ❌ Problem |
| 📥 Loading message from DB | Loading from DB | ✅ Good |
| hasActionPayload: true | Action in DB | ✅ Good |
| hasActionPayload: false | Action NOT in DB | ❌ Problem |
| shouldRender: true | Will display | ✅ Good |
| shouldRender: false | Won't display | ❌ Problem |

---

## Most Likely Issues

### Issue 1: No "💾 Captured action" log
**Problem**: Action not being captured
**Check**: Is the action being extracted? (see "🎬 Extracted action")
**Fix**: Check if ACTION tags are in the stream

### Issue 2: "⚠️ No action_payload in metadata" in backend
**Problem**: Backend not receiving action
**Check**: Network tab - is metadata empty in finalize request?
**Fix**: Frontend not sending action

### Issue 3: "hasActionPayload: false" after refresh
**Problem**: Action not saved to database
**Check**: Backend logs - did it receive the action?
**Fix**: Check MongoDB directly

### Issue 4: "shouldRender: false" after refresh
**Problem**: Render condition failing
**Check**: Which condition is false?
**Fix**: Check messageBlocks or isThinking

---

## Quick Fixes to Try

### Fix 1: Clear Browser Cache
```
DevTools → Application → Clear site data
Then refresh page
```

### Fix 2: Check API URL
```
DevTools → Console
Type: console.log(process.env.VITE_API_URL)
Should show your backend URL
```

### Fix 3: Check Network Errors
```
DevTools → Network tab
Look for red X on finalize request
Check error message
```

---

## Report Template

When reporting the issue, provide:

```
1. Frontend Console Logs:
   [Paste logs starting with 🎬, 💾, 📤]

2. Backend Logs:
   [Paste logs starting with 💾, ✅, ⚠️]

3. Network Payload:
   [Paste the metadata from finalize request]

4. After Refresh Logs:
   [Paste logs starting with 📥, 🎬]

5. Which step fails:
   [ ] Action extraction
   [ ] Action capture
   [ ] Finalize send
   [ ] Backend receive
   [ ] Database save
   [ ] Database load
   [ ] Render check
```

---

## Expected Flow

```
Request Video
    ↓
🎬 Extracted action ✅
    ↓
💾 Captured action ✅
    ↓
📤 Finalizing with metadata ✅
    ↓
💾 Saving message with metadata ✅
    ↓
✅ Action payload found ✅
    ↓
Refresh Page
    ↓
📥 Loading message from DB ✅
    ↓
hasActionPayload: true ✅
    ↓
🎬 MediaActionCard render check ✅
    ↓
shouldRender: true ✅
    ↓
Video Displays ✅
```

If any step is missing or shows ❌, that's where the problem is.

---

## Time Estimate

- Step 1: 2 minutes
- Step 2: 2 minutes
- Step 3: 2 minutes
- Step 4: 2 minutes
- **Total: 8 minutes**

Then we'll know exactly where the issue is!
