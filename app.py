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

PORT = int(os.environ.get("PORT", 8080))

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

# Update required variables
required_env_vars = ['EMAIL_SENDER', 'EMAIL_PASSWORD', 'FLASK_SECRET_KEY']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.warning("Application may not function properly")

# Ensure proper session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False

# Initialize BigQuery client
project_id = 'gewportal2025'
dataset_id = 'discount_management'
client = None

# Update BigQuery client initialization
def get_bigquery_client():
    global client
    if client is None:
        try:
            # Try to use service account credentials first
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path and os.path.exists(credentials_path):
                logger.info(f"Using service account credentials from: {credentials_path}")
                credentials = service_account.Credentials.from_service_account_file(credentials_path)
                client = bigquery.Client(project=project_id, credentials=credentials)
            else:
                # Fall back to Application Default Credentials
                logger.info("Using Application Default Credentials")
                client = bigquery.Client(project=project_id)
            
            # Test the connection
            client.query("SELECT 1 as test").result()
            logger.info(f"BigQuery client initialized successfully with project: {project_id}")
        except Exception as e:
            logger.error(f"Error initializing BigQuery client: {e}")
            logger.warning("BigQuery operations will be disabled")
            client = None
    return client


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        session['logged_in_email'] = email
        
        # Set a default approver_level for non-approvers
        session['approver_level'] = 'User'
        
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in_email', None)
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

@app.before_request
def track_logged_in_user():
    # Only log if the key exists, don't try to access it
    if 'logged_in_email' in session:
        logger.info(f"Session contains logged-in email")
    else:
        logger.info("No logged-in user found in session")


@app.route('/')
def index():
    # Set approver_level from session or default to 'Unknown'
    approver_level = session.get('approver_level', 'Unknown')
    return render_template('index.html', approver_level=approver_level)

