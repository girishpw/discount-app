import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret_key'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture
def mock_bigquery():
    """Mock BigQuery client."""
    with patch('app.get_bigquery_client') as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_email():
    """Mock email functionality."""
    with patch('app.smtplib.SMTP') as mock:
        yield mock


@pytest.fixture
def authenticated_session(client):
    """Create an authenticated session."""
    with client.session_transaction() as sess:
        sess['logged_in_email'] = 'test@pw.live'
        sess['user_name'] = 'Test User'
        sess['can_request_discount'] = True
        sess['can_approve_discount'] = True
    return client


@pytest.fixture
def mock_environment():
    """Mock environment variables."""
    env_vars = {
        'FLASK_SECRET_KEY': 'test_secret',
        'EMAIL_SENDER': 'test@pw.live',
        'EMAIL_PASSWORD': 'test_password',
        'GOOGLE_CLOUD_PROJECT': 'test-project'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars