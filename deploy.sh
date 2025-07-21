#!/bin/bash

# Deployment script for discount-app
set -e

REGION="asia-south2"
PROJECT_ID="gewportal2025"
SERVICE_NAME="discount-app"
IMAGE_NAME="asia-south2-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/discount-app/discount-app"

echo "🚀 Deploying discount-app..."

# Function to check prerequisites
check_prerequisites() {
    echo "🔍 Checking prerequisites..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        echo "❌ gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if logged into gcloud
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo "❌ Not logged into gcloud. Please run 'gcloud auth login'"
        exit 1
    fi
    
    echo "✅ Prerequisites check passed"
}

# Function to run tests
run_tests() {
    echo "🧪 Running tests..."
    if ! ./run_tests.sh; then
        echo "❌ Tests failed. Aborting deployment."
        exit 1
    fi
    echo "✅ All tests passed"
}

# Function to build and deploy
deploy() {
    echo "🔨 Building and deploying..."
    
    # Submit build to Cloud Build
    gcloud builds submit --config=cloudbuild.yaml .
    
    echo "✅ Deployment completed"
}

# Function to verify deployment
verify_deployment() {
    echo "🔍 Verifying deployment..."
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')
    
    if [ -z "$SERVICE_URL" ]; then
        echo "❌ Failed to get service URL"
        exit 1
    fi
    
    echo "🌐 Service URL: $SERVICE_URL"
    
    # Health check
    echo "⚡ Performing health check..."
    if curl -f "$SERVICE_URL/_health" > /dev/null 2>&1; then
        echo "✅ Health check passed"
        echo "🎉 Deployment successful! Service is available at: $SERVICE_URL"
    else
        echo "❌ Health check failed"
        exit 1
    fi
}

# Function to deploy locally with Docker
deploy_local() {
    echo "🏠 Deploying locally with Docker..."
    
    # Build Docker image
    docker build -t discount-app .
    
    # Run container
    echo "🐳 Starting Docker container on port 8080..."
    docker run -d -p 8080:8080 --name discount-app-local discount-app
    
    # Wait for container to start
    sleep 5
    
    # Health check
    if curl -f "http://localhost:8080/_health" > /dev/null 2>&1; then
        echo "✅ Local deployment successful!"
        echo "🌐 Service is available at: http://localhost:8080"
        echo "To stop: docker stop discount-app-local && docker rm discount-app-local"
    else
        echo "❌ Local health check failed"
        docker logs discount-app-local
        exit 1
    fi
}

# Main script logic
case "${1:-}" in
    "local")
        run_tests
        deploy_local
        ;;
    "cloud")
        check_prerequisites
        run_tests
        deploy
        verify_deployment
        ;;
    "test-only")
        run_tests
        ;;
    "verify-only")
        verify_deployment
        ;;
    *)
        echo "Usage: $0 {local|cloud|test-only|verify-only}"
        echo ""
        echo "  local       - Run tests and deploy locally with Docker"
        echo "  cloud       - Run tests and deploy to Google Cloud Run"
        echo "  test-only   - Run tests only"
        echo "  verify-only - Verify existing cloud deployment"
        exit 1
        ;;
esac