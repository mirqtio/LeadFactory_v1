#!/usr/bin/env python3
"""
Push YAML scoring configuration to Google Sheets.

This script updates a Google Sheet with the current scoring rules
from the YAML configuration file.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from ruamel.yaml import YAML


class YamlToSheetPusher:
    """Push YAML scoring rules to Google Sheets."""

    def __init__(self, credentials_json: str = None):
        """Initialize with Google Sheets API credentials."""
        self.yaml = YAML()
        self.service = self._init_sheets_service(credentials_json)

    def _init_sheets_service(self, credentials_json: str = None):
        """Initialize Google Sheets API service."""
        if credentials_json:
            creds_data = json.loads(credentials_json)
        else:
            creds_json_env = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
            if not creds_json_env:
                raise ValueError(
                    "No Google Sheets credentials provided. Set GOOGLE_SHEETS_CREDENTIALS environment variable."
                )
            creds_data = json.loads(creds_json_env)

        credentials = service_account.Credentials.from_service_account_info(
            creds_data, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )

        return build("sheets", "v4", credentials=credentials)

    def load_yaml_config(self, yaml_path: str) -> dict[str, Any]:
        """Load and parse YAML configuration."""
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"YAML file not found: {yaml_path}")

        with open(path) as f:
            return self.yaml.load(f)

    def prepare_tier_data(self, config: dict[str, Any]) -> list[list[Any]]:
        """Convert tier configuration to sheet rows."""
        rows = [["Tier Name", "Min Score", "Label"]]  # Header

        tiers = config.get("tiers", {})
        # Sort by min score descending
        sorted_tiers = sorted(tiers.items(), key=lambda x: x[1]["min"], reverse=True)

        for tier_key, tier_data in sorted_tiers:
            rows.append([tier_key, tier_data["min"], tier_data["label"]])

        return rows

    def prepare_component_data(self, config: dict[str, Any]) -> list[list[Any]]:
        """Convert component configuration to sheet rows."""
        rows = [["Component/Factor", "Weight", "Factor Weight", "Description"]]  # Header

        components = config.get("components", {})

        for comp_name, comp_data in components.items():
            # Component row
            rows.append(
                [
                    comp_name.replace("_", " ").title(),
                    comp_data["weight"],
                    "",  # No factor weight for component rows
                    "",  # Description could be added
                ]
            )

            # Factor rows (indented)
            factors = comp_data.get("factors", {})
            for factor_name, factor_data in factors.items():
                rows.append(
                    [
                        f"  {factor_name.replace('_', ' ').title()}",
                        "",  # No component weight for factor rows
                        factor_data["weight"],
                        "",  # Description could be added
                    ]
                )

        return rows

    def clear_range(self, sheet_id: str, tab: str, range_notation: str):
        """Clear a range in the sheet."""
        try:
            self.service.spreadsheets().values().clear(
                spreadsheetId=sheet_id, range=f"{tab}!{range_notation}"
            ).execute()
        except HttpError as e:
            print(f"Warning: Could not clear range {range_notation}: {e}")

    def update_sheet(self, sheet_id: str, tab: str, config: dict[str, Any]):
        """Update Google Sheet with YAML configuration."""
        try:
            # Prepare data
            tier_data = self.prepare_tier_data(config)
            component_data = self.prepare_component_data(config)

            # Clear existing data
            self.clear_range(sheet_id, tab, "A1:E50")

            # Update tier section
            tier_range = f"{tab}!A1:C{len(tier_data)}"
            tier_body = {"values": tier_data}

            self.service.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=tier_range, valueInputOption="RAW", body=tier_body
            ).execute()

            # Update component section (start at row 10)
            comp_start_row = 10
            comp_range = f"{tab}!A{comp_start_row}:D{comp_start_row + len(component_data) - 1}"
            comp_body = {"values": component_data}

            self.service.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=comp_range, valueInputOption="RAW", body=comp_body
            ).execute()

            # Format the sheet
            self._apply_formatting(sheet_id, tab)

            print(f"✓ Successfully updated sheet {sheet_id}, tab '{tab}'")

        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    def _apply_formatting(self, sheet_id: str, tab: str):
        """Apply formatting to make the sheet more readable."""
        # Get sheet ID for the tab
        sheet_metadata = self.service.spreadsheets().get(spreadsheetId=sheet_id).execute()

        tab_id = None
        for sheet in sheet_metadata.get("sheets", []):
            if sheet["properties"]["title"] == tab:
                tab_id = sheet["properties"]["sheetId"]
                break

        if not tab_id:
            print(f"Warning: Could not find tab '{tab}' for formatting")
            return

        # Format requests
        requests = [
            # Bold headers
            {
                "repeatCell": {
                    "range": {"sheetId": tab_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": tab_id, "startRowIndex": 9, "endRowIndex": 10},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold",
                }
            },
            # Auto-resize columns
            {
                "autoResizeDimensions": {
                    "dimensions": {"sheetId": tab_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 4}
                }
            },
        ]

        try:
            self.service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": requests}).execute()
        except HttpError as e:
            print(f"Warning: Could not apply formatting: {e}")


def main():
    """Main entry point for YAML to sheet push."""
    parser = argparse.ArgumentParser(description="Push YAML scoring configuration to Google Sheets")
    parser.add_argument("--yaml-file", required=True, help="Path to scoring rules YAML file")
    parser.add_argument("--sheet-id", required=True, help="Google Sheet ID")
    parser.add_argument("--tab", required=True, help="Sheet tab name")
    parser.add_argument("--credentials", help="Google service account credentials JSON")

    args = parser.parse_args()

    try:
        # Initialize pusher
        pusher = YamlToSheetPusher(args.credentials)

        # Load YAML configuration
        print(f"Loading configuration from {args.yaml_file}...")
        config = pusher.load_yaml_config(args.yaml_file)

        # Update sheet
        print(f"Updating sheet {args.sheet_id}, tab '{args.tab}'...")
        pusher.update_sheet(args.sheet_id, args.tab, config)

        print("✓ Sheet update completed successfully")

    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
