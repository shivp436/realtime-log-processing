.PHONY: help build start stop restart logs status clean reset

# Colors
GREEN := $(shell echo "\033[0;32m")
YELLOW := $(shell echo "\033[1;33m")
RED := $(shell echo "\033[0;31m")
BLUE := $(shell echo "\033[0;34m")
NC := $(shell echo "\033[0m")

help: ## Show this help message
	@echo '${GREEN}Real-Time Log Processing Pipeline${NC}'
	@echo '${YELLOW}Available commands:${NC}'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  ${GREEN}%-15s${NC} %s\n", $$1, $$2}'

build: ## Build all Docker images
	@chmod +x docker_build.sh
	@./docker_build.sh

start: ## Start all services with health checks
	@chmod +x docker_start.sh
	@./docker_start.sh

stop: ## Stop all services
	@chmod +x docker_stop.sh
	@./docker_stop.sh

restart: stop start ## Restart all services

# logs: ## Show logs for all services
# 	@echo "${YELLOW}Showing logs (Ctrl+C to exit)${NC}"
# 	@docker-compose -f docker-compose-kafka.yml logs -f & \
# 	docker-compose -f docker-compose-elasticsearch.yml logs -f & \
# 	docker-compose -f docker-compose-airflow.yml logs -f
#
# logs-airflow: ## Show Airflow worker logs
# 	@docker logs airflow-worker -f
#
# logs-producer: ## Show producer DAG logs
# 	@docker logs airflow-worker -f | grep "log-producer"
#
# logs-consumer: ## Show consumer DAG logs
# 	@docker logs airflow-worker -f | grep "log-consumer"
#
# logs-kafka: ## Show Kafka broker logs
# 	@docker logs kafka-broker-1 -f
#
# logs-es: ## Show Elasticsearch logs
# 	@docker logs elasticsearch -f

status: ## Show status of all services
	@echo "${GREEN}Docker Containers:${NC}"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "${GREEN}Service URLs:${NC}"
	@echo "  Airflow:       http://localhost:8081"
	@echo "  Kibana:        http://localhost:5601"
	@echo "  Elasticsearch: http://localhost:9200"
	@echo ""
	@echo "${GREEN}Kafka Topics:${NC}"
	@docker exec kafka-broker-1 kafka-topics.sh --bootstrap-server localhost:19092 --list || echo "  Kafka not ready"
	@echo ""
	@echo "${GREEN}Elasticsearch Indices:${NC}"
	@curl -s http://localhost:9200/_cat/indices?v 2>/dev/null || echo "  Elasticsearch not ready"

health: ## Check health of all services
	@echo "${YELLOW}Checking service health...${NC}"
	@echo -n "Kafka:         "
	@docker exec kafka-broker-1 kafka-topics.sh --bootstrap-server localhost:19092 --list >/dev/null 2>&1 && echo "${GREEN}✓${NC}" || echo "${YELLOW}✗${NC}"
	@echo -n "Elasticsearch: "
	@curl -sf http://localhost:9200/_cluster/health >/dev/null && echo "${GREEN}✓${NC}" || echo "${YELLOW}✗${NC}"
	@echo -n "Kibana:        "
	@curl -sf http://localhost:5601/api/status >/dev/null && echo "${GREEN}✓${NC}" || echo "${YELLOW}✗${NC}"
	@echo -n "Airflow:       "
	@curl -sf http://localhost:8081/health >/dev/null && echo "${GREEN}✓${NC}" || echo "${YELLOW}✗${NC}"

kafka-topics: ## List Kafka topics
	@docker exec kafka-broker-1 kafka-topics.sh --bootstrap-server localhost:19092 --list

kafka-describe: ## Describe web-logs-topic
	@docker exec kafka-broker-1 kafka-topics.sh --bootstrap-server localhost:19092 --describe --topic web-logs-topic

kafka-lag: ## Check consumer group lag
	@docker exec kafka-broker-1 kafka-consumer-groups.sh --bootstrap-server localhost:19092 --group elasticsearch-consumer-group --describe

es-count: ## Count documents in Elasticsearch
	@curl -s http://localhost:9200/web-logs-topic/_count | python3 -m json.tool

es-sample: ## Show sample documents from Elasticsearch
	@curl -s http://localhost:9200/web-logs-topic/_search?size=3&pretty

es-stats: ## Show Elasticsearch index statistics
	@curl -s http://localhost:9200/web-logs-topic/_stats?pretty

es-delete-index: ## Delete Elasticsearch index (will be recreated)
	@read -p "Are you sure you want to delete the index? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		curl -X DELETE http://localhost:9200/web-logs-topic; \
		echo "Index deleted"; \
	fi

reset-offsets: ## Reset Kafka consumer offsets to earliest
	@read -p "Are you sure you want to reset offsets? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker exec kafka-broker-1 kafka-consumer-groups.sh \
			--bootstrap-server localhost:19092 \
			--group elasticsearch-consumer-group \
			--reset-offsets --to-earliest \
			--topic web-logs-topic --execute; \
	fi

clean: ## Remove all containers (keeps volumes)
	@docker-compose -f docker-compose-airflow.yml down 2>/dev/null || true
	@docker-compose -f airflow-compose.yml down 2>/dev/null || true
	@docker-compose -f docker-compose-elasticsearch.yml down 2>/dev/null || true
	@docker-compose -f elasticsearch-compose.yml down 2>/dev/null || true
	@docker-compose -f docker-compose-kafka.yml down 2>/dev/null || true
	@docker-compose -f kafka-compose.yml down 2>/dev/null || true
	@echo "${GREEN}All containers removed${NC}"

reset: ## Remove all containers AND volumes (complete reset)
	@read -p "This will delete ALL data. Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose -f docker-compose-airflow.yml down -v 2>/dev/null || true; \
		docker-compose -f airflow-compose.yml down -v 2>/dev/null || true; \
		docker-compose -f docker-compose-elasticsearch.yml down -v 2>/dev/null || true; \
		docker-compose -f elasticsearch-compose.yml down -v 2>/dev/null || true; \
		docker-compose -f docker-compose-kafka.yml down -v 2>/dev/null || true; \
		docker-compose -f kafka-compose.yml down -v 2>/dev/null || true; \
		echo "${GREEN}Complete reset done${NC}"; \
	fi

shell-airflow: ## Open shell in Airflow worker
	@docker exec -it airflow-worker bash

shell-kafka: ## Open shell in Kafka broker
	@docker exec -it kafka-broker-1 bash

shell-es: ## Open shell in Elasticsearch
	@docker exec -it elasticsearch bash

test-kafka: ## Test Kafka connectivity from Airflow
	@docker exec airflow-worker bash -c "nc -zv kafka-broker-1 19092 && echo 'Kafka reachable'"

test-es: ## Test Elasticsearch connectivity from Airflow
	@docker exec airflow-worker bash -c "curl -f http://elasticsearch:9200/_cluster/health && echo 'Elasticsearch reachable'"

update: ## Pull latest images and rebuild
	@echo "${YELLOW}Pulling latest images...${NC}"
	@docker-compose -f docker-compose-kafka.yml pull 2>/dev/null || true
	@docker-compose -f docker-compose-elasticsearch.yml pull 2>/dev/null || true
	@echo "${YELLOW}Rebuilding Airflow...${NC}"
	@docker-compose -f docker-compose-airflow.yml build --no-cache

init: build start ## Initialize everything (build + start)
	@echo "${GREEN}Initialization complete!${NC}"
	@echo "Open Airflow UI: http://localhost:8081 (airflow/airflow)"

# Default target
.DEFAULT_GOAL := help
