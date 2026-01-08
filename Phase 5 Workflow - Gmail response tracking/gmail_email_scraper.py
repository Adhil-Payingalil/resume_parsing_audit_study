"""
Gmail Email Scraper

This script reads Gmail credentials from a CSV file and scrapes emails from each account
using IMAP. The scraped emails are stored in MongoDB for later analysis and classification.

The end goal is to classify how many job applications got callbacks based on applications
generated in Phase 4.
"""

import csv
import imaplib
import email
import re
from email.message import Message
from email.header import decode_header
from email.utils import parsedate_to_datetime
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import traceback

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.mongodb import _get_mongo_client
from utils import get_logger
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)

# Gmail IMAP settings
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993


def clean_passkey(passkey: str) -> str:
    """
    Remove all whitespace characters from passkey (Gmail app passwords are 16 characters without spaces).
    Handles regular spaces, non-breaking spaces (\xa0), and other whitespace characters.
    
    Args:
        passkey: Passkey string that may contain spaces or non-breaking spaces
        
    Returns:
        Cleaned passkey without any whitespace
    """
    if not passkey:
        return ""
    # Remove all whitespace characters including non-breaking spaces (\xa0)
    return re.sub(r'\s+', '', passkey)


def decode_mime_words(s: str) -> str:
    """
    Decode MIME encoded words in email headers.
    
    Args:
        s: String that may contain MIME encoded words
        
    Returns:
        Decoded string
    """
    if not s:
        return ""
    decoded_parts = decode_header(s)
    decoded_str = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                decoded_str += part.decode(encoding or 'utf-8', errors='ignore')
            except (UnicodeDecodeError, LookupError):
                decoded_str += part.decode('utf-8', errors='ignore')
        else:
            decoded_str += part
    return decoded_str


def get_email_body(msg: Message) -> Dict[str, str]:
    """
    Extract email body from message, trying both text and HTML.
    
    Args:
        msg: Email message object
        
    Returns:
        Dictionary with 'text' and 'html' keys containing body content
    """
    body = {"text": "", "html": ""}
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            
            # Skip attachments
            if "attachment" in content_disposition:
                continue
            
            try:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    decoded = payload.decode(charset, errors='ignore')
                    
                    if content_type == "text/plain":
                        body["text"] += decoded
                    elif content_type == "text/html":
                        body["html"] += decoded
            except Exception as e:
                logger.warning(f"Error decoding email part: {e}")
                continue
    else:
        # Not multipart
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                decoded = payload.decode(charset, errors='ignore')
                content_type = msg.get_content_type()
                
                if content_type == "text/plain":
                    body["text"] = decoded
                elif content_type == "text/html":
                    body["html"] = decoded
                else:
                    body["text"] = decoded
        except Exception as e:
            logger.warning(f"Error decoding email body: {e}")
    
    return body


def parse_email(msg_bytes: bytes, email_id: str) -> Dict[str, Any]:
    """
    Parse email message bytes into a structured dictionary.
    
    Args:
        msg_bytes: Raw email message bytes
        email_id: IMAP email ID (UID)
        
    Returns:
        Dictionary containing parsed email data
    """
    msg = email.message_from_bytes(msg_bytes)
    
    # Extract headers
    subject = decode_mime_words(msg.get("Subject", ""))
    from_addr = decode_mime_words(msg.get("From", ""))
    to_addr = decode_mime_words(msg.get("To", ""))
    cc_addr = decode_mime_words(msg.get("Cc", ""))
    bcc_addr = decode_mime_words(msg.get("Bcc", ""))
    reply_to = decode_mime_words(msg.get("Reply-To", ""))
    date_str = msg.get("Date", "")
    
    # Parse date
    email_date = None
    if date_str:
        try:
            email_date = parsedate_to_datetime(date_str)
        except Exception as e:
            logger.warning(f"Could not parse date '{date_str}': {e}")
    
    # Extract body
    body = get_email_body(msg)
    
    # Extract message ID and references
    message_id = msg.get("Message-ID", "")
    in_reply_to = msg.get("In-Reply-To", "")
    references = msg.get("References", "")
    
    return {
        "email_id": email_id,
        "subject": subject,
        "from": from_addr,
        "to": to_addr,
        "cc": cc_addr if cc_addr else None,
        "bcc": bcc_addr if bcc_addr else None,
        "reply_to": reply_to if reply_to else None,
        "date": email_date,
        "date_str": date_str,
        "message_id": message_id,
        "in_reply_to": in_reply_to if in_reply_to else None,
        "references": references if references else None,
        "body_text": body["text"],
        "body_html": body["html"] if body["html"] else None,
        "scraped_at": datetime.now()
    }


