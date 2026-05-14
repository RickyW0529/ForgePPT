# Makefile
.PHONY: up down test logs build clean

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd python_worker && pytest tests/ -v
	cargo test

test-e2e:
	pytest tests/e2e/ -v

build:
	docker compose build

clean:
	docker compose down -v
	rm -rf python_worker/tests/fixtures/output_*.pptx
	rm -rf python_worker/tests/fixtures/round_trip.pptx
