import fnmatch
import os
from constants import SPAM_SCORE_THRESHOLD, SKIP_FROM_DOMAIN, CONFIG_DIR
from functions.email_processing import safe_get_payload, decode_mime_words

def load_spam_keywords():
    """Load spam keywords from spam_keywords.txt file"""
    spam_keywords = set()
    keywords_file = os.path.join(CONFIG_DIR, 'spam_keywords.txt')

    try:
        with open(keywords_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    spam_keywords.add(line.lower())
    except FileNotFoundError:
        print(f"Warning: {keywords_file} not found. Using default empty keyword list.")
    except Exception as e:
        print(f"Error loading spam keywords: {e}")

    return spam_keywords

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

def is_blacklisted(email_address, blacklist):
    """Check if email address matches any pattern in blacklist (supports wildcards)"""
    email_lower = email_address.lower()

    for pattern in blacklist:
        # Direct match
        if pattern == email_lower:
            return True

        # Wildcard match (e.g., *@spamdomain.com)
        if '*' in pattern:
            if fnmatch.fnmatch(email_lower, pattern):
                return True

    return False

def is_spam_indicator(msg_obj, from_addr, to_addrs, cc_addrs, BLACKLISTED_FROM):
    """Check for common spam indicators. Returns (is_newsletter, other_spam_reasons)"""
    is_newsletter = False
    reasons = []

    # 1. Check for blacklisted senders first
    if from_addr and is_blacklisted(from_addr, BLACKLISTED_FROM):
        reasons.append(f"🚨 Blacklisted sender: {from_addr}")
        return True, reasons  # If blacklisted, always mark as spam

    # 2. Check for List-Unsubscribe header (mass mailing) - this indicates newsletter
    if msg_obj.get('List-Unsubscribe'):
        is_newsletter = True

    # 3. Check for SpamAssassin indicators
    spamassassin_spam, reason = is_spamassassin_spam(msg_obj)
    if spamassassin_spam:
        reasons.append(reason)

    # 4. Check for suspicious Return-Path mismatch
    return_path = msg_obj.get('Return-Path', '')
    if return_path and from_addr:
        return_domain = return_path.split('@')[-1].strip('<>')
        from_domain = from_addr.split('@')[-1] if '@' in from_addr else ''
        if return_domain != from_domain and 'bounces' in return_path.lower():
            reasons.append(f"Return-Path mismatch (bulk service: {return_domain})")

    # 5. Check if From domain is suspicious (very long, random)
    if from_addr and '@' in from_addr:
        from_domain = from_addr.split('@')[1]
        if len(from_domain) > 30:
            reasons.append(f"Suspicious long domain: {from_domain}")

    # 6. Check for common spam keywords
    spam_keywords = load_spam_keywords()

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