def connect_to_gmail(email_addr: str, passkey: str) -> Optional[imaplib.IMAP4_SSL]:
    """
    Connect to Gmail using IMAP.
    
    Args:
        email_addr: Gmail email address
        passkey: Gmail app password (passkey)
        
    Returns:
        IMAP connection object or None if connection fails
    """
    try:
        # Clean passkey (remove spaces)
        clean_key = clean_passkey(passkey)
        
        # Connect to Gmail IMAP server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        
        # Login
        mail.login(email_addr, clean_key)
        
        logger.info(f"Successfully connected to Gmail account: {email_addr}")
        return mail
        
    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP error connecting to {email_addr}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error connecting to {email_addr}: {e}")
        return None


def fetch_emails(
    mail: imaplib.IMAP4_SSL, 
    email_addr: str, 
    limit: Optional[int] = None,
    existing_email_ids: Optional[set] = None
) -> List[Dict[str, Any]]:
    """
    Fetch emails from Gmail inbox, skipping emails that already exist.
    
    Args:
        mail: IMAP connection object
        email_addr: Email address (for logging)
        limit: Maximum number of emails to fetch (None for all)
        existing_email_ids: Set of email IDs that already exist in MongoDB (to skip)
        
    Returns:
        List of parsed email dictionaries (only new emails)
    """
    emails = []
    existing_ids = existing_email_ids or set()
    skipped_count = 0
    
    try:
        # Select inbox
        status, messages = mail.select("INBOX")
        if status != "OK":
            logger.error(f"Failed to select INBOX for {email_addr}")
            return emails
        
        # Get total number of emails
        status, message_ids = mail.search(None, "ALL")
        if status != "OK":
            logger.error(f"Failed to search emails for {email_addr}")
            return emails
        
        # Get list of email IDs
        email_ids = message_ids[0].split()
        total_emails_in_gmail = len(email_ids)
        
        # Apply limit if specified
        if limit:
            email_ids = email_ids[-limit:]  # Get most recent emails
        
        total_emails_to_check = len(email_ids)
        logger.info(f"Found {total_emails_in_gmail} total emails in Gmail for {email_addr}")
        logger.info(f"Checking {total_emails_to_check} emails (limit: {limit if limit else 'all'})")
        
        if existing_ids:
            logger.info(f"Found {len(existing_ids)} existing emails in MongoDB, will skip duplicates")
        
        # Fetch each email
        for idx, email_id in enumerate(email_ids, 1):
            try:
                email_id_str = email_id.decode()
                
                # Skip if email already exists
                if email_id_str in existing_ids:
                    skipped_count += 1
                    continue
                
                # Fetch email
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                if status != "OK":
                    logger.warning(f"Failed to fetch email {email_id_str} for {email_addr}")
                    continue
                
                # Parse email
                email_body = msg_data[0][1]
                parsed_email = parse_email(email_body, email_id_str)
                
                # Add email address to parsed email
                parsed_email["gmail_account"] = email_addr
                
                emails.append(parsed_email)
                
                if idx % 10 == 0:
                    logger.info(f"Processed {idx}/{total_emails_to_check} emails for {email_addr} "
                              f"(new: {len(emails)}, skipped: {skipped_count})")
                    
            except Exception as e:
                logger.error(f"Error processing email {email_id} for {email_addr}: {e}")
                logger.debug(traceback.format_exc())
                continue
        
        logger.info(f"Successfully fetched {len(emails)} new emails for {email_addr} "
                   f"(skipped {skipped_count} existing emails)")
        
    except Exception as e:
        logger.error(f"Error fetching emails for {email_addr}: {e}")
        logger.debug(traceback.format_exc())
    
    return emails


def get_existing_email_info(email_addr: str, collection_name: str = "email_scrapping_test") -> Dict[str, Any]:
    """
    Get information about existing emails in MongoDB for an account.
    
    Args:
        email_addr: Gmail email address
        collection_name: MongoDB collection name
        
    Returns:
        Dictionary with 'count' and 'email_ids' (set of existing email IDs)
    """
    mongo_client = _get_mongo_client()
    if not mongo_client:
        return {"count": 0, "email_ids": set()}
    
    try:
        db = mongo_client["Resume_study"]
        collection = db[collection_name]
        
        # Get count of existing emails
        count = collection.count_documents({"gmail_account": email_addr})
        
        # Get set of existing email IDs (IMAP UIDs)
        existing_ids = set()
        cursor = collection.find(
            {"gmail_account": email_addr},
            {"email_id": 1, "_id": 0}
        )
        for doc in cursor:
            if "email_id" in doc:
                existing_ids.add(str(doc["email_id"]))
        
        return {"count": count, "email_ids": existing_ids}
        
    except Exception as e:
        logger.warning(f"Error checking existing emails for {email_addr}: {e}")
        return {"count": 0, "email_ids": set()}
    finally:
        mongo_client.close()


