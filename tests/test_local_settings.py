"""Private config must never silently select an unintended account."""
import json

import pytest

from pipeline import local_settings
from modules.publish import publisher
from modules.review import reviewer
from modules.distribution import orchestrator


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / 'private.json'
    path.write_text(json.dumps({
        'appid': 'test-app', 'appsecret': 'test-secret',
        'author': 'Test Author', 'wechatsync_token': 'test-sync',
        'llm': {'api_key': 'test-key', 'model': 'test-model', 'base_url': 'https://example.invalid/v1'},
    }))
    monkeypatch.setenv('PAPER_LOOP_CONFIG', str(path))
    for name in ('WECHAT_APPID', 'WECHAT_APPSECRET', 'WECHATSYNC_TOKEN', 'DEEPSEEK_API_KEY',
                 'PAPER_LOOP_LLM_MODEL', 'PAPER_LOOP_LLM_BASE_URL', 'PAPER_LOOP_AUTHOR'):
        monkeypatch.delenv(name, raising=False)
    return path


def test_all_consumers_read_private_file(config_file):
    assert publisher.load_config()['appid'] == 'test-app'
    assert publisher.load_config()['appsecret'] == 'test-secret'
    assert orchestrator._load_token() == 'test-sync'
    assert reviewer.get_api_credentials() == ('test-key', 'https://example.invalid/v1', 'test-model')
    assert local_settings.setting('author', 'PAPER_LOOP_AUTHOR') == 'Test Author'


def test_environment_overrides(config_file, monkeypatch):
    monkeypatch.setenv('WECHAT_APPSECRET', 'env-secret')
    monkeypatch.setenv('WECHATSYNC_TOKEN', 'env-sync')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'env-key')
    monkeypatch.setenv('PAPER_LOOP_AUTHOR', 'Env Author')
    assert publisher.load_config()['appsecret'] == 'env-secret'
    assert orchestrator._load_token() == 'env-sync'
    assert reviewer.get_api_credentials()[0] == 'env-key'
    assert local_settings.setting('author', 'PAPER_LOOP_AUTHOR') == 'Env Author'


@pytest.mark.parametrize('content', ['{bad-json SECRET', '[]', 'null'])
def test_invalid_config_fails_without_leaking_contents(config_file, content):
    config_file.write_text(content)
    with pytest.raises(ValueError, match='Invalid local configuration') as error:
        local_settings.load_local_settings()
    assert content not in str(error.value)


def test_explicit_missing_path_never_falls_back(config_file):
    config_file.unlink()
    with pytest.raises(FileNotFoundError, match='PAPER_LOOP_CONFIG'):
        publisher.load_config()


def test_repo_local_precedence_and_legacy_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv('PAPER_LOOP_CONFIG', raising=False)
    monkeypatch.setattr(local_settings, 'REPO_ROOT', tmp_path)
    monkeypatch.setattr(local_settings.Path, 'home', lambda: tmp_path / 'home')
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'config.json').write_text('{"author":"Legacy"}')
    assert local_settings.setting('author') == 'Legacy'
    (data / 'config.local.json').write_text('{"author":"Local"}')
    assert local_settings.setting('author') == 'Local'


def test_draft_uses_configured_author(config_file, monkeypatch):
    from unittest.mock import MagicMock
    response = MagicMock()
    response.read.return_value = b'{"media_id":"test-draft"}'
    captured = []
    def open_request(req, **kwargs):
        captured.append(json.loads(req.data))
        return response
    monkeypatch.setattr(publisher.urllib.request, 'urlopen', open_request)
    publisher.create_draft('test-token', 'title', '<p>text</p>', 'test-thumb')
    publisher.create_draft('test-token', 'title', '<p>text</p>', 'test-thumb', author='Article Author')
    assert captured[0]['articles'][0]['author'] == 'Test Author'
    assert captured[1]['articles'][0]['author'] == 'Article Author'
