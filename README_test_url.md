# URL Analysis Test Tool

This tool allows you to test the LeadFactory pipeline on any arbitrary URL without generating reports or sending emails.

## Usage

```bash
./test_url_simple.sh <url> [options]
```

### Options

- `--search-location <location>` - Location for Yelp business search (default: "United States")
- `-v, --verbose` - Show detailed output including all Yelp results

### Examples

```bash
# Test a restaurant website
./test_url_simple.sh https://www.mcdonalds.com

# Test with specific location
./test_url_simple.sh https://www.starbucks.com --search-location "Seattle, WA"

# Test with verbose output
./test_url_simple.sh example.com --search-location "San Francisco, CA" -v
```

## What It Does

1. **Yelp Search** - Searches for the business on Yelp based on the domain name
2. **Website Analysis** - Runs PageSpeed Insights to analyze the website performance
3. **Lead Scoring** - Calculates a simple lead score based on:
   - Business data (Yelp rating, reviews)
   - Website performance (PageSpeed score)
   - Returns a tier (A/B/C/D) and pass/fail gate decision

## Results

The tool displays:
- Business information (name, address, phone, ratings)
- Website performance scores (if PageSpeed API is available)
- Lead score with tier and breakdown
- Database ID for further queries

## Database Verification

After analysis, you can query the database directly:

```bash
# View business details
docker exec anthrasite_leadfactory_v1-db-1 psql -U leadfactory -d leadfactory_dev \
  -c "SELECT * FROM businesses WHERE id = '<business_id>'"

# View scoring details
docker exec anthrasite_leadfactory_v1-db-1 psql -U leadfactory -d leadfactory_dev \
  -c "SELECT * FROM scoring_results WHERE business_id = '<business_id>'"
```

## Notes

- The tool uses the domain name to search Yelp, so results may not always match the intended business
- PageSpeed API requires a valid API key in the environment
- Existing businesses are updated rather than duplicated
- This is a simplified version for testing - the full pipeline includes more sophisticated analysis