def save_emails_to_mongodb(emails: List[Dict[str, Any]], collection_name: str = "email_scrapping_test") -> bool:
    """
    Save scraped emails to MongoDB.
    
    Args:
        emails: List of email dictionaries
        collection_name: MongoDB collection name
        
    Returns:
        True if successful, False otherwise
    """
    if not emails:
        logger.warning("No emails to save")
        return False
    
    mongo_client = _get_mongo_client()
    if not mongo_client:
        logger.error("Failed to connect to MongoDB")
        return False
    
    try:
        # Get database (using default from project)
        db = mongo_client["Resume_study"]
        collection = db[collection_name]
        
        # Insert emails
        result = collection.insert_many(emails)
        logger.info(f"Successfully saved {len(result.inserted_ids)} emails to MongoDB collection '{collection_name}'")
        
        return True
        
    except Exception as e:
        logger.error(f"Error saving emails to MongoDB: {e}")
        logger.debug(traceback.format_exc())
        return False
    finally:
        mongo_client.close()


def read_gmail_credentials(csv_path: str) -> List[Dict[str, str]]:
    """
    Read Gmail credentials from CSV file.
    
    Args:
        csv_path: Path to CSV file containing Gmail credentials
        
    Returns:
        List of dictionaries containing email credentials
    """
    credentials = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email_addr = row.get("Email", "").strip()
                passkey = row.get("Passkey", "").strip()
                
                if email_addr and passkey:
                    credentials.append({
                        "PII_Identifier_ID": row.get("PII_Identifier_ID", "").strip(),
                        "Geographic_Cluster": row.get("Geographic_Cluster", "").strip(),
                        "Treatment_Type": row.get("Treatment Type", "").strip(),
                        "Associated_Countries": row.get("Associated_Countries", "").strip(),
                        "Last_Name": row.get("Last_Name", "").strip(),
                        "Email": email_addr,
                        "Password": row.get("Password", "").strip(),
                        "Passkey": passkey
                    })
                else:
                    logger.warning(f"Skipping row with missing email or passkey: {row}")
        
        logger.info(f"Read {len(credentials)} Gmail credentials from CSV")
        
    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_path}")
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        logger.debug(traceback.format_exc())
    
    return credentials