@app.route('/_health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat(),'port': PORT}), 200


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
                try:
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
                except Exception as e:
                    logger.warning(f"Authorization check failed: {e}. Proceeding without authorization check.")
            else:
                logger.warning("BigQuery client is unavailable. Skipping authorization check.")

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

    approver_level = session.get('approver_level', 'Unknown')
    return render_template('request_discount.html', approver_level=approver_level)


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
        return render_template('approve_request.html', 
                          requests=requests, 
                          approver_level=session.get('approver_level', 'Unknown'))
    except Exception as e:
        logger.error(f"Error fetching pending requests: {e}")
        flash('An error occurred while fetching pending requests. Please try again later.', 'error')
        return redirect(url_for('index'))

# Add new routes for redesigned UI
def get_dashboard_stats():
    client = get_bigquery_client()
    if client is None:
        logger.warning("BigQuery client not available, returning default stats")
        return 0, 0, 0, 0, []
    
    try:
        # Get stats
        stats_query = f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status LIKE 'APPROVED%' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected
            FROM `{project_id}.{dataset_id}.discount_requests`
        """
        stats_result = list(client.query(stats_query).result())[0]
        total = stats_result['total'] or 0
        pending = stats_result['pending'] or 0
        approved = stats_result['approved'] or 0
        rejected = stats_result['rejected'] or 0
        
        # Get recent requests
        recent_query = f"""
            SELECT enquiry_no, student_name, branch_name, status, mrp, discounted_fees, net_discount
            FROM `{project_id}.{dataset_id}.discount_requests`
            ORDER BY created_at DESC
            LIMIT 5
        """
        recent = list(client.query(recent_query).result())
        return total, pending, approved, rejected, recent
    except Exception as e:
        if 'Access Denied' in str(e) or '403' in str(e):
            logger.warning(f"Access denied to BigQuery tables: {e}")
        elif 'Not found' in str(e) or '404' in str(e):
            logger.warning(f"BigQuery table not found: {e}")
        else:
            logger.error(f"Error fetching dashboard stats: {e}")
        return 0, 0, 0, 0, []

@app.route('/dashboard')
def dashboard():
    total_requests, pending_requests, approved_requests, rejected_requests, recent_requests = get_dashboard_stats()
    return render_template(
        'dashboard.html',
        total_requests=total_requests,
        pending_requests=pending_requests,
        approved_requests=approved_requests,
        rejected_requests=rejected_requests,
        recent_requests=recent_requests
    )

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

# Add to app.py
def parse_datetime(value):
    from dateutil import parser
    try:
        return parser.parse(value)
    except Exception:
        return value

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%b %d, %Y %I:%M %p'):
    if value is None:
        return ""
    dt = value
    if isinstance(value, str):
        dt = parse_datetime(value)
    try:
        return dt.strftime(format)
    except Exception:
        return str(value)

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

@app.route('/test_bigquery')
def test_bigquery():
    """Test BigQuery connectivity and authentication"""
    try:
        client = get_bigquery_client()
        if client is None:
            return jsonify({
                'status': 'error',
                'message': 'BigQuery client could not be initialized'
            }), 500
        
        # Test basic query
        test_query = "SELECT 1 as test_value"
        result = list(client.query(test_query).result())
        
        # Test project access
        project_info = {
            'project_id': client.project,
            'location': getattr(client, 'location', 'US'),
        }
        
        # Test dataset access
        try:
            dataset_ref = client.dataset(dataset_id, project=project_id)
            dataset = client.get_dataset(dataset_ref)
            dataset_info = {
                'dataset_id': dataset.dataset_id,
                'created': dataset.created.isoformat() if dataset.created else None,
                'location': dataset.location
            }
        except Exception as e:
            dataset_info = {'error': str(e)}
        
        # Test table access
        try:
            table_ref = client.dataset(dataset_id, project=project_id).table('discount_requests')
            table = client.get_table(table_ref)
            table_info = {
                'table_id': table.table_id,
                'num_rows': table.num_rows,
                'created': table.created.isoformat() if table.created else None
            }
        except Exception as e:
            table_info = {'error': str(e)}
        
        return jsonify({
            'status': 'success',
            'test_query_result': result[0] if result else None,
            'project_info': project_info,
            'dataset_info': dataset_info,
            'table_info': table_info,
            'credentials_path': os.getenv('GOOGLE_APPLICATION_CREDENTIALS'),
            'project_env': os.getenv('GOOGLE_CLOUD_PROJECT')
        })
        
    except Exception as e:
        logger.error(f"BigQuery test failed: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'credentials_path': os.getenv('GOOGLE_APPLICATION_CREDENTIALS'),
            'project_env': os.getenv('GOOGLE_CLOUD_PROJECT')
        }), 500

# Ensure the project ID is explicitly set in the environment
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gewportal2025'
logger.info(f"GOOGLE_CLOUD_PROJECT set to: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")

# Ensure GOOGLE_APPLICATION_CREDENTIALS is set
if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
    logger.error("GOOGLE_APPLICATION_CREDENTIALS is not set. BigQuery client will fail to initialize.")
else:
    logger.info(f"GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")

# Retrieve credentials from Secret Manager (for Cloud Run deployment)
SECRET_NAME = os.getenv('SECRET_NAME', 'discount-key')

def setup_bigquery_credentials():
    """Setup BigQuery credentials from Secret Manager if available"""
    try:
        # Skip Secret Manager setup if credentials are already available
        if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') and os.path.exists(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')):
            logger.info("Using existing service account credentials")
            return
        
        # Try to get credentials from Secret Manager
        secret_client = secretmanager.SecretManagerServiceClient()
        secret_path = f"projects/{os.getenv('GOOGLE_CLOUD_PROJECT', project_id)}/secrets/{SECRET_NAME}/versions/latest"
        response = secret_client.access_secret_version(name=secret_path)
        credentials_content = response.payload.data.decode('UTF-8')

        # Write credentials to a temporary file
        temp_credentials_path = '/tmp/gewportal2025-key.json'
        with open(temp_credentials_path, 'w') as temp_file:
            temp_file.write(credentials_content)

        # Set GOOGLE_APPLICATION_CREDENTIALS to the temporary file
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
        logger.info(f"GOOGLE_APPLICATION_CREDENTIALS set from Secret Manager: {temp_credentials_path}")
    except Exception as e:
        logger.warning(f"Failed to retrieve credentials from Secret Manager: {e}")
        logger.info("Will try to use Application Default Credentials or existing credentials")

# Setup credentials on startup
setup_bigquery_credentials()

# Make stats available in all templates
@app.context_processor
def inject_dashboard_stats():
    try:
        total_requests, pending_requests, approved_requests, rejected_requests, recent_requests = get_dashboard_stats()
    except Exception as e:
        logger.warning(f"Failed to get dashboard stats: {e}")
        total_requests = pending_requests = approved_requests = rejected_requests = 0
        recent_requests = []
    return {
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'rejected_requests': rejected_requests,
        'recent_requests': recent_requests
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)