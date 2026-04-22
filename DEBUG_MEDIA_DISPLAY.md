# 🔍 DEBUG GUIDE - MEDIA DISPLAY ISSUE

## Comprehensive Logging Added

I've added detailed logging at every step of the media display flow to help identify where the action payload is being lost.

---

## Step 1: Check Frontend Console Logs

### When Requesting a Video

Open browser DevTools (F12) → Console tab

**Look for these logs:**

```
🎬 Extracted action: { type: 'media_play', payload: {...} }
💾 Captured action for persistence: { type: 'media_play', payload: {...} }
📤 Finalizing with metadata: { hasCapturedAction: true, capturedAction: {...}, metadata: {...} }
```

**If you see these**: ✅ Frontend is capturing and sending the action

**If you DON'T see these**: ❌ Action is not being extracted from stream

---

## Step 2: Check Backend Logs

### When Message is Finalized

Check Render logs: https://render.com/dashboard → prism-api → Logs

**Look for these logs:**

```
💾 Saving message with metadata: {'action_payload': {...}}
✅ Action payload found: {'type': 'media_play', 'payload': {...}}
```

**If you see these**: ✅ Backend is receiving and saving the action

**If you see this instead**: ❌ No action_payload in metadata
```
⚠️ No action_payload in metadata
```

---

## Step 3: Check Database

### Verify MongoDB Has the Action

1. Go to MongoDB Atlas: https://cloud.mongodb.com
2. Find your database
3. Find the chat session
4. Look at the message document

**Should look like:**
```javascript
{
  id: "msg-123",
  role: "assistant",
  content: "Here's the video...",
  metadata: {
    action_payload: {
      type: "media_play",
      payload: {
        mode: "video",
        video_id: "...",
        query: "Song name"
      }
    }
  }
}
```

**If metadata is empty**: ❌ Backend didn't save it

---

## Step 4: Check Page Refresh

### When You Refresh the Page

Open browser DevTools (F12) → Console tab

**Look for these logs:**

```
📥 Loading message from DB: {
  id: "msg-123",
  hasMetadata: true,
  metadataKeys: ['action_payload'],
  hasActionPayload: true,
  actionPayload: { type: 'media_play', payload: {...} },
  fallbackAction: undefined
}
```

**If you see this**: ✅ Frontend is loading the action from database

**If you see this instead**: ❌ Action not in database
```
📥 Loading message from DB: {
  hasMetadata: false,
  metadataKeys: [],
  hasActionPayload: false,
  actionPayload: undefined
}
```

---

## Step 5: Check MediaActionCard Rendering

### When Message Loads After Refresh

Open browser DevTools (F12) → Console tab

**Look for these logs:**

```
🎬 MediaActionCard render check: {
  messageId: "msg-123",
  isThinking: false,
  actionType: "media_play",
  hasMessageBlocks: true,
  messageBlocksLength: 1,
  hasActionBlock: false,
  shouldRender: true,
  payload: { mode: 'video', video_id: '...', query: '...' }
}
```

**If shouldRender is true**: ✅ Component should render

**If shouldRender is false**: ❌ One of these is wrong:
- `isThinking: true` - Message still thinking
- `actionType` is not "video" or "media_play"
- `hasActionBlock: true` - Already rendered as block

---

## Debugging Flowchart

```
Request Video
    ↓
[Check Frontend Console]
    ├─ See "🎬 Extracted action"? 
    │  ├─ YES → Continue
    │  └─ NO → Action not extracted from stream ❌
    ↓
[Check Frontend Console]
    ├─ See "💾 Captured action"?
    │  ├─ YES → Continue
    │  └─ NO → Action not captured ❌
    ↓
[Check Frontend Console]
    ├─ See "📤 Finalizing with metadata"?
    │  ├─ YES → Continue
    │  └─ NO → Finalize not called ❌
    ↓
[Check Backend Logs]
    ├─ See "💾 Saving message with metadata"?
    │  ├─ YES → Continue
    │  └─ NO → Request not reaching backend ❌
    ↓
[Check Backend Logs]
    ├─ See "✅ Action payload found"?
    │  ├─ YES → Continue
    │  └─ NO → Metadata empty ❌
    ↓
[Check MongoDB]
    ├─ See action_payload in metadata?
    │  ├─ YES → Continue
    │  └─ NO → Backend didn't save ❌
    ↓
Refresh Page
    ↓
[Check Frontend Console]
    ├─ See "📥 Loading message from DB"?
    │  ├─ YES → Continue
    │  └─ NO → Chat history not loading ❌
    ↓
[Check Frontend Console]
    ├─ See "hasActionPayload: true"?
    │  ├─ YES → Continue
    │  └─ NO → Action not in database ❌
    ↓
[Check Frontend Console]
    ├─ See "🎬 MediaActionCard render check"?
    │  ├─ YES → Continue
    │  └─ NO → Message not rendering ❌
    ↓
[Check Frontend Console]
    ├─ See "shouldRender: true"?
    │  ├─ YES → Video should display ✅
    │  └─ NO → Render condition failed ❌
```

