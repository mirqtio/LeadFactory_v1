#!/usr/bin/env python3
"""Test metrics initialization"""
import prometheus_client
from prometheus_client import Counter

# Test if prometheus adds names
print("Testing metric names...")

try:
    test_counter = Counter(
        "test_metric_total",
        "Test metric",
        registry=prometheus_client.REGISTRY
    )
    print(f"Created metric with name: test_metric_total")
    print(f"Metric describe: {test_counter.describe()}")
    
    # Try creating another with similar name
    test_counter2 = Counter(
        "test_metric",
        "Test metric 2",
        registry=prometheus_client.REGISTRY  
    )
    print(f"Created second metric with name: test_metric")
    
except Exception as e:
    print(f"Error: {e}")