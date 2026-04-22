# 🚀 START HERE - MEDIA DISPLAY DEBUG

## What's the Problem?

Media cards (videos) don't load after page refresh. They show immediately after the AI response, but disappear when you refresh.

## What I've Done

Added comprehensive logging at every step to identify where the action payload is being lost.

---

## DO THIS NOW (10 minutes)

### Step 1: Open Chat (1 minute)
1. Go to your chat app
2. Open DevTools: Press **F12**
3. Go to **Console** tab
4. Keep it open

### Step 2: Request a Video (2 minutes)
1. Type in chat: **"play devera song"** (or any video request)
2. Wait for AI response
3. **Copy ALL logs from console** that start with:
   - 🎬 Extracted action
   - 💾 Captured action
   - 📤 Finalizing with metadata

**Example of what you should see:**
```
🎬 Extracted action: {type: "media_play", payload: {...}}
💾 Captured action for persistence: {type: "media_play", payload: {...}}
📤 Finalizing with metadata: {hasCapturedAction: true, ...}
```

### Step 3: Check Backend Logs (2 minutes)
1. Go to: https://render.com/dashboard
2. Click: **prism-api** service
3. Click: **Logs** tab
4. Search for: **"💾 Saving message"**
5. **Copy the log** that shows:
   - ✅ Action payload found OR
   - ⚠️ No action_payload in metadata

**Example of what you should see:**
```
💾 Saving message with metadata: {'action_payload': {...}}
✅ Action payload found: {'type': 'media_play', ...}
```

### Step 4: Refresh Page (2 minutes)
1. Press **F5** to refresh
2. Open DevTools Console again
3. **Copy logs** that show:
   - 📥 Loading message from DB
   - 🎬 MediaActionCard render check

**Example of what you should see:**
```
📥 Loading message from DB: {hasActionPayload: true, ...}
🎬 MediaActionCard render check: {shouldRender: true, ...}
```

### Step 5: Check Network (2 minutes)
1. Open DevTools → **Network** tab
2. Request video again
3. Look for request: `/api/streaming/chat/.../finalize/...`
4. Click on it
5. Go to **Payload** tab
6. **Check if metadata has action_payload**

**Should show:**
```json
{
  "final_content": "...",
  "metadata": {
    "action_payload": {
      "type": "media_play",
      "payload": {...}
    }
  }
}
```

---

## What to Report

After doing the 5 steps above, tell me:

1. **Did you see 🎬 Extracted action?** YES / NO
2. **Did you see 💾 Captured action?** YES / NO
3. **Did you see 📤 Finalizing with metadata?** YES / NO
4. **Did backend show ✅ Action payload found?** YES / NO
5. **Did backend show ⚠️ No action_payload?** YES / NO
6. **Did you see 📥 Loading message from DB?** YES / NO
7. **Did you see hasActionPayload: true?** YES / NO
8. **Did you see shouldRender: true?** YES / NO
9. **Did video display after refresh?** YES / NO

**If ANY of these is NO, that's where the problem is!**

---

## Quick Diagnosis

### If you see NO logs at all
**Problem**: Logging not working
**Solution**: Make sure DevTools is open BEFORE requesting video

### If you see 🎬 but NO 💾
**Problem**: Action not being captured
**Solution**: Check if action extraction is working

### If you see 💾 but NO 📤
**Problem**: Finalize not being called
**Solution**: Check if stream completes

### If you see 📤 but backend shows ⚠️
**Problem**: Metadata empty in request
**Solution**: Check Network tab payload

### If backend shows ✅ but NO 📥 after refresh
**Problem**: Database load not working
**Solution**: Check if chat history loads

### If you see 📥 but hasActionPayload: false
**Problem**: Action not in database
**Solution**: Check MongoDB directly

### If you see shouldRender: false
**Problem**: Render condition failing
**Solution**: Check which condition is false

---

## Expected Success Flow

```
Request Video
    ↓
See: 🎬 Extracted action ✅
See: 💾 Captured action ✅
See: 📤 Finalizing with metadata ✅
    ↓
Backend shows: ✅ Action payload found ✅
    ↓
Video displays ✅
    ↓
Refresh Page
    ↓
See: 📥 Loading message from DB ✅
See: hasActionPayload: true ✅
See: 🎬 MediaActionCard render check ✅
See: shouldRender: true ✅
    ↓
Video displays ✅
```

---

## Documentation

For more details, read:

1. **QUICK_DEBUG_STEPS.md** - Quick reference (5 min)
2. **WHAT_TO_LOOK_FOR.md** - Visual guide (5 min)
3. **DEBUG_MEDIA_DISPLAY.md** - Comprehensive guide (15 min)

---

## Time Estimate

- Step 1: 1 minute
- Step 2: 2 minutes
- Step 3: 2 minutes
- Step 4: 2 minutes
- Step 5: 2 minutes
- **Total: 9 minutes**

---

## Next

1. **Do the 5 steps above**
2. **Report which step fails**
3. **I'll fix that specific step**

Let's debug this! 🔍
