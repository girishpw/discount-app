# 🎓 Discount Management System - Production Deployment Guide

A modern, production-ready Flask application for managing student discount requests with BigQuery integration and beautiful Tailwind CSS UI.

## 📋 Prerequisites

Before deploying, ensure you have:

1. **Google Cloud Project**: `gewportal2025`
2. **Service Account**: `classmanager-sa@gewportal2025.iam.gserviceaccount.com`
3. **Required IAM Roles** (assigned to service account):
   - Artifact Registry Writer
   - BigQuery Data Editor
   - BigQuery Job User
   - Cloud Run Admin
   - Logs Writer
   - Storage Admin
   - Secret Manager Secret Accessor

## 🔐 Required Secrets

Create these secrets in Google Secret Manager:

### 1. Service Account Key (`discount-key`)
```bash
gcloud secrets create discount-key --data-file=path/to/service-account-key.json
```

### 2. Flask Secret Key (`flask-secret-key`)
```bash
# Generate a strong secret key
python -c "import secrets; print(secrets.token_hex(32))" > flask_secret.txt
gcloud secrets create flask-secret-key --data-file=flask_secret.txt
rm flask_secret.txt
```

### 3. Email Configuration
```bash
# Email sender
echo "your_email@domain.com" | gcloud secrets create email-sender --data-file=-

# Email password (use app password for Gmail)
echo "your_app_password" | gcloud secrets create email-password --data-file=-
```

## 🚀 Quick Deployment

### Option 1: Automated Script
```bash
# Make sure you're authenticated
gcloud auth login
gcloud config set project gewportal2025

# Run the deployment script
./deploy.sh
```

### Option 2: Manual Deployment
```bash
# Enable APIs
gcloud services enable cloudbuild.googleapis.com run.googleapis.com secretmanager.googleapis.com bigquery.googleapis.com

# Deploy using Cloud Build
gcloud builds submit --config=cloudbuild.yaml .
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Cloud Run     │    │   Secret Manager │    │    BigQuery     │
│                 │    │                  │    │                 │
│  ┌───────────┐  │    │  ┌─────────────┐ │    │  ┌────────────┐ │
│  │Flask App  │  │◄───┤  │   Secrets   │ │    │  │  discount  │ │
│  │           │  │    │  │             │ │    │  │management  │ │
│  │- Dashboard│  │    │  │- flask-key  │ │    │  │  dataset   │ │
│  │- Requests │  │    │  │- email-creds│ │    │  │            │ │
│  │- Approvals│  │    │  │- sa-key     │ │    │  └────────────┘ │
│  └───────────┘  │    │  └─────────────┘ │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🔧 Configuration

### Environment Variables (automatically set by Cloud Run)
- `PORT`: 8080
- `GOOGLE_CLOUD_PROJECT`: gewportal2025
- `SECRET_NAME`: discount-key
- `K_SERVICE`: (Cloud Run identifier)

### Secrets (mounted from Secret Manager)
- `FLASK_SECRET_KEY`: Flask session encryption key
- `EMAIL_SENDER`: SMTP sender email
- `EMAIL_PASSWORD`: SMTP password

## 📊 BigQuery Setup

### Required Dataset and Tables

1. **Create Dataset**:
```sql
CREATE SCHEMA `gewportal2025.discount_management`
```

2. **Create Tables**:

```sql
-- Discount requests table
CREATE TABLE `gewportal2025.discount_management.discount_requests` (
  enquiry_no STRING,
  student_name STRING,
  mobile_no STRING,
  card_name STRING,
  mrp FLOAT64,
  discounted_fees FLOAT64,
  net_discount FLOAT64,
  reason STRING,
  remarks STRING,
  requester_email STRING,
  requester_name STRING,
  branch_name STRING,
  status STRING,
  created_at STRING,
  l1_approver STRING,
  l2_approver STRING
);

-- Authorized persons table
CREATE TABLE `gewportal2025.discount_management.authorized_persons` (
  email STRING,
  name STRING,
  branch_name ARRAY<STRING>,
  level STRING
);

-- Approvers table
CREATE TABLE `gewportal2025.discount_management.approvers` (
  email STRING,
  name STRING,
  level STRING,
  branch_name ARRAY<STRING>
);
```

3. **Grant Permissions** to service account:
```bash
# Grant BigQuery permissions
gcloud projects add-iam-policy-binding gewportal2025 \
    --member="serviceAccount:classmanager-sa@gewportal2025.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding gewportal2025 \
    --member="serviceAccount:classmanager-sa@gewportal2025.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"
```

## 🔍 Monitoring & Troubleshooting

### Check Service Status
```bash
gcloud run services describe discount-app --region=asia-south2 --project=gewportal2025
```

### View Logs
```bash
gcloud logs tail --follow --service=discount-app --project=gewportal2025
```

### Test BigQuery Connection
Visit: `https://your-service-url/test_bigquery`

### Health Check
Visit: `https://your-service-url/_health`

## 🎯 Features

- ✅ **Modern UI**: Responsive design with Tailwind CSS
- ✅ **Secure Authentication**: Service account-based BigQuery access
- ✅ **Secret Management**: All sensitive data stored in Secret Manager
- ✅ **Error Handling**: Graceful degradation when services are unavailable
- ✅ **Logging**: Comprehensive logging for debugging
- ✅ **Production Ready**: Gunicorn WSGI server with proper scaling

## 🚨 Security Considerations

1. **Secrets**: Never commit secrets to version control
2. **Service Account**: Principle of least privilege - only necessary roles
3. **Network**: Cloud Run provides HTTPS by default
4. **Environment**: Use different service accounts for dev/staging/prod

## 📞 Support

For deployment issues:
1. Check Cloud Build logs: `gcloud builds log [BUILD_ID]`
2. Check Cloud Run logs: `gcloud logs tail --service=discount-app`
3. Verify service account permissions
4. Ensure all secrets are properly created

---
**Built with ❤️ for efficient discount management**
