#!/usr/bin/env python3
import sys
import argparse

import email
from email import policy
from functions.imap_utils import get_imap_connection, get_last_emails, ensure_newsletters_folder_exists
from functions.config import load_whitelist, add_to_whitelist, load_blacklist, add_to_blacklist
from functions.email_processing import parse_email_headers
from functions.spam_detection import is_ovh_spam, is_spamassassin_spam, is_whitelisted, is_blacklisted, is_spam_indicator
from functions.blacklist import process_blacklist_folder
from constants import SERVER,JUNK_FOLDER, ARCHIVE_FOLDER, NEWSLETTERS_FOLDER, SKIP_FROM_DOMAIN
from functions.brevo import is_brevo_email

def process_email(conn, num, msg_obj, WHITELISTED_FROM, VALID_TO_CC, BLACKLISTED_FROM, yes_to_all, checked, msg_id, total_processed):
    """Process a single email and determine if it should be moved"""
    # Parse email headers
    email_info = parse_email_headers(msg_obj)
    from_addr = email_info['from_addr']
    to_addrs = email_info['to_addrs']
    cc_addrs = email_info['cc_addrs']
    subject = email_info['subject']
    date = email_info['date']

    if is_brevo_email(msg_obj):
        return ARCHIVE_FOLDER, "📩 Brevo email to archive", email_info

    # Check for blacklisted senders first
    if from_addr and is_blacklisted(from_addr, BLACKLISTED_FROM):
        return JUNK_FOLDER, f"🚨 Blacklisted sender: {from_addr}", email_info

    # Skip whitelisted senders
    if from_addr and is_whitelisted(from_addr, WHITELISTED_FROM):
        return None, "Skipped (whitelisted)", None

    # Check if any valid address is in To or CC
    all_recipients = set(to_addrs + cc_addrs)
    has_valid_address = bool(VALID_TO_CC & all_recipients)

    # Check spam indicators
    is_newsletter, spam_reasons = is_spam_indicator(msg_obj, from_addr, to_addrs, cc_addrs, BLACKLISTED_FROM)
    ovh_spam, ovh_reason = is_ovh_spam(msg_obj)
    spamassassin_spam, spamassassin_reason = is_spamassassin_spam(msg_obj)

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

    return destination, reason_text, email_info

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Email filter tool')
    parser.add_argument('--yes-to-all', '-y', action='store_true',
                        help='Automatically move all suspicious emails without prompting')
    parser.add_argument('--last-emails', '-l', type=int, default=0,
                        help='Only process the last N most recent emails (0 to disable)')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Enable debug mode to show all email subjects')
    parser.add_argument('--email-id', '-e', type=str, default=None,
                        help='Process only this specific email ID')
    args = parser.parse_args()



    yes_to_all = args.yes_to_all
    last_emails_count = args.last_emails
    debug_mode = args.debug  # Add debug mode flag


    # Validate last_emails_count
    if last_emails_count < 0:
        print("Error: --last-emails must be a positive number or 0")
        sys.exit(1)

    # Load whitelists and blacklist from config files
    print("Loading whitelists and blacklist...")
    WHITELISTED_FROM = load_whitelist('whitelist_from.txt')
    VALID_TO_CC = load_whitelist('whitelist_to_cc.txt')
    BLACKLISTED_FROM = load_blacklist('blacklist.txt')
    print()

    # Process INBOX.Blacklist folder first
    if yes_to_all:
        print("🚀 Running in AUTO MODE (--yes-to-all)")
        print("All suspicious emails will be moved automatically\n")

    # Connect to IMAP server
    print(f"Connecting to {SERVER}...")
    conn = get_imap_connection()

    # Ensure newsletters folder exists
    ensure_newsletters_folder_exists(conn)

    # Process blacklist folder
    added_to_blacklist = process_blacklist_folder(conn, 'blacklist.txt', BLACKLISTED_FROM)
    # Select INBOX
    conn.select('INBOX')

    # Get message IDs based on mode
    if args.email_id:
        print(f"Searching for specific email ID: {args.email_id}...")
        # Search for the specific email ID
        typ, data = conn.search(None, f'(HEADER "X-Ovh-Tracer-Id" "{args.email_id}")')
        if typ != 'OK' or not data[0]:
            print(f"Error: Email with ID {args.email_id} not found")
            return
        msg_ids = data[0].split()
        print(f"Found {len(msg_ids)} message(s) matching ID {args.email_id}")
    else:
        if last_emails_count > 0:
            print(f"Fetching last {last_emails_count} most recent emails...")
            msg_ids = get_last_emails(conn, last_emails_count)
            print(f"Found {len(msg_ids)} messages (last {last_emails_count} most recent)")
        else:
            print("Fetching all messages...")
            try:
                typ, data = conn.sort('REVERSE DATE', 'UTF-8', 'ALL')
                msg_ids = data[0].split()
                print(f"Found {len(msg_ids)} messages in INBOX (sorted by date, newest first)")
            except:
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
        print("  b (blacklist sender and move to junk)")
        print("Press Enter for default (Yes)")
        print("Tip: Use --yes-to-all or -y to auto-move all suspicious emails")
        print("     Use --debug or -d to enable debug mode")
        print("="*80 + "\n")
    else:
        print("="*80 + "\n")

    # Initialize counters
    moved_junk = 0
    moved_newsletters = 0
    moved_archive = 0
    skipped = 0
    failed = 0
    checked = 0
    whitelisted = 0
    blacklisted = 0
    errors = 0
    total_processed = 0

     # Process each email
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
            typ, msg_data = conn.fetch(num, '(BODY.PEEK[])')
            if typ != 'OK' or not msg_data[0]:
                continue

            raw_email = msg_data[0][1]
            msg_obj = email.message_from_bytes(raw_email, policy=policy.default)

            # Parse email headers for debug mode
            email_info = parse_email_headers(msg_obj)

            # Show subject in debug mode
            if debug_mode:
                print(f"\nProcessing email {i+1}/{len(msg_ids)} (ID: {msg_id})")
                print(f"Subject: {email_info['subject'][:100]}")
                print(f"From:    {email_info['from_addr'][:70] if email_info['from_addr'] else 'Unknown'}")
                print(f"Date:    {email_info['date']}")
                print("-" * 80)

            # Process the email
            destination, reason_text, email_info = process_email(
                conn, num, msg_obj, WHITELISTED_FROM, VALID_TO_CC, BLACKLISTED_FROM,
                yes_to_all, checked, msg_id, total_processed
            )


            # Only process if we have a destination
            if destination:
                checked += 1
                total_processed += 1

                if not yes_to_all:
                    print(f"\nEmail {checked} of {len(msg_ids)} (ID: {msg_id})")
                    print(f"Date:    {email_info['date']}")
                    print(f"From:    {email_info['from_addr'][:70] if email_info['from_addr'] else 'Unknown'}")
                    print(f"To:      {', '.join(email_info['to_addrs'][:2])}")
                    if email_info['cc_addrs']:
                        print(f"Cc:      {', '.join(email_info['cc_addrs'][:2])}")
                    print(f"Subject: {email_info['subject'][:100]}")
                    print(reason_text)
                    print(f"→ Will move to: {destination}")
                    print("-"*80)

                    response = input("Move? [Y/n/a/w/b]: ").strip().lower()

                    if response == 'a':
                        yes_to_all = True
                        response = 'y'
                        print("\n🚀 Switching to AUTO MODE for remaining emails...\n")
                    elif response == 'w':
                        # Add to whitelist and skip
                        if email_info['from_addr']:
                            if add_to_whitelist(email_info['from_addr'], 'whitelist_from.txt'):
                                WHITELISTED_FROM.add(email_info['from_addr'])  # Update in-memory set
                                whitelisted += 1
                                print("○ Kept in inbox\n")
                            else:
                                print("⚠️  Failed to whitelist, keeping in inbox\n")
                        else:
                            print("⚠️  No From address found, keeping in inbox\n")
                        skipped += 1
                        continue
                    elif response == 'b':
                        # Add to blacklist and move to junk
                        if email_info['from_addr']:
                            if add_to_blacklist(email_info['from_addr'], 'blacklist.txt'):
                                BLACKLISTED_FROM.add(email_info['from_addr'])  # Update in-memory set
                                blacklisted += 1
                                destination = JUNK_FOLDER
                                reason_text = f"🚨 Added to blacklist: {email_info['from_addr']}"
                                print("✓ Added to blacklist\n")
                            else:
                                print("⚠️  Failed to blacklist, keeping in inbox\n")
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

                            if destination == ARCHIVE_FOLDER:
                                moved_archive += 1
                                if not yes_to_all:
                                    print("✓ Moved to Archive\n")
                            else:
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
    if moved_junk > 0 or moved_newsletters > 0 or moved_archive > 0:
        print("\nExpunging deleted messages...")
        conn.expunge()

    print(f"\n{'='*80}")
    print("Summary:")
    print(f"  Mode: {'Debug' if debug_mode else 'Normal'}")
    print(f"  Total messages scanned: {len(msg_ids)}")
    print(f"  Suspicious emails found: {checked}")
    print(f"  Moved to Junk: {moved_junk}")
    print(f"  Moved to Newsletters: {moved_newsletters}")
    print(f"  Moved to Archive: {moved_archive}")
    print(f"  Kept in inbox: {skipped}")
    if whitelisted > 0:
        print(f"  Added to whitelist: {whitelisted}")
    if blacklisted > 0:
        print(f"  Added to blacklist: {blacklisted}")
    if errors > 0:
        print(f"  Errors (skipped): {errors}")
    print(f"  Failed:        {failed}")
    print(f"{'='*80}\n")

    conn.close()
    conn.logout()

if __name__ == "__main__":
    main()