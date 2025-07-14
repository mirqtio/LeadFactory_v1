#!/bin/bash
# Start the AI CTO Dashboard Docker container

echo "🚀 Starting AI CTO Dashboard container..."

# Stop existing container if running
docker stop leadfactory-dashboard 2>/dev/null
docker rm leadfactory-dashboard 2>/dev/null

# Start new container with the dashboard
docker run -d \
  --name leadfactory-dashboard \
  -p 8080:80 \
  -v $(pwd)/ai_cto_dashboard.html:/usr/share/nginx/html/index.html:ro \
  nginx:alpine

echo "✅ Dashboard running at http://localhost:8080"
echo "📊 The dashboard auto-refreshes every 30 seconds"
echo ""
echo "To update the dashboard manually, run:"
echo "  python update_dashboard_ci_status.py"
echo ""
echo "To run continuous updates (every 30s), run:"
echo "  python dashboard_continuous_updater.py"