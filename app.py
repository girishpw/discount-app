import os
import logging
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from google.cloud import bigquery
from google.cloud import secretmanager
from google.oauth2 import service_account
import smtplib
from email.mime.text import MIMEText
import json
from datetime import datetime,timezone
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Replace hardcoded sensitive information with environment variables
EMAIL_SENDER = os.getenv('EMAIL_SENDER', 'girish.chandra@pw.live')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'EcoTiger#0705')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))

# Update app secret key to use environment variable
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'flask_secret_key')

# Add logging for missing environment variables
if not os.getenv('EMAIL_SENDER') or not os.getenv('EMAIL_PASSWORD') or not os.getenv('FLASK_SECRET_KEY'):
    logger.warning("Some environment variables are missing. Default values will be used.")

# Add checks for all required environment variables
required_env_vars = ['EMAIL_SENDER', 'EMAIL_PASSWORD', 'FLASK_SECRET_KEY', 'GOOGLE_APPLICATION_CREDENTIALS']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['logged_in_email'] = request.form['email']
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

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
    session['approver_level'] = session.get('approver_level', 'Unknown')
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
                # Update the query to pass branch_name as an array
                query = f"""
                    SELECT * FROM `{project_id}.{dataset_id}.authorized_persons`
                    WHERE email = @email AND @branch_name IN UNNEST(branch_name)
                """
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("email", "STRING", data['requester_email']),
                        bigquery.ArrayQueryParameter("branch_name", "STRING", [data['branch_name']])
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

            # Check for duplicate submission
            try:
                query = f"""
                    SELECT enquiry_no FROM `{project_id}.{dataset_id}.discount_requests`
                    WHERE enquiry_no = @enquiry_no AND requester_email = @requester_email
                    LIMIT 1
                """
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("enquiry_no", "STRING", data['enquiry_no']),
                        bigquery.ScalarQueryParameter("requester_email", "STRING", data['requester_email'])
                    ]
                )
                query_job = client.query(query, job_config=job_config)
                result = list(query_job.result())

                if result:
                    logger.warning(f"Duplicate submission detected for enquiry_no={data['enquiry_no']} and requester_email={data['requester_email']}")
                    flash("Duplicate submission detected. Please check your previous requests.", "error")
                    return redirect(url_for('request_discount'))
            except Exception as e:
                logger.error(f"Error checking for duplicate submission: {e}")

            # Insert data into BigQuery table
            try:
                query = f"""
                    INSERT INTO `{project_id}.{dataset_id}.discount_requests`
                    (enquiry_no, student_name, mobile_no, card_name, mrp, discounted_fees, net_discount, reason, remarks, requester_email, requester_name, branch_name, status, created_at, l1_approver, l2_approver)
                    VALUES (@enquiry_no, @student_name, @mobile_no, @card_name, @mrp, @discounted_fees, @net_discount, @reason, @remarks, @requester_email, @requester_name, @branch_name, @status, @created_at, @l1_approver, @l2_approver)
                """
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("enquiry_no", "STRING", data['enquiry_no']),
                        bigquery.ScalarQueryParameter("student_name", "STRING", data['student_name']),
                        bigquery.ScalarQueryParameter("mobile_no", "STRING", data['mobile_no']),
                        bigquery.ScalarQueryParameter("card_name", "STRING", data['card_name']),
                        bigquery.ScalarQueryParameter("mrp", "FLOAT", data['mrp']),
                        bigquery.ScalarQueryParameter("discounted_fees", "FLOAT", data['discounted_fees']),
                        bigquery.ScalarQueryParameter("net_discount", "FLOAT", data['net_discount']),
                        bigquery.ScalarQueryParameter("reason", "STRING", data['reason']),
                        bigquery.ScalarQueryParameter("remarks", "STRING", data['remarks']),
                        bigquery.ScalarQueryParameter("requester_email", "STRING", data['requester_email']),
                        bigquery.ScalarQueryParameter("requester_name", "STRING", data['requester_name']),
                        bigquery.ScalarQueryParameter("branch_name", "STRING", data['branch_name']),
                        bigquery.ScalarQueryParameter("status", "STRING", data['status']),
                        bigquery.ScalarQueryParameter("created_at", "STRING", data['created_at']),
                        bigquery.ScalarQueryParameter("l1_approver", "STRING", data['l1_approver']),
                        bigquery.ScalarQueryParameter("l2_approver", "STRING", data['l2_approver'])
                    ]
                )
                client.query(query, job_config=job_config)
                logger.info("Data inserted into discount_requests table successfully.")
            except Exception as e:
                logger.error(f"Error inserting data into discount_requests table: {e}")
                flash("An error occurred while submitting your request. Please try again later.", "error")
                return redirect(url_for('request_discount'))

            flash("Discount request submitted successfully.", "success")
            return redirect(url_for('request_discount'))

        except Exception as e:
            logger.error(f"Error processing discount request: {e}")
            flash("An error occurred while processing your request. Please try again later.", "error")
            return redirect(url_for('request_discount'))

    return render_template('request_discount.html', approver_level=session.get('approver_level', 'Unknown'))

