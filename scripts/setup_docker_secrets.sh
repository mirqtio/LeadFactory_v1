#!/bin/bash
# Setup Docker secrets for production

echo "Setting up Docker secrets..."

# Function to create secret
create_secret() {
    local name=$1
    local value=$2
    echo "$value" | docker secret create "$name" - 2>/dev/null || echo "Secret $name already exists"
}

# Read values from .env file (you should fill these in)
if [ ! -f .env ]; then
    echo "Error: .env file not found. Copy .env.example and fill in values."
    exit 1
fi

# Source the env file
set -a
source .env
set +a

# Create secrets
create_secret "db_password" "$DATABASE_PASSWORD"
create_secret "redis_password" "$REDIS_PASSWORD"
create_secret "stripe_secret_key" "$STRIPE_SECRET_KEY"
create_secret "sendgrid_api_key" "$SENDGRID_API_KEY"
create_secret "openai_api_key" "$OPENAI_API_KEY"
create_secret "yelp_api_key" "$YELP_API_KEY"
create_secret "google_api_key" "$GOOGLE_API_KEY"
create_secret "sentry_dsn" "$SENTRY_DSN"
create_secret "secret_key" "$SECRET_KEY"

echo "Docker secrets created successfully!"
echo "Deploy with: docker stack deploy -c docker-compose.production.yml -c docker-compose.secrets.yml leadfactory"
