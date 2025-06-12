# LeadFactory Observability Guide

## Quick Start (< 1 minute)

1. **Get your Datadog API key**
   - Sign in to [Datadog](https://app.datadoghq.com)
   - Navigate to Integrations → APIs → API Keys
   - Copy your API key

2. **Configure your environment**
   ```bash
   echo "DATADOG_API_KEY=your-api-key-here" >> .env
   echo "LF_ENV=local" >> .env  # or staging/production
   ```

3. **Start monitoring**
   ```bash
   docker compose pull
   docker compose up -d
   ```

4. **View your data**
   - Open [Datadog Infrastructure → Containers](https://app.datadoghq.com/containers)
   - All LeadFactory services should appear within ~30 seconds
   - Container metrics, logs, and traces are automatically collected

## What's Monitored

### Automatic Collection
The Datadog Agent automatically discovers and monitors:
- **All containers**: CPU, memory, network, disk I/O
- **Application logs**: Structured JSON logs from all services
- **Database metrics**: PostgreSQL queries, connections, performance
- **Cache metrics**: Redis operations, memory usage, hit rates
- **API traces**: Request flows across services (if instrumented)

### Zero Configuration Required
After this initial setup, any new services added to docker-compose will be automatically discovered and monitored.

## Datadog Dashboards

### Pre-built Dashboards
Navigate to these dashboards in Datadog:

1. **[Container Overview](https://app.datadoghq.com/containers)**
   - Real-time container status
   - Resource utilization
   - Container lifecycle events

2. **[Logs Explorer](https://app.datadoghq.com/logs)**
   - Search and filter logs across all services
   - Pattern detection and anomaly alerts
   - Log-based metrics

3. **[APM Service Map](https://app.datadoghq.com/apm/services)**
   - Service dependencies
   - Request flow visualization
   - Performance bottlenecks

4. **[Host Map](https://app.datadoghq.com/infrastructure/map)**
   - Infrastructure overview
   - Resource heat maps
   - Grouping by environment

### Custom Dashboards
Create custom dashboards for:
- Business metrics (leads, conversions, revenue)
- API performance by endpoint
- External API usage and costs
- Campaign funnel analytics

## Environment Configuration

Set `LF_ENV` in your `.env` file:
- `local` - Local development
- `staging` - Staging environment
- `production` - Production environment

This tags all metrics, logs, and traces with the environment for easy filtering.

## Troubleshooting

- **No data appearing?** Check `docker logs datadog` for API key errors
- **Missing containers?** Ensure Docker socket is mounted correctly
- **No logs?** Verify `DD_LOGS_ENABLED=true` is set
- **APM not working?** Applications need instrumentation libraries installed