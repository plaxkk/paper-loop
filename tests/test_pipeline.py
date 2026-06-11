"""Smoke tests for the Paper-to-WeChat Pipeline."""

from __future__ import annotations

import importlib
import tempfile
import os
from pathlib import Path
from unittest import mock

import pytest

import pipeline


class TestPackage:
    def test_version_is_string(self) -> None:
        assert isinstance(pipeline.__version__, str)
        assert len(pipeline.__version__) > 0

    def test_version_parseable(self) -> None:
        parts = pipeline.__version__.split(".")
        assert len(parts) == 3
        for p in parts:
            int(p)


class TestConfig:
    def test_singleton_same_instance(self) -> None:
        from pipeline.config import Config
        c1 = Config.get()
        c2 = Config.get()
        assert c1 is c2

    def test_default_values(self) -> None:
        from pipeline.config import Config
        with mock.patch.object(Config, "_default_config_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/config.json")
            cfg = Config.reload()
        assert cfg.collector_port == 8899

    def test_env_var_fallback(self) -> None:
        from pipeline.config import Config
        with mock.patch.dict("os.environ", {"PAPER_TO_WECHAT_COLLECTOR_PORT": "9999"}):
            with mock.patch.object(Config, "_default_config_path") as mock_path:
                mock_path.return_value = Path("/nonexistent/config.json")
                cfg = Config.reload()
            assert cfg.collector_port == 9999

    def test_config_file_overrides_env(self) -> None:
        from pipeline.config import Config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            tf.write('{"collector_port": 7777}')
            config_path = tf.name
        try:
            with mock.patch.dict("os.environ", {"PAPER_TO_WECHAT_COLLECTOR_PORT": "9999"}):
                with mock.patch.object(Config, "_default_config_path") as mock_path:
                    mock_path.return_value = Path(config_path)
                    cfg = Config.reload()
                assert cfg.collector_port == 7777
        finally:
            Path(config_path).unlink()


class TestCLI:
    def test_parser_help(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit) as e:
            main(["-h"])
        assert e.value.code == 0

    def test_collector_start(self) -> None:
        from pipeline.run import main
        # collector-start opens a server, so we just verify parser accepts it
        with pytest.raises(SystemExit) as e:
            main(["collector-start", "--help"])
        assert e.value.code == 0

    def test_profile_command(self) -> None:
        from pipeline.run import main
        import sys
        # Mock to avoid actual DB query
        rc = main(["profile"])
        assert rc is None  # prints to stdout, returns None

    def test_strategy_command(self) -> None:
        from pipeline.run import main
        rc = main(["strategy"])
        assert rc is None

    def test_publish_command_requires_file(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit):
            main(["publish"])

    def test_publish_command_with_file(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit) as e:
            main(["publish", "/nonexistent/article.json"])
        assert e.value.code == 1  # file not found

    def test_review_command_requires_file(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit):
            main(["review"])

    def test_review_command_with_file(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit) as e:
            main(["review", "/nonexistent/article.json"])
        assert e.value.code == 1

    def test_unknown_command_exits(self) -> None:
        from pipeline.run import main
        with pytest.raises(SystemExit):
            main(["nonexistent"])


class TestModulesImportable:
    def test_modules_package(self) -> None:
        import modules
        assert modules

    @pytest.mark.parametrize("module_name", ["write", "review", "publish", "analytics", "browser"])
    def test_submodule_importable(self, module_name: str) -> None:
        mod = importlib.import_module(f"modules.{module_name}")
        assert mod is not None
