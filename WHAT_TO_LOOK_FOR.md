# 👀 WHAT TO LOOK FOR - VISUAL GUIDE

## When You Request a Video

### Frontend Console Should Show

```
🎬 Extracted action: {
  type: "media_play",
  payload: {
    mode: "video",
    url: "https://www.youtube.com/watch?v=...",
    video_id: "...",
    query: "Devera Song"
  }
}
```

✅ **If you see this**: Action was extracted from stream

❌ **If you DON'T see this**: Action tags not in stream

---

```
💾 Captured action for persistence: {
  type: "media_play",
  payload: { ... }
}
```

✅ **If you see this**: Action was captured

❌ **If you DON'T see this**: Capture code not working

---

```
📤 Finalizing with metadata: {
  hasCapturedAction: true,
  capturedAction: { type: "media_play", payload: {...} },
  metadata: { action_payload: {...} }
}
```

✅ **If you see this**: Action being sent to backend

❌ **If you DON'T see this**: Finalize not called

---

## Backend Logs Should Show

Go to: https://render.com/dashboard → prism-api → Logs

```
💾 Saving message with metadata: {'action_payload': {'type': 'media_play', 'payload': {...}}}
```

✅ **If you see this**: Backend received the action

❌ **If you DON'T see this**: Request didn't reach backend

---

```
✅ Action payload found: {'type': 'media_play', 'payload': {...}}
```

✅ **If you see this**: Backend is saving the action

❌ **If you see this instead**:
```
⚠️ No action_payload in metadata
```
Then metadata was empty

---

## MongoDB Should Have

Go to: MongoDB Atlas → Your Database → chat_sessions

Find the message and look at metadata:

```javascript
{
  "id": "msg-123",
  "role": "assistant",
  "content": "Here's the video...",
  "metadata": {
    "action_payload": {
      "type": "media_play",
      "payload": {
        "mode": "video",
        "video_id": "dQw4w9WgXcQ",
        "query": "Devera Song"
      }
    }
  }
}
```

✅ **If metadata has action_payload**: Data saved correctly

❌ **If metadata is empty**: Backend didn't save

---

## After Page Refresh

### Frontend Console Should Show

```
📥 Loading message from DB: {
  id: "msg-123",
  hasMetadata: true,
  metadataKeys: ['action_payload'],
  hasActionPayload: true,
  actionPayload: {
    type: 'media_play',
    payload: { ... }
  },
  fallbackAction: undefined
}
```

✅ **If you see this**: Action loaded from database

❌ **If you see this instead**:
```
📥 Loading message from DB: {
  hasMetadata: false,
  metadataKeys: [],
  hasActionPayload: false,
  actionPayload: undefined
}
```
Then action not in database

---

```
🎬 MediaActionCard render check: {
  messageId: "msg-123",
  isThinking: false,
  actionType: "media_play",
  hasMessageBlocks: true,
  messageBlocksLength: 1,
  hasActionBlock: false,
  shouldRender: true,
  payload: {
    mode: 'video',
    video_id: 'dQw4w9WgXcQ',
    query: 'Devera Song'
  }
}
```

✅ **If shouldRender is true**: Video will display

❌ **If shouldRender is false**: Check which condition failed:
- `isThinking: true` - Message still thinking
- `actionType` is not "media_play" - Wrong action type
- `hasActionBlock: true` - Already rendered as block

---

## Network Tab Should Show

### Finalize Request

Look for: `/api/streaming/chat/{chatId}/finalize/{generation_id}`

**Request Payload:**
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

✅ **If metadata has action_payload**: Frontend sending correctly

❌ **If metadata is empty**: Frontend not capturing action

---

## Visual Checklist

### Before Refresh
- [ ] See 🎬 Extracted action in console
- [ ] See 💾 Captured action in console
- [ ] See 📤 Finalizing with metadata in console
- [ ] Video displays on screen
- [ ] See 💾 Saving message in backend logs
- [ ] See ✅ Action payload found in backend logs

### After Refresh
- [ ] See 📥 Loading message from DB in console
- [ ] See hasActionPayload: true in console
- [ ] See 🎬 MediaActionCard render check in console
- [ ] See shouldRender: true in console
- [ ] Video displays on screen

---

## Troubleshooting by Symptom

### Symptom: No logs at all
**Problem**: Logging not working
**Check**: DevTools console is open?
**Fix**: Refresh page, open DevTools BEFORE requesting video

### Symptom: Only see 🎬 Extracted action
**Problem**: Action extracted but not captured
**Check**: Is capturedAction variable being set?
**Fix**: Check api.ts lines 351, 360

### Symptom: See 💾 Captured action but no 📤 Finalizing
**Problem**: Finalize not being called
**Check**: Does stream complete?
**Fix**: Check for stream errors

### Symptom: See 📤 Finalizing but no backend log
**Problem**: Request not reaching backend
**Check**: Network tab for failed request
**Fix**: Check API URL, CORS, network connection

### Symptom: See backend log but ⚠️ No action_payload
**Problem**: Metadata empty in request
**Check**: Network tab payload
**Fix**: Frontend not sending action

### Symptom: See ✅ Action payload found but no video after refresh
**Problem**: Action in DB but not loading
**Check**: See 📥 Loading message log?
**Fix**: Check if hasActionPayload is true

### Symptom: See hasActionPayload: true but shouldRender: false
**Problem**: Render condition failing
**Check**: Which condition is false?
**Fix**: Check messageBlocks or isThinking

---

## Expected Console Output

### Complete Success Flow

```
🎬 Extracted action: {type: "media_play", payload: {...}}
💾 Captured action for persistence: {type: "media_play", payload: {...}}
📤 Finalizing with metadata: {hasCapturedAction: true, capturedAction: {...}, metadata: {...}}
[Video displays]
[Refresh page]
📥 Loading message from DB: {hasActionPayload: true, actionPayload: {...}}
🎬 MediaActionCard render check: {shouldRender: true, payload: {...}}
[Video displays again]
```

### Failure Points

**If missing 💾 Captured action**:
```
🎬 Extracted action: {...}
[MISSING: 💾 Captured action]
📤 Finalizing with metadata: {hasCapturedAction: false}
```

**If missing 📤 Finalizing**:
```
🎬 Extracted action: {...}
💾 Captured action: {...}
[MISSING: 📤 Finalizing]
```

**If missing 📥 Loading**:
```
[Refresh page]
[MISSING: 📥 Loading message from DB]
```

**If hasActionPayload is false**:
```
📥 Loading message from DB: {hasActionPayload: false}
```

---

## Quick Reference

| What | Where | What to Look For |
|-----|-------|------------------|
| Action Extraction | Frontend Console | 🎬 Extracted action |
| Action Capture | Frontend Console | 💾 Captured action |
| Finalize Send | Frontend Console | 📤 Finalizing with metadata |
| Backend Receive | Backend Logs | 💾 Saving message with metadata |
| Backend Save | Backend Logs | ✅ Action payload found |
| Database | MongoDB | metadata.action_payload |
| Database Load | Frontend Console | 📥 Loading message from DB |
| Render Check | Frontend Console | 🎬 MediaActionCard render check |
| Render Result | Frontend Console | shouldRender: true/false |

---

## Next Steps

1. **Request a video** and look for all the logs above
2. **Note which logs are missing**
3. **Check the corresponding step** in the troubleshooting section
4. **Report which step fails** with the exact logs

This will help us identify exactly where the issue is!
