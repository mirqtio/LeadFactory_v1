#!/bin/bash
# Test URL analysis script
# Usage: ./test_url.sh <url> [options]

if [ -z "$1" ]; then
    echo "Usage: $0 <url> [options]"
    echo "Options:"
    echo "  --search-location <location>  Location for Yelp search (default: 'United States')"
    echo "  --search-radius <meters>      Search radius in meters (default: 40000, max: 40000)"
    echo "  -v, --verbose                 Show detailed output"
    echo ""
    echo "Examples:"
    echo "  $0 https://example.com"
    echo "  $0 example.com --search-location 'San Francisco, CA' -v"
    echo "  $0 https://restaurant.com --search-radius 10000"
    exit 1
fi

# Run the script in the Docker container
docker exec anthrasite_leadfactory_v1-app-1 python scripts/test_url_analysis.py "$@"