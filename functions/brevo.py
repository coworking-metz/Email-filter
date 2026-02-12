from email.utils import parseaddr

def is_brevo_email(msg_obj):
    """Check if email is from contact@coworking-metz.fr and has a non-empty X-sib-id header"""
    if not msg_obj:
        return False

    from_header = msg_obj.get('From', '')
    if not from_header:
        return False

    _, email_addr = parseaddr(from_header)

    if email_addr.lower() != "contact@coworking-metz.fr":
        return False

    x_sib_id = msg_obj.get('X-sib-id', '')
    return bool(x_sib_id.strip())
