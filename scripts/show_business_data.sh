#!/bin/bash
# Show all data for a business listing
# Usage: ./show_business_data.sh <business_id>

if [ -z "$1" ]; then
    echo "Usage: $0 <business_id>"
    echo ""
    echo "To find business IDs, run:"
    echo "docker exec leadfactory-postgres psql -U leadfactory -d leadfactory -c \"SELECT id, name, website FROM businesses ORDER BY created_at DESC LIMIT 10\""
    exit 1
fi

BUSINESS_ID=$1
DB_CONTAINER="leadfactory-postgres"
DB_USER="leadfactory"
DB_NAME="leadfactory"

echo "========================================="
echo "BUSINESS DETAILS"
echo "========================================="
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -x -c "
SELECT 
    id,
    yelp_id,
    name,
    website,
    url as yelp_url,
    phone,
    email,
    address,
    city,
    state,
    zip_code,
    latitude,
    longitude,
    vertical,
    categories,
    geo_bucket,
    vert_bucket,
    place_id as google_place_id,
    rating,
    user_ratings_total as review_count,
    price_level,
    business_status,
    created_at,
    updated_at
FROM businesses 
WHERE id = '$BUSINESS_ID'"

echo ""
echo "========================================="
echo "SCORING RESULTS"
echo "========================================="
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -x -c "
SELECT 
    id as score_id,
    score_raw,
    score_pct as score_percentage,
    tier,
    confidence,
    scoring_version,
    score_breakdown,
    passed_gate,
    created_at as scored_at
FROM scoring_results 
WHERE business_id = '$BUSINESS_ID'
ORDER BY created_at DESC"

echo ""
echo "========================================="
echo "ASSESSMENT RESULTS (if any)"
echo "========================================="
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
SELECT 
    id,
    assessment_type,
    performance_score,
    seo_score,
    accessibility_score,
    best_practices_score,
    created_at
FROM d3_assessment_results 
WHERE business_id = '$BUSINESS_ID'
ORDER BY created_at DESC" 2>/dev/null || echo "No assessment results found"

echo ""
echo "========================================="
echo "GEO FEATURES (if ZIP code exists)"
echo "========================================="
if [ ! -z "$2" ]; then
    ZIP_CODE=$2
else
    ZIP_CODE=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT zip_code FROM businesses WHERE id = '$BUSINESS_ID'" | xargs)
fi

if [ ! -z "$ZIP_CODE" ] && [ "$ZIP_CODE" != "" ]; then
    docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -x -c "
    SELECT * FROM geo_features WHERE zip = '$ZIP_CODE'" 2>/dev/null || echo "No geo features found for ZIP: $ZIP_CODE"
else
    echo "No ZIP code available"
fi

echo ""
echo "========================================="
echo "VERTICAL FEATURES (if categories exist)"
echo "========================================="
CATEGORIES=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT categories::text FROM businesses WHERE id = '$BUSINESS_ID'" | xargs)
if [ ! -z "$CATEGORIES" ] && [ "$CATEGORIES" != "" ] && [ "$CATEGORIES" != "null" ]; then
    # Extract first category from JSON array
    FIRST_CATEGORY=$(echo $CATEGORIES | sed 's/\["\([^"]*\)".*/\1/')
    if [ ! -z "$FIRST_CATEGORY" ]; then
        docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -x -c "
        SELECT * FROM vertical_features WHERE yelp_alias = '$FIRST_CATEGORY'" 2>/dev/null || echo "No vertical features found for category: $FIRST_CATEGORY"
    fi
else
    echo "No categories available"
fi