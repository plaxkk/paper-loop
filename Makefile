.PHONY: install test collector-start collector-stop collector-status collector-acceptance-report collector-inspect collector-script-info collector-self-test collector-title-fingerprint collector-validate collector-validate-published collector-watch-published profile strategy publish clean

# ── Install ──────────────────────────────────────────────────────────────────
install:
	pip install -e .

# ── Test ─────────────────────────────────────────────────────────────────────
test:
	pytest -v

# ── Collector ────────────────────────────────────────────────────────────────
collector-start:
	python -m pipeline.run collector-start --daemon

collector-stop:
	python -m pipeline.run collector-stop

collector-status:
	python -m pipeline.run collector-status

collector-acceptance-report:
	python -m pipeline.run collector-acceptance-report

collector-inspect:
	python -m pipeline.run collector-inspect --page-type all

collector-script-info:
	python -m pipeline.run collector-script-info

collector-self-test:
	python -m pipeline.run collector-self-test

collector-title-fingerprint:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make collector-title-fingerprint FILE=<expected_titles.txt>"; \
		exit 1; \
	fi
	python -m pipeline.run collector-title-fingerprint "$(FILE)"

collector-validate:
	python -m pipeline.run collector-validate

collector-validate-published:
	python -m pipeline.run collector-validate --strict-diagnostic --expected-diagnostic-kinds published_records_page_loaded,published_records_scan_started --strict-preview --strict-latest --strict-session --expected-preview-count 10 --expected-published-count 22 --expected-page-counts 10,10,2 --max-raw-age-seconds 600

collector-watch-published:
	python -m pipeline.run collector-validate --strict-diagnostic --expected-diagnostic-kinds published_records_page_loaded,published_records_scan_started --strict-preview --strict-latest --strict-session --expected-preview-count 10 --expected-published-count 22 --expected-page-counts 10,10,2 --max-raw-age-seconds 600 --watch-seconds 120 --poll-interval 2

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
