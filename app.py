import os
import logging
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from google.cloud import bigquery
from google.cloud import secretmanager
from google.oauth2 import service_account
import smtplib
from email.mime.text import MIMEText
import json
from datetime import datetime,timezone

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.secret_key = 'a05e2129e96e25091f8db85a54fe8b229fbc22bcdd2de6cfedb3a78369d434fd'
 
# Initialize BigQuery client
project_id = 'gewportal2025'
dataset_id = 'discount_management'
client = None

def get_bigquery_client():
    global client
    if client is None:
        try:
            from google.auth import default
            credentials, project = default()
            client = bigquery.Client(credentials=credentials, project=project)
            logger.info(f"BigQuery client initialized with project: {project}")
        except Exception as e:
            logger.error(f"Error initializing BigQuery client: {e}")
            raise
    return client

# Email configuration
EMAIL_SENDER = 'girish.chandra@pw.live'
EMAIL_PASSWORD = 'EcoTiger#0705'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

def send_email(to_email, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = to_email
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email sent successfully to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/request_discount', methods=['GET', 'POST'])
def request_discount():
    if request.method == 'POST':
        try:
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
                'created_at': datetime.now(timezone.utc).isoformat(),
                'l1_approver': None,
                'l2_approver': None
            }

            logger.info(f"Form data received: {data}")

            # Verify authorized requester
            client = get_bigquery_client()
            if client:
                query = f"""
                    SELECT * FROM `{project_id}.{dataset_id}.authorized_persons`
                    WHERE email = @email AND branch_name = @branch_name
                """
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("email", "STRING", data['requester_email']),
                        bigquery.ScalarQueryParameter("branch_name", "STRING", data['branch_name'])
                    ]
                )
                query_job = client.query(query, job_config=job_config)
                results = list(query_job.result())

                if not results:
                    logger.warning(f"Unauthorized requester: {data['requester_email']} at {data['branch_name']}")
                    flash("Unauthorized requester. Please contact admin.", "error")
                    return redirect(url_for('request_discount'))

                logger.info(f"Authorized requester verified: {data['requester_email']} at {data['branch_name']}")
            else:
                logger.error("BigQuery client is unavailable. Skipping authorization check.")

            # TODO: Insert data into BigQuery table
            flash("Discount request submitted successfully.", "success")
            return redirect(url_for('index'))

        except Exception as e:
            logger.error(f"Error processing discount request: {e}")
            flash("An error occurred while processing your request. Please try again later.", "error")
            return redirect(url_for('request_discount'))

    return render_template('request_discount.html')

@app.route('/approve_request', methods=['GET', 'POST'])
def approve_request():
    client = get_bigquery_client()

    if request.method == 'POST':
        try:
            request_id = request.form['request_id']
            action = request.form['action']
            approver_email = request.form['approver_email']
            new_discounted_fees = float(request.form.get('discounted_fees', 0))

            logger.info(f"Approve request received: request_id={request_id}, action={action}, approver_email={approver_email}, new_discounted_fees={new_discounted_fees}")

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
                logger.warning(f"Unauthorized approver: {approver_email}")
                flash('Unauthorized approver', 'error')
                return redirect(url_for('approve_request'))

            logger.info(f"Approver verified: {approver}")

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
            discount_request = list(result)[0] if list(result) else None

            if not discount_request:
                logger.warning(f"Discount request not found: enquiry_no={request_id}")
                flash('Discount request not found', 'error')
                return redirect(url_for('approve_request'))

            logger.info(f"Discount request details: {discount_request}")

            if approver['level'] == 'L1' and approver['branch_name'] != discount_request['branch_name']:
                logger.warning(f"Approver not authorized for branch: approver_branch={approver['branch_name']}, request_branch={discount_request['branch_name']}")
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

            logger.info(f"Discount request updated successfully: {update_data}")

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
                        f'A discount request has been approved by L1 for {discount_request["student_name"]}.'
                        f'\nPlease review at: {url_for("approve_request", _external=True)}'
                    )

            flash('Request processed successfully', 'success')
            return redirect(url_for('approve_request'))

        except Exception as e:
            logger.error(f"Error processing approve request: {e}")
            flash('An error occurred while processing your request. Please try again later.', 'error')
            return redirect(url_for('approve_request'))

    try:
        # Get pending requests
        query = f"""
            SELECT * FROM `{project_id}.{dataset_id}.discount_requests`
            WHERE status IN ('PENDING', 'APPROVED_L1')
        """
        logger.info(f"Executing query to fetch pending requests: {query}")
        result = client.query(query).result()
        requests = list(result)
        logger.info(f"Pending requests fetched successfully: {requests}")
        return render_template('approve_request.html', requests=requests)

    except Exception as e:
        logger.error(f"Error fetching pending requests: {e}")
        flash('An error occurred while fetching pending requests. Please try again later.', 'error')
        return redirect(url_for('index'))

@app.route('/test_adc')
def test_adc():
    try:
        from google.auth import default
        credentials, project = default()
        logger.info(f"ADC credentials loaded successfully for project: {project}")
        return jsonify({'status': 'success', 'project': project})
    except Exception as e:
        logger.error(f"Error loading ADC credentials: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

# Ensure the project ID is explicitly set in the environment
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gewportal2025'
logger.info(f"GOOGLE_CLOUD_PROJECT set to: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")

logger.info(f"GOOGLE_APPLICATION_CREDENTIALS: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
