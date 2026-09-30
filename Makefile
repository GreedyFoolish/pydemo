.PHONY: dev debug

dev:
	uv run --package web-service fastapi dev app/web-service/src/web_service/main.py --port 8080

debug:
	uv run --package web-service python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m fastapi dev app/web-service/src/web_service/main.py --port 8080