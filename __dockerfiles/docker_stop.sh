#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${YELLOW}🛑 Stopping Real-Time Log Processing Pipeline...${NC}\n"

# Stop services in reverse order
echo -e "${YELLOW}Stopping Airflow...${NC}"
docker compose -f "$SCRIPT_DIR/airflow-compose.yml" down
echo -e "${GREEN}✅ Airflow stopped${NC}\n"

echo -e "${YELLOW}Stopping Elasticsearch and Kibana...${NC}"
docker compose -f "$SCRIPT_DIR/elasticsearch-compose.yml" down
echo -e "${GREEN}✅ Elasticsearch and Kibana stopped${NC}\n"

echo -e "${YELLOW}Stopping Kafka...${NC}"
docker compose -f "$SCRIPT_DIR/kafka-compose.yml" down
echo -e "${GREEN}✅ Kafka stopped${NC}\n"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ All services stopped successfully!${NC}"
echo -e "${GREEN}👋 Goodbye!${NC}"
echo -e "${GREEN}========================================${NC}\n"
