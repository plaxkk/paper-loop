.PHONY: install test collector-start collector-stop profile strategy publish clean

# ── Install ──────────────────────────────────────────────────────────────────
install:
	pip install -e .

# ── Test ─────────────────────────────────────────────────────────────────────
test:
	pytest -v

# ── Collector ────────────────────────────────────────────────────────────────
collector-start:
	python -m pipeline run collect &

collector-stop:
	@PID=$$(pgrep -f "pipeline run collect" 2>/dev/null); \
	if [ -n "$$PID" ]; then \
		kill $$PID && echo "Collector stopped (PID: $$PID)"; \
	else \
		echo "Collector not running"; \
	fi

# ── Reports & Strategy ───────────────────────────────────────────────────────
profile:
	python -m pipeline run profile

strategy:
	python -m pipeline run strategy

# ── Publish ──────────────────────────────────────────────────────────────────
publish:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make publish FILE=<path>"; \
		exit 1; \
	fi
	python -m pipeline run publish --file "$(FILE)"

# ── Clean ────────────────────────────────────────────────────────────────────
clean:
	@echo "Cleaning temp files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "Done."
