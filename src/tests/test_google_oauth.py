def test_google_login_redirect(client):
    response = client.get('/login/google', follow_redirects=False)
    assert response.status_code == 307
    location = response.headers.get('location')
    assert location is not None
    assert 'accounts.google.com' in location
    assert 'client_id=fakeid' in location


def test_token_401_body(client):
    # incorrect credentials should produce a 401 and JSON detail
    response = client.post('/token', data={'username': 'bad', 'password': 'creds'})
    assert response.status_code == 401
    assert response.json() == {'detail': 'Incorrect username or password'}
