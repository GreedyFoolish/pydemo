.PHONY: dev debug test test-unit test-integration test-e2e test-smoke db-migrate db-upgrade db-downgrade

dev:
	uv run --package web-service fastapi dev app/web-service/src/web_service/main.py --port 8080

debug:
	uv run --package web-service python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m fastapi dev app/web-service/src/web_service/main.py --port 8080

test:
	uv run pytest app/web-service/test/unit/ app/web-service/test/integration/ -q --cov=web-service --cov-report=term-missing --cov-fail-under=80

test-unit:
	uv run pytest app/web-service/test/unit/ -q

test-integration:
	uv run pytest app/web-service/test/integration/ -q

test-e2e:
	uv run pytest app/web-service/test/e2e/ -q

test-smoke:
	uv run pytest app/web-service/test/unit/ app/web-service/test/integration/ app/web-service/test/e2e/ -q -m smoke

db-migrate:
	uv run --package web-service alembic -c app/web-service/alembic.ini revision --autogenerate -m "$(message)"

db-upgrade:
	uv run --package web-service alembic -c app/web-service/alembic.ini upgrade head

db-downgrade:
	uv run --package web-service alembic -c app/web-service/alembic.ini downgrade $(version)
