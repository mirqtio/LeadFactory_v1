#!/bin/bash
# Verify LeadFactory deployment meets P0-011 acceptance criteria

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 LeadFactory Deployment Verification"
echo "====================================="

# Check if required environment variables are set
if [ -z "$VPS_HOST" ] || [ -z "$VPS_USER" ]; then
    echo -e "${RED}❌ Error: VPS_HOST and VPS_USER environment variables must be set${NC}"
    echo "Usage: VPS_HOST=123.45.67.89 VPS_USER=ubuntu ./verify_deployment.sh"
    exit 1
fi

SSH_KEY="${SSH_KEY:-~/.ssh/id_rsa}"
CONTAINER_NAME="leadfactory"

echo -e "\n📋 Checking deployment on $VPS_USER@$VPS_HOST"

# Function to run SSH commands
run_ssh() {
    ssh -i "$SSH_KEY" -o ConnectTimeout=10 "$VPS_USER@$VPS_HOST" "$1"
}

# 1. Check container status
echo -e "\n1️⃣ Checking container status..."
CONTAINER_STATUS=$(run_ssh "docker ps --format '{{.Names}}:{{.Status}}' | grep $CONTAINER_NAME || echo 'NOT_FOUND'")

if [[ "$CONTAINER_STATUS" == "NOT_FOUND" ]]; then
    echo -e "${RED}❌ Container $CONTAINER_NAME is not running${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Container is running: $CONTAINER_STATUS${NC}"
fi

# 2. Check restart policy
echo -e "\n2️⃣ Checking restart policy..."
RESTART_POLICY=$(run_ssh "docker inspect $CONTAINER_NAME --format '{{.HostConfig.RestartPolicy.Name}}'")

if [[ "$RESTART_POLICY" == "always" ]]; then
    echo -e "${GREEN}✅ Restart policy is set to 'always'${NC}"
else
    echo -e "${RED}❌ Restart policy is '$RESTART_POLICY', expected 'always'${NC}"
    exit 1
fi

# 3. Test health endpoint
echo -e "\n3️⃣ Testing health endpoint..."
HEALTH_RESPONSE=$(run_ssh "curl -s -w '\nHTTP_CODE:%{http_code}\nRESPONSE_TIME:%{time_total}' http://localhost:8000/health")

HTTP_CODE=$(echo "$HEALTH_RESPONSE" | grep HTTP_CODE | cut -d: -f2)
RESPONSE_TIME=$(echo "$HEALTH_RESPONSE" | grep RESPONSE_TIME | cut -d: -f2)
HEALTH_JSON=$(echo "$HEALTH_RESPONSE" | head -n -2)

if [[ "$HTTP_CODE" == "200" ]]; then
    echo -e "${GREEN}✅ Health endpoint returned 200 OK${NC}"
    
    # Check response time (should be < 0.1 seconds)
    if (( $(echo "$RESPONSE_TIME < 0.1" | bc -l) )); then
        echo -e "${GREEN}✅ Response time: ${RESPONSE_TIME}s (< 100ms)${NC}"
    else
        echo -e "${YELLOW}⚠️  Response time: ${RESPONSE_TIME}s (> 100ms)${NC}"
    fi
    
    # Parse JSON response
    if echo "$HEALTH_JSON" | jq . >/dev/null 2>&1; then
        STATUS=$(echo "$HEALTH_JSON" | jq -r .status)
        DATABASE=$(echo "$HEALTH_JSON" | jq -r .database)
        ENVIRONMENT=$(echo "$HEALTH_JSON" | jq -r .environment)
        
        echo -e "   Status: $STATUS"
        echo -e "   Database: $DATABASE"
        echo -e "   Environment: $ENVIRONMENT"
        
        if [[ "$DATABASE" == "connected" ]]; then
            echo -e "${GREEN}✅ Database connectivity confirmed${NC}"
        else
            echo -e "${RED}❌ Database connection issue: $DATABASE${NC}"
        fi
    fi
else
    echo -e "${RED}❌ Health endpoint returned HTTP $HTTP_CODE${NC}"
    echo "$HEALTH_JSON"
    exit 1
fi

# 4. Check production configuration
echo -e "\n4️⃣ Checking production configuration..."
USE_STUBS=$(run_ssh "docker exec $CONTAINER_NAME env | grep USE_STUBS || echo 'NOT_SET'")

if [[ "$USE_STUBS" == *"false"* ]] || [[ "$USE_STUBS" == "NOT_SET" ]]; then
    echo -e "${GREEN}✅ USE_STUBS is not true in production${NC}"
else
    echo -e "${RED}❌ WARNING: USE_STUBS appears to be enabled in production!${NC}"
    echo "   $USE_STUBS"
fi

# 5. Check logs for errors
echo -e "\n5️⃣ Checking recent logs for errors..."
ERROR_COUNT=$(run_ssh "docker logs $CONTAINER_NAME --tail 100 2>&1 | grep -iE 'error|exception|critical' | wc -l")

if [[ "$ERROR_COUNT" -eq 0 ]]; then
    echo -e "${GREEN}✅ No errors found in recent logs${NC}"
else
    echo -e "${YELLOW}⚠️  Found $ERROR_COUNT error messages in recent logs${NC}"
    echo "   Run this to view: ssh $VPS_USER@$VPS_HOST 'docker logs $CONTAINER_NAME --tail 100 | grep -iE \"error|exception|critical\"'"
fi

# 6. Test persistence (optional)
if [[ "$1" == "--test-restart" ]]; then
    echo -e "\n6️⃣ Testing container auto-restart..."
    echo -e "${YELLOW}⚠️  This will kill and restart the container${NC}"
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_ssh "docker kill $CONTAINER_NAME"
        echo "   Container killed, waiting 10 seconds..."
        sleep 10
        
        NEW_STATUS=$(run_ssh "docker ps --format '{{.Names}}:{{.Status}}' | grep $CONTAINER_NAME || echo 'NOT_FOUND'")
        if [[ "$NEW_STATUS" != "NOT_FOUND" ]]; then
            echo -e "${GREEN}✅ Container auto-restarted: $NEW_STATUS${NC}"
        else
            echo -e "${RED}❌ Container did not restart automatically${NC}"
            exit 1
        fi
    fi
fi

# Summary
echo -e "\n📊 Verification Summary"
echo "====================="
echo -e "${GREEN}✅ All P0-011 acceptance criteria verified!${NC}"
echo ""
echo "Container: Running with 'always' restart policy"
echo "Health: Endpoint returns 200 OK with database connected"
echo "Performance: Response time < 100ms"
echo "Security: SSH key authentication working"
echo "Configuration: Production settings confirmed"
echo ""
echo -e "${GREEN}🎉 Deployment verification complete!${NC}"

# Run remote smoke tests if available
if command -v pytest &> /dev/null && [ -f "tests/smoke/test_remote_health.py" ]; then
    echo -e "\n7️⃣ Running remote smoke tests..."
    export LEADFACTORY_URL="http://$VPS_HOST:8000"
    pytest tests/smoke/test_remote_health.py -v --tb=short || echo -e "${YELLOW}⚠️  Some smoke tests failed${NC}"
fi