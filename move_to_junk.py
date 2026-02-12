#!/usr/bin/env python3
import imaplib
import email
from email.utils import parseaddr
from email.header import decode_header
import re
import sys
import os
import fnmatch
from email import policy
import argparse

# Configuration
SERVER = 'ssl0.ovh.net'
USER = 'contact@coworking-metz.fr'
PASSWORD = 'p7G!8bH5@'
JUNK_FOLDER = 'INBOX.INBOX.Junk'
NEWSLETTERS_FOLDER = 'INBOX.Newsletters'

# Domain to skip in From field
SKIP_FROM_DOMAIN = 'coworking-metz.fr'

# Config directory
CONFIG_DIR = os.path.join(os.path.dirname(__file__), 'config')
SPAM_SCORE_THRESHOLD = 80

def load_whitelist(filename):
    """Load whitelist from file, ignoring comments and empty lines"""
    whitelist = set()
    filepath = os.path.join(CONFIG_DIR, filename)

    if not os.path.exists(filepath):
        print(f"⚠️  Warning: {filepath} not found, using empty whitelist")
        return whitelist

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    whitelist.add(line.lower())
        print(f"✓ Loaded {len(whitelist)} addresses from {filename}")
    except Exception as e:
        print(f"⚠️  Error loading {filename}: {e}")

    return whitelist

def is_ovh_spam(msg_obj):
    """Check OVH spam headers"""
    spam_status = msg_obj.get('X-Ovh-Spam-Status', '')
    spam_score = msg_obj.get('X-VR-SPAMSCORE', '')

    # Trust explicit SPAM flag
    if spam_status.upper() == 'SPAM':
        return True, "OVH marked as SPAM"

    if msg_obj.get('X-VR-SPAMSTATE') == 'DCE':
        return True, "OVH DCE classification"

    # Fallback to score threshold
    try:
        score = int(spam_score)
        if score >= SPAM_SCORE_THRESHOLD:
            return True, f"High OVH spam score ({score})"
    except (ValueError, TypeError):
        pass

    return False, ""

def is_spamassassin_spam(msg_obj):
    """Check for SpamAssassin spam indicators"""
    ham_report = msg_obj.get('X-Ham-Report', '')
    spam_flag = msg_obj.get('X-Spam-Flag', '')

    if "SPAM" in ham_report.upper() or "SPAM" in spam_flag.upper():
        return True, "SpamAssassin marked as SPAM"

    # Check for SpamAssassin score
    spam_score = msg_obj.get('X-Spam-Score', '')
    try:
        if float(spam_score) >= 5.0:  # Typical SpamAssassin threshold
            return True, f"High SpamAssassin score ({spam_score})"
    except (ValueError, TypeError):
        pass

    return False, ""

def is_whitelisted(email_address, whitelist):
    """Check if email address matches any pattern in whitelist (supports wildcards)"""
    email_lower = email_address.lower()

    for pattern in whitelist:
        # Direct match
        if pattern == email_lower:
            return True

        # Wildcard match (e.g., *@amazon.fr)
        if '*' in pattern:
            if fnmatch.fnmatch(email_lower, pattern):
                return True

    return False

def add_to_whitelist(email_address, filename):
    """Add an email address to whitelist file"""
    filepath = os.path.join(CONFIG_DIR, filename)

    try:
        # Read existing content
        existing_lines = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_lines = f.readlines()

        # Check if already exists
        if any(email_address.lower() in line.lower() for line in existing_lines):
            print(f"✓ '{email_address}' is already in {filename}")
            return True

        # Add new address at the end
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"{email_address}\n")

        print(f"✓ Added '{email_address}' to {filename}")
        return True
    except Exception as e:
        print(f"✗ Error adding to whitelist: {e}")
        return False

def decode_mime_words(value):
    """Decode MIME encoded-word strings safely"""
    if not value:
        return ''

    # Ensure we always work with a string
    if not isinstance(value, str):
        value = str(value)

    try:
        decoded_fragments = decode_header(value)
        decoded_string = ''

        for fragment, charset in decoded_fragments:
            if isinstance(fragment, bytes):
                try:
                    decoded_string += fragment.decode(charset or 'utf-8', errors='replace')
                except (LookupError, UnicodeDecodeError):
                    decoded_string += fragment.decode('utf-8', errors='replace')
            else:
                decoded_string += fragment

        return decoded_string

    except Exception:
        return str(value)

