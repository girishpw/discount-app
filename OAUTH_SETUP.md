# OAuth Setup Guide

## Google OAuth Configuration

### 1. Create OAuth Credentials in Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to "APIs & Services" > "Credentials"
3. Click "Create Credentials" > "OAuth 2.0 Client IDs"
4. Choose "Web application"
5. Add authorized redirect URIs:
   - `https://your-app-domain.com/auth/google/callback`
   - `http://localhost:8080/auth/google/callback` (for development)

### 2. Set Environment Variables

Add these to your environment or Secret Manager:

```bash
GOOGLE_OAUTH_CLIENT_ID=your_client_id_here
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here
```

### 3. Update Cloud Run Environment Variables

In your `cloudbuild.yaml` or deployment script, add:

```yaml
--set-env-vars="GOOGLE_OAUTH_CLIENT_ID=projects/gewportal2025/secrets/oauth-client-id/versions/latest"
--set-env-vars="GOOGLE_OAUTH_CLIENT_SECRET=projects/gewportal2025/secrets/oauth-client-secret/versions/latest"
```

### 4. Create Secrets in Secret Manager

```bash
# Create OAuth Client ID secret
gcloud secrets create oauth-client-id --data-file=client_id.txt

# Create OAuth Client Secret secret  
gcloud secrets create oauth-client-secret --data-file=client_secret.txt

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding oauth-client-id \
    --member="serviceAccount:discount-app-sa@gewportal2025.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding oauth-client-secret \
    --member="serviceAccount:discount-app-sa@gewportal2025.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

## Domain Authentication Setup

### Browser-Based Domain Authentication (Optional Enhancement)

For automatic browser-based authentication with pw.live domain, you can:

1. **Use Google Workspace SSO**: Configure your domain in Google Workspace to automatically authenticate users
2. **Browser Extension**: Create a browser extension that automatically populates the login with domain credentials
3. **Iframe Integration**: Embed the app in an iframe within your domain's intranet portal

The current implementation provides both Google OAuth and manual login options for maximum flexibility.

## Database Setup

Ensure your BigQuery tables are properly configured with the setup script:

```bash
python setup_database.py
```

This creates all required tables with sample data.

## Color Theme

The app now uses the requested magenta/black/white/cyan color theme:
- Primary Magenta: #d946ef
- Dark Magenta: #a21caf  
- Cyan: #06b6d4
- Dark Cyan: #0891b2
- Black: #000000
- White: #ffffff

## Features Implemented

✅ Google OAuth integration for pw.live domain
✅ Manual login fallback
✅ Email domain validation (@pw.live only)
✅ Enquiry number format validation (EN########)
✅ Dynamic branch/card/MRP dropdowns
✅ Authorization check against database
✅ L1/L2 approval workflow with email notifications
✅ Status transitions (PENDING_L1 → PENDING_L2 → APPROVED)
✅ Magenta/black/white/cyan color theme
✅ Modern, responsive UI design
✅ Session management and authentication decorators
