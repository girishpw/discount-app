#!/bin/bash

# Deployment script for discount management app to Google Cloud Run
# Make sure you're authenticated with gcloud and have the necessary permissions

set -e

echo "🚀 Starting deployment of discount management app..."

# Set project
PROJECT_ID="gewportal2025"
SERVICE_ACCOUNT="classmanager-sa@gewportal2025.iam.gserviceaccount.com"
REGION="asia-south2"

echo "📋 Project: $PROJECT_ID"
echo "🔐 Service Account: $SERVICE_ACCOUNT"
echo "🌍 Region: $REGION"

# Check if required secrets exist
echo "🔍 Checking if required secrets exist..."

REQUIRED_SECRETS=("discount-key" "flask-secret-key" "email-sender" "email-password")

for secret in "${REQUIRED_SECRETS[@]}"; do
    if gcloud secrets describe "$secret" --project="$PROJECT_ID" >/dev/null 2>&1; then
        echo "✅ Secret '$secret' exists"
    else
        echo "❌ Secret '$secret' does not exist. Please create it first."
        echo "   Example: gcloud secrets create $secret --data-file=path/to/secret"
        exit 1
    fi
done

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com --project="$PROJECT_ID"
gcloud services enable run.googleapis.com --project="$PROJECT_ID"
gcloud services enable secretmanager.googleapis.com --project="$PROJECT_ID"
gcloud services enable bigquery.googleapis.com --project="$PROJECT_ID"
gcloud services enable artifactregistry.googleapis.com --project="$PROJECT_ID"

# Check if service account has required roles
echo "🔍 Checking service account roles..."
REQUIRED_ROLES=(
    "roles/artifactregistry.writer"
    "roles/bigquery.dataEditor"
    "roles/bigquery.jobUser"
    "roles/run.admin"
    "roles/logging.logWriter"
    "roles/storage.admin"
    "roles/secretmanager.secretAccessor"
)

for role in "${REQUIRED_ROLES[@]}"; do
    if gcloud projects get-iam-policy "$PROJECT_ID" --format="json" | grep -q "$SERVICE_ACCOUNT.*$role"; then
        echo "✅ Service account has role: $role"
    else
        echo "⚠️  Adding role $role to service account..."
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$SERVICE_ACCOUNT" \
            --role="$role"
    fi
done

# Create Artifact Registry repository if it doesn't exist
echo "📦 Creating Artifact Registry repository..."
if ! gcloud artifacts repositories describe cloud-run-source-deploy --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud artifacts repositories create cloud-run-source-deploy \
        --repository-format=docker \
        --location="$REGION" \
        --project="$PROJECT_ID"
    echo "✅ Artifact Registry repository created"
else
    echo "✅ Artifact Registry repository already exists"
fi

# Submit build
echo "🏗️  Starting Cloud Build..."
gcloud builds submit \
    --config=cloudbuild.yaml \
    --project="$PROJECT_ID" \
    .

echo "🎉 Deployment completed successfully!"
echo "📍 Your app should be available at:"
echo "   https://discount-app-[hash]-uc.a.run.app"
echo ""
echo "🔧 To check the service URL:"
echo "   gcloud run services describe discount-app --region=$REGION --project=$PROJECT_ID --format='value(status.url)'"
echo ""
echo "📊 To view logs:"
echo "   gcloud logs tail --follow --service=discount-app --project=$PROJECT_ID"