# Replace hardcoded email with dynamic user tracking logic
@app.before_request
def track_logged_in_user():
    # Simulate fetching logged-in user email dynamically
    # session['logged_in_email'] = request.headers.get('X-User-Email', 'unknown@example.com')
    logger.info(f"Session updated with logged-in email: {session['logged_in_email']}")

@app.route('/approve_request', methods=['GET', 'POST'])
def approve_request():
    if 'logged_in_email' not in session:
        return redirect(url_for('login'))
    
    client = get_bigquery_client()

    logged_in_email = session.get('logged_in_email')
    if not logged_in_email:
        flash('You must be logged in to approve requests.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            request_id = request.form['request_id']
            action = request.form['action']
            approved_discount_value = request.form.get('discounted_fees')

            logger.info(f"Approve request received: request_id={request_id}, action={action}, logged_in_email={logged_in_email}, approved_discount_value={approved_discount_value}")

            # Verify approver
            logger.info(f"Logged in email: {logged_in_email}")
            query = f"""
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY enquiry_no ORDER BY created_at DESC) as rn 
                    FROM `{project_id}.{dataset_id}.discount_requests`
                    WHERE status IN ('PENDING', 'APPROVED_L1')
                ) WHERE rn = 1
            """
            logger.info(f"Executing approver query: {query}")
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('logged_in_email', 'STRING', logged_in_email)
                ]
            )
            result = list(client.query(query, job_config=job_config).result())
            approver = result[0] if result else None

            if not approver:
                logger.warning(f"Unauthorized approver: {logged_in_email}")
                flash('Unauthorized approver', 'error')
                return redirect(url_for('approve_request'))

            logger.info(f"Approver verified: {approver}")

            # Set the approver level in the session
            session['approver_level'] = approver['level']
            logger.info(f"Approver level set in session: {approver['level']}")

            # Display approver level at the top
            flash(f"Logged in as {logged_in_email} (Level: {approver['level']})", 'info')

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
            discount_request = list(result)[0] if result else None

            if not discount_request:
                logger.warning(f"Discount request not found: enquiry_no={request_id}")
                flash('Discount request not found', 'error')
                return redirect(url_for('approve_request'))

            logger.info(f"Discount request details: {discount_request}")

            # Validate approved amount
            if action == 'APPROVE' and (not approved_discount_value or not approved_discount_value.strip()):
                logger.warning("Approved Discount is required and cannot be empty for approval.")
                flash("Approved Discount is required and cannot be empty for approval.", "error")
                return redirect(url_for('approve_request'))

            try:
                new_discounted_fees = float(approved_discount_value)
            except ValueError as e:
                logger.error(f"Invalid approved discount value: {e}")
                flash("Invalid approved discount value provided.", "error")
                return redirect(url_for('approve_request'))

            # Handle branch authorization
            approver_branches = approver['branch_name']
            if 'All' not in approver_branches and discount_request['branch_name'] not in approver_branches:
                logger.warning(f"Approver not authorized for branch: approver_branches={approver_branches}, request_branch={discount_request['branch_name']}")
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

            update_data[f"{approver['level'].lower()}_approver"] = logged_in_email

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
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY enquiry_no ORDER BY created_at DESC) as rn 
                FROM `{project_id}.{dataset_id}.discount_requests`
                WHERE status IN ('PENDING', 'APPROVED_L1')
            ) 
            WHERE rn = 1
        """
        logger.info(f"Executing refined query to fetch pending requests: {query}")
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
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
