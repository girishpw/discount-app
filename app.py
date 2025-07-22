import os
import logging
import re
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from google.cloud import bigquery
from google.cloud import secretmanager
from google.oauth2 import service_account
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

PORT = int(os.environ.get("PORT", 8080))

# Remove hardcoded sensitive information; rely on environment variables/secrets
EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')  # Keep default for server as it's not sensitive
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))  # Keep default for port as it's not sensitive

# Update app secret key to use environment variable
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Enhanced check for missing environment variables
required_env_vars = ['EMAIL_SENDER', 'EMAIL_PASSWORD', 'FLASK_SECRET_KEY']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.critical(f"Missing required environment variables: {', '.join(missing_vars)}. Application will run but email sending is disabled.")
    # Optionally, raise an exception in non-prod: raise ValueError("Missing required env vars")
else:
    logger.info("All required environment variables are set.")

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


def validate_pw_email(email):
    """Validate if email is from pw.live domain"""
    return email.endswith('@pw.live')


def require_auth(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def require_permission(permission):
    """Decorator to require specific permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in_email' not in session:
                return redirect(url_for('login'))
            
            if permission == 'request_discount' and not session.get('can_request_discount', False):
                flash('You are not authorized to request discounts.', 'error')
                return redirect(url_for('dashboard'))
            elif permission == 'approve' and session.get('approver_level') not in ['L1', 'L2']:
                flash('You are not authorized to approve requests.', 'error')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def validate_enquiry_no(enquiry_no):
    """Validate enquiry number format EN********* (8 digits)"""
    pattern = r'^EN\d{9}$'
    return re.match(pattern, enquiry_no) is not None


def get_authorized_person(email):
    """Get authorized person details from database"""
    client = get_bigquery_client()
    if not client:
        return None
    
    try:
        query = f"""
            SELECT email, name, branch_name, approver_level, can_request_discount
            FROM `{project_id}.{dataset_id}.authorized_persons`
            WHERE email = @email AND is_active = true
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('email', 'STRING', email)
            ]
        )
        result = list(client.query(query, job_config=job_config).result())
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error fetching authorized person: {e}")
        return None


def authenticate_user(email, password):
    """Authenticate user with email and password"""
    client = get_bigquery_client()
    if not client:
        return None
    
    try:
        query = f"""
            SELECT email, name, branch_name, approver_level, can_request_discount, password
            FROM `{project_id}.{dataset_id}.authorized_persons`
            WHERE email = @email AND password = @password AND is_active = true
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('email', 'STRING', email),
                bigquery.ScalarQueryParameter('password', 'STRING', password)
            ]
        )
        result = list(client.query(query, job_config=job_config).result())
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        return None


def get_branches():
    """Get unique branches from branch_cards_fees table"""
    client = get_bigquery_client()
    if not client:
        logger.error("BigQuery client not available for get_branches")
        return []
    
    try:
        query = f"""
            SELECT DISTINCT branch_name
            FROM `{project_id}.{dataset_id}.branch_cards_fees`
            ORDER BY branch_name
        """
        logger.info(f"Executing query: {query}")
        result = client.query(query).result()
        branches = [row.branch_name for row in result]
        logger.info(f"Found {len(branches)} branches: {branches}")
        return branches
    except Exception as e:
        logger.error(f"Error fetching branches: {e}")
        return []


def get_cards_for_branch(branch_name):
    """Get cards for a specific branch"""
    client = get_bigquery_client()
    if not client:
        logger.error("BigQuery client not available for get_cards_for_branch")
        return []
    
    try:
        query = f"""
            SELECT DISTINCT card_name
            FROM `{project_id}.{dataset_id}.branch_cards_fees`
            WHERE branch_name = @branch_name
            ORDER BY card_name
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('branch_name', 'STRING', branch_name)
            ]
        )
        logger.info(f"Executing query for branch {branch_name}: {query}")
        result = client.query(query, job_config=job_config).result()
        cards = [row.card_name for row in result]
        logger.info(f"Found {len(cards)} cards for branch {branch_name}: {cards}")
        return cards
    except Exception as e:
        logger.error(f"Error fetching cards for branch {branch_name}: {e}")
        return []


