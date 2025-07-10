#!/bin/bash

# Script to set up required secrets for discount management app
# Run this before deploying the application

set -e

PROJECT_ID="gewportal2025"

echo "🔐 Setting up secrets for discount management app..."
echo "📋 Project: $PROJECT_ID"

# Function to create secret safely
create_secret() {
    local secret_name=$1
    local description=$2
    
    if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" >/dev/null 2>&1; then
        echo "✅ Secret '$secret_name' already exists"
    else
        echo "🔨 Creating secret '$secret_name'..."
        echo "📝 Please enter value for $secret_name ($description):"
        read secret_value
        echo "$secret_value" | gcloud secrets create "$secret_name" --data-file=- --project="$PROJECT_ID"
        echo "✅ Secret '$secret_name' created successfully"
    fi
}

# Enable Secret Manager API
echo "🔧 Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project="$PROJECT_ID"

# Create Flask secret key
if gcloud secrets describe "flask-secret-key" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "✅ Secret 'flask-secret-key' already exists"
else
    echo "🔨 Creating Flask secret key..."
    flask_secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "$flask_secret" | gcloud secrets create "flask-secret-key" --data-file=- --project="$PROJECT_ID"
    echo "✅ Flask secret key created successfully"
fi

# Create email secrets
create_secret "email-sender" "Email address for sending notifications"
create_secret "email-password" "Email password (use app password for Gmail)"

# Service account key instructions
echo ""
echo "🔑 For the service account key (discount-key):"
echo "   1. Go to Google Cloud Console"
echo "   2. Navigate to IAM & Admin > Service Accounts"
echo "   3. Find: classmanager-sa@gewportal2025.iam.gserviceaccount.com"
echo "   4. Click 'Actions' > 'Manage keys' > 'Add key' > 'Create new key'"
echo "   5. Choose JSON format and download"
echo "   6. Run: gcloud secrets create discount-key --data-file=path/to/downloaded-key.json --project=$PROJECT_ID"

# Grant service account access to secrets
SERVICE_ACCOUNT="classmanager-sa@gewportal2025.iam.gserviceaccount.com"

echo ""
echo "🔐 Granting service account access to secrets..."

SECRETS=("discount-key" "flask-secret-key" "email-sender" "email-password")

for secret in "${SECRETS[@]}"; do
    if gcloud secrets describe "$secret" --project="$PROJECT_ID" >/dev/null 2>&1; then
        echo "🔨 Granting access to '$secret'..."
        gcloud secrets add-iam-policy-binding "$secret" \
            --member="serviceAccount:$SERVICE_ACCOUNT" \
            --role="roles/secretmanager.secretAccessor" \
            --project="$PROJECT_ID"
        echo "✅ Access granted to '$secret'"
    else
        echo "⚠️  Secret '$secret' not found, skipping..."
    fi
done

echo ""
echo "🎉 Secret setup completed!"
echo "📝 Next steps:"
echo "   1. Create the service account key and upload it as 'discount-key' secret"
echo "   2. Run ./deploy.sh to deploy the application"
