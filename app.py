import os
from flask import Flask, request, render_template, redirect, url_for, flash
from google.cloud import bigquery
from google.cloud import secretmanager
from google.oauth2 import service_account
import smtplib
from email.mime.text import MIMEText
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Initialize BigQuery client
project_id = 'gewportal2025'
dataset_id = 'discount_management'
client = None

def get_bigquery_client():
    global client
    if client is None:
        # Access secret from Secret Manager
        secret_client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{project_id}/secrets/discount-key/versions/latest"
        response = secret_client.access_secret_version(name=secret_name)
        secret = response.payload.data.decode('UTF-8')
        
        credentials = service_account.Credentials.from_service_account_info(json.loads(secret))
        client = bigquery.Client(credentials=credentials, project=project_id)
    return client

# Email configuration
EMAIL_SENDER = 'girish.chandra@pw.live'
EMAIL_PASSWORD = 'EcoTiger#0705'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = to_email
    
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/request_discount', methods=['GET', 'POST'])
def request_discount():
    if request.method == 'POST':
        # Capture form data
        data = {
            'enquiry_no': request.form['enquiry_no'],
            'student_name': request.form['student_name'],
            'mobile_no': request.form['mobile_no'],
            'card_name': request.form['card_name'],
            'mrp': float(request.form['mrp']),
            'discounted_fees': float(request.form['discounted_fees']),
            'net_discount': float(request.form['mrp']) - float(request.form['discounted_fees']),
            'reason': request.form['reason'],
            'remarks': request.form['remarks'],
            'requester_email': request.form['requester_email'],
            'requester_name': request.form['requester_name'],
            'branch_name': request.form['branch_name'],
            'status': 'PENDING',
            'created_at': datetime.utcnow().isoformat(),
            'l1_approver': None,
            'l2_approver': None
        }
        
        # Verify authorized requester
        client = get_bigquery_client()
        query = f"""
            SELECT * FROM `{project_id}.{dataset_id}.authorized_persons`
            WHERE email = @email AND branch_name = @branch_name
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('email', 'STRING', data['requester_email']),
                bigquery.ScalarQueryParameter('branch_name', 'STRING', data['branch_name'])
            ]
        )
        result = client.query(query, job_config=job_config).result()
        
        if not list(result):
            flash('Unauthorized requester', 'error')
            return redirect(url_for('request_discount'))
        
        # Insert request into BigQuery
        table_ref = client.dataset(dataset_id).table('discount_requests')
        client.insert_rows_json(table_ref, [data])
        
        # Find L1 approver
        query = f"""
            SELECT email FROM `{project_id}.{dataset_id}.approvers`
            WHERE level = 'L1' AND branch_name = @branch_name
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('branch_name', 'STRING', data['branch_name'])
            ]
        )
        result = client.query(query, job_config=job_config).result()
        l1_approver = list(result)[0]['email'] if list(result) else None
        
        if l1_approver:
            send_email(
                l1_approver,
                'New Discount Request',
                f'A new discount request has been submitted for {data["student_name"]}.\n'
                f'Please review at: {url_for("approve_request", _external=True)}'
            )
        
        flash('Discount request submitted successfully', 'success')
        return redirect(url_for('index'))
    
    return render_template('request_discount.html')

@app.route('/approve_request', methods=['GET', 'POST'])
def approve_request():
    client = get_bigquery_client()
    
    if request.method == 'POST':
        request_id = request.form['request_id']
        action = request.form['action']
        approver_email = request.form['approver_email']
        new_discounted_fees = float(request.form.get('discounted_fees', 0))
        
        # Verify approver
        query = f"""
            SELECT level, branch_name FROM `{project_id}.{dataset_id}.approvers`
            WHERE email = @email
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('email', 'STRING', approver_email)
            ]
        )
        result = client.query(query, job_config=job_config).result()
        approver = list(result)[0] if list(result) else None
        
        if not approver:
            flash('Unauthorized approver', 'error')
            return redirect(url_for('approve_request'))
        
        # Get request details
        query = f"""
            SELECT * FROM `{project_id}.{dataset_id}.discount_requests`
            WHERE enquiry_no = @enquiry_no
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('enquiry_no', 'STRING', request_id)
            ]
        )
        result = client.query(query, job_config=job_config).result()
        discount_request = list(result)[0]
        
        if approver['level'] == 'L1' and approver['branch_name'] != discount_request['branch_name']:
            flash('Not authorized to approve this branch', 'error')
            return redirect(url_for('approve_request'))
        
        update_data = {}
        if action == 'APPROVE':
            update_data['status'] = 'APPROVED_L1' if approver['level'] == 'L1' else 'APPROVED'
            if new_discounted_fees > 0:
                update_data['discounted_fees'] = new_discounted_fees
                update_data['net_discount'] = discount_request['mrp'] - new_discounted_fees
        
        elif action == 'REJECT':
            update_data['status'] = 'REJECTED'
        
        update_data[f"{approver['level'].lower()}_approver"] = approver_email
        
        # Update request in BigQuery
        query = f"""
            UPDATE `{project_id}.{dataset_id}.discount_requests`
            SET {', '.join(f'{k} = @{k}' for k in update_data.keys())}
            WHERE enquiry_no = @enquiry_no
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('enquiry_no', 'STRING', request_id),
                *[bigquery.ScalarQueryParameter(k, 'STRING' if k.endswith('_approver') else 'FLOAT' if k in ['discounted_fees', 'net_discount'] else 'STRING', v) for k, v in update_data.items()]
            ]
        )
        client.query(query, job_config=job_config)
        
        # If L1 approved, notify L2 approver
        if approver['level'] == 'L1' and action == 'APPROVE':
            query = f"""
                SELECT email FROM `{project_id}.{dataset_id}.approvers`
                WHERE level = 'L2'
                LIMIT 1
            """
            result = client.query(query).result()
            l2_approver = list(result)[0]['email'] if list(result) else None
            
            if l2_approver:
                send_email(
                    l2_approver,
                    'Discount Request for L2 Approval',
                    f'A discount request has been approved by L1 for {discount_request["student_name"]}.\n'
                    f'Please review at: {url_for("approve_request", _external=True)}'
                )
        
        flash('Request processed successfully', 'success')
        return redirect(url_for('approve_request'))
    
    # Get pending requests
    query = f"""
        SELECT * FROM `{project_id}.{dataset_id}.discount_requests`
        WHERE status IN ('PENDING', 'APPROVED_L1')
    """
    result = client.query(query).result()
    requests = list(result)
    
    return render_template('approve_request.html', requests=requests)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