def get_mrp_installment_for_branch_card(branch_name, card_name):
    """Get MRP and installment for specific branch and card combination"""
    client = get_bigquery_client()
    if not client:
        logger.error("BigQuery client not available for get_mrp_installment_for_branch_card")
        return None
    
    try:
        query = f"""
            SELECT mrp, installment
            FROM `{project_id}.{dataset_id}.branch_cards_fees`
            WHERE branch_name = @branch_name AND card_name = @card_name
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('branch_name', 'STRING', branch_name),
                bigquery.ScalarQueryParameter('card_name', 'STRING', card_name)
            ]
        )
        logger.info(f"Executing MRP and installment query for branch {branch_name}, card {card_name}: {query}")
        result = list(client.query(query, job_config=job_config).result())
        if result:
            mrp = float(result[0].mrp)
            installment = float(result[0].installment)
            logger.info(f"Found MRP: {mrp}, Installment: {installment}")
            return {'mrp': mrp, 'installment': installment}
        else:
            logger.warning(f"No MRP/installment found for branch {branch_name}, card {card_name}")
            return None
    except Exception as e:
        logger.error(f"Error fetching MRP/installment for branch {branch_name}, card {card_name}: {e}")
        return None

def get_mrp_for_branch_card(branch_name, card_name):
    """Get MRP for specific branch and card combination - backward compatibility"""
    data = get_mrp_installment_for_branch_card(branch_name, card_name)
    return data['mrp'] if data else None


def get_approvers_for_branch(branch_name, level):
    client = get_bigquery_client()
    if not client:
        return []
    
    try:
        if level == 'L1':
            # Custom L1 logic remains, but use ARRAY_CONTAINS
            query = f"""
                SELECT email, name
                FROM `{project_id}.{dataset_id}.authorized_persons`
                WHERE is_active = true
                AND approver_level = @level
                AND (ARRAY_CONTAINS(@branch_name, branch_names) OR ARRAY_LENGTH(branch_names) = 0)  -- Empty array means 'ALL'
            """
        else:
            query = f"""
                SELECT email, name
                FROM `{project_id}.{dataset_id}.authorized_persons`
                WHERE is_active = true
                AND approver_level = @level
                AND (ARRAY_CONTAINS(@branch_name, branch_names) OR ARRAY_LENGTH(branch_names) = 0)
            """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('branch_name', 'STRING', branch_name),
                bigquery.ScalarQueryParameter('level', 'STRING', level)
            ]
        )
        result = client.query(query, job_config=job_config).result()
        return [(row.email, row.name) for row in result]
    except Exception as e:
        logger.error(f"Error fetching approvers: {e}")
        return []


def send_notification_email(to_emails, subject, body):
    """Send notification email with CC recipients and detailed debugging"""
    # Required CC recipients as per problem statement
    cc_emails = [
        'prince.tiwari@pw.live',
        'rohan.kumar1@pw.live', 
        'sanover.naquvi@pw.live',
        'prashant.soni@pw.live'
    ]
    
    logger.info(f"Email Debug: Sender={EMAIL_SENDER}, Recipients={to_emails}, CC={cc_emails}")
    logger.info(f"Email Debug: SMTP_SERVER={SMTP_SERVER}, SMTP_PORT={SMTP_PORT}")
    
    try:
        for email in to_emails:
            logger.info(f"Sending email to: {email}")
            msg = MIMEText(body, 'html')
            msg['Subject'] = subject
            msg['From'] = EMAIL_SENDER
            msg['To'] = email
            # Add CC recipients
            msg['Cc'] = ', '.join(cc_emails)
            
            # Combine TO and CC for actual sending
            all_recipients = [email] + cc_emails
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                logger.info("Connecting to SMTP server...")
                server.starttls()
                logger.info("Starting TLS...")
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                logger.info("Login successful")
                server.send_message(msg, to_addrs=all_recipients)
                logger.info(f"Email sent successfully to {email} with CC to {cc_emails}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        # Handle authentication errors specifically
        logger.error(f"SMTP Auth Error: {e}")
        logger.error(f"Please check email credentials for {EMAIL_SENDER}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {e}")
        return False
    except Exception as e:
        logger.error(f"General Email Error: {e}")
        return False

@app.route('/debug/config')
def debug_config():
    """Debug route to check configuration - remove in production"""
    if 'logged_in_email' not in session:
        return '<h2>Please login first</h2><a href="/login">Login</a>'
    
    config_info = {
        'EMAIL_SENDER': EMAIL_SENDER,
        'EMAIL_PASSWORD': '***' if EMAIL_PASSWORD else 'NOT SET',
        'SMTP_SERVER': SMTP_SERVER,
        'SMTP_PORT': SMTP_PORT,
        'BIGQUERY_PROJECT': project_id,
        'BIGQUERY_DATASET': dataset_id,
        'BIGQUERY_CLIENT': 'Available' if get_bigquery_client() else 'Not Available'
    }
    
    html = '<h2>Configuration Debug</h2><ul>'
    for key, value in config_info.items():
        html += f'<li><b>{key}:</b> {value}</li>'
    html += '</ul>'
    
    return html

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Password-based login for users"""
    # Check if user is already logged in
    if 'logged_in_email' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Validate pw.live domain
        if not validate_pw_email(email):
            flash('Please use your official pw.live email address.', 'error')
            return render_template('login.html')
        
        # Check credentials in database
        auth_person = authenticate_user(email, password)
        if not auth_person:
            flash('Invalid email or password. Please try again.', 'error')
            return render_template('login.html')
        
        # Set session data
        session['logged_in_email'] = email
        session['user_name'] = auth_person['name']
        session['branch_name'] = auth_person['branch_name']
        session['approver_level'] = auth_person['approver_level']
        session['can_request_discount'] = auth_person['can_request_discount']
        
        flash(f'Welcome {auth_person["name"]}! You are logged in as {auth_person["approver_level"]} for {auth_person["branch_name"]}.', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')


@app.route('/login/manual', methods=['GET', 'POST'])
def manual_login():
    """Alternative manual login endpoint (same as main login)"""
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

def send_email(to_email, subject, body):
    """Send email using the updated notification system with CC"""
    return send_notification_email([to_email], subject, body)

@app.before_request
def track_logged_in_user():
    # Only log if the key exists, don't try to access it
    if 'logged_in_email' in session:
        logger.info("Session contains logged-in email")
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
@require_auth
@require_permission('request_discount')
def request_discount():
    
    if request.method == 'POST':
        try:
            # Validate enquiry number format
            enquiry_no = request.form['enquiry_no']
            if not validate_enquiry_no(enquiry_no):
                flash('Invalid enquiry number format. Must be EN followed by 8 digits (e.g., EN12345678).', 'error')
                return redirect(url_for('request_discount'))
            
            # Get form data
            branch_name = request.form['branch_name']
            card_name = request.form['card_name']
            
            # Validate MRP and installment from database
            db_data = get_mrp_installment_for_branch_card(branch_name, card_name)
            if not db_data:
                flash('Invalid branch and card combination.', 'error')
                return redirect(url_for('request_discount'))
            
            db_mrp = db_data['mrp']
            db_installment = db_data['installment']
            
            form_mrp = float(request.form['mrp'])
            form_installment = float(request.form['installment'])
            
            if abs(form_mrp - db_mrp) > 0.01:  # Allow small floating point differences
                flash(f'MRP mismatch. Expected: ₹{db_mrp}, Provided: ₹{form_mrp}', 'error')
                return redirect(url_for('request_discount'))
                
            if abs(form_installment - db_installment) > 0.01:  # Allow small floating point differences  
                flash(f'Installment mismatch. Expected: ₹{db_installment}, Provided: ₹{form_installment}', 'error')
                return redirect(url_for('request_discount'))

            # Get discount amount and calculate percentage
            discount_amount = float(request.form['discount_amount'])
            discount_percentage = (discount_amount / db_installment) * 100
            
            # Validate discount percentage - must be greater than 30%
            if discount_percentage <= 30:
                flash('Use ERP for the discounts upto 30%, this portal can receive discounts requests which are greater than 30%.', 'error')
                return redirect(url_for('request_discount'))
            
            # Calculate discounted fees
            discounted_fees = db_mrp - discount_amount
            data = {
                'enquiry_no': enquiry_no,
                'student_name': request.form['student_name'],
                'mobile_no': request.form['mobile_no'],
                'card_name': card_name,
                'mrp': db_mrp,
                'installment': db_installment,
                'discounted_fees': discounted_fees,
                'discount_amount': discount_amount,
                'discount_percentage': discount_percentage,
                'net_discount': discount_amount,
                'reason': request.form['reason'],
                'remarks': request.form.get('remarks', ''),
                'requester_email': session['logged_in_email'],
                'requester_name': session['user_name'],
                'branch_name': branch_name,
                'status': 'PENDING_L1',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'l1_approver': None,
                'l2_approver': None
            }

            # Insert into database
            client = get_bigquery_client()
            if client:
                # Check for duplicates
                dup_query = f"""
                    SELECT COUNT(*) as count FROM `{project_id}.{dataset_id}.discount_requests`
                    WHERE enquiry_no = @enquiry_no AND requester_email = @requester_email
                """
                dup_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter('enquiry_no', 'STRING', enquiry_no),
                        bigquery.ScalarQueryParameter('requester_email', 'STRING', session['logged_in_email'])
                    ]
                )
                dup_result = list(client.query(dup_query, dup_config).result())[0]
                
                if dup_result.count > 0:
                    flash('Duplicate request. This enquiry number has already been submitted.', 'error')
                    return redirect(url_for('request_discount'))
                
                # Insert new request
                insert_query = f"""
                    INSERT INTO `{project_id}.{dataset_id}.discount_requests`
                    (enquiry_no, student_name, mobile_no, card_name, mrp, installment, discounted_fees, 
                     discount_amount, discount_percentage, net_discount, reason, remarks, requester_email, 
                     requester_name, branch_name, status, created_at, l1_approver, l2_approver)
                    VALUES (@enquiry_no, @student_name, @mobile_no, @card_name, @mrp, @installment, 
                            @discounted_fees, @discount_amount, @discount_percentage, @net_discount, 
                            @reason, @remarks, @requester_email, @requester_name, @branch_name, 
                            @status, @created_at, @l1_approver, @l2_approver)
                """
                
                insert_params = [
                    bigquery.ScalarQueryParameter('enquiry_no', 'STRING', data['enquiry_no']),
                    bigquery.ScalarQueryParameter('student_name', 'STRING', data['student_name']),
                    bigquery.ScalarQueryParameter('mobile_no', 'STRING', data['mobile_no']),
                    bigquery.ScalarQueryParameter('card_name', 'STRING', data['card_name']),
                    bigquery.ScalarQueryParameter('mrp', 'FLOAT', data['mrp']),
                    bigquery.ScalarQueryParameter('installment', 'FLOAT', data['installment']),
                    bigquery.ScalarQueryParameter('discounted_fees', 'FLOAT', data['discounted_fees']),
                    bigquery.ScalarQueryParameter('discount_amount', 'FLOAT', data['discount_amount']),
                    bigquery.ScalarQueryParameter('discount_percentage', 'FLOAT', data['discount_percentage']),
                    bigquery.ScalarQueryParameter('net_discount', 'FLOAT', data['net_discount']),
                    bigquery.ScalarQueryParameter('reason', 'STRING', data['reason']),
                    bigquery.ScalarQueryParameter('remarks', 'STRING', data['remarks']),
                    bigquery.ScalarQueryParameter('requester_email', 'STRING', data['requester_email']),
                    bigquery.ScalarQueryParameter('requester_name', 'STRING', data['requester_name']),
                    bigquery.ScalarQueryParameter('branch_name', 'STRING', data['branch_name']),
                    bigquery.ScalarQueryParameter('status', 'STRING', data['status']),
                    bigquery.ScalarQueryParameter('created_at', 'STRING', data['created_at']),
                    bigquery.ScalarQueryParameter('l1_approver', 'STRING', data['l1_approver']),
                    bigquery.ScalarQueryParameter('l2_approver', 'STRING', data['l2_approver'])
                ]
                
                insert_config = bigquery.QueryJobConfig(query_parameters=insert_params)
                client.query(insert_query, insert_config).result()
                
            # Notify L1 approvers
            l1_approvers = get_approvers_for_branch(branch_name, 'L1')
            if l1_approvers:
                approver_emails = [email for email, name in l1_approvers]
                subject = f"New Discount Request - {enquiry_no}"
                body = f"""
                    <html><body style='font-family: Arial, sans-serif;'>
                    <h2 style='color:#4CAF50;'>New Discount Request - L1 Approval Required</h2>
                    <p>A new discount request has been submitted and requires your approval.</p>
                    <table style='border-collapse:collapse;'>
                    <tr><td><b>Enquiry No:</b></td><td>{enquiry_no}</td></tr>
                    <tr><td><b>Student Name:</b></td><td>{data['student_name']}</td></tr>
                    <tr><td><b>Mobile No:</b></td><td>{data['mobile_no']}</td></tr>
                    <tr><td><b>Branch:</b></td><td>{branch_name}</td></tr>
                    <tr><td><b>Card:</b></td><td>{card_name}</td></tr>
                    <tr><td><b>MRP:</b></td><td>₹{data['mrp']:,.2f}</td></tr>
                    <tr><td><b>Installment:</b></td><td>₹{data['installment']:,.2f}</td></tr>
                    <tr><td><b>Requested Discount Amount:</b></td><td>₹{discount_amount:,.2f}</td></tr>
                    <tr><td><b>Discount Percentage:</b></td><td>{discount_percentage:.2f}%</td></tr>
                    <tr><td><b>Discounted Fees:</b></td><td>₹{discounted_fees:,.2f}</td></tr>
                    <tr><td><b>Reason:</b></td><td>{data['reason']}</td></tr>
                    <tr><td><b>Requested by:</b></td><td>{data['requester_name']} ({data['requester_email']})</td></tr>
                    </table>
                    <p style='margin-top:20px;'>
                    <a href='https://discount-app-644139762582.asia-south2.run.app/login' style='background:#007bff;color:#fff;padding:10px 20px;text-decoration:none;border-radius:5px;'>Login to Approve</a>
                    <a href='https://discount-app-644139762582.asia-south2.run.app/approve_request' style='background:#28a745;color:#fff;padding:10px 20px;text-decoration:none;border-radius:5px;margin-left:10px;'>Go to Approval Page</a>
                    </p>
                    <p style='color:#888;font-size:12px;margin-top:30px;'>This is an automated notification from the Discount Management System.<br>Physics Wallah</p>
                    </body></html>
                """
                send_notification_email(approver_emails, subject, body)
                            
            flash('Discount request submitted successfully! L1 approvers have been notified.', 'success')
            return redirect(url_for('request_discount'))
        except Exception as e:
            logger.error(f"Error processing discount request: {e}")
            flash('An error occurred while processing your request. Please try again.', 'error')
            return redirect(url_for('request_discount'))
    
    # GET request - show form
    branches = get_branches()
    return render_template('request_discount.html', 
                         branches=branches,
                         user_branch=session.get('branch_name', ''),
                         approver_level=session.get('approver_level', 'Unknown'))