def scrape_gmail_accounts(
    csv_path: str,
    collection_name: str = "email_scrapping_test",
    emails_per_account: Optional[int] = None,
    skip_existing: bool = True
) -> Dict[str, Any]:
    """
    Main function to scrape emails from all Gmail accounts in CSV.
    
    Args:
        csv_path: Path to CSV file with Gmail credentials
        collection_name: MongoDB collection name to store emails
        emails_per_account: Maximum number of emails to fetch per account (None for all)
        skip_existing: If True, skip accounts that already have emails in MongoDB
        
    Returns:
        Dictionary with scraping statistics
    """
    stats = {
        "total_accounts": 0,
        "successful_connections": 0,
        "failed_connections": 0,
        "total_emails_scraped": 0,
        "accounts_processed": []
    }
    
    # Read credentials
    credentials = read_gmail_credentials(csv_path)
    stats["total_accounts"] = len(credentials)
    
    if not credentials:
        logger.error("No credentials found in CSV file")
        return stats
    
    # Process each account
    for idx, cred in enumerate(credentials, 1):
        email_addr = cred["Email"]
        passkey = cred["Passkey"]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing account {idx}/{len(credentials)}: {email_addr}")
        logger.info(f"{'='*60}")
        
        # Check existing emails in MongoDB if skip_existing is enabled
        existing_email_info = None
        if skip_existing:
            existing_email_info = get_existing_email_info(email_addr, collection_name)
            existing_count = existing_email_info["count"]
            existing_ids = existing_email_info["email_ids"]
            
            if existing_count > 0:
                logger.info(f"Found {existing_count} existing emails in MongoDB for {email_addr}")
        
        # Connect to Gmail
        mail = connect_to_gmail(email_addr, passkey)
        if not mail:
            stats["failed_connections"] += 1
            stats["accounts_processed"].append({
                "email": email_addr,
                "status": "failed",
                "reason": "connection_failed"
            })
            continue
        
        stats["successful_connections"] += 1
        
        try:
            # Get email count from Gmail to compare with MongoDB
            try:
                status, messages = mail.select("INBOX")
                if status == "OK":
                    status, message_ids = mail.search(None, "ALL")
                    if status == "OK":
                        gmail_email_ids = message_ids[0].split()
                        gmail_count = len(gmail_email_ids)
                        
                        # If skip_existing is enabled and counts match, skip scraping
                        if skip_existing and existing_email_info:
                            existing_count = existing_email_info["count"]
                            if existing_count == gmail_count and existing_count > 0:
                                logger.info(f"Skipping {email_addr} - MongoDB count ({existing_count}) "
                                          f"matches Gmail count ({gmail_count}). No new emails to scrape.")
                                try:
                                    mail.logout()
                                except Exception:
                                    pass  # Ignore logout errors
                                stats["accounts_processed"].append({
                                    "email": email_addr,
                                    "status": "skipped",
                                    "reason": "count_matches",
                                    "gmail_count": gmail_count,
                                    "mongodb_count": existing_count
                                })
                                continue
                            elif existing_count > 0:
                                logger.info(f"MongoDB has {existing_count} emails, Gmail has {gmail_count} emails. "
                                          f"Will fetch {gmail_count - existing_count} new emails.")
                            elif existing_count == 0 and gmail_count == 0:
                                logger.info(f"No emails in Gmail or MongoDB for {email_addr}")
                                try:
                                    mail.logout()
                                except Exception:
                                    pass
                                stats["accounts_processed"].append({
                                    "email": email_addr,
                                    "status": "skipped",
                                    "reason": "no_emails",
                                    "gmail_count": 0,
                                    "mongodb_count": 0
                                })
                                continue
            except Exception as e:
                logger.warning(f"Could not compare email counts for {email_addr}: {e}")
            
            # Fetch emails (will skip existing ones)
            existing_ids = existing_email_info["email_ids"] if existing_email_info else None
            emails = fetch_emails(mail, email_addr, limit=emails_per_account, existing_email_ids=existing_ids)
            
            if emails:
                # Add metadata from CSV
                for email_data in emails:
                    email_data["PII_Identifier_ID"] = cred["PII_Identifier_ID"]
                    email_data["Geographic_Cluster"] = cred["Geographic_Cluster"]
                    email_data["Treatment_Type"] = cred["Treatment_Type"]
                    email_data["Associated_Countries"] = cred["Associated_Countries"]
                    email_data["Last_Name"] = cred["Last_Name"]
                
                # Save to MongoDB
                if save_emails_to_mongodb(emails, collection_name):
                    stats["total_emails_scraped"] += len(emails)
                    stats["accounts_processed"].append({
                        "email": email_addr,
                        "status": "success",
                        "emails_scraped": len(emails)
                    })
                else:
                    stats["accounts_processed"].append({
                        "email": email_addr,
                        "status": "failed",
                        "reason": "mongodb_save_failed",
                        "emails_scraped": len(emails)
                    })
            else:
                logger.warning(f"No emails found for {email_addr}")
                stats["accounts_processed"].append({
                    "email": email_addr,
                    "status": "success",
                    "emails_scraped": 0
                })
        
        except Exception as e:
            logger.error(f"Error processing {email_addr}: {e}")
            logger.debug(traceback.format_exc())
            stats["accounts_processed"].append({
                "email": email_addr,
                "status": "failed",
                "reason": str(e)
            })
        
        finally:
            # Close IMAP connection (if not already closed)
            try:
                mail.logout()
            except Exception:
                pass  # Ignore logout errors (connection may already be closed)
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("SCRAPING SUMMARY")
    logger.info("="*60)
    logger.info(f"Total accounts: {stats['total_accounts']}")
    logger.info(f"Successful connections: {stats['successful_connections']}")
    logger.info(f"Failed connections: {stats['failed_connections']}")
    logger.info(f"Total emails scraped: {stats['total_emails_scraped']}")
    logger.info("="*60)
    
    return stats


def main():
    """Main entry point for the script."""
    # Path to CSV file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "Gmail passkey mapping.csv")
    
    # Configuration
    collection_name = "email_scrapping_test"
    emails_per_account = None  # Set to a number to limit emails per account, or None for all
    
    logger.info("Starting Gmail email scraping...")
    logger.info(f"CSV file: {csv_path}")
    logger.info(f"MongoDB collection: {collection_name}")
    
    # Run scraping
    stats = scrape_gmail_accounts(
        csv_path=csv_path,
        collection_name=collection_name,
        emails_per_account=emails_per_account,
        skip_existing=True
    )
    
    logger.info("Gmail email scraping completed!")


if __name__ == "__main__":
    main()

