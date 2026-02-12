#!/usr/bin/env python3
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
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    whitelist.add(line.lower())
        return whitelist
    except Exception as e:
        print(f"⚠️  Error loading whitelist from {filename}: {str(e)}")
        return set()

def add_to_whitelist(email_address, filename):
    """Add an email address to the whitelist file"""
    filepath = os.path.join(CONFIG_DIR, filename)

    try:
        # Check if email is already in the whitelist
        with open(filepath, 'r') as f:
            if email_address.lower() in [line.strip().lower() for line in f if not line.strip().startswith('#')]:
                return False  # Already whitelisted

        # Add the email to the whitelist
        with open(filepath, 'a') as f:
            f.write(f"\n{email_address}")
        return True
    except Exception as e:
        print(f"⚠️  Error adding to whitelist: {str(e)}")
        return False
