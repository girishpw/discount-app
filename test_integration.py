import pytest
from unittest.mock import patch, MagicMock
import json


class TestRoutes:
    """Test Flask routes and endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/_health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
    
    def test_login_page_get(self, client):
        """Test login page loads correctly."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower()
    
    def test_manual_login_redirects_to_login(self, client):
        """Test manual login redirects to main login page."""
        response = client.get('/login/manual')
        assert response.status_code == 302  # Redirect
        assert '/login' in response.headers['Location']
    
    def test_logout_clears_session(self, client):
        """Test logout clears session."""
        # First login
        with client.session_transaction() as sess:
            sess['logged_in_email'] = 'test@pw.live'
            sess['user_name'] = 'Test User'
        
        # Then logout
        response = client.get('/logout')
        assert response.status_code == 302  # Redirect
        
        # Check session is cleared
        with client.session_transaction() as sess:
            assert 'logged_in_email' not in sess
            assert 'user_name' not in sess
    
    def test_index_page_loads(self, client, mock_bigquery):
        """Test index page loads (doesn't require auth)."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'html' in response.data.lower() or b'index' in response.data.lower()
    
    def test_request_discount_requires_auth(self, client):
        """Test request discount page requires authentication."""
        response = client.get('/request_discount')
        assert response.status_code == 302  # Redirect to login
        assert '/login' in response.headers['Location']
    
    def test_request_discount_page_authenticated(self, authenticated_session, mock_bigquery):
        """Test request discount page loads when authenticated."""
        # Mock BigQuery response for branch data
        mock_result = MagicMock()
        mock_result.__iter__ = lambda x: iter([
            {'branch_name': 'Test Branch', 'branch_code': 'TB001'}
        ])
        mock_bigquery.query.return_value.result.return_value = mock_result
        
        response = authenticated_session.get('/request_discount')
        assert response.status_code == 200
        assert b'request' in response.data.lower()
    
    def test_approve_request_requires_auth(self, client):
        """Test approve request page requires authentication."""
        response = client.get('/approve_request')
        assert response.status_code == 302  # Redirect to login
    
    def test_dashboard_requires_auth(self, client):
        """Test dashboard requires authentication."""
        response = client.get('/dashboard')
        assert response.status_code == 302  # Redirect to login
    
    @patch('app.get_bigquery_client')
    def test_dashboard_authenticated(self, mock_client_func, authenticated_session):
        """Test dashboard loads when authenticated."""
        # Mock BigQuery client and queries
        mock_client = MagicMock()
        mock_client_func.return_value = mock_client
        
        # Mock query results
        mock_result = MagicMock()
        mock_result.__iter__ = lambda x: iter([])  # Empty result set
        mock_client.query.return_value.result.return_value = mock_result
        
        response = authenticated_session.get('/dashboard')
        assert response.status_code == 200
        assert b'dashboard' in response.data.lower() or b'Dashboard' in response.data
    
    def test_debug_config_requires_auth(self, client):
        """Test debug configuration endpoint requires auth."""
        response = client.get('/debug/config')
        assert response.status_code == 200
        assert b'Please login first' in response.data
    
    def test_debug_config_authenticated(self, authenticated_session):
        """Test debug configuration endpoint when authenticated."""
        response = authenticated_session.get('/debug/config')
        assert response.status_code == 200
        assert b'Configuration Debug' in response.data


class TestFormSubmissions:
    """Test form submissions and POST requests."""
    
    @patch('app.get_bigquery_client')
    @patch('app.smtplib.SMTP')
    def test_request_discount_submission(self, mock_smtp, mock_client_func, authenticated_session):
        """Test discount request form submission."""
        # Mock BigQuery client
        mock_client = MagicMock()
        mock_client_func.return_value = mock_client
        
        # Mock branch data query
        mock_branch_result = MagicMock()
        mock_branch_result.__iter__ = lambda x: iter([
            {'branch_name': 'Test Branch', 'branch_code': 'TB001'}
        ])
        
        # Mock card data query  
        mock_card_result = MagicMock()
        mock_card_result.__iter__ = lambda x: iter([
            {'card_name': 'Test Card', 'card_id': 'TC001', 'mrp': 100.0}
        ])
        
        mock_client.query.side_effect = [
            MagicMock(result=lambda: mock_branch_result),
            MagicMock(result=lambda: mock_card_result),
            MagicMock(result=lambda: [])  # Insert query
        ]
        
        # Mock SMTP
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        
        form_data = {
            'branch': 'TB001',
            'card': 'TC001', 
            'discount_percentage': '10',
            'reason': 'Test discount request',
            'customer_phone': '1234567890'
        }
        
        response = authenticated_session.post('/request_discount', data=form_data)
        # Should redirect after successful submission
        assert response.status_code in [200, 302]
    
    def test_manual_login_redirects(self, client):
        """Test manual login POST also redirects to main login."""
        response = client.post('/login/manual', data={
            'email': 'test@pw.live'
        })
        
        # Should redirect to main login
        assert response.status_code == 302
        assert '/login' in response.headers['Location']


class TestAPIEndpoints:
    """Test API endpoints."""
    
    @patch('app.get_bigquery_client')
    def test_api_cards_endpoint(self, mock_client_func, client):
        """Test API endpoint for getting cards by branch."""
        mock_client = MagicMock()
        mock_client_func.return_value = mock_client
        
        # Mock query result - using Row objects with card_name attribute
        mock_row1 = MagicMock()
        mock_row1.card_name = 'Test Card 1'
        
        mock_row2 = MagicMock()  
        mock_row2.card_name = 'Test Card 2'
        
        mock_result = [mock_row1, mock_row2]
        mock_client.query.return_value.result.return_value = mock_result
        
        response = client.get('/api/cards/TB001')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2
        assert data[0] == 'Test Card 1'  # API returns array of strings, not objects
        assert data[1] == 'Test Card 2'
    
    @patch('app.get_bigquery_client')
    def test_api_mrp_endpoint(self, mock_client_func, client):
        """Test API endpoint for getting MRP by branch and card."""
        mock_client = MagicMock()
        mock_client_func.return_value = mock_client
        
        # Mock query result - using Row object with attributes
        mock_row = MagicMock()
        mock_row.mrp = 100.0
        mock_row.installment = 50.0
        
        mock_result = [mock_row]
        mock_client.query.return_value.result.return_value = mock_result
        
        response = client.get('/api/mrp/TB001/TC001')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['mrp'] == 100.0
        assert data['installment'] == 50.0


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @patch('app.get_bigquery_client')
    def test_bigquery_connection_failure(self, mock_client_func, authenticated_session):
        """Test handling of BigQuery connection failures."""
        mock_client_func.return_value = None  # Simulate connection failure
        
        response = authenticated_session.get('/dashboard')
        # Should still load page but with limited functionality
        assert response.status_code == 200
    
    @patch('app.get_bigquery_client')
    def test_api_endpoint_with_no_data(self, mock_client_func, client):
        """Test API endpoint when no data is found."""
        mock_client = MagicMock()
        mock_client_func.return_value = mock_client
        
        # Mock empty result
        mock_result = []
        mock_client.query.return_value.result.return_value = mock_result
        
        response = client.get('/api/cards/INVALID_BRANCH')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 0