def safe_get_payload(part):
    """Safely get and decode email payload"""
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ''

        # Try to decode with multiple encodings
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        for encoding in encodings:
            try:
                return payload.decode(encoding, errors='ignore')
            except (UnicodeDecodeError, AttributeError):
                continue

        # Last resort
        return payload.decode('utf-8', errors='replace')
    except Exception:
        return ''

def is_spam_indicator(msg_obj, from_addr, to_addrs, cc_addrs):
    """Check for common spam indicators. Returns (is_newsletter, other_spam_reasons)"""
    is_newsletter = False
    reasons = []

    # 1. Check for List-Unsubscribe header (mass mailing) - this indicates newsletter
    if msg_obj.get('List-Unsubscribe'):
        is_newsletter = True

    # 2. Check for SpamAssassin indicators
    spamassassin_spam, reason = is_spamassassin_spam(msg_obj)
    if spamassassin_spam:
        reasons.append(reason)

    # 3. Check for suspicious Return-Path mismatch
    return_path = msg_obj.get('Return-Path', '')
    if return_path and from_addr:
        return_domain = return_path.split('@')[-1].strip('<>')
        from_domain = from_addr.split('@')[-1] if '@' in from_addr else ''
        if return_domain != from_domain and 'bounces' in return_path.lower():
            reasons.append(f"Return-Path mismatch (bulk service: {return_domain})")

    # 4. Check if From domain is suspicious (very long, random)
    if from_addr and '@' in from_addr:
        from_domain = from_addr.split('@')[1]
        if len(from_domain) > 30:
            reasons.append(f"Suspicious long domain: {from_domain}")

    # 5. Check for common spam keywords
    spam_keywords = []

    body_text = ''

    try:
        if msg_obj.is_multipart():
            for part in msg_obj.walk():
                if part.get_content_type() == "text/plain":
                    body_text = safe_get_payload(part).lower()
                    if body_text:
                        break
        else:
            body_text = safe_get_payload(msg_obj).lower()
    except Exception:
        pass

    # Also check subject for spam keywords
    subject = msg_obj.get('Subject', '')
    decoded_subject = decode_mime_words(subject)
    combined_text = (decoded_subject + ' ' + body_text).lower()

    for keyword in spam_keywords:
        if keyword in combined_text:
            reasons.append(f"Spam keyword: '{keyword}'")
            break  # Only report first match



    return is_newsletter, reasons

def get_last_emails(conn, count=100):
    """Get the last N most recent emails from the server"""
    try:
        # Use IMAP SORT to get messages sorted by date (newest first)
        typ, data = conn.sort('REVERSE DATE', 'UTF-8', 'ALL')
        msg_ids = data[0].split()

        # Return only the most recent N messages
        return msg_ids[:count]
    except:
        # Fallback if SORT not supported
        print("Server doesn't support SORT, using unsorted list...")
        typ, data = conn.search(None, 'ALL')
        msg_ids = data[0].split()
        msg_ids.reverse()
        return msg_ids[:count]

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Email filter tool')
    parser.add_argument('--yes-to-all', '-y', action='store_true',
                        help='Automatically move all suspicious emails without prompting')
    parser.add_argument('--last-emails', '-l', type=int, default=0,
                        help='Only process the last N most recent emails (0 to disable)')
    args = parser.parse_args()

    yes_to_all = args.yes_to_all
    last_emails_count = args.last_emails

    # Validate last_emails_count
    if last_emails_count < 0:
        print("Error: --last-emails must be a positive number or 0")
        sys.exit(1)

    # Load whitelists from config files
    print("Loading whitelists...")
    WHITELISTED_FROM = load_whitelist('whitelist_from.txt')
    VALID_TO_CC = load_whitelist('whitelist_to_cc.txt')
    print()

    if yes_to_all:
        print("🚀 Running in AUTO MODE (--yes-to-all)")
        print("All suspicious emails will be moved automatically\n")

    print(f"Connecting to {SERVER}...")
    conn = imaplib.IMAP4_SSL(SERVER)
    conn.login(USER, PASSWORD)

    # Check if Newsletters folder exists, create if not
    try:
        status, folders = conn.list()
        folder_names = [f.decode().split('"')[-2] for f in folders if isinstance(f, bytes)]

        if NEWSLETTERS_FOLDER not in folder_names:
            print(f"Creating {NEWSLETTERS_FOLDER} folder...")
            conn.create(NEWSLETTERS_FOLDER)
            print(f"✓ Created {NEWSLETTERS_FOLDER}\n")
    except Exception as e:
        print(f"⚠️  Warning: Could not check/create Newsletters folder: {e}\n")

    # Select INBOX
    conn.select('INBOX')

    # Get message IDs based on mode
    if last_emails_count > 0:
        print(f"Fetching last {last_emails_count} most recent emails...")
        msg_ids = get_last_emails(conn, last_emails_count)
        print(f"Found {len(msg_ids)} messages (last {last_emails_count} most recent)")
    else:
        print("Fetching all messages...")
        try:
            # Use IMAP SORT to get messages sorted by date (newest first)
            typ, data = conn.sort('REVERSE DATE', 'UTF-8', 'ALL')
            msg_ids = data[0].split()
            print(f"Found {len(msg_ids)} messages in INBOX (sorted by date, newest first)")
        except:
            # Fallback if SORT not supported
            print("Server doesn't support SORT, using unsorted list...")
            typ, data = conn.search(None, 'ALL')
            msg_ids = data[0].split()
            msg_ids.reverse()
            print(f"Found {len(msg_ids)} messages in INBOX")

    if not yes_to_all:
        print("="*80)
        print("Options:")
        print("  Y (yes, move to junk/newsletters) - default")
        print("  n (no, keep in inbox)")
        print("  a (yes to all remaining)")
        print("  w (whitelist sender and keep)")
        print("Press Enter for default (Yes)")
        print("Tip: Use --yes-to-all or -y to auto-move all suspicious emails")
        print("="*80 + "\n")
    else:
        print("="*80 + "\n")

    moved_junk = 0
    moved_newsletters = 0
    skipped = 0
    failed = 0
    checked = 0
    whitelisted = 0
    errors = 0
    total_processed = 0

    for i, num in enumerate(msg_ids):
        try:
            # Convert message ID to string if it's bytes
            msg_id = num.decode() if isinstance(num, bytes) else num

            # First check if message still exists and is not deleted
            typ, flags_data = conn.fetch(num, '(FLAGS)')
            if typ != 'OK':
                continue

            # Check if message is already marked as deleted
            flags_str = flags_data[0].decode() if isinstance(flags_data[0], bytes) else str(flags_data[0])
            if '\\Deleted' in flags_str:
                continue

            # Fetch full message
            typ, msg_data = conn.fetch(num, '(RFC822)')
            if typ != 'OK' or not msg_data[0]:
                continue

            raw_email = msg_data[0][1]
            msg_obj = email.message_from_bytes(raw_email, policy=policy.default)

            ovh_spam, ovh_reason = is_ovh_spam(msg_obj)
            spamassassin_spam, spamassassin_reason = is_spamassassin_spam(msg_obj)

            to_addrs = []
            cc_addrs = []
            from_addr = ''
            subject = msg_obj.get('Subject', '(No subject)')
            date = msg_obj.get('Date', '')

            # Decode subject
            decoded_subject = decode_mime_words(subject) if subject else '(No subject)'

            # Parse From
            from_header = msg_obj.get('From', '')
            if from_header:
                name, from_addr = parseaddr(from_header)
                from_addr = from_addr.lower()

            # Skip emails from our own domain
            if from_addr and from_addr.endswith(f'@{SKIP_FROM_DOMAIN}'):
                skipped += 1
                continue

            # Skip whitelisted senders (with wildcard support)
            if from_addr and is_whitelisted(from_addr, WHITELISTED_FROM):
                skipped += 1
                continue

            # Parse To
            to_header = msg_obj.get_all('To', [])
            for addr_line in to_header:
                for addr in addr_line.split(','):
                    name, email_addr = parseaddr(addr.strip())
                    if email_addr:
                        to_addrs.append(email_addr.lower())

            # Parse CC
            cc_header = msg_obj.get_all('Cc', [])
            for addr_line in cc_header:
                for addr in addr_line.split(','):
                    name, email_addr = parseaddr(addr.strip())
                    if email_addr:
                        cc_addrs.append(email_addr.lower())

            # Check if any valid address is in To or CC
            all_recipients = set(to_addrs + cc_addrs)
            has_valid_address = bool(VALID_TO_CC & all_recipients)

            # Check for spam indicators
            is_newsletter, spam_reasons = is_spam_indicator(msg_obj, from_addr, to_addrs, cc_addrs)

            # Determine destination folder
            destination = None
            reason_text = ""

            if is_newsletter:
                destination = NEWSLETTERS_FOLDER
                reason_text = "📧 Newsletter (List-Unsubscribe header detected)"
            elif not has_valid_address or spam_reasons or ovh_spam or spamassassin_spam:
                destination = JUNK_FOLDER
                if not has_valid_address:
                    reason_text = "⚠️  No valid address in To/CC"
                if ovh_spam:
                    reason_text += f"\n🚩 {ovh_reason}\n"
                if spamassassin_spam:
                    reason_text += f"\n🚩 {spamassassin_reason}\n"
                if spam_reasons:
                    reason_text += "\n🚩 SPAM INDICATORS:\n"
                    for reason in spam_reasons[:3]:
                        reason_text += f"   • {reason}\n"

            # Only process if we have a destination
            if destination:
                checked += 1
                total_processed += 1

                if not yes_to_all:
                    print(f"\nEmail {checked} of {len(msg_ids)} (ID: {msg_id})")
                    print(f"Date:    {date}")
                    print(f"From:    {from_addr[:70] if from_addr else 'Unknown'}")
                    print(f"To:      {', '.join(to_addrs[:2])}")
                    if cc_addrs:
                        print(f"Cc:      {', '.join(cc_addrs[:2])}")
                    print(f"Subject: {decoded_subject[:100]}")
                    print(reason_text)
                    print(f"→ Will move to: {destination}")
                    print("-"*80)

                    response = input("Move? [Y/n/a/w]: ").strip().lower()

                    if response == 'a':
                        yes_to_all = True
                        response = 'y'
                        print("\n🚀 Switching to AUTO MODE for remaining emails...\n")
                    elif response == 'w':
                        # Add to whitelist and skip
                        if from_addr:
                            if add_to_whitelist(from_addr, 'whitelist_from.txt'):
                                WHITELISTED_FROM.add(from_addr)  # Update in-memory set
                                whitelisted += 1
                                print("○ Kept in inbox\n")
                            else:
                                print("⚠️  Failed to whitelist, keeping in inbox\n")
                        else:
                            print("⚠️  No From address found, keeping in inbox\n")
                        skipped += 1
                        continue
                    elif response == '':
                        response = 'y'
                else:
                    response = 'y'
                    if checked % 10 == 0:
                        print(f"✓ Processed {checked} suspicious emails...")

                if response in ['y', 'yes']:
                    try:
                        # Copy to destination folder
                        result = conn.copy(num, destination)
                        if result[0] == 'OK':
                            # Mark as deleted in INBOX
                            conn.store(num, '+FLAGS', '\\Deleted')

                            if destination == NEWSLETTERS_FOLDER:
                                moved_newsletters += 1
                                if not yes_to_all:
                                    print("✓ Moved to Newsletters\n")
                            else:
                                moved_junk += 1
                                if not yes_to_all:
                                    print("✓ Moved to Junk\n")
                        else:
                            failed += 1
                            if not yes_to_all:
                                print(f"✗ Failed to move\n")
                    except Exception as e:
                        failed += 1
                        if not yes_to_all:
                            print(f"✗ Error: {e}\n")
                else:
                    skipped += 1
                    if not yes_to_all:
                        print("○ Kept in inbox\n")
            else:
                skipped += 1

        except Exception as e:
            errors += 1
            if errors <= 5:  # Only show first 5 errors
                print(f"⚠️  Error processing message {msg_id}: {str(e)[:100]}")
            continue

    # Expunge to permanently delete from INBOX
    if moved_junk > 0 or moved_newsletters > 0:
        print("\nExpunging deleted messages...")
        conn.expunge()

    print(f"\n{'='*80}")
    print("Summary:")
    print(f"  Total messages scanned: {len(msg_ids)}")
    print(f"  Suspicious emails found: {checked}")
    print(f"  Moved to Junk: {moved_junk}")
    print(f"  Moved to Newsletters: {moved_newsletters}")
    print(f"  Kept in inbox: {skipped}")
    if whitelisted > 0:
        print(f"  Added to whitelist: {whitelisted}")
    if errors > 0:
        print(f"  Errors (skipped): {errors}")
    print(f"  Failed:        {failed}")
    print(f"{'='*80}\n")

    conn.close()
    conn.logout()

if __name__ == "__main__":
    main()
