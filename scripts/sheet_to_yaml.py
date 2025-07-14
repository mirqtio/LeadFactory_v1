#!/usr/bin/env python3
"""
Convert Google Sheets scoring configuration to YAML format.

This script reads scoring rules from a Google Sheet and converts them
to the canonical YAML format while preserving comments and structure.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from ruamel.yaml import YAML

# Constants for sheet structure
TIER_RANGE = "A2:C6"  # Tier configuration rows
COMPONENT_RANGE = "A10:E50"  # Component weights and factors


class SheetToYamlConverter:
    """Convert Google Sheets data to scoring rules YAML."""

    def __init__(self, credentials_json: Optional[str] = None):
        """
        Initialize converter with Google Sheets API credentials.

        Args:
            credentials_json: JSON string with service account credentials
        """
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False
        self.service = self._init_sheets_service(credentials_json)

    def _init_sheets_service(self, credentials_json: Optional[str]):
        """Initialize Google Sheets API service."""
        if credentials_json:
            creds_data = json.loads(credentials_json)
        else:
            # Try to load from environment variable
            creds_json_env = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
            if not creds_json_env:
                raise ValueError(
                    "No Google Sheets credentials provided. " "Set GOOGLE_SHEETS_CREDENTIALS environment variable."
                )
            creds_data = json.loads(creds_json_env)

        credentials = service_account.Credentials.from_service_account_info(
            creds_data, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )

        return build("sheets", "v4", credentials=credentials)

    def fetch_sheet_data(self, sheet_id: str, tab: str) -> Dict[str, Any]:
        """
        Fetch data from Google Sheet.

        Args:
            sheet_id: Google Sheet ID (TODO: inject SHEET_ID)
            tab: Sheet tab name (TODO: inject TAB_NAME)

        Returns:
            Dictionary with tier and component data
        """
        try:
            # Fetch tier configuration
            tier_range = f"{tab}!{TIER_RANGE}"
            tier_result = self.service.spreadsheets().values().get(spreadsheetId=sheet_id, range=tier_range).execute()
            tier_values = tier_result.get("values", [])

            # Fetch component configuration
            comp_range = f"{tab}!{COMPONENT_RANGE}"
            comp_result = self.service.spreadsheets().values().get(spreadsheetId=sheet_id, range=comp_range).execute()
            comp_values = comp_result.get("values", [])

            # Fetch SHA from cell Z1
            sha_range = f"{tab}!Z1"
            sha_result = self.service.spreadsheets().values().get(spreadsheetId=sheet_id, range=sha_range).execute()
            sha_values = sha_result.get("values", [[""]])
            sha = sha_values[0][0] if sha_values and sha_values[0] else ""

            return {
                "tiers": self._parse_tiers(tier_values),
                "components": self._parse_components(comp_values),
                "sha": sha,
            }

        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    def _parse_tiers(self, values: List[List[str]]) -> Dict[str, Dict]:
        """Parse tier configuration from sheet values."""
        tiers = {}

        for row in values:
            if len(row) >= 3:
                tier_name = row[0].strip()
                try:
                    min_score = float(row[1])
                    label = row[2].strip()

                    tiers[tier_name] = {"min": min_score, "label": label}
                except (ValueError, IndexError):
                    print(f"Warning: Skipping invalid tier row: {row}")

        return tiers

    def _parse_components(self, values: List[List[str]]) -> Dict[str, Dict]:
        """Parse component configuration from sheet values."""
        components = {}
        current_component = None

        for row in values:
            if not row or not row[0]:
                continue

            # Check if this is a component header (bold/uppercase in sheet)
            if len(row) >= 2 and row[1] and not any(row[2:] if len(row) > 2 else []):
                # This is a component with weight
                comp_name = row[0].strip().lower().replace(" ", "_")
                try:
                    weight = float(row[1])
                    current_component = comp_name
                    components[comp_name] = {"weight": weight, "factors": {}}
                except ValueError:
                    print(f"Warning: Invalid component weight: {row}")

            elif current_component and len(row) >= 3 and row[2]:
                # This is a factor for the current component
                factor_name = row[0].strip().lower().replace(" ", "_")
                try:
                    factor_weight = float(row[2])
                    components[current_component]["factors"][factor_name] = {"weight": factor_weight}
                except ValueError:
                    print(f"Warning: Invalid factor weight: {row}")

        return components

    def validate_structure(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate sheet structure before conversion.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check tiers
        required_tiers = {"A", "B", "C", "D"}
        found_tiers = {t.get("label") for t in data["tiers"].values()}
        missing_tiers = required_tiers - found_tiers

        if missing_tiers:
            errors.append(f"Missing tier labels: {missing_tiers}")

        # Check component weights
        if data["components"]:
            total_weight = sum(c["weight"] for c in data["components"].values())
            if abs(total_weight - 1.0) > 0.05:
                errors.append(f"Component weights sum to {total_weight:.3f}, must be 1.0 ± 0.05")
        else:
            errors.append("No components found in sheet")

        # Check factor weights
        for comp_name, comp_data in data["components"].items():
            if comp_data["factors"]:
                factor_total = sum(f["weight"] for f in comp_data["factors"].values())
                if abs(factor_total - 1.0) > 0.05:
                    errors.append(
                        f"Component '{comp_name}' factor weights sum to {factor_total:.3f}, " f"must be 1.0 ± 0.05"
                    )

        return errors

    def convert_to_yaml(self, sheet_data: Dict[str, Any]) -> str:
        """
        Convert sheet data to YAML format with comments preserved.

        Args:
            sheet_data: Data fetched from Google Sheets

        Returns:
            YAML string with proper formatting and comments
        """
        # Create YAML structure
        yaml_data = {"version": "1.0", "tiers": sheet_data["tiers"], "components": sheet_data["components"]}

        # Add formulas section if not present
        if "formulas" not in yaml_data:
            yaml_data["formulas"] = {
                "total_score": "SUM(component_scores)",
                "weighted_score": "SUMPRODUCT(component_values, component_weights)",
                "tier_assignment": "IF(total_score >= 80, 'A', IF(total_score >= 60, 'B', IF(total_score >= 40, 'C', 'D')))",
            }

        # Convert to YAML string
        import io

        stream = io.StringIO()

        # Write header comments
        stream.write("# LeadFactory Scoring Configuration\n")
        stream.write("# Edit weights and thresholds here. Changes will be live after PR merge.\n")

        # Write version
        stream.write(f"version: \"{yaml_data['version']}\"\n\n")

        # Write tiers with comments
        stream.write("# Tier thresholds - used for analytics only in Phase 0\n")
        stream.write("# Comment: Tier used for analytics only until Phase 0.5. Do not branch on tier.\n")
        stream.write("tiers:\n")
        for tier_key, tier_data in yaml_data["tiers"].items():
            stream.write(f"  {tier_key}: {{min: {tier_data['min']}, label: \"{tier_data['label']}\"}}\n")

        # Write components with comments
        stream.write("\n# Component weights must sum to 1.0 (±0.005 tolerance)\n")
        stream.write("components:\n")

        for comp_name, comp_data in yaml_data["components"].items():
            stream.write(f"  {comp_name}:\n")
            stream.write(f"    weight: {comp_data['weight']}\n")

            if comp_data["factors"]:
                stream.write("    factors:\n")
                for factor_name, factor_data in comp_data["factors"].items():
                    stream.write(f"      {factor_name}: {{weight: {factor_data['weight']}}}\n")
            stream.write("  \n")

        # Write formulas section
        stream.write("# Scoring formula configuration (for xlcalculator integration)\n")
        stream.write("formulas:\n")
        stream.write("  # Reference formulas from lead_value.xlsx ImpactCalcs sheet\n")
        for formula_name, formula in yaml_data["formulas"].items():
            stream.write(f'  {formula_name}: "{formula}"\n')

        return stream.getvalue()


def main():
    """Main entry point for sheet to YAML conversion."""
    parser = argparse.ArgumentParser(description="Convert Google Sheets scoring configuration to YAML")
    parser.add_argument("--sheet-id", required=True, help="Google Sheet ID")
    parser.add_argument("--tab", required=True, help="Sheet tab name")
    parser.add_argument("--output", required=True, help="Output YAML file path")
    parser.add_argument("--credentials", help="Google service account credentials JSON")

    args = parser.parse_args()

    try:
        # Initialize converter
        converter = SheetToYamlConverter(args.credentials)

        # Fetch data from sheet
        print(f"Fetching data from sheet {args.sheet_id}, tab '{args.tab}'...")
        sheet_data = converter.fetch_sheet_data(args.sheet_id, args.tab)

        # Validate structure
        errors = converter.validate_structure(sheet_data)
        if errors:
            print("Validation errors found:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)

        # Convert to YAML
        yaml_content = converter.convert_to_yaml(sheet_data)

        # Write to file
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(yaml_content)

        print(f"✓ Successfully converted sheet to {args.output}")
        print(f"  SHA: {sheet_data.get('sha', 'N/A')}")

    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
