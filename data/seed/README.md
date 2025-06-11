# Seed Data for Phase 0.5 Bucket Intelligence

This directory contains CSV files used to generate bucket assignments for businesses based on geographic and vertical characteristics.

## Files

### geo_features.csv
Contains ZIP code level features for generating geo buckets:
- **zip_code**: 5-digit US ZIP code
- **city**: City name
- **state**: 2-letter state code
- **affluence**: Income level (high/medium/low)
- **agency_density**: Concentration of marketing agencies (high/medium/low)
- **broadband_quality**: Internet infrastructure quality (high/medium/low)

Geo bucket format: `{affluence}-{agency_density}-{broadband_quality}`

Examples:
- `high-high-high`: Affluent area with many agencies and excellent broadband (e.g., SF Financial District)
- `low-low-medium`: Lower income area with few agencies and moderate broadband

### vertical_features.csv
Contains Yelp category mappings to vertical characteristics:
- **yelp_category**: Category slug from Yelp API
- **business_vertical**: High-level vertical grouping
- **urgency**: How urgently businesses need marketing (high/medium/low)
- **ticket_size**: Average customer transaction value (high/medium/low)
- **maturity**: Digital marketing sophistication (high/medium/low)

Vertical bucket format: `{urgency}-{ticket_size}-{maturity}`

Examples:
- `high-high-high`: Urgent need, high ticket, sophisticated (e.g., lawyers, plastic surgeons)
- `low-low-low`: Low urgency, small tickets, unsophisticated (e.g., cafes, hair salons)

## Usage

These CSV files are loaded by the bucket enrichment ETL process to:
1. Map businesses to their appropriate buckets based on ZIP code and categories
2. Enable targeted campaign segmentation
3. Provide input features for the hierarchical targeting model

## Data Coverage

- **Geo features**: 79 ZIP codes covering major US metro areas
- **Vertical features**: 90 Yelp categories covering 10 major business verticals

## Bucket Combinations

Theoretical combinations:
- Geo buckets: 3³ = 27 possible combinations (but only ~12 actually used)
- Vertical buckets: 3³ = 27 possible combinations (but only ~8 actually used)
- Total business buckets: ~96 meaningful combinations