@app.route('/approve_request', methods=['GET', 'POST'])
@require_auth
@require_permission('approve')
def approve_request():
    
    client = get_bigquery_client()
    logged_in_email = session.get('logged_in_email')
    user_branch = session.get('branch_name')
    approver_level = session.get('approver_level')

    if request.method == 'POST':
        try:
            request_id = request.form.get('request_id')
            action = request.form.get('action')
            approved_discount_value = request.form.get('approved_discount_value')
            approver_comments = request.form.get('approver_comments', '')

            logger.info(f"Processing {action} for request {request_id} by {logged_in_email} (Level: {approver_level})")

            if not request_id or not action:
                flash('Invalid request data.', 'error')
                return redirect(url_for('approve_request'))

            # Get current request details - remove branch restriction for approvers
            get_query = f"""
                SELECT * FROM `{project_id}.{dataset_id}.discount_requests`
                WHERE enquiry_no = @enquiry_no
            """
            get_params = [
                bigquery.ScalarQueryParameter('enquiry_no', 'STRING', request_id)
            ]
            get_config = bigquery.QueryJobConfig(query_parameters=get_params)
            result = list(client.query(get_query, get_config).result())
            
            if not result:
                flash('Request not found or you are not authorized to approve this request.', 'error')
                return redirect(url_for('approve_request'))
            
            current_request = result[0]
            
            if action == 'APPROVE':
                if not approved_discount_value:
                    flash("Approved amount is required for approval.", "error")
                    return redirect(url_for('approve_request'))
                
                try:
                    approved_amount = float(approved_discount_value)
                    if approved_amount <= 0:
                        flash("Approved amount must be greater than 0.", "error")
                        return redirect(url_for('approve_request'))
                except ValueError:
                    flash("Invalid approved amount.", "error")
                    return redirect(url_for('approve_request'))
                
                # Determine new status and update fields based on approver level
                if approver_level == 'L1':
                    if current_request['status'] != 'PENDING_L1':
                        flash('This request is not pending L1 approval.', 'error')
                        return redirect(url_for('approve_request'))
                    
                    new_status = 'PENDING_L2'
                    update_query = f"""
                        UPDATE `{project_id}.{dataset_id}.discount_requests`
                        SET status = @status, 
                            discounted_fees = @approved_amount,
                            net_discount = @net_discount,
                            l1_approver = @approver_email,
                            l1_approved_at = @approved_at,
                            l1_comments = @comments
                        WHERE enquiry_no = @enquiry_no
                    """
                    net_discount = current_request['mrp'] - approved_amount
                    
                elif approver_level == 'L2':
                    if current_request['status'] != 'PENDING_L2':
                        flash('This request is not pending L2 approval.', 'error')
                        return redirect(url_for('approve_request'))
                    
                    new_status = 'APPROVED'
                    update_query = f"""
                        UPDATE `{project_id}.{dataset_id}.discount_requests`
                        SET status = @status, 
                            discounted_fees = @approved_amount,
                            net_discount = @net_discount,
                            l2_approver = @approver_email,
                            l2_approved_at = @approved_at,
                            l2_comments = @comments
                        WHERE enquiry_no = @enquiry_no
                    """
                    net_discount = current_request['mrp'] - approved_amount
                
                params = [
                    bigquery.ScalarQueryParameter('status', 'STRING', new_status),
                    bigquery.ScalarQueryParameter('approved_amount', 'FLOAT', approved_amount),
                    bigquery.ScalarQueryParameter('net_discount', 'FLOAT', net_discount),
                    bigquery.ScalarQueryParameter('approver_email', 'STRING', logged_in_email),
                    bigquery.ScalarQueryParameter('approved_at', 'STRING', datetime.now(timezone.utc).isoformat()),
                    bigquery.ScalarQueryParameter('comments', 'STRING', approver_comments),
                    bigquery.ScalarQueryParameter('enquiry_no', 'STRING', request_id)
                ]
                
            elif action == 'REJECT':
                # Rejection can happen at any level
                update_query = f"""
                    UPDATE `{project_id}.{dataset_id}.discount_requests`
                    SET status = 'REJECTED',
                        {approver_level.lower()}_approver = @approver_email,
                        {approver_level.lower()}_approved_at = @approved_at,
                        {approver_level.lower()}_comments = @comments
                    WHERE enquiry_no = @enquiry_no
                """
                params = [
                    bigquery.ScalarQueryParameter('approver_email', 'STRING', logged_in_email),
                    bigquery.ScalarQueryParameter('approved_at', 'STRING', datetime.now(timezone.utc).isoformat()),
                    bigquery.ScalarQueryParameter('comments', 'STRING', approver_comments),
                    bigquery.ScalarQueryParameter('enquiry_no', 'STRING', request_id)
                ]
            
            # Execute the update
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            client.query(update_query, job_config=job_config).result()
            
            # Send notifications
            if action == 'APPROVE':
                if approver_level == 'L1':
                    # Notify L2 approvers
                    l2_approvers = get_approvers_for_branch(user_branch, 'L2')
                    if l2_approvers:
                        approver_emails = [email for email, name in l2_approvers]
                        subject = f"L2 Approval Required - {request_id}"
                        body = f"""
<html><body style='font-family: Arial, sans-serif;'>
<h2 style='color:#ff9800;'>L2 Approval Required - Request Approved at L1</h2>
<p>A discount request has been <b>approved at L1 level</b> and now requires your L2 approval.</p>
<table style='border-collapse:collapse;'>
<tr><td><b>Enquiry No:</b></td><td>{request_id}</td></tr>
<tr><td><b>Student Name:</b></td><td>{current_request['student_name']}</td></tr>
<tr><td><b>Branch:</b></td><td>{current_request['branch_name']}</td></tr>
<tr><td><b>Card:</b></td><td>{current_request['card_name']}</td></tr>
<tr><td><b>Original MRP:</b></td><td>₹{current_request['mrp']:,.2f}</td></tr>
<tr><td><b>Installment:</b></td><td>₹{current_request.get('installment', 0):,.2f}</td></tr>
<tr><td><b>Discount Amount:</b></td><td>₹{net_discount:,.2f}</td></tr>
<tr><td><b>Discount Percentage:</b></td><td>{(net_discount / current_request.get('installment', 1) * 100):,.2f}%</td></tr>
<tr><td><b>L1 Approved Discounted Fees:</b></td><td>₹{approved_amount:,.2f}</td></tr>
<tr><td><b>L1 Approver:</b></td><td>{logged_in_email}</td></tr>
<tr><td><b>Original Requester:</b></td><td>{current_request['requester_name']} ({current_request['requester_email']})</td></tr>
</table>
<p style='margin-top:20px;'>
<a href='https://discount-app-644139762582.asia-south2.run.app/login' style='background:#007bff;color:#fff;padding:10px 20px;text-decoration:none;border-radius:5px;'>Login to Approve</a>
<a href='https://discount-app-644139762582.asia-south2.run.app/approve_request' style='background:#28a745;color:#fff;padding:10px 20px;text-decoration:none;border-radius:5px;margin-left:10px;'>Go to Approval Page</a>
</p>
<p style='color:#888;font-size:12px;margin-top:30px;'>This is an automated notification from the Discount Management System.<br>Physics Wallah</p>
</body></html>
                        """
                        send_notification_email(approver_emails, subject, body)
                    
                    flash(f'Request #{request_id} approved at L1 level! L2 approvers have been notified.', 'success')
                else:  # L2
                    flash(f'Request #{request_id} fully approved!', 'success')
                return redirect(url_for('approve_request'))
            else:
                flash(f'Request #{request_id} rejected successfully!', 'success')
                return redirect(url_for('approve_request'))
        except Exception as e:
            logger.error(f"Error processing approve request: {e}")
            flash(f'An error occurred while processing your request: {str(e)}', 'error')
            return redirect(url_for('approve_request'))

    try:
        # Get pending requests for the user's branch and level
        if approver_level == 'L1':
            status_filter = 'PENDING_L1'
            # For L1, filter by specific approver logic
            if logged_in_email == 'raja.ray@pw.live':
                branch_filter = "AND branch_name IN ('Kolkata', 'Siliguri', 'Bhubaneshwar')"
            elif logged_in_email == 'praduman.shukla@pw.live':
                branch_filter = "AND branch_name NOT IN ('Kolkata', 'Siliguri', 'Bhubaneshwar')"
            else:
                # For others like Girish who can handle all
                branch_filter = ""
        else:  # L2
            status_filter = 'PENDING_L2'
            branch_filter = ""  # L2 approvers can handle all branches
        
        query = f"""
            SELECT * FROM `{project_id}.{dataset_id}.discount_requests`
            WHERE status = @status 
            {branch_filter}
            ORDER BY created_at DESC
        """
        params = [
            bigquery.ScalarQueryParameter('status', 'STRING', status_filter)
        ]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        result = client.query(query, job_config=job_config).result()
        requests = list(result)
        
        return render_template('approve_request.html', 
                             requests=requests, 
                             approver_level=approver_level,
                             user_branch=user_branch)
    except Exception as e:
        logger.error(f"Error fetching pending requests: {e}")
        flash('An error occurred while fetching pending requests. Please try again later.', 'error')
        return redirect(url_for('dashboard'))


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
                SUM(CASE WHEN status LIKE 'PENDING%' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) as approved,
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
@require_auth
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



