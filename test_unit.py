import pytest
from unittest.mock import patch, MagicMock
from app import validate_pw_email
from flask import session


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_validate_pw_email_valid(self):
        """Test email validation with valid pw.live email."""
        assert validate_pw_email('test@pw.live') == True
        assert validate_pw_email('user.name@pw.live') == True
        assert validate_pw_email('admin@pw.live') == True
    
    def test_validate_pw_email_invalid(self):
        """Test email validation with invalid emails."""
        assert validate_pw_email('test@gmail.com') == False
        assert validate_pw_email('user@yahoo.com') == False
        assert validate_pw_email('invalid-email') == False
        assert validate_pw_email('') == False
        assert validate_pw_email(None) == False


class TestBigQueryIntegration:
    """Test BigQuery integration functions."""
    
    @patch('app.client', None)  # Reset global client
    def test_get_bigquery_client_with_credentials(self, mock_environment):
        """Test BigQuery client initialization with service account."""
        with patch('app.service_account.Credentials.from_service_account_file') as mock_creds:
            with patch('app.bigquery.Client') as mock_client:
                with patch('os.path.exists', return_value=True):
                    with patch.dict('os.environ', {'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'}):
                        from app import get_bigquery_client
                        
                        # Reset the global client to force re-initialization
                        import app
                        app.client = None
                        
                        client = get_bigquery_client()
                        mock_creds.assert_called_once()
                        mock_client.assert_called_once()
    
    @patch('app.client', None)  # Reset global client
    def test_get_bigquery_client_with_adc(self, mock_environment):
        """Test BigQuery client initialization with Application Default Credentials."""
        with patch('app.bigquery.Client') as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.query.return_value.result.return_value = True
            
            from app import get_bigquery_client
            
            # Reset the global client to force re-initialization
            import app
            app.client = None
            
            client = get_bigquery_client()
            mock_client.assert_called_once()
    
    @patch('app.client', None)  # Reset global client
    def test_get_bigquery_client_failure(self, mock_environment):
        """Test BigQuery client initialization failure handling."""
        with patch('app.bigquery.Client', side_effect=Exception("Connection failed")):
            from app import get_bigquery_client
            
            # Reset the global client to force re-initialization
            import app
            app.client = None
            
            client = get_bigquery_client()
            assert client is None


class TestEmailValidation:
    """Test email-related functionality."""
    
    def test_pw_email_validation(self):
        """Test pw.live email domain validation."""
        # Valid emails
        assert validate_pw_email('john.doe@pw.live') == True
        assert validate_pw_email('admin@pw.live') == True
        assert validate_pw_email('test123@pw.live') == True
        
        # Invalid emails
        assert validate_pw_email('john@gmail.com') == False
        assert validate_pw_email('user@pw.com') == False
        assert validate_pw_email('invalid@pw.live.com') == False
        assert validate_pw_email('') == False
        assert validate_pw_email(None) == False