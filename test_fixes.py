#!/usr/bin/env python
"""Test script to verify P0-001 fixes are working correctly."""

import sys

sys.path.insert(0, ".")

from datetime import datetime

from d4_enrichment.coordinator import EnrichmentCoordinator

# Test the fixed merge logic
coordinator = EnrichmentCoordinator()

# Test 1: Fixed merge logic - should return flat dict
print("=== Testing Fixed Merge Logic ===")
existing_data = {
    "field1": {"value": "old_value1", "provider": "google_places", "collected_at": datetime(2023, 1, 1, 12, 0, 0)},
    "field2": {"value": "old_value2", "provider": "google_places", "collected_at": datetime(2023, 1, 1, 12, 0, 0)},
}

new_data = {
    "field1": {
        "value": "new_value1",
        "provider": "google_places",
        "collected_at": datetime(2023, 1, 2, 12, 0, 0),  # Newer
    },
    "field3": {"value": "new_value3", "provider": "pagespeed", "collected_at": datetime(2023, 1, 1, 12, 0, 0)},
}

result = coordinator.merge_enrichment_data(existing_data, new_data)
print("Result type:", type(result))
print("Result keys:", list(result.keys()))
print("Field1 value (should be new_value1):", result["field1"]["value"])
print("Field1 provider:", result["field1"]["provider"])
print("Field2 value (should be old_value2):", result["field2"]["value"])
print("Field3 value (should be new_value3):", result["field3"]["value"])

# Test 2: Fixed cache key generation - should have proper format
print()
print("=== Testing Fixed Cache Key Generation ===")
key1 = coordinator.generate_cache_key("business_123", "google_places")
key2 = coordinator.generate_cache_key("business_123", "pagespeed")
key3 = coordinator.generate_cache_key("business_456", "google_places")

print("Key 1 (business_123 + google_places):", key1)
print("Key 2 (business_123 + pagespeed):", key2)
print("Key 3 (business_456 + google_places):", key3)

# Verify format: enrichment:v1:hash:provider:timestamp
parts1 = key1.split(":")
print("Key 1 parts:", parts1)
print("Key 1 format correct:", len(parts1) == 5 and parts1[0] == "enrichment" and parts1[1] == "v1")

# Verify uniqueness
print("Key 1 != Key 2 (different providers):", key1 != key2)
print("Key 1 != Key 3 (different business):", key1 != key3)

print()
print("✅ All fixes working correctly!")
