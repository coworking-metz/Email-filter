import email
from email import policy
from functions.imap_utils import get_imap_connection
from functions.config import add_to_blacklist
from constants import JUNK_FOLDER
from functions.email_processing import parse_email_headers

def process_blacklist_folder(conn, blacklist_file, blacklist_set):
    """Process emails in the INBOX.Blacklist folder and add senders to blacklist

    Args:
        conn: IMAP connection object
        blacklist_file: Path to the blacklist file
        blacklist_set: Set containing current blacklisted addresses

    Returns:
        int: Number of senders added to blacklist
    """
    try:
        # Select the blacklist folder
        conn.select('INBOX.Blacklist')
        print("Processing INBOX.Blacklist folder...")

        # Get all messages in the folder
        typ, data = conn.search(None, 'ALL')
        if typ != 'OK':
            print("No messages found in INBOX.Blacklist folder")
            return 0

        msg_ids = data[0].split()
        processed = 0
        added = 0
        errors = 0

        for num in msg_ids:
            try:
                # Fetch the email
                typ, msg_data = conn.fetch(num, '(BODY.PEEK[])')
                if typ != 'OK' or not msg_data[0]:
                    continue

                raw_email = msg_data[0][1]
                msg_obj = email.message_from_bytes(raw_email, policy=policy.default)

                # Parse email headers
                email_info = parse_email_headers(msg_obj)
                from_addr = email_info['from_addr']

                if from_addr:
                    # Add to blacklist
                    if add_to_blacklist(from_addr, blacklist_file):
                        blacklist_set.add(from_addr)  # Update in-memory set
                        added += 1

                        # Move the email to Junk folder
                        # First select the Junk folder
                        conn.select(JUNK_FOLDER)

                        # Then append the email to Junk folder
                        result = conn.append(
                            JUNK_FOLDER,
                            '',
                            None,
                            raw_email
                        )

                        if result[0] == 'OK':
                            # Now return to Blacklist folder
                            conn.select('INBOX.Blacklist')

                            # Mark as deleted in Blacklist folder
                            conn.store(num, '+FLAGS', '\\Deleted')
                        else:
                            errors += 1
                            print(f"Failed to move email {num} to Junk folder")
                            continue
                    else:
                        errors += 1
                processed += 1
            except Exception as e:
                errors += 1
                print(f"Error processing email {num}: {str(e)}")
                continue

        # Expunge to permanently delete from INBOX.Blacklist
        if added > 0:
            print("Expunging processed messages from INBOX.Blacklist...")
            conn.expunge()

        print(f"Processed {processed} emails from INBOX.Blacklist")
        print(f"Added {added} senders to blacklist")
        if errors > 0:
            print(f"Skipped {errors} emails due to errors")
        return added
    except Exception as e:
        print(f"Error processing INBOX.Blacklist folder: {str(e)}")
        return 0
