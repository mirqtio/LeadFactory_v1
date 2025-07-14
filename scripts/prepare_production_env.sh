#!/bin/bash
# Prepare production environment from existing .env file

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🔧 Preparing Production Environment${NC}"
echo "================================================"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    exit 1
fi

# Create .env.production from .env
echo -e "${YELLOW}📋 Copying secrets from .env to .env.production...${NC}"
cp .env .env.production

# Update production-specific values
echo -e "${YELLOW}🔄 Updating production-specific settings...${NC}"

# Use a temporary file for sed operations
temp_file=$(mktemp)
cp .env.production "$temp_file"

# Update ENVIRONMENT to production
sed -i.bak 's/^ENVIRONMENT=.*/ENVIRONMENT=production/' "$temp_file"

# Ensure DEBUG is false
sed -i.bak 's/^DEBUG=.*/DEBUG=false/' "$temp_file"

# Ensure USE_STUBS is false
sed -i.bak 's/^USE_STUBS=.*/USE_STUBS=false/' "$temp_file"

# Update LOG_LEVEL to INFO (if it's DEBUG)
sed -i.bak 's/^LOG_LEVEL=DEBUG/LOG_LEVEL=INFO/' "$temp_file"

# Update LF_ENV to production
sed -i.bak 's/^LF_ENV=.*/LF_ENV=production/' "$temp_file"

# Generate a new SECRET_KEY for production if it's still the default
if grep -q "SECRET_KEY=your-secret-key-here" "$temp_file"; then
    echo -e "${YELLOW}🔑 Generating new SECRET_KEY for production...${NC}"
    NEW_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
    sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET_KEY|" "$temp_file"
fi

# Generate a strong database password if using default
if grep -q "DB_PASSWORD=leadfactory123" "$temp_file" || grep -q "POSTGRES_PASSWORD=leadfactory123" "$temp_file"; then
    echo -e "${YELLOW}🔐 Generating strong database password...${NC}"
    NEW_DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    
    # Update all database password references
    sed -i.bak "s|DB_PASSWORD=.*|DB_PASSWORD=$NEW_DB_PASSWORD|" "$temp_file"
    sed -i.bak "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$NEW_DB_PASSWORD|" "$temp_file"
    sed -i.bak "s|postgresql://leadfactory:[^@]*@|postgresql://leadfactory:$NEW_DB_PASSWORD@|" "$temp_file"
fi

# Move temp file back
mv "$temp_file" .env.production
rm -f "$temp_file.bak"

# Handle naming differences
echo -e "${YELLOW}🔄 Handling key naming differences...${NC}"

# If SENDGRID_KEY exists but not SENDGRID_API_KEY, copy it
if grep -q "^SENDGRID_KEY=" .env.production && ! grep -q "^SENDGRID_API_KEY=" .env.production; then
    SENDGRID_VALUE=$(grep "^SENDGRID_KEY=" .env.production | cut -d'=' -f2-)
    echo "SENDGRID_API_KEY=$SENDGRID_VALUE" >> .env.production
fi

# Add missing Google Places API key if we have Google API key
if grep -q "^GOOGLE_API_KEY=" .env.production && ! grep -q "^GOOGLE_PLACES_API_KEY=" .env.production; then
    GOOGLE_VALUE=$(grep "^GOOGLE_API_KEY=" .env.production | cut -d'=' -f2-)
    echo "GOOGLE_PLACES_API_KEY=$GOOGLE_VALUE" >> .env.production
    echo "GOOGLE_PAGESPEED_API_KEY=$GOOGLE_VALUE" >> .env.production
fi

# Add default SECRET_KEY if missing
if ! grep -q "^SECRET_KEY=" .env.production; then
    echo -e "${YELLOW}🔑 Adding SECRET_KEY...${NC}"
    NEW_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
    echo "SECRET_KEY=$NEW_SECRET_KEY" >> .env.production
fi

# Add database configuration if missing
if ! grep -q "^DB_PASSWORD=" .env.production; then
    echo -e "${YELLOW}🔐 Adding database configuration...${NC}"
    NEW_DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    echo "DB_PASSWORD=$NEW_DB_PASSWORD" >> .env.production
    echo "POSTGRES_PASSWORD=$NEW_DB_PASSWORD" >> .env.production
    echo "DATABASE_URL=postgresql://leadfactory:$NEW_DB_PASSWORD@db:5432/leadfactory" >> .env.production
fi

# Add Stripe price ID if missing (you'll need to update this with real value)
if ! grep -q "^STRIPE_PRICE_ID=" .env.production; then
    echo "STRIPE_PRICE_ID=price_UPDATE_ME_WITH_REAL_PRICE_ID" >> .env.production
fi

# Run verification
echo -e "\n${YELLOW}🔍 Verifying production secrets...${NC}"
./scripts/verify_secrets.sh .env.production

echo -e "\n${GREEN}✅ Production environment prepared!${NC}"
echo "================================================"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review .env.production to ensure all values are correct"
echo "2. Run: ./scripts/deploy_secrets.sh"
echo ""
echo -e "${YELLOW}⚠️  Security Notes:${NC}"
echo "- A new SECRET_KEY was generated for production"
echo "- Database password was strengthened (if using default)"
echo "- All production flags have been set correctly"