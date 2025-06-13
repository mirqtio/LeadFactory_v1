#!/bin/bash
# Simple URL test script
# Usage: ./test_url_simple.sh <url> [options]

if [ -z "$1" ]; then
    echo "Usage: $0 <url> [options]"
    echo "Options:"
    echo "  --search-location <location>  Location for Yelp search (default: 'United States')"
    echo "  -v, --verbose                 Show detailed output"
    echo ""
    echo "Examples:"
    echo "  $0 https://example.com"
    echo "  $0 starbucks.com --search-location 'Seattle, WA' -v"
    exit 1
fi

# Run the script in the Docker container
docker exec anthrasite_leadfactory_v1-app-1 python scripts/test_url_analysis_simple.py "$@"