# Add to app.py
def parse_datetime(value):
    try:
        # Simple datetime parsing without dateutil
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value
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
        # In Cloud Run, service account is automatically available
        if os.getenv('K_SERVICE'):  # Cloud Run environment
            logger.info("Running in Cloud Run, using service account authentication")
            return

        # Skip Secret Manager setup if credentials are already available
        if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') and os.path.exists(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')):
            logger.info("Using existing service account credentials")
            return

        # Try to get credentials from Secret Manager (for local development)
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



@app.route('/api/cards/<branch_name>')
def get_cards_api(branch_name):
    """API endpoint to get cards for a branch"""
    try:
        logger.info(f"Getting cards for branch: {branch_name}")
        cards = get_cards_for_branch(branch_name)
        logger.info(f"Found {len(cards)} cards for branch {branch_name}: {cards}")
        return jsonify(cards)
    except Exception as e:
        logger.error(f"Error in get_cards_api: {e}")
        return jsonify([]), 500


@app.route('/api/mrp/<branch_name>/<card_name>')
def get_mrp_api(branch_name, card_name):
    """API endpoint to get MRP and installment for branch and card"""
    try:
        logger.info(f"Getting MRP and installment for branch: {branch_name}, card: {card_name}")
        data = get_mrp_installment_for_branch_card(branch_name, card_name)
        if data:
            logger.info(f"Found MRP: {data['mrp']}, Installment: {data['installment']}")
            return jsonify(data)
        else:
            logger.warning(f"No data found for branch: {branch_name}, card: {card_name}")
            return jsonify({'mrp': None, 'installment': None})
    except Exception as e:
        logger.error(f"Error in get_mrp_api: {e}")
        return jsonify({'mrp': None, 'installment': None}), 500

@app.route('/test_email')
def test_email():
    if 'logged_in_email' not in session:
        return '<h2>Please login first</h2><a href="/login">Login</a>'
    
    success = send_notification_email([session['logged_in_email']], 
                                    "Test Email", "Test successful!")
    return f"<h2>Test Result: {'SUCCESS' if success else 'FAILED'}</h2>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)