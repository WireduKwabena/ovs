# =============================================================================
# OVS / CAVP — Local Development Makefile
# =============================================================================
# Usage:
#   make up           Start all services
#   make down         Stop all services
#   make test         Run backend tests inside Docker
#   make test-fe      Run frontend tests locally
#   make coverage     Run backend tests with coverage report
#   make migrate      Apply database migrations
#   make lint         Run all linters
#   make build-fe     Build the frontend and hot-deploy to the running container
# =============================================================================

COMPOSE        = docker compose
BACKEND        = $(COMPOSE) run --rm --no-deps backend
BACKEND_DB     = $(COMPOSE) run --rm backend
FRONTEND_DIR   = frontend
DIST_DIR       = $(FRONTEND_DIR)/dist

# Django settings used for local test runs
DJANGO_SETTINGS ?= config.settings.development

.PHONY: up down restart logs \
        migrate migrations shell \
        test test-keep coverage \
        test-fe lint lint-be lint-fe \
        build-fe deploy-fe \
        check-deploy openapi-check

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

migrate:
	$(BACKEND_DB) python manage.py migrate

migrations:
	$(BACKEND_DB) python manage.py makemigrations

shell:
	$(BACKEND_DB) python manage.py shell

# ---------------------------------------------------------------------------
# Backend tests
# ---------------------------------------------------------------------------

test:
	$(BACKEND_DB) python manage.py test --keepdb

# Keep DB and run a single test path: make test-one PATH=apps.appointments.tests
test-one:
	$(BACKEND_DB) python manage.py test --keepdb $(PATH)

coverage:
	$(BACKEND_DB) sh -lc \
		"coverage run --rcfile=.coveragerc manage.py test --keepdb && \
		 coverage report --rcfile=.coveragerc && \
		 coverage html --rcfile=.coveragerc"
	@echo "HTML report: backend/htmlcov/index.html"

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

test-fe:
	cd $(FRONTEND_DIR) && npm test -- --run

test-fe-coverage:
	cd $(FRONTEND_DIR) && npm run test:coverage

lint-be:
	$(BACKEND) sh -lc "python -m flake8 . && mypy ."

lint-fe:
	cd $(FRONTEND_DIR) && npm run lint && npm run type-check

lint: lint-fe lint-be

build-fe:
	cd $(FRONTEND_DIR) && npm run build:ci

# Build frontend and hot-copy into the running container
deploy-fe: build-fe
	docker cp $(DIST_DIR)/. ovs_frontend:/workspace/dist/
	@echo "Frontend deployed to ovs_frontend container."

# ---------------------------------------------------------------------------
# CI helpers (run locally to pre-check before push)
# ---------------------------------------------------------------------------

check-deploy:
	$(BACKEND) sh -lc \
		"DJANGO_SETTINGS_MODULE=config.settings.production \
		 DEBUG=false \
		 SECRET_KEY=local-ci-check-key-1234567890 \
		 ALLOWED_HOSTS=localhost \
		 python manage.py check --deploy"

openapi-check:
	$(BACKEND) sh -lc \
		"python manage.py spectacular --file /tmp/openapi.generated.yaml --validate && \
		 diff -u openapi.yaml /tmp/openapi.generated.yaml" \
	&& echo "OpenAPI schema is in sync." \
	|| echo "OpenAPI schema has drifted — run 'python manage.py spectacular --file openapi.yaml' to update."
