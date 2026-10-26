"""One-time script to trigger the Google OAuth2 consent flow.

Run this once to create token.json:
    cd mcp_server
    python auth_setup.py
"""
import os
import sys

# Add parent dir so we can resolve credentials relative to project root
sys.path.insert(0, os.path.dirname(__file__))

from server import _get_google_creds

print("Attempting Google OAuth2 authorization...")
print("A browser window should open — sign in and grant access.\n")

try:
    creds = _get_google_creds()
    print(f"\n✅ Authorization successful! Token saved.")
    print(f"   Token file: {os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'token.json'))}")
    print(f"   You can now run the MCP server normally.")
except Exception as e:
    print(f"\n❌ Authorization failed: {e}")
