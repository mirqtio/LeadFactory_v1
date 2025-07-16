#!/usr/bin/env python3
import re


def test_patterns():
    test_prompt = "Execute P2-010: Collaborative Buckets"

    # Test PRP extraction
    prp_patterns = [
        r"\\b(P[0-9]+-[0-9]+)\\b",
        r"PRP[\\s-]*(P[0-9]+-[0-9]+)",
    ]

    print(f"Testing prompt: '{test_prompt}'")
    print("\\nPRP ID extraction:")
    for pattern in prp_patterns:
        matches = re.finditer(pattern, test_prompt, re.IGNORECASE)
        for match in matches:
            print(f"  Pattern '{pattern}' found: {match.group(1)}")

    # Test intent detection
    start_patterns = [
        r"execute\\s+(P[0-9]+-[0-9]+)",
        r"(P[0-9]+-[0-9]+).*execute",
    ]

    print("\\nIntent detection:")
    for pattern in start_patterns:
        if re.search(pattern, test_prompt, re.IGNORECASE):
            print(f"  Pattern '{pattern}' MATCHED")
        else:
            print(f"  Pattern '{pattern}' no match")


if __name__ == "__main__":
    test_patterns()
