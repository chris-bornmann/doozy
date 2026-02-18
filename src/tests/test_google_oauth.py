from fastapi.testclient import TestClient
import os, sys
sys.path.append(os.path.join(os.getcwd(), 'src'))

from app.main import app

# set dummy credentials so the application initialises cleanly
os.environ.setdefault('GOOGLE_CLIENT_ID', 'fakeid')
os.environ.setdefault('GOOGLE_CLIENT_SECRET', 'fakesecret')

client = TestClient(app)

def test_google_login_redirect():
    response = client.get('/login/google', follow_redirects=False)
    assert response.status_code == 307
    location = response.headers.get('location')
    assert location is not None
    assert 'accounts.google.com' in location
    assert 'client_id=fakeid' in location
