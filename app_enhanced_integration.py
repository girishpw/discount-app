"""
Updated application code showing integration with the restructured database.

This demonstrates a feature flag approach where the application can use either
the old structure or the new normalized structure based on configuration.
"""

import os
from enhanced_data_access import DiscountDataAccess

# Feature flag to enable new database structure
USE_ENHANCED_DATA_ACCESS = os.getenv('USE_ENHANCED_DATA_ACCESS', 'false').lower() == 'true'

# Global enhanced data access instance
enhanced_data_access = None

def get_enhanced_data_access():
    """Get or create enhanced data access instance."""
    global enhanced_data_access
    if enhanced_data_access is None:
        client = get_bigquery_client()
        if client:
            enhanced_data_access = DiscountDataAccess(client, project_id, dataset_id)
    return enhanced_data_access

def get_branches_enhanced():
    """Enhanced version of get_branches using new structure."""
    if USE_ENHANCED_DATA_ACCESS:
        data_access = get_enhanced_data_access()
        if data_access:
            return data_access.get_branches()
    
    # Fallback to original implementation
    return get_branches()

def get_cards_for_branch_enhanced(branch_name):
    """Enhanced version of get_cards_for_branch using new structure."""
    if USE_ENHANCED_DATA_ACCESS:
        data_access = get_enhanced_data_access()
        if data_access:
            return data_access.get_cards_for_branch(branch_name)
    
    # Fallback to original implementation
    return get_cards_for_branch(branch_name)

def get_mrp_installment_for_branch_card_enhanced(branch_name, card_name):
    """Enhanced version using new structure."""
    if USE_ENHANCED_DATA_ACCESS:
        data_access = get_enhanced_data_access()
        if data_access:
            course_details = data_access.get_course_details(branch_name, card_name)
            if course_details:
                return {
                    'mrp': course_details['mrp'],
                    'installment': course_details['installment']
                }
            return None
    
    # Fallback to original implementation
    return get_mrp_installment_for_branch_card(branch_name, card_name)

def create_discount_request_enhanced(request_data):
    """Enhanced version of discount request creation."""
    if USE_ENHANCED_DATA_ACCESS:
        data_access = get_enhanced_data_access()
        if data_access:
            # Check for duplicates using new structure
            if data_access.check_duplicate_request(
                request_data['enquiry_no'], 
                request_data['requester_email']
            ):
                return {'success': False, 'error': 'Duplicate request'}
            
            # Get course details
            course_details = data_access.get_course_details(
                request_data['branch_name'],
                request_data['card_name']
            )
            if not course_details:
                return {'success': False, 'error': 'Invalid branch/card combination'}
            
            # Create or get student
            student_id = data_access.create_or_get_student(
                request_data['enquiry_no'],
                request_data['student_name'],
                request_data['mobile_no']
            )
            if not student_id:
                return {'success': False, 'error': 'Failed to create student record'}
            
            # Create discount request
            request_id = data_access.create_discount_request(
                student_id=student_id,
                course_id=course_details['course_id'],
                course_details=course_details,
                requested_discount_amount=request_data['discount_amount'],
                discount_reason=request_data['reason'],
                remarks=request_data.get('remarks', ''),
                requester_email=request_data['requester_email'],
                requester_name=request_data['requester_name']
            )
            
            if request_id:
                return {'success': True, 'request_id': request_id}
            else:
                return {'success': False, 'error': 'Failed to create request'}
    
    # Fallback to original implementation
    return create_discount_request_original(request_data)

def get_pending_requests_enhanced(approver_level, approver_email):
    """Enhanced version of getting pending requests."""
    if USE_ENHANCED_DATA_ACCESS:
        data_access = get_enhanced_data_access()
        if data_access:
            return data_access.get_pending_requests_for_approver(
                approver_level, approver_email
            )
    
    # Fallback to original implementation
    return get_pending_requests_original(approver_level, approver_email)

def approve_request_enhanced(request_data):
    """Enhanced version of request approval."""
    if USE_ENHANCED_DATA_ACCESS:
        data_access = get_enhanced_data_access()
        if data_access:
            success = data_access.approve_or_reject_request(
                request_id=request_data['request_id'],
                action=request_data['action'],
                approver_level=request_data['approver_level'],
                approver_email=request_data['approver_email'],
                approver_name=request_data['approver_name'],
                approved_amount=request_data.get('approved_amount'),
                comments=request_data.get('comments', '')
            )
            return {'success': success}
    
    # Fallback to original implementation
    return approve_request_original(request_data)

def get_dashboard_stats_enhanced():
    """Enhanced version of dashboard stats."""
    if USE_ENHANCED_DATA_ACCESS:
        data_access = get_enhanced_data_access()
        if data_access:
            return data_access.get_dashboard_stats()
    
    # Fallback to original implementation
    return get_dashboard_stats()

# Example of how to update the routes to use enhanced functions

