#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ask if user wants to remove volumes
read -p "Do you want to delete all containers & remove all data volumes? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🗑️  Removing volumes...${NC}"
    
    docker compose -f "$SCRIPT_DIR/airflow-compose.yml" down -v
    echo -e "${GREEN}✅ Airflow Removed${NC}\n"
    
    docker compose -f "$SCRIPT_DIR/elasticsearch-compose.yml" down -v
    echo -e "${GREEN}✅ Elasticsearch and Kibana Removed${NC}\n"
    
    docker compose -f "$SCRIPT_DIR/kafka-compose.yml" down -v
    echo -e "${GREEN}✅ Kafka Removed${NC}\n"

    echo -e "${GREEN}✅ All Containers Deleted & volumes removed${NC}\n"
else
    echo -e "${YELLOW}No Containers Deleted. Data will persist on next startup.${NC}\n"
fi

echo -e "${GREEN}👋 Goodbye!${NC}\n"
