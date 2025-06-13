#!/bin/bash
# Wrapper script to show business data
# Usage: ./show_business.sh <business_id or partial_name>

if [ -z "$1" ]; then
    echo "Usage: $0 <business_id or partial_name>"
    echo ""
    echo "Recent businesses:"
    docker exec leadfactory-postgres psql -U leadfactory -d leadfactory_dev -c "
    SELECT 
        id,
        name,
        website,
        created_at
    FROM businesses 
    ORDER BY created_at DESC 
    LIMIT 10"
    exit 1
fi

INPUT=$1

# Check if input looks like a UUID
if [[ $INPUT =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    # It's a UUID, use directly
    ./scripts/show_business_data.sh "$INPUT"
else
    # It's a name search, find the business
    echo "Searching for businesses matching: $INPUT"
    
    BUSINESS_ID=$(docker exec leadfactory-postgres psql -U leadfactory -d leadfactory_dev -t -c "
    SELECT id 
    FROM businesses 
    WHERE LOWER(name) LIKE LOWER('%$INPUT%') 
    ORDER BY created_at DESC 
    LIMIT 1" | xargs)
    
    if [ -z "$BUSINESS_ID" ] || [ "$BUSINESS_ID" == "" ]; then
        echo "No business found matching: $INPUT"
        echo ""
        echo "Recent businesses:"
        docker exec leadfactory-postgres psql -U leadfactory -d leadfactory_dev -c "
        SELECT 
            id,
            name,
            website,
            created_at
        FROM businesses 
        ORDER BY created_at DESC 
        LIMIT 10"
        exit 1
    fi
    
    echo "Found business ID: $BUSINESS_ID"
    echo ""
    ./scripts/show_business_data.sh "$BUSINESS_ID"
fi