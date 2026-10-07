.PHONY: dev debug test test-unit test-integration test-e2e test-smoke test-changed db-migrate db-upgrade db-downgrade

dev:
	uv run --package web-service fastapi dev app/web-service/src/web_service/main.py --port 8080

debug:
	uv run --package web-service python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m fastapi dev app/web-service/src/web_service/main.py --port 8080

test:
	uv run --env-file .env pytest package/web-utils/test/ -q --cov=web_utils \
		--cov-report=html:htmlcov/web-utils \
		--cov-fail-under=20 && \
	uv run --env-file .env pytest app/web-service/test/unit/ -q --cov=web_service \
		--cov-report=html:htmlcov/web-service \
		--cov-fail-under=20

test-unit:
	uv run pytest package/web-utils/test/integration/ app/web-service/test/unit/ -q

test-integration:
	uv run pytest package/web-utils/test/integration/ app/web-service/test/integration/ -q

test-e2e:
	uv run pytest app/web-service/test/e2e/ -q

test-smoke:
	uv run pytest app/web-service/test/e2e/ -q -m smoke
	uv run pytest package/web-utils/test/ app/web-service/test/unit/ app/web-service/test/integration/ -q -m smoke

test-changed:
	uv run python scripts/run_changed_tests.py

db-migrate:
	uv run --package web-service alembic -c app/web-service/alembic.ini revision --autogenerate -m "$(message)"

db-upgrade:
	uv run --package web-service alembic -c app/web-service/alembic.ini upgrade head

db-downgrade:
	uv run --package web-service alembic -c app/web-service/alembic.ini downgrade $(version)
