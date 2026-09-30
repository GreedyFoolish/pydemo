.PHONY: dev

dev:
	uv run --package web-service fastapi dev app/web-service/src/web_service/main.py --port 8080