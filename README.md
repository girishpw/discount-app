# Discount Management App

A Flask-based web application for managing and approving discounts with Google Cloud integration.

## Features

- **Authentication**: Google OAuth integration with pw.live domain restriction
- **Discount Management**: Request and approve discounts with workflow
- **Data Storage**: Google BigQuery integration for data persistence
- **Email Notifications**: Automated email notifications for approvals
- **Dashboard**: Real-time dashboard for tracking discount requests
- **API Endpoints**: RESTful APIs for integration

## Technology Stack

- **Backend**: Flask (Python 3.9+)
- **Database**: Google BigQuery
- **Authentication**: Google OAuth 2.0
- **Deployment**: Google Cloud Run with Docker
- **Testing**: pytest, pytest-mock, pytest-cov
- **Email**: SMTP with Gmail integration

## Quick Start

### Prerequisites

- Python 3.9+
- Docker (for local deployment)
- Google Cloud SDK (for cloud deployment)
- Access to Google Cloud Project with BigQuery and Secret Manager

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd discount-app
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   export FLASK_SECRET_KEY="your-secret-key"
   export EMAIL_SENDER="your-email@pw.live"
   export EMAIL_PASSWORD="your-app-password"
   export GOOGLE_CLOUD_PROJECT="your-project-id"
   ```

4. **Run tests**
   ```bash
   ./run_tests.sh
   ```

5. **Start the application**
   ```bash
   python app.py
   ```

## Testing

The application includes comprehensive test coverage:

### Running Tests

```bash
# Run all tests with coverage
./run_tests.sh

# Run only unit tests
./run_tests.sh unit

# Run only integration tests
./run_tests.sh integration

# Run quick smoke tests
./run_tests.sh quick

# Run tests manually
python -m pytest -v
```

### Test Structure

- **Unit Tests** (`test_unit.py`): Test individual functions and utilities
- **Integration Tests** (`test_integration.py`): Test API endpoints and workflows
- **Fixtures** (`conftest.py`): Shared test fixtures and mocks

### Coverage Requirements

- Minimum test coverage: 40% (focused on critical paths)
- Coverage report: `htmlcov/index.html`

## Deployment

### Local Deployment with Docker

```bash
# Deploy locally
./deploy.sh local

# Access application at http://localhost:8080
```

### Cloud Deployment (Google Cloud Run)

```bash
# Deploy to Google Cloud Run
./deploy.sh cloud

# Test deployment only
./deploy.sh test-only

# Verify existing deployment
./deploy.sh verify-only
```

### Manual Cloud Build

```bash
# Submit to Cloud Build
gcloud builds submit --config=cloudbuild.yaml .
```

## CI/CD Pipeline

The Cloud Build pipeline includes:

1. **Test Phase**: Runs full test suite with coverage
2. **Build Phase**: Builds Docker image
3. **Deploy Phase**: Deploys to Cloud Run
4. **Verification Phase**: Performs health checks

### Pipeline Configuration

- **File**: `cloudbuild.yaml`
- **Triggers**: Automatic on main branch push
- **Environment**: Google Cloud Build
- **Duration**: ~5-10 minutes

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_SECRET_KEY` | Flask session secret | `your-secret-key` |
| `EMAIL_SENDER` | SMTP sender email | `user@pw.live` |
| `EMAIL_PASSWORD` | SMTP password | `app-password` |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | `your-project-id` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Application port |
| `SMTP_SERVER` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |

## API Endpoints

### Public Endpoints

- `GET /_health` - Health check endpoint
- `GET /login` - Login page
- `POST /login/manual` - Manual login

### Authenticated Endpoints

- `GET /` - Dashboard
- `GET /dashboard` - Main dashboard
- `GET /request_discount` - Request discount form
- `POST /request_discount` - Submit discount request
- `GET /approve_request` - Approve requests page
- `POST /approve_request` - Approve/reject requests

### API Endpoints

- `GET /api/cards/<branch_name>` - Get cards for branch
- `GET /api/mrp/<branch_name>/<card_name>` - Get MRP for branch/card

## Database Schema

### BigQuery Tables

- `discount_management.branch_cards_fees` - Branch, card, and pricing data
- `discount_management.discount_requests` - Discount requests
- `discount_management.discount_approvals` - Approval history

## Monitoring and Health Checks

### Health Check Endpoint

```bash
curl http://localhost:8080/_health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "port": 8080
}
```

### Monitoring

- **Google Cloud Monitoring**: Automatic monitoring for Cloud Run
- **Application Logs**: Structured logging to Cloud Logging
- **Error Reporting**: Automatic error tracking

## Security

- **Authentication**: Google OAuth with domain restriction
- **Authorization**: Role-based access control
- **Secrets**: Google Secret Manager for sensitive data
- **HTTPS**: Enforced in production
- **CSRF**: Protection enabled for forms

## Troubleshooting

### Common Issues

1. **BigQuery Connection Failed**
   - Check service account permissions
   - Verify `GOOGLE_APPLICATION_CREDENTIALS`

2. **Email Sending Failed**
   - Verify SMTP credentials
   - Check Gmail app password

3. **Authentication Issues**
   - Verify OAuth client configuration
   - Check domain restrictions

### Logs

```bash
# Local logs
tail -f app.log

# Cloud Run logs
gcloud logs read --service=discount-app
```

## Development

### Code Structure

```
discount-app/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── Dockerfile         # Docker configuration
├── cloudbuild.yaml    # Cloud Build pipeline
├── run_tests.sh       # Test runner script
├── deploy.sh          # Deployment script
├── test_unit.py       # Unit tests
├── test_integration.py # Integration tests
├── conftest.py        # Test fixtures
├── templates/         # HTML templates
├── static/           # Static assets
└── README.md         # This file
```

### Contributing

1. Create feature branch
2. Write tests for new features
3. Ensure all tests pass
4. Submit pull request
5. Pipeline will run tests automatically

## License

Internal use only - PW Education
