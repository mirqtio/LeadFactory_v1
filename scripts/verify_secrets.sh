#!/bin/bash
# Verify that all required secrets are present in .env.production

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ENV_FILE="${1:-.env.production}"

echo -e "${GREEN}🔍 Verifying Production Secrets${NC}"
echo "================================================"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: $ENV_FILE not found${NC}"
    exit 1
fi

# Required secrets
REQUIRED_SECRETS=(
    "SECRET_KEY"
    "DB_PASSWORD"
    "DATABASE_URL"
    "GOOGLE_API_KEY"
    "GOOGLE_PLACES_API_KEY"
    "GOOGLE_PAGESPEED_API_KEY"
    "STRIPE_SECRET_KEY"
    "STRIPE_PUBLISHABLE_KEY"
    "STRIPE_WEBHOOK_SECRET"
    "STRIPE_PRICE_ID"
    "SENDGRID_API_KEY"
    "OPENAI_API_KEY"
)

# Optional but recommended
OPTIONAL_SECRETS=(
    "DATA_AXLE_API_KEY"
    "SEMRUSH_API_KEY"
    "SCREENSHOTONE_KEY"
    "HUNTER_API_KEY"
    "DATADOG_API_KEY"
    "SENTRY_DSN"
)

echo -e "${YELLOW}Checking required secrets...${NC}"
missing_required=0
for secret in "${REQUIRED_SECRETS[@]}"; do
    if grep -q "^${secret}=" "$ENV_FILE"; then
        value=$(grep "^${secret}=" "$ENV_FILE" | cut -d'=' -f2-)
        if [[ "$value" == *"<"* ]] || [[ -z "$value" ]]; then
            echo -e "${RED}❌ $secret is not set (contains placeholder or empty)${NC}"
            missing_required=$((missing_required + 1))
        else
            echo -e "${GREEN}✅ $secret is set${NC}"
        fi
    else
        echo -e "${RED}❌ $secret is missing${NC}"
        missing_required=$((missing_required + 1))
    fi
done

echo -e "\n${YELLOW}Checking optional secrets...${NC}"
missing_optional=0
for secret in "${OPTIONAL_SECRETS[@]}"; do
    if grep -q "^${secret}=" "$ENV_FILE"; then
        value=$(grep "^${secret}=" "$ENV_FILE" | cut -d'=' -f2-)
        if [[ "$value" == *"<"* ]] || [[ -z "$value" ]]; then
            echo -e "${YELLOW}⚠️  $secret is not set (optional)${NC}"
            missing_optional=$((missing_optional + 1))
        else
            echo -e "${GREEN}✅ $secret is set${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  $secret is missing (optional)${NC}"
        missing_optional=$((missing_optional + 1))
    fi
done

echo -e "\n================================================"
if [ $missing_required -eq 0 ]; then
    echo -e "${GREEN}✅ All required secrets are set!${NC}"
    echo -e "${YELLOW}📊 Optional secrets: $((${#OPTIONAL_SECRETS[@]} - missing_optional))/${#OPTIONAL_SECRETS[@]} set${NC}"
    echo -e "\n${GREEN}Ready to deploy!${NC}"
    exit 0
else
    echo -e "${RED}❌ Missing $missing_required required secrets${NC}"
    echo -e "${YELLOW}Please fill in all required values in $ENV_FILE${NC}"
    exit 1
fi