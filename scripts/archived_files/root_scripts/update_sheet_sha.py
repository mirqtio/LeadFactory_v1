#!/usr/bin/env python3
"""
Update SHA in Google Sheet for version tracking.
"""
import argparse
import json
import os
import sys
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def init_sheets_service(credentials_json: str = None):
    """Initialize Google Sheets API service."""
    if credentials_json:
        creds_data = json.loads(credentials_json)
    else:
        creds_json_env = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
        if not creds_json_env:
            raise ValueError(
                "No Google Sheets credentials provided. " "Set GOOGLE_SHEETS_CREDENTIALS environment variable."
            )
        creds_data = json.loads(creds_json_env)

    credentials = service_account.Credentials.from_service_account_info(
        creds_data, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )

    return build("sheets", "v4", credentials=credentials)


def update_sha(sheet_id: str, tab: str, sha: str):
    """Update SHA and timestamp in the sheet."""
    service = init_sheets_service()

    try:
        # Update SHA in Z1
        sha_range = f"{tab}!Z1"
        sha_body = {"values": [[sha]]}

        service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=sha_range, valueInputOption="RAW", body=sha_body
        ).execute()

        # Update last sync info in AA1:AB2
        timestamp = datetime.utcnow().isoformat() + "Z"
        sync_data = [["Last Sync:", timestamp], ["SHA:", sha[:8]]]  # Short SHA

        sync_range = f"{tab}!AA1:AB2"
        sync_body = {"values": sync_data}

        service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=sync_range, valueInputOption="RAW", body=sync_body
        ).execute()

        print(f"✓ Updated SHA to {sha[:8]} at {timestamp}")

    except HttpError as error:
        print(f"An error occurred: {error}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Update SHA in Google Sheet")
    parser.add_argument("--sheet-id", required=True, help="Google Sheet ID")
    parser.add_argument("--tab", required=True, help="Sheet tab name")
    parser.add_argument("--sha", required=True, help="Git SHA to store")
    parser.add_argument("--credentials", help="Google service account credentials JSON")

    args = parser.parse_args()

    try:
        update_sha(args.sheet_id, args.tab, args.sha)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
