#!/usr/bin/env python3
"""
Design Token Validation

Validates design tokens against the JSON schema and performs additional
quality checks to ensure compliance with the Anthrasite Design System
requirements.

This module provides both programmatic validation functions and a CLI
for validating token files.
"""

import json
import sys
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:
    print("Error: jsonschema package is required. Install with: pip install jsonschema")
    sys.exit(1)


class DesignTokenValidator:
    """Validates design tokens against schema and quality requirements."""

    def __init__(self, schema_path: str | None = None):
        """
        Initialize validator with schema.

        Args:
            schema_path (str, optional): Path to JSON schema file.
                                       If None, uses default schema.
        """
        if schema_path is None:
            schema_file_path = Path(__file__).parent / "token_schema.json"
        else:
            schema_file_path = Path(schema_path)

        with open(schema_file_path, encoding="utf-8") as f:
            self.schema = json.load(f)

        self.validator = jsonschema.Draft7Validator(self.schema)

    def validate_schema(self, tokens: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate tokens against JSON schema.

        Args:
            tokens (dict): Design tokens to validate.

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []

        try:
            # Validate against schema
            schema_errors = list(self.validator.iter_errors(tokens))

            for error in schema_errors:
                # Format error message with path context
                path = " -> ".join(str(p) for p in error.absolute_path)
                if path:
                    errors.append(f"Schema error at {path}: {error.message}")
                else:
                    errors.append(f"Schema error: {error.message}")

        except Exception as e:
            errors.append(f"Schema validation failed: {str(e)}")

        return len(errors) == 0, errors

    def validate_file_size(self, tokens_path: str, max_size_bytes: int = 2048) -> tuple[bool, list[str]]:
        """
        Validate that tokens file meets size constraint.

        Args:
            tokens_path (str): Path to tokens JSON file.
            max_size_bytes (int): Maximum file size in bytes.

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []
        tokens_file = Path(tokens_path)

        if not tokens_file.exists():
            errors.append(f"Tokens file not found: {tokens_path}")
            return False, errors

        file_size = tokens_file.stat().st_size

        if file_size > max_size_bytes:
            errors.append(f"File size {file_size} bytes exceeds {max_size_bytes} byte limit")
            return False, errors

        return True, errors

    def validate_color_contrast(self, tokens: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate that color tokens include proper contrast ratios.

        Args:
            tokens (dict): Design tokens to validate.

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []
        warnings = []

        colors = tokens.get("colors", {})

        # Check that some colors have contrast information
        colors_with_contrast = 0

        for category_name, category in colors.items():
            for color_name, color_data in category.items():
                if isinstance(color_data, dict) and "contrast" in color_data:
                    colors_with_contrast += 1

                    # Validate contrast ratio format
                    contrast_data = color_data["contrast"]
                    for combo_name, ratio in contrast_data.items():
                        if not isinstance(ratio, str) or ":1" not in ratio:
                            errors.append(
                                f"Invalid contrast ratio format for {category_name}.{color_name}.{combo_name}: {ratio}"
                            )
                        else:
                            # Extract numeric part and validate
                            try:
                                ratio_value = float(ratio.split(":")[0])
                                if ratio_value < 3.0:
                                    warnings.append(
                                        f"Low contrast ratio for {category_name}.{color_name}.{combo_name}: {ratio} (below AA standard)"
                                    )
                            except ValueError:
                                errors.append(
                                    f"Invalid contrast ratio value for {category_name}.{color_name}.{combo_name}: {ratio}"
                                )

        if colors_with_contrast == 0:
            warnings.append("No colors found with contrast ratio information")

        # Add warnings to errors for reporting (but don't fail validation)
        for warning in warnings:
            errors.append(f"WARNING: {warning}")

        return len([e for e in errors if not e.startswith("WARNING:")]) == 0, errors

    def validate_spacing_system(self, tokens: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate that spacing system follows 8px base unit.

        Args:
            tokens (dict): Design tokens to validate.

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []

        spacing = tokens.get("spacing", {})

        # Check base unit
        base = spacing.get("base", "")
        if base != "8px":
            errors.append(f"Spacing base must be '8px', got '{base}'")

        # Check scale values are multiples of 8
        scale = spacing.get("scale", {})
        for scale_name, scale_value in scale.items():
            if isinstance(scale_value, str) and scale_value.endswith("px"):
                try:
                    numeric_value = int(scale_value[:-2])
                    if numeric_value % 8 != 0:
                        errors.append(f"Spacing value {scale_name} = {scale_value} is not a multiple of 8px")
                except ValueError:
                    errors.append(f"Invalid spacing value format: {scale_name} = {scale_value}")
            else:
                errors.append(f"Spacing value must end with 'px': {scale_name} = {scale_value}")

        return len(errors) == 0, errors

    def validate_typography_hierarchy(self, tokens: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate that typography scale maintains proper hierarchy.

        Args:
            tokens (dict): Design tokens to validate.

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []

        typography = tokens.get("typography", {})
        scale = typography.get("scale", {})

        # Extract font sizes for hierarchy checking
        sizes = {}
        for scale_name, scale_data in scale.items():
            if isinstance(scale_data, dict) and "size" in scale_data:
                size_value = scale_data["size"]
                if isinstance(size_value, str) and size_value.endswith("px"):
                    try:
                        sizes[scale_name] = int(size_value[:-2])
                    except ValueError:
                        errors.append(f"Invalid font size format: {scale_name} = {size_value}")
                else:
                    errors.append(f"Font size must end with 'px': {scale_name} = {size_value}")

        # Check hierarchy relationships
        hierarchies = [
            ("display", "h1", "Display should be larger than h1"),
            ("h1", "h2", "h1 should be larger than h2"),
            ("h2", "h3", "h2 should be larger than h3"),
            ("h3", "h4", "h3 should be larger than h4"),
            ("body-large", "body", "body-large should be larger than body"),
            ("body", "body-small", "body should be larger than body-small"),
            ("body-small", "caption", "body-small should be larger than caption"),
        ]

        for larger, smaller, message in hierarchies:
            if larger in sizes and smaller in sizes:
                if sizes[larger] <= sizes[smaller]:
                    errors.append(
                        f"Typography hierarchy error: {message} ({larger}: {sizes[larger]}px, {smaller}: {sizes[smaller]}px)"
                    )

        return len(errors) == 0, errors

    def validate_completeness(self, tokens: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate that all required tokens are present with correct counts.

        Args:
            tokens (dict): Design tokens to validate.

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []

        # Check token counts match PRP requirements
        requirements = {
            "colors.primary": 3,
            "colors.status": 3,
            "colors.functional": 4,
            "typography.scale": 9,
            "spacing.scale": 7,
            "animation.duration": 4,
            "breakpoints": 3,
        }

        for path, expected_count in requirements.items():
            parts = path.split(".")
            current = tokens

            try:
                for part in parts:
                    current = current[part]

                actual_count = len(current)
                if actual_count != expected_count:
                    errors.append(f"Token count mismatch for {path}: expected {expected_count}, got {actual_count}")

            except (KeyError, TypeError):
                errors.append(f"Missing token section: {path}")

        # Check total color count
        try:
            colors = tokens["colors"]
            total_colors = sum(len(category) for category in colors.values())
            if total_colors != 10:
                errors.append(f"Total color count should be 10, got {total_colors}")
        except (KeyError, TypeError):
            errors.append("Colors section missing or invalid")

        return len(errors) == 0, errors

    def validate_all(self, tokens: dict[str, Any], tokens_path: str | None = None) -> tuple[bool, dict[str, list[str]]]:
        """
        Run all validation checks.

        Args:
            tokens (dict): Design tokens to validate.
            tokens_path (str, optional): Path to tokens file for size validation.

        Returns:
            tuple: (all_valid, dict_of_validation_results)
        """
        results = {}
        all_valid = True

        # Schema validation
        schema_valid, schema_errors = self.validate_schema(tokens)
        results["schema"] = schema_errors
        if not schema_valid:
            all_valid = False

        # File size validation (if path provided)
        if tokens_path:
            size_valid, size_errors = self.validate_file_size(tokens_path)
            results["file_size"] = size_errors
            if not size_valid:
                all_valid = False

        # Color contrast validation
        contrast_valid, contrast_errors = self.validate_color_contrast(tokens)
        results["color_contrast"] = contrast_errors
        if not contrast_valid:
            all_valid = False

        # Spacing system validation
        spacing_valid, spacing_errors = self.validate_spacing_system(tokens)
        results["spacing_system"] = spacing_errors
        if not spacing_valid:
            all_valid = False

        # Typography hierarchy validation
        typography_valid, typography_errors = self.validate_typography_hierarchy(tokens)
        results["typography_hierarchy"] = typography_errors
        if not typography_valid:
            all_valid = False

        # Completeness validation
        completeness_valid, completeness_errors = self.validate_completeness(tokens)
        results["completeness"] = completeness_errors
        if not completeness_valid:
            all_valid = False

        return all_valid, results


def validate_tokens_file(tokens_path: str, schema_path: str | None = None, verbose: bool = False) -> bool:
    """
    Validate a design tokens JSON file.

    Args:
        tokens_path (str): Path to the tokens JSON file.
        schema_path (str, optional): Path to the schema file.
        verbose (bool): Whether to print detailed results.

    Returns:
        bool: True if validation passes, False otherwise.
    """
    try:
        # Load tokens
        with open(tokens_path, encoding="utf-8") as f:
            tokens = json.load(f)

        # Create validator
        validator = DesignTokenValidator(schema_path)

        # Run validation
        all_valid, results = validator.validate_all(tokens, tokens_path)

        if verbose or not all_valid:
            print(f"Validation results for {tokens_path}:")
            print(f"Overall result: {'PASS' if all_valid else 'FAIL'}")
            print()

            for check_name, errors in results.items():
                status = "PASS" if len([e for e in errors if not e.startswith("WARNING:")]) == 0 else "FAIL"
                print(f"{check_name.replace('_', ' ').title()}: {status}")

                if errors:
                    for error in errors:
                        if error.startswith("WARNING:"):
                            print(f"  ⚠️  {error}")
                        else:
                            print(f"  ❌ {error}")
                print()

        return all_valid

    except FileNotFoundError:
        print(f"Error: Tokens file not found: {tokens_path}")
        return False
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in tokens file: {e}")
        return False
    except Exception as e:
        print(f"Error: Validation failed: {e}")
        return False


def main() -> None:
    """CLI entry point for token validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate Anthrasite Design System tokens")
    parser.add_argument("tokens_file", help="Path to design tokens JSON file")
    parser.add_argument("--schema", help="Path to JSON schema file (optional)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    success = validate_tokens_file(args.tokens_file, args.schema, args.verbose)

    if success:
        print("✅ All validation checks passed!")
        sys.exit(0)
    else:
        print("❌ Validation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
