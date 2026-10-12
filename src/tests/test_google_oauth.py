from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

# A well-formed OAuth state, like the one the GUI generates (43 URL-safe chars).
VALID_STATE = "Abc123_-Abc123_-Abc123_-Abc123_-Abc123_-Abc"


def test_google_login_redirect(
    client,
):
    response = client.get('/login/google', params={'state': VALID_STATE}, follow_redirects=False)
    assert response.status_code == 307
    location = response.headers.get('location')
    assert location is not None
    assert 'accounts.google.com' in location
    assert 'client_id=fakeid' in location
    # The GUI's state must be passed to Google so it comes back to /auth/google.
    assert parse_qs(urlsplit(location).query)['state'] == [VALID_STATE]
    # Sign-in only needs the user's email and name once, so we must not ask
    # Google for offline access (a refresh token) or force the consent screen.
    query = parse_qs(urlsplit(location).query)
    assert 'access_type' not in query
    assert 'prompt' not in query
    assert query['scope'] == ['openid email profile']


def test_google_login_requires_state(
    client,
):
    # Without a state the GUI could not tell its own logins from forged ones.
    response = client.get('/login/google', follow_redirects=False)
    assert response.status_code == 400
    assert response.json() == {'detail': 'Missing or invalid state parameter'}


def test_google_login_rejects_malformed_state(
    client,
):
    # The state is echoed into a redirect URL, so anything other than a short
    # URL-safe token is refused (here: too short, and containing URL syntax).
    for bad_state in ['short', 'x' * 15, 'a' * 20 + '&token_type=evil', 'a' * 129]:
        response = client.get('/login/google', params={'state': bad_state}, follow_redirects=False)
        assert response.status_code == 400, bad_state


def test_google_callback_requires_state(
    client,
):
    response = client.get('/auth/google', params={'code': 'somecode'}, follow_redirects=False)
    assert response.status_code == 400
    assert response.json() == {'detail': 'Missing or invalid state parameter'}


def _mock_response(
    status_code: int,
    body: dict,
) -> MagicMock:
    """Build a stand-in for an httpx response with the given status and JSON body."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = body
    return response


def test_google_callback_returns_token_and_state_to_gui_callback(
    client,
):
    # Fake Google's token and userinfo endpoints.
    token_response = _mock_response(200, {'access_token': 'google-access-token'})
    userinfo_response = _mock_response(200, {'email': 'newuser@example.com', 'name': 'New User'})
    with patch('httpx.post', return_value=token_response), patch('httpx.get', return_value=userinfo_response):
        response = client.get(
            '/auth/google',
            params={'code': 'somecode', 'state': VALID_STATE},
            follow_redirects=False,
        )

    assert response.status_code == 307
    location = urlsplit(response.headers['location'])
    # The GUI only accepts tokens on its dedicated callback page...
    assert location.path == '/auth/callback'
    # ...and the token travels in the fragment, never in the query string.
    assert location.query == ''
    fragment = parse_qs(location.fragment)
    assert fragment['token_type'] == ['bearer']
    assert fragment['access_token'][0]
    # The state comes back unchanged so the GUI can match it to the login it started.
    assert fragment['state'] == [VALID_STATE]


def test_token_401_body(client):
    # incorrect credentials should produce a 401 and JSON detail
    response = client.post('/token', data={'username': 'bad', 'password': 'creds'})
    assert response.status_code == 401
    assert response.json() == {'detail': 'Incorrect username or password'}
