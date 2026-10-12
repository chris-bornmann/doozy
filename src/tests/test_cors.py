import pytest
from pydantic import ValidationError

from pydantic_settings import SettingsConfigDict

from app.config import Settings

# Set for the test environment in src/conftest.py, the same way any other
# environment sets CORS_ORIGINS in its own .env file.
TEST_GUI_ORIGIN = 'https://gui.test.example'


class _SettingsWithoutDotenv(Settings):
    """Settings that read only environment variables, so a developer's local
    .env file can't affect these tests."""
    model_config = SettingsConfigDict(env_file=None)


def _preflight(
    client,
    origin: str,
):
    """Send the CORS preflight request a browser makes before a cross-origin API call."""
    return client.options(
        '/users/me',
        headers={
            'Origin': origin,
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Authorization',
        },
    )


def test_cors_allows_the_environments_gui_origin(
    client,
):
    response = _preflight(client, TEST_GUI_ORIGIN)
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == TEST_GUI_ORIGIN


def test_cors_refuses_other_origins(
    client,
):
    # Includes the local-dev default, which this environment did not list:
    # each environment's list replaces the default rather than adding to it.
    for origin in ['https://evil.example', 'http://localhost:5173']:
        response = _preflight(client, origin)
        assert response.status_code == 400, origin
        assert 'access-control-allow-origin' not in response.headers, origin


def test_cors_origins_parses_a_comma_separated_list(
    monkeypatch,
):
    # Set the way an environment would: one comma-separated variable.
    monkeypatch.setenv(
        'CORS_ORIGINS',
        ' https://doozy.example.com , http://localhost:5173,,https://staging.example.com:8443 ',
    )
    settings = _SettingsWithoutDotenv()
    assert settings.CORS_ORIGINS == [
        'https://doozy.example.com',
        'http://localhost:5173',
        'https://staging.example.com:8443',
    ]


def test_cors_origins_defaults_to_local_development(
    monkeypatch,
):
    monkeypatch.delenv('CORS_ORIGINS', raising=False)
    settings = _SettingsWithoutDotenv()
    assert settings.CORS_ORIGINS == ['http://localhost:5173', 'http://localhost:8080']


@pytest.mark.parametrize(
    'bad_origin',
    [
        'https://doozy.example.com/',      # trailing slash: would never match
        'https://doozy.example.com/app',   # origins have no path
        'doozy.example.com',               # missing scheme
        '*',                               # wildcard: callers must be listed explicitly
    ],
)
def test_cors_origins_rejects_malformed_entries(
    monkeypatch,
    bad_origin: str,
):
    monkeypatch.setenv('CORS_ORIGINS', f'https://ok.example,{bad_origin}')
    with pytest.raises(ValidationError, match='Invalid CORS origin'):
        _SettingsWithoutDotenv()
