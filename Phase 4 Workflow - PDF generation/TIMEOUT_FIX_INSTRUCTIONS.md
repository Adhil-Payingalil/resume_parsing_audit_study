# Fix 524 Timeout Error - Instructions

## Problem
The n8n workflow times out (524 error) because Cloudflare closes connections after ~100 seconds, but your workflow takes longer (3+ minutes) to process PDFs.

## Solution
Make the webhook respond immediately with an acceptance message, then process asynchronously.

---

## Part 1: n8n Workflow Changes

### Step 1: Add Early Respond to Webhook Node

1. **Open your n8n workflow** (`Resume API end point v3 (5).json`)
2. **Add a "Respond to Webhook" node** right after "Edit Fields" and before "Keyword Extractor"
3. **Configure the node:**
   - Node name: `Early Response`
   - Response Code: `200`
   - Response Body: Use "JSON" format, paste this:
   ```json
   {
     "status": "accepted",
     "id": "{{ $('Webhook').item.json.body.id }}",
     "treatment_type": "{{ $('Webhook').item.json.body.treatment_type }}",
     "message": "Processing started - resume will be processed asynchronously"
   }
   ```
4. **Connect the flow:**
   - Webhook → Find documents → Edit Fields → **Early Response** → Keyword Extractor → ... (rest of workflow)

### Step 2: Keep Final Response (Optional)
- Your existing final "Respond to Webhook" at the end can remain, but Python won't wait for it
- Or remove it if not needed (processing happens async anyway)

### Step 3: Update Webhook Node Settings
- Ensure webhook node has "Response Mode" set appropriately
- The early response node will handle the HTTP response

---

## Part 2: Python Code Changes

### Changes to Production Processing Cell

Update the cell that contains:
```python
# Send request to n8n webhook
response = requests.post(
    PRODUCTION_WEBHOOK_URL,
    json=request_body,
    auth=AUTHORIZATION,
    timeout=180  # 3 minutes timeout
)
```

**Replace with:**
```python
# Send request to n8n webhook (async mode - accepts immediate ack)
response = requests.post(
    PRODUCTION_WEBHOOK_URL,
    json=request_body,
    auth=AUTHORIZATION,
    timeout=10  # Short timeout for immediate acceptance response
)
```

### Update Success Validation

**OLD CODE:**
```python
# Check for required fields in successful response
google_drive_link = response_data.get('Google_Drive_Link', '')
file_id_response = response_data.get('id', '')
file_name = response_data.get('file_name', '')

if not google_drive_link or not file_id_response or not file_name:
    # Error handling...
```

**NEW CODE:**
```python
# Check for immediate acceptance (async processing)
status = response_data.get('status', '').lower()
if status == 'accepted':
    # Success - request accepted, processing will continue async
    consecutive_errors = 0
    success_count += 1
    
    print(f"     ✅ Request accepted (processing async)")
    print(f"        🆔 ID: {response_data.get('id', 'N/A')}")
    print(f"        🔬 Treatment: {response_data.get('treatment_type', 'N/A')}")
    print(f"        📝 Message: {response_data.get('message', 'N/A')}")
    continue  # Move to next request

# Fallback: Check for old-style response with PDF link (for backward compatibility)
google_drive_link = response_data.get('Google_Drive_Link', '')
file_id_response = response_data.get('id', '')
file_name = response_data.get('file_name', '')

if google_drive_link and file_id_response and file_name:
    # Old-style synchronous response (backward compatibility)
    consecutive_errors = 0
    success_count += 1
    
    print(f"     ✅ Success: PDF generated")
    print(f"        🔗 Google Drive Link: {google_drive_link}")
    print(f"        📄 Filename: {file_name}")
    print(f"        🆔 ID: {file_id_response}")
    continue
```

### Update Test Webhook Cell (Optional)

For testing, you can also update the test webhook timeout:
```python
# Change from:
timeout=120

# To:
timeout=10
```

---

## Summary of Changes

### n8n:
- ✅ Add "Respond to Webhook" node after "Edit Fields" (returns immediately)
- ✅ Continue workflow processing after response

### Python:
- ✅ Reduce timeout from 180s to 10s
- ✅ Accept "accepted" status as success
- ✅ Remove dependency on waiting for PDF link in response
- ✅ Keep backward compatibility with old-style responses

---

## Verification

After changes:
1. Test with single file first
2. Check that Python receives "accepted" response quickly (< 10s)
3. Verify PDFs still appear in Google Drive/Sheets (processing happens async)
4. Monitor n8n execution logs to confirm processing completes

---

## Notes

- Python will no longer wait for PDF generation - it just needs confirmation the request was accepted
- PDFs will still be generated and saved to Google Drive/Sheets as before
- Use Excel/Sheets logs to verify final completion if needed
- This change prevents 524 errors while maintaining full functionality


