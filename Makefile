.ONESHELL:

install-requirements:
	uv sync --all-extras

dev-install:
	uv sync --all-extras --dev

install-hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-commit
	chmod +x .githooks/pre-push

pre-commit-run:
	uv run pre-commit run --all-files

pre-push-check:
	make quality
	uv run pytest tests/ -x -q --ignore=tests/integration/video

build-local-image:
	docker buildx bake -f docker-bake.hcl top-video-generator-local

#build-image:
#	docker build -t top-video-generator .

run-web:
	docker-compose -f ~/Git/top-video-generator/docker-compose.yml run -e "STEP=web" -p 8080:8080 --detach --rm top-video-generator

run-fetch-data:
	docker-compose -f ~/Git/top-video-generator/docker-compose.yml run -e "STEP=fetch_data" --rm top-video-generator

run-compose-daily:
	docker-compose -f ~/Git/top-video-generator/docker-compose.yml run -e "STEP=vertical_publish" --rm top-video-generator

format:
	uv run ruff format .

lint:
	uv run ruff check src tests

type-check:
	uv run ty src tests

quality:
	uv run ruff format --check src/ tests/
	uv run ruff check src/ tests/
	uv run ty check src/

test:
	uv run pytest tests/

schedule:
	@echo "No in-repo scheduler entrypoint is maintained. Run fetch-run/publish-run from cron, CI, or orchestration."
	@exit 1

web-run:
	uv run api-server

fetch-run:
	uv run fetch-data

publish-run:
	uv run publish-video

vertical-publish-run:
	uv run publish-vertical
