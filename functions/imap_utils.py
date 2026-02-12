import imaplib
from constants import SERVER, USER, PASSWORD, NEWSLETTERS_FOLDER

def get_imap_connection():
    """Create and return an IMAP connection"""
    conn = imaplib.IMAP4_SSL(SERVER)
    conn.login(USER, PASSWORD)
    return conn

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

def ensure_newsletters_folder_exists(conn):
    """Check if Newsletters folder exists, create if not"""
    try:
        status, folders = conn.list()
        folder_names = [f.decode().split('"')[-2] for f in folders if isinstance(f, bytes)]

        if NEWSLETTERS_FOLDER not in folder_names:
            print(f"Creating {NEWSLETTERS_FOLDER} folder...")
            conn.create(NEWSLETTERS_FOLDER)
            print(f"✓ Created {NEWSLETTERS_FOLDER}\n")
    except Exception as e:
        print(f"⚠️  Warning: Could not check/create Newsletters folder: {e}\n")
