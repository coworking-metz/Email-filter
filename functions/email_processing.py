import email
from email.utils import parseaddr
from email.header import decode_header
import fnmatch
from email import policy
from constants import SKIP_FROM_DOMAIN

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

def parse_email_headers(msg_obj):
    """Parse email headers and return relevant information"""
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

    return {
        'from_addr': from_addr,
        'to_addrs': to_addrs,
        'cc_addrs': cc_addrs,
        'subject': decoded_subject,
        'date': date
    }
