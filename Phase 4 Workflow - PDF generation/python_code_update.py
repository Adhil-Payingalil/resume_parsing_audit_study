# UPDATED PRODUCTION PROCESSING CODE
# Replace the try/except block in Cell 17 (Production File Processing)

        try:
            # Send request to n8n webhook (async mode - accepts immediate ack)
            response = requests.post(
                PRODUCTION_WEBHOOK_URL,
                json=request_body,
                auth=AUTHORIZATION,
                timeout=10  # Short timeout for immediate acceptance response
            )
            
            # Check for HTTP errors
            if response.status_code != 200:
                consecutive_errors += 1
                print(f"     ❌ HTTP Error: {response.status_code}")
                print(f"     🔢 Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
                
                if consecutive_errors >= max_consecutive_errors:
                    print(f"\n🛑 STOPPING EXECUTION: {consecutive_errors} consecutive errors detected!")
                    processing_stopped = True
                    break
                continue
            
            # Parse response JSON
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                consecutive_errors += 1
                print(f"     ❌ JSON Parse Error")
                print(f"     🔢 Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
                
                if consecutive_errors >= max_consecutive_errors:
                    print(f"\n🛑 STOPPING EXECUTION: {consecutive_errors} consecutive errors detected!")
                    processing_stopped = True
                    break
                continue
            
            # Check for immediate acceptance (async processing mode)
            status = response_data.get('status', '').lower()
            
            if status == 'accepted':
                # Success - request accepted, processing will continue async
                consecutive_errors = 0
                success_count += 1
                
                print(f"     ✅ Request accepted (processing async)")
                print(f"        🆔 ID: {response_data.get('id', 'N/A')}")
                print(f"        🔬 Treatment: {response_data.get('treatment_type', 'N/A')}")
                print(f"        📝 Message: {response_data.get('message', 'N/A')}")
                
                # Progress tracking
                progress_percent = (current_operation / total_operations) * 100
                print(f"     📊 Progress: {current_operation}/{total_operations} ({progress_percent:.1f}%)")
                
                # Wait between requests (reduced since we're not waiting for PDF generation)
                if current_operation < total_operations and not processing_stopped:
                    print(f"     ⏳ Waiting 2 seconds before next request...")
                    time.sleep(2)  # Reduced from 5 to 2 seconds
                
                continue  # Move to next request
            
            # Fallback: Check for old-style response with PDF link (for backward compatibility)
            # This handles the case where the early response node isn't set up yet
            google_drive_link = response_data.get('Google_Drive_Link', '')
            file_id_response = response_data.get('id', '')
            file_name = response_data.get('file_name', '')
            
            if google_drive_link and file_id_response and file_name:
                # Old-style synchronous response (backward compatibility)
                consecutive_errors = 0
                success_count += 1
                
                print(f"     ✅ Success: PDF generated (synchronous mode)")
                print(f"        🔗 Google Drive Link: {google_drive_link}")
                print(f"        📄 Filename: {file_name}")
                print(f"        🆔 ID: {file_id_response}")
                
                # Progress tracking
                progress_percent = (current_operation / total_operations) * 100
                print(f"     📊 Progress: {current_operation}/{total_operations} ({progress_percent:.1f}%)")
                
                # Wait between requests
                if current_operation < total_operations and not processing_stopped:
                    print(f"     ⏳ Waiting 5 seconds before next request...")
                    time.sleep(5)
                
                continue
            
            # If we get here, response is neither "accepted" nor old-style success
            # Check for error status
            status = response_data.get('status', '').lower()
            if 'error' in status or 'failed' in status or 'exception' in status:
                consecutive_errors += 1
                print(f"     ❌ n8n Workflow Error: {status}")
                print(f"     🔢 Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
                
                if consecutive_errors >= max_consecutive_errors:
                    print(f"\n🛑 STOPPING EXECUTION: {consecutive_errors} consecutive errors detected!")
                    processing_stopped = True
                    break
                continue
            
            # Unknown response format
            consecutive_errors += 1
            print(f"     ⚠️  Unknown response format")
            print(f"     Response: {json.dumps(response_data, indent=2)[:200]}...")
            print(f"     🔢 Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"\n🛑 STOPPING EXECUTION: {consecutive_errors} consecutive errors detected!")
                processing_stopped = True
                break
            continue
            
        except requests.exceptions.Timeout:
            consecutive_errors += 1
            print(f"     ❌ Request Timeout (webhook didn't respond in 10s)")
            print(f"     🔢 Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"\n🛑 STOPPING EXECUTION: {consecutive_errors} consecutive errors detected!")
                processing_stopped = True
                break
            continue
            
        except Exception as e:
            consecutive_errors += 1
            print(f"     ❌ Exception: {str(e)}")
            print(f"     🔢 Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"\n🛑 STOPPING EXECUTION: {consecutive_errors} consecutive errors detected!")
                processing_stopped = True
                break
            continue


