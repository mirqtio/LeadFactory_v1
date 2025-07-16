# P1-080: Bucket Enrichment Flow

## Overview

The Bucket Enrichment Flow is a sophisticated batch processing system that enriches businesses by industry segment with intelligent prioritization, budget controls, and performance monitoring.

## Key Features

### 1. Industry Bucket Strategy

The system categorizes businesses into buckets based on their industry/vertical with different processing strategies:

- **Healthcare** (HIGH priority): High-value targets with strict budget controls
  - Max budget: $1,000
  - Batch size: 50 (smaller for quality)
  - Enrichment sources: Internal, Data Axle, Hunter.io
  - Skip if enriched within 30 days

- **SaaS** (MEDIUM priority): Medium-value targets with normal budget
  - Max budget: $500
  - Batch size: 100
  - Enrichment sources: Internal, Hunter.io
  - Skip if enriched within 14 days

- **Restaurants** (LOW priority): Low-value targets with minimal budget
  - Max budget: $100
  - Batch size: 200 (larger for efficiency)
  - Enrichment sources: Internal only
  - Skip if enriched within 7 days

- **Default** (MINIMAL priority): Other businesses
  - Max budget: $50
  - Batch size: 150
  - Enrichment sources: Internal only
  - Skip if enriched within 7 days

### 2. Priority Queue System

Buckets are processed in priority order to ensure high-value targets get enriched first:

```python
queue = BucketQueue()
queue.add_bucket("healthcare-urgent", healthcare_config)
queue.add_bucket("restaurants-low", restaurant_config)

# Process in priority order
bucket1 = queue.get_next()  # Returns healthcare (HIGH priority)
bucket2 = queue.get_next()  # Returns restaurants (LOW priority)
```

### 3. Budget Management

The system enforces budget limits at multiple levels:
- Per-bucket budget limits
- Total flow budget limit
- Cost tracking per enrichment ($0.10 estimated per business)
- Automatic stopping when budget exhausted

### 4. Batch Processing

Efficient batch processing with:
- Configurable batch sizes per bucket type
- Concurrent enrichment with rate limiting
- Skip recently enriched businesses
- Error resilience (failures don't stop the batch)

### 5. Progress Tracking

Comprehensive statistics tracking:
- Businesses processed per bucket
- Success rates
- Cost tracking
- Processing time
- Error collection

## Usage

### Manual Trigger

```python
from flows.bucket_enrichment_flow import trigger_bucket_enrichment

# Process top 3 buckets with $100 budget
result = await trigger_bucket_enrichment(
    max_buckets=3,
    total_budget=100.0
)

print(f"Processed {result['buckets_processed']} buckets")
print(f"Enriched {result['total_enriched']} businesses")
print(f"Total cost: ${result['total_cost']:.2f}")
```

### Scheduled Deployment

The flow is designed to run nightly via Prefect:

```python
from flows.bucket_enrichment_flow import create_nightly_deployment

deployment = create_nightly_deployment()
# Runs at 2 AM daily with:
# - No bucket limit (process all)
# - $5,000 daily budget
# - Focus on top 50 buckets by size
```

### Direct Flow Execution

```python
from flows.bucket_enrichment_flow import bucket_enrichment_flow

result = await bucket_enrichment_flow(
    max_buckets=10,        # Process max 10 buckets
    total_budget=1000.0,   # $1,000 total budget
    bucket_limit=20        # Consider only top 20 buckets
)
```

## Flow Process

1. **Identify Bucket Segments**
   - Query database for unique vertical buckets
   - Count businesses per bucket
   - Order by business count

2. **Build Priority Queue**
   - Map buckets to strategies (healthcare, saas, restaurants, default)
   - Order by priority (HIGH → MEDIUM → LOW → MINIMAL)

3. **Process Each Bucket**
   - Get businesses needing enrichment (skip recent)
   - Process in batches with configured size
   - Track cost and enforce budget limits
   - Update database with results

4. **Generate Summary**
   - Total businesses processed
   - Success rates per bucket
   - Total cost
   - Processing statistics

## Database Schema

The flow requires:
- `businesses.vert_bucket`: Vertical bucket assignment
- `businesses.geo_bucket`: Geographic bucket assignment  
- `businesses.last_enriched_at`: Timestamp of last enrichment

## Integration Points

### Enrichment Sources
- Uses `EnrichmentCoordinator` from D4
- Supports multiple enrichment sources per bucket
- Automatic failover between sources

### Bucket Loader
- Uses `BucketLoader` from D1 for bucket assignments
- Maps businesses to geo/vert buckets based on features

### Database
- Reads from `businesses` table
- Updates enrichment timestamps
- Tracks processing state

## Performance Considerations

- **Concurrency**: Configurable per bucket type (3-10 concurrent requests)
- **Batch Sizes**: Optimized per bucket (50-200 businesses)
- **Skip Logic**: Avoids re-enriching recent data
- **Budget Controls**: Prevents runaway costs
- **Error Handling**: Continues on failures

## Monitoring

The flow provides detailed monitoring:
- Per-bucket statistics
- Success/failure rates
- Cost tracking
- Processing times
- Error logs

## Example Output

```json
{
    "status": "completed",
    "buckets_processed": 3,
    "total_businesses": 350,
    "total_enriched": 285,
    "total_failed": 15,
    "total_cost": 28.50,
    "average_success_rate": 81.4,
    "bucket_stats": [
        {
            "bucket": "healthcare-urgent",
            "strategy": "healthcare",
            "enriched": 90,
            "total": 100,
            "cost": 9.0,
            "success_rate": 90.0,
            "errors": 0
        },
        {
            "bucket": "saas-medium",
            "strategy": "saas",
            "enriched": 145,
            "total": 150,
            "cost": 14.5,
            "success_rate": 96.7,
            "errors": 1
        },
        {
            "bucket": "restaurants-low",
            "strategy": "restaurants",
            "enriched": 50,
            "total": 100,
            "cost": 5.0,
            "success_rate": 50.0,
            "errors": 2
        }
    ]
}
```

## Error Handling

- Individual business failures don't stop the batch
- Bucket processing errors are logged but flow continues
- Budget exhaustion stops processing gracefully
- All errors collected in statistics

## Testing

The implementation includes:
- Unit tests for all components
- Integration tests with mock database
- Priority queue testing
- Budget enforcement testing
- Error scenario testing