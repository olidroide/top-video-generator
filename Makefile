.ONESHELL:

install-requirements:
	uv sync --all-extras

dev-install:
	uv sync --all-extras --dev

install-hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-push

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
	uv run python scheduler.py

web-run:
	uv run python src/web/main.py

fetch-run:
	uv run python src/script_fetch_yt_data.py

publish-run:
	uv run python src/script_generate_publish_top_video.py

vertical-publish-run:
	uv run python src/script_generate_vertical_publish_top_video.py