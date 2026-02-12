import os
from constants import CONFIG_DIR

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

def load_blacklist(filename):
    """Load blacklist from file, ignoring comments and empty lines"""
    blacklist = set()
    filepath = os.path.join(CONFIG_DIR, filename)

    if not os.path.exists(filepath):
        print(f"⚠️  Warning: {filepath} not found, using empty blacklist")
        return blacklist

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    blacklist.add(line.lower())
        print(f"✓ Loaded {len(blacklist)} addresses from {filename}")
    except Exception as e:
        print(f"⚠️  Error loading {filename}: {e}")

    return blacklist

def add_to_blacklist(email_address, filename):
    """Add an email address to blacklist file"""
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
        print(f"✗ Error adding to blacklist: {e}")
        return False