---

## Common Issues & Solutions

### Issue 1: Action Not Extracted
**Symptom**: No "🎬 Extracted action" log
**Cause**: Action tags not in stream
**Solution**: Check backend is sending ACTION tags in response

### Issue 2: Action Not Captured
**Symptom**: "🎬 Extracted action" but no "💾 Captured action"
**Cause**: capturedAction variable not being set
**Solution**: Check api.ts lines 351, 360

### Issue 3: Metadata Not Sent
**Symptom**: "💾 Captured action" but no "📤 Finalizing with metadata"
**Cause**: Finalize not being called
**Solution**: Check if stream completes properly

### Issue 4: Backend Not Receiving
**Symptom**: "📤 Finalizing with metadata" but no backend log
**Cause**: Request not reaching backend
**Solution**: Check network tab for failed requests

### Issue 5: Backend Not Saving
**Symptom**: Backend log shows "⚠️ No action_payload in metadata"
**Cause**: Metadata empty in request
**Solution**: Check finalize request body in network tab

### Issue 6: Database Empty
**Symptom**: MongoDB shows empty metadata
**Cause**: Backend didn't save
**Solution**: Check backend logs for errors

### Issue 7: Not Loading After Refresh
**Symptom**: No "📥 Loading message from DB" log
**Cause**: Chat history not loading
**Solution**: Check network tab for getChatHistory request

### Issue 8: Action Not in Database
**Symptom**: "hasActionPayload: false" in load log
**Cause**: Action not saved to database
**Solution**: Go back to Issue 6

### Issue 9: Not Rendering
**Symptom**: "shouldRender: false" in render check
**Cause**: One of the conditions failed
**Solution**: Check which condition is false

---

## Network Tab Debugging

### Check Finalize Request

1. Open DevTools → Network tab
2. Request a video
3. Look for request to `/api/streaming/chat/{chatId}/finalize/{generation_id}`
4. Click on it
5. Check "Request" tab → "Payload"

**Should show:**
```json
{
  "final_content": "Here's the video...",
  "metadata": {
    "action_payload": {
      "type": "media_play",
      "payload": {
        "mode": "video",
        "video_id": "...",
        "query": "..."
      }
    }
  }
}
```

**If metadata is empty**: ❌ Frontend not sending action

---

## MongoDB Query to Check

```javascript
db.chat_sessions.findOne(
  { "messages.generation_id": "your-generation-id" },
  { "messages.$": 1 }
)
```

**Should show:**
```javascript
{
  messages: [
    {
      id: "...",
      role: "assistant",
      content: "...",
      metadata: {
        action_payload: {
          type: "media_play",
          payload: { ... }
        }
      }
    }
  ]
}
```

---

## Step-by-Step Testing

### Test 1: Immediate Display
1. Open chat
2. Request video
3. Open DevTools Console
4. Look for all logs
5. Video should appear

### Test 2: After Refresh
1. Request video
2. Video appears
3. Refresh page (F5)
4. Open DevTools Console
5. Look for "📥 Loading message from DB"
6. Video should appear

### Test 3: Multiple Videos
1. Request video 1
2. Request video 2
3. Refresh page
4. Both videos should appear

---

## Logs Summary

| Log | Meaning | Location |
|-----|---------|----------|
| 🎬 Extracted action | Action found in stream | Frontend Console |
| 💾 Captured action | Action saved for persistence | Frontend Console |
| 📤 Finalizing with metadata | Sending to backend | Frontend Console |
| 💾 Saving message with metadata | Backend received | Backend Logs |
| ✅ Action payload found | Backend saving action | Backend Logs |
| ⚠️ No action_payload | Metadata empty | Backend Logs |
| 📥 Loading message from DB | Loading from database | Frontend Console |
| 🎬 MediaActionCard render check | Checking render condition | Frontend Console |

---

## Next Steps

1. **Request a video** and check all frontend console logs
2. **Check backend logs** for metadata logs
3. **Verify MongoDB** has the action_payload
4. **Refresh page** and check loading logs
5. **Report which step fails** with the exact logs

This will help identify exactly where the action payload is being lost.

---

## Files Modified for Debugging

- `Frontend/src/lib/api.ts` - Added action capture and finalize logging
- `Frontend/src/stores/chatStore.ts` - Added database load logging
- `Frontend/src/components/chat/MessageBubble.tsx` - Added render check logging
- `prism-backend/app/routers/streaming.py` - Added metadata save logging

All logs are console.log() and logger.info() so they won't affect production performance.
