.ONESHELL:

install-requirements:
	pip install -r requirements-dev.txt
	pip install -r requirements.txt


build-local-image:
	docker buildx bake -f docker-bake.hcl top-video-generator-local

#build-image:
#	docker build -t top-video-generator .

run-web:
	docker-compose -f ~/Git/top-video-generator/docker-compose.yml run -e "STEP=web" -p 8080:8080 --rm top-video-generator

run-fetch-data:
	docker-compose -f ~/Git/top-video-generator/docker-compose.yml run -e "STEP=fetch_data" --rm top-video-generator

run-compose-daily:
	docker-compose -f ~/Git/top-video-generator/docker-compose.yml run -e "STEP=vertical_publish" --rm top-video-generator


format:
	black .

lint:
	ruff check src tests

schedule:
	python scheduler.py