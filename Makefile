# Colors for terminal output
GREEN := $(shell echo "\033[0;32m")
YELLOW := $(shell echo "\033[1;33m")
RED := $(shell echo "\033[0;31m")
BLUE := $(shell echo "\033[0;34m")
NC := $(shell echo "\033[0m")

# Docker compose file paths
DOCKER_DIR := __dockerfiles
KAFKA_COMPOSE := $(DOCKER_DIR)/kafka-compose.yml
ES_COMPOSE := $(DOCKER_DIR)/elasticsearch-compose.yml
AIRFLOW_COMPOSE := $(DOCKER_DIR)/airflow-compose.yml

.PHONY: help
help: ## Show this help message
	@echo '${GREEN}Real-Time Log Processing Pipeline${NC}'
	@echo '${YELLOW}Available commands:${NC}'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "   ${GREEN}%-15s${NC} %s\n", $$1, $$2}'

.PHONY: build
build: ## Build all Docker images
	@chmod +x $(DOCKER_DIR)/docker_build.sh
	@cd $(DOCKER_DIR) && ./docker_build.sh

.PHONY: start
start: ## Start all services with health checks
	@chmod +x $(DOCKER_DIR)/docker_start.sh
	@cd $(DOCKER_DIR) && ./docker_start.sh

.PHONY: stop
stop: ## Stop all services
	@chmod +x $(DOCKER_DIR)/docker_stop.sh
	@cd $(DOCKER_DIR) && ./docker_stop.sh

.PHONY: restart
restart: stop start ## Restart all services

.PHONY: clean
clean: ## Stop all docker services and remove their volumes
	@chmod +x $(DOCKER_DIR)/docker_remove.sh
	@cd $(DOCKER_DIR) && ./docker_remove.sh

.PHONY: logs-kafka
logs-kafka: ## Show Kafka logs
	@docker compose -f $(KAFKA_COMPOSE) logs -f

.PHONY: logs-elasticsearch
logs-elasticsearch: ## Show Elasticsearch logs
	@docker compose -f $(ES_COMPOSE) logs -f

.PHONY: logs-airflow
logs-airflow: ## Show Airflow logs
	@docker compose -f $(AIRFLOW_COMPOSE) logs -f

.PHONY: status
status: ## Show status of all containers
	@echo "${YELLOW}Container Status:${NC}"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "kafka|elasticsearch|kibana|airflow|conduktor" || echo "No containers running"

.PHONY: shell-airflow
shell-airflow: ## Open shell in Airflow worker container
	@docker exec -it airflow-worker /bin/bash

.PHONY: shell-kafka
shell-kafka: ## Open shell in Kafka broker container
	@docker exec -it kafka-broker-1 /bin/bash

.PHONY: shell-elasticsearch
shell-elasticsearch: ## Open shell in Elasticsearch container
	@docker exec -it elasticsearch /bin/bash

.PHONY: init
init: ## Initialize project (create .env and directories)
	@echo "${YELLOW}Initializing project...${NC}"
	@mkdir -p dags logs plugins config
	@if [ ! -f .env ]; then \
		echo "${YELLOW}Creating .env file...${NC}"; \
		echo "# Airflow Configuration" > .env; \
		echo "AIRFLOW_UID=$$(id -u)" >> .env; \
		echo "AIRFLOW_PROJ_DIR=." >> .env; \
		echo "_AIRFLOW_WWW_USER_USERNAME=airflow" >> .env; \
		echo "_AIRFLOW_WWW_USER_PASSWORD=airflow" >> .env; \
		echo "" >> .env; \
		echo "# Kafka Configuration (for containers)" >> .env; \
		echo "KAFKA_BOOTSTRAP_SERVERS=kafka-broker-1:19092,kafka-broker-2:19092" >> .env; \
		echo "" >> .env; \
		echo "# Elasticsearch Configuration (for containers)" >> .env; \
		echo "ELASTICSEARCH_HOSTS=http://elasticsearch:9200" >> .env; \
		echo "${GREEN}✅ Created .env file${NC}"; \
	else \
		echo "${BLUE}ℹ️  .env file already exists${NC}"; \
	fi
	@echo "${GREEN}✅ Project initialized${NC}"