# Update the request_discount route
def request_discount_route_enhanced():
    """Enhanced request discount route."""
    if request.method == 'POST':
        try:
            # Validate enquiry number format
            enquiry_no = request.form['enquiry_no']
            if not validate_enquiry_no(enquiry_no):
                flash('Invalid enquiry number format. Must be EN followed by 8 digits.', 'error')
                return redirect(url_for('request_discount'))
            
            # Prepare request data
            request_data = {
                'enquiry_no': enquiry_no,
                'student_name': request.form['student_name'],
                'mobile_no': request.form['mobile_no'],
                'branch_name': request.form['branch_name'],
                'card_name': request.form['card_name'],
                'discount_amount': float(request.form['discount_amount']),
                'reason': request.form['reason'],
                'remarks': request.form.get('remarks', ''),
                'requester_email': session['logged_in_email'],
                'requester_name': session['user_name']
            }
            
            # Validate pricing using enhanced function
            pricing = get_mrp_installment_for_branch_card_enhanced(
                request_data['branch_name'], 
                request_data['card_name']
            )
            if not pricing:
                flash('Invalid branch and card combination.', 'error')
                return redirect(url_for('request_discount'))
            
            # Validate discount percentage
            discount_percentage = (request_data['discount_amount'] / pricing['installment']) * 100
            if discount_percentage <= 30:
                flash('Use ERP for discounts up to 30%. This portal handles discounts greater than 30%.', 'error')
                return redirect(url_for('request_discount'))
            
            # Create request using enhanced function
            result = create_discount_request_enhanced(request_data)
            
            if result['success']:
                # Send notifications (existing code)
                flash('Discount request submitted successfully!', 'success')
                return redirect(url_for('request_discount'))
            else:
                flash(f'Error: {result["error"]}', 'error')
                return redirect(url_for('request_discount'))
                
        except Exception as e:
            logger.error(f"Error processing discount request: {e}")
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('request_discount'))
    
    # GET request - show form
    branches = get_branches_enhanced()
    return render_template('request_discount.html', 
                         branches=branches,
                         user_branch=session.get('branch_name', ''),
                         approver_level=session.get('approver_level', 'Unknown'))

# Configuration check route
@app.route('/debug/db-structure')
def debug_db_structure():
    """Debug route to check which database structure is being used."""
    if 'logged_in_email' not in session:
        return '<h2>Please login first</h2><a href="/login">Login</a>'
    
    info = {
        'USE_ENHANCED_DATA_ACCESS': USE_ENHANCED_DATA_ACCESS,
        'Enhanced Data Access Available': bool(get_enhanced_data_access()),
        'BigQuery Client Available': bool(get_bigquery_client()),
    }
    
    if USE_ENHANCED_DATA_ACCESS:
        try:
            # Test enhanced functions
            branches = get_branches_enhanced()
            info['Enhanced Branches Count'] = len(branches)
            
            total, pending, approved, rejected, recent = get_dashboard_stats_enhanced()
            info['Enhanced Dashboard Stats'] = f"Total: {total}, Pending: {pending}"
        except Exception as e:
            info['Enhanced Functions Error'] = str(e)
    
    html = '<h2>Database Structure Debug</h2><ul>'
    for key, value in info.items():
        html += f'<li><b>{key}:</b> {value}</li>'
    html += '</ul>'
    
    html += '<h3>Migration Commands</h3>'
    html += '<p>To enable enhanced data access:</p>'
    html += '<ol>'
    html += '<li>Run: <code>python migrate_database.py migrate</code></li>'
    html += '<li>Set environment variable: <code>USE_ENHANCED_DATA_ACCESS=true</code></li>'
    html += '<li>Restart application</li>'
    html += '</ol>'
    
    return html

# Example: Updated API endpoints
@app.route('/api/cards/<branch_name>/enhanced')
def get_cards_api_enhanced(branch_name):
    """Enhanced API endpoint for getting cards."""
    try:
        cards = get_cards_for_branch_enhanced(branch_name)
        return jsonify({
            'cards': cards,
            'using_enhanced': USE_ENHANCED_DATA_ACCESS,
            'count': len(cards)
        })
    except Exception as e:
        logger.error(f"Error in enhanced cards API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/mrp/<branch_name>/<card_name>/enhanced')
def get_mrp_api_enhanced(branch_name, card_name):
    """Enhanced API endpoint for getting MRP and installment."""
    try:
        data = get_mrp_installment_for_branch_card_enhanced(branch_name, card_name)
        if data:
            return jsonify({
                'mrp': data['mrp'],
                'installment': data['installment'],
                'using_enhanced': USE_ENHANCED_DATA_ACCESS
            })
        else:
            return jsonify({
                'mrp': None, 
                'installment': None,
                'using_enhanced': USE_ENHANCED_DATA_ACCESS
            })
    except Exception as e:
        logger.error(f"Error in enhanced MRP API: {e}")
        return jsonify({'error': str(e)}), 500

# Migration helper functions for backward compatibility
def create_discount_request_original(request_data):
    """Original implementation placeholder."""
    # This would contain the original implementation
    # for backward compatibility during transition
    pass

def get_pending_requests_original(approver_level, approver_email):
    """Original implementation placeholder."""
    # This would contain the original implementation
    pass

def approve_request_original(request_data):
    """Original implementation placeholder."""
    # This would contain the original implementation
    pass