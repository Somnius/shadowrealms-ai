# Frontend Manual Testing Checklist

## Test Session: $(date)
## Tester: Manual Testing

---

## 1. Frontend Access Test

### Access Points to Test:
- [ ] http://localhost (via Nginx)
- [ ] http://localhost:3000 (direct React)
- [ ] http://localhost:80 (Nginx alternative)

### Expected Result:
- Login page should appear
- No console errors
- Page loads completely

### Actual Result:
_[TO BE FILLED BY TESTER]_

---

## 2. Authentication Flow Test

### Test 2.1: Registration
- [ ] Click "Register" or sign up link
- [ ] Fill in username, password
- [ ] Submit form
- [ ] Check for success message
- [ ] Check browser console for errors
- [ ] Check Network tab for API call

**Expected**: POST to /api/auth/register with 201 response

### Test 2.2: Login  
- [ ] Enter testuser_phase2 / testpass123
- [ ] Submit login form
- [ ] Check localStorage for token
- [ ] Should redirect to /dashboard

**Expected**: POST to /api/auth/login with 200 + token

### Test 2.3: Dashboard Access
- [ ] Should see dashboard after login
- [ ] User name displayed in header
- [ ] Quick action cards visible
- [ ] No console errors

### Test 2.4: Logout
- [ ] Click logout button
- [ ] Should redirect to login
- [ ] Token removed from localStorage
- [ ] Can't access /dashboard anymore

---

## 3. Campaign Management Test

### Test 3.1: View Campaigns
- [ ] Navigate to /campaigns
- [ ] See campaigns list or empty state
- [ ] Check Network tab for API call

**Expected**: GET to /api/campaigns

### Test 3.2: Create Campaign
- [ ] Click "Create Campaign" button
- [ ] Modal opens
- [ ] Fill in campaign details
- [ ] Submit form
- [ ] Check for success feedback
- [ ] New campaign appears in list

**Expected**: POST to /api/campaigns with campaign data

### Test 3.3: Enter Campaign
- [ ] Click on a campaign card
- [ ] Should navigate to /campaign/:id/chat
- [ ] Chat interface loads

---

## 4. Chat/AI Interaction Test

### Test 4.1: Chat Interface Loads
- [ ] Chat interface visible
- [ ] Message input field present
- [ ] Character sidebar visible
- [ ] No console errors

### Test 4.2: Send Message
- [ ] Type a message
- [ ] Click send or press Enter
- [ ] Message appears in chat
- [ ] Loading indicator shows
- [ ] AI response appears

**Expected**: POST to /api/ai/generate

### Test 4.3: AI with RAG
- [ ] Send: "What are the vampire clans?"
- [ ] Wait for AI response
- [ ] Check if response references rule books
- [ ] Verify context from ChromaDB used

---

## 5. Browser Console Check

### Errors to Watch For:
- [ ] CORS errors
- [ ] 404 Not Found errors
- [ ] Network timeouts
- [ ] React errors
- [ ] API connection failures

### Network Tab Check:
- [ ] API calls going to correct endpoint
- [ ] Response status codes
- [ ] Request/response payloads
- [ ] Loading times

---

## Issues Found:

### Issue #1:
**Description**: 
**Severity**: Critical / High / Medium / Low
**Fix Required**: 

### Issue #2:
**Description**: 
**Severity**: 
**Fix Required**: 

---

## Summary:
- **Tests Passed**: __/14
- **Tests Failed**: __/14
- **Critical Issues**: __
- **Next Steps**: 

