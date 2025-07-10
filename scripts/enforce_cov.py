#!/usr/bin/env python3
"""
Coverage enforcement script for CI

Usage: python scripts/enforce_cov.py coverage.xml 90
"""
import sys
import xml.etree.ElementTree as ET
import pathlib

def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/enforce_cov.py <coverage.xml> <threshold>")
        sys.exit(1)
    
    coverage_file = pathlib.Path(sys.argv[1])
    threshold = float(sys.argv[2])
    
    if not coverage_file.exists():
        print(f"Error: Coverage file {coverage_file} not found")
        sys.exit(1)
    
    # Parse XML
    tree = ET.parse(coverage_file)
    root = tree.getroot()
    
    # Get line rate (coverage percentage)
    line_rate = float(root.attrib.get('line-rate', '0'))
    coverage_percent = line_rate * 100
    
    print(f"Total coverage: {coverage_percent:.1f}% (required {threshold}%)")
    
    if coverage_percent >= threshold:
        print("✅ Coverage check passed!")
        sys.exit(0)
    else:
        print("❌ Coverage check failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()