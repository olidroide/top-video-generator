.ONESHELL:

install-requirements:
	uv sync --all-extras

dev-install:
	uv sync --all-extras --dev

install-hooks:
	git config --unset core.hooksPath || true
	uv run pre-commit install --install-hooks

pre-commit-run:
	uv run pre-commit run --hook-stage pre-commit --all-files

pre-push-check:
	uv run pre-commit run --hook-stage pre-push --all-files

build-local-image:
	docker buildx bake -f docker-bake.hcl top-video-generator-local

#build-image:
#	docker build -t top-video-generator .

run-web:
	docker compose build web
	docker compose up -d web

run-fetch-data:
	docker compose run --rm -e "STEP=fetch_data" top-video-generator

run-compose-daily:
	docker compose run --rm -e "STEP=vertical_publish" top-video-generator

format:
	uv run ruff format .

lint:
	uv run ruff check src tests

type-check:
	uv run ty check src/ tests/

quality:
	uv run ruff format --check src/ tests/
	uv run ruff check src/ tests/
	uv run ty check src/ tests/

test:
	uv run pytest tests/

schedule:
	docker compose up -d scheduler

web-run:
	uv run api-server

fetch-run:
	uv run fetch-data

publish-run:
	uv run publish-video

vertical-publish-run:
	uv run publish-vertical

scheduler-run:
	uv run scheduler-run
