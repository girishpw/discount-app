"""
Enhanced data access layer for the restructured database schema.

This module provides functions to work with the new normalized database structure
while maintaining backward compatibility with existing application code.
"""

import uuid
import logging
from datetime import datetime, timezone
from google.cloud import bigquery

logger = logging.getLogger(__name__)

class DiscountDataAccess:
    """Enhanced data access layer for restructured database."""
    
    def __init__(self, client, project_id, dataset_id):
        self.client = client
        self.project_id = project_id
        self.dataset_id = dataset_id
    
    def get_branches(self):
        """Get unique branches from courses table."""
        if not self.client:
            logger.error("BigQuery client not available")
            return []
        
        try:
            query = f"""
                SELECT DISTINCT branch_name
                FROM `{self.project_id}.{self.dataset_id}.courses`
                WHERE is_active = TRUE
                ORDER BY branch_name
            """
            result = self.client.query(query).result()
            return [row.branch_name for row in result]
        except Exception as e:
            logger.error(f"Error fetching branches: {e}")
            return []
    
    def get_cards_for_branch(self, branch_name):
        """Get cards for a specific branch from courses table."""
        if not self.client:
            logger.error("BigQuery client not available")
            return []
        
        try:
            query = f"""
                SELECT DISTINCT card_name
                FROM `{self.project_id}.{self.dataset_id}.courses`
                WHERE branch_name = @branch_name AND is_active = TRUE
                ORDER BY card_name
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('branch_name', 'STRING', branch_name)
                ]
            )
            result = self.client.query(query, job_config=job_config).result()
            return [row.card_name for row in result]
        except Exception as e:
            logger.error(f"Error fetching cards for branch {branch_name}: {e}")
            return []
    
    def get_course_details(self, branch_name, card_name):
        """Get course details including MRP and installment."""
        if not self.client:
            logger.error("BigQuery client not available")
            return None
        
        try:
            query = f"""
                SELECT course_id, mrp, installment
                FROM `{self.project_id}.{self.dataset_id}.courses`
                WHERE branch_name = @branch_name AND card_name = @card_name AND is_active = TRUE
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('branch_name', 'STRING', branch_name),
                    bigquery.ScalarQueryParameter('card_name', 'STRING', card_name)
                ]
            )
            result = list(self.client.query(query, job_config=job_config).result())
            if result:
                row = result[0]
                return {
                    'course_id': row.course_id,
                    'mrp': float(row.mrp),
                    'installment': float(row.installment)
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching course details: {e}")
            return None
    
    def create_or_get_student(self, enquiry_no, student_name, mobile_no):
        """Create a new student or get existing one by enquiry_no."""
        if not self.client:
            logger.error("BigQuery client not available")
            return None
        
        try:
            # First check if student exists
            query = f"""
                SELECT student_id
                FROM `{self.project_id}.{self.dataset_id}.students`
                WHERE enquiry_no = @enquiry_no
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('enquiry_no', 'STRING', enquiry_no)
                ]
            )
            result = list(self.client.query(query, job_config=job_config).result())
            
            if result:
                return result[0].student_id
            
            # Create new student
            student_id = str(uuid.uuid4())
            insert_query = f"""
                INSERT INTO `{self.project_id}.{self.dataset_id}.students`
                (student_id, enquiry_no, student_name, mobile_no, created_at, updated_at)
                VALUES (@student_id, @enquiry_no, @student_name, @mobile_no, @created_at, @updated_at)
            """
            now = datetime.now(timezone.utc).isoformat()
            insert_params = [
                bigquery.ScalarQueryParameter('student_id', 'STRING', student_id),
                bigquery.ScalarQueryParameter('enquiry_no', 'STRING', enquiry_no),
                bigquery.ScalarQueryParameter('student_name', 'STRING', student_name),
                bigquery.ScalarQueryParameter('mobile_no', 'STRING', mobile_no),
                bigquery.ScalarQueryParameter('created_at', 'STRING', now),
                bigquery.ScalarQueryParameter('updated_at', 'STRING', now)
            ]
            insert_config = bigquery.QueryJobConfig(query_parameters=insert_params)
            self.client.query(insert_query, insert_config).result()
            
            return student_id
            
        except Exception as e:
            logger.error(f"Error creating/getting student: {e}")
            return None
    
    def create_discount_request(self, student_id, course_id, course_details, 
                              requested_discount_amount, discount_reason, remarks,
                              requester_email, requester_name):
        """Create a new discount request with pricing snapshot."""
        if not self.client:
            logger.error("BigQuery client not available")
            return None
        
        try:
            request_id = str(uuid.uuid4())
            snapshot_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            
            # Create discount request
            request_query = f"""
                INSERT INTO `{self.project_id}.{self.dataset_id}.discount_requests_new`
                (request_id, student_id, course_id, requested_discount_amount, discount_reason,
                 remarks, requester_email, requester_name, status, created_at, updated_at)
                VALUES (@request_id, @student_id, @course_id, @requested_discount_amount, @discount_reason,
                        @remarks, @requester_email, @requester_name, @status, @created_at, @updated_at)
            """
            request_params = [
                bigquery.ScalarQueryParameter('request_id', 'STRING', request_id),
                bigquery.ScalarQueryParameter('student_id', 'STRING', student_id),
                bigquery.ScalarQueryParameter('course_id', 'STRING', course_id),
                bigquery.ScalarQueryParameter('requested_discount_amount', 'FLOAT', requested_discount_amount),
                bigquery.ScalarQueryParameter('discount_reason', 'STRING', discount_reason),
                bigquery.ScalarQueryParameter('remarks', 'STRING', remarks or ''),
                bigquery.ScalarQueryParameter('requester_email', 'STRING', requester_email),
                bigquery.ScalarQueryParameter('requester_name', 'STRING', requester_name),
                bigquery.ScalarQueryParameter('status', 'STRING', 'PENDING_L1'),
                bigquery.ScalarQueryParameter('created_at', 'STRING', now),
                bigquery.ScalarQueryParameter('updated_at', 'STRING', now)
            ]
            request_config = bigquery.QueryJobConfig(query_parameters=request_params)
            self.client.query(request_query, request_config).result()
            
            # Create pricing snapshot
            snapshot_query = f"""
                INSERT INTO `{self.project_id}.{self.dataset_id}.pricing_snapshots`
                (snapshot_id, request_id, course_id, mrp_at_request, installment_at_request, created_at)
                VALUES (@snapshot_id, @request_id, @course_id, @mrp_at_request, @installment_at_request, @created_at)
            """
            snapshot_params = [
                bigquery.ScalarQueryParameter('snapshot_id', 'STRING', snapshot_id),
                bigquery.ScalarQueryParameter('request_id', 'STRING', request_id),
                bigquery.ScalarQueryParameter('course_id', 'STRING', course_id),
                bigquery.ScalarQueryParameter('mrp_at_request', 'FLOAT', course_details['mrp']),
                bigquery.ScalarQueryParameter('installment_at_request', 'FLOAT', course_details['installment']),
                bigquery.ScalarQueryParameter('created_at', 'STRING', now)
            ]
            snapshot_config = bigquery.QueryJobConfig(query_parameters=snapshot_params)
            self.client.query(snapshot_query, snapshot_config).result()
            
            return request_id
            
        except Exception as e:
            logger.error(f"Error creating discount request: {e}")
            return None
    
    def check_duplicate_request(self, enquiry_no, requester_email):
        """Check if a duplicate request exists for the same enquiry number and requester."""
        if not self.client:
            return False
        
        try:
            query = f"""
                SELECT COUNT(*) as count 
                FROM `{self.project_id}.{self.dataset_id}.discount_requests_new` dr
                JOIN `{self.project_id}.{self.dataset_id}.students` s ON dr.student_id = s.student_id
                WHERE s.enquiry_no = @enquiry_no AND dr.requester_email = @requester_email
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('enquiry_no', 'STRING', enquiry_no),
                    bigquery.ScalarQueryParameter('requester_email', 'STRING', requester_email)
                ]
            )
            result = list(self.client.query(query, job_config=job_config).result())[0]
            return result.count > 0
        except Exception as e:
            logger.error(f"Error checking duplicate request: {e}")
            return False
    
    def get_pending_requests_for_approver(self, approver_level, approver_email):
        """Get pending requests for a specific approver level and email."""
        if not self.client:
            return []
        
        try:
            status_filter = f'PENDING_{approver_level}'
            
            # Apply branch-specific filtering for L1 approvers
            branch_filter = ""
            if approver_level == 'L1':
                if approver_email == 'raja.ray@pw.live':
                    branch_filter = "AND c.branch_name IN ('Kolkata', 'Siliguri', 'Bhubaneshwar')"
                elif approver_email == 'praduman.shukla@pw.live':
                    branch_filter = "AND c.branch_name NOT IN ('Kolkata', 'Siliguri', 'Bhubaneshwar')"
            
            query = f"""
                SELECT 
                    dr.request_id,
                    s.enquiry_no,
                    s.student_name,
                    s.mobile_no,
                    c.branch_name,
                    c.card_name,
                    ps.mrp_at_request as mrp,
                    ps.installment_at_request as installment,
                    dr.requested_discount_amount as discount_amount,
                    dr.discount_reason as reason,
                    dr.remarks,
                    dr.requester_email,
                    dr.requester_name,
                    dr.status,
                    dr.created_at
                FROM `{self.project_id}.{self.dataset_id}.discount_requests_new` dr
                JOIN `{self.project_id}.{self.dataset_id}.students` s ON dr.student_id = s.student_id
                JOIN `{self.project_id}.{self.dataset_id}.courses` c ON dr.course_id = c.course_id
                JOIN `{self.project_id}.{self.dataset_id}.pricing_snapshots` ps ON dr.request_id = ps.request_id
                WHERE dr.status = @status 
                {branch_filter}
                ORDER BY dr.created_at DESC
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter('status', 'STRING', status_filter)
                ]
            )
            result = self.client.query(query, job_config=job_config).result()
            return list(result)
        except Exception as e:
            logger.error(f"Error fetching pending requests: {e}")
            return []
    
    def approve_or_reject_request(self, request_id, action, approver_level, 
                                 approver_email, approver_name, approved_amount=None, 
                                 comments=''):
        """Approve or reject a discount request."""
        if not self.client:
            return False
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            approval_id = str(uuid.uuid4())
            
            # Determine new status
            if action == 'APPROVE':
                new_status = 'PENDING_L2' if approver_level == 'L1' else 'APPROVED'
            else:
                new_status = 'REJECTED'
            
            # Update request status
            update_query = f"""
                UPDATE `{self.project_id}.{self.dataset_id}.discount_requests_new`
                SET status = @status, updated_at = @updated_at
                WHERE request_id = @request_id
            """
            update_params = [
                bigquery.ScalarQueryParameter('status', 'STRING', new_status),
                bigquery.ScalarQueryParameter('updated_at', 'STRING', now),
                bigquery.ScalarQueryParameter('request_id', 'STRING', request_id)
            ]
            update_config = bigquery.QueryJobConfig(query_parameters=update_params)
            self.client.query(update_query, update_config).result()
            
            # Record approval/rejection
            approval_query = f"""
                INSERT INTO `{self.project_id}.{self.dataset_id}.request_approvals`
                (approval_id, request_id, approver_level, approver_email, approver_name,
                 action, approved_discount_amount, comments, approved_at)
                VALUES (@approval_id, @request_id, @approver_level, @approver_email, @approver_name,
                        @action, @approved_discount_amount, @comments, @approved_at)
            """
            approval_params = [
                bigquery.ScalarQueryParameter('approval_id', 'STRING', approval_id),
                bigquery.ScalarQueryParameter('request_id', 'STRING', request_id),
                bigquery.ScalarQueryParameter('approver_level', 'STRING', approver_level),
                bigquery.ScalarQueryParameter('approver_email', 'STRING', approver_email),
                bigquery.ScalarQueryParameter('approver_name', 'STRING', approver_name),
                bigquery.ScalarQueryParameter('action', 'STRING', action),
                bigquery.ScalarQueryParameter('approved_discount_amount', 'FLOAT', approved_amount),
                bigquery.ScalarQueryParameter('comments', 'STRING', comments),
                bigquery.ScalarQueryParameter('approved_at', 'STRING', now)
            ]
            approval_config = bigquery.QueryJobConfig(query_parameters=approval_params)
            self.client.query(approval_query, approval_config).result()
            
            return True
            
        except Exception as e:
            logger.error(f"Error approving/rejecting request: {e}")
            return False
    
    def get_dashboard_stats(self):
        """Get dashboard statistics from the new structure."""
        if not self.client:
            return 0, 0, 0, 0, []
        
        try:
            # Get stats
            stats_query = f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status LIKE 'PENDING%' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected
                FROM `{self.project_id}.{self.dataset_id}.discount_requests_new`
            """
            stats_result = list(self.client.query(stats_query).result())[0]
            total = stats_result['total'] or 0
            pending = stats_result['pending'] or 0
            approved = stats_result['approved'] or 0
            rejected = stats_result['rejected'] or 0
            
            # Get recent requests
            recent_query = f"""
                SELECT 
                    s.enquiry_no,
                    s.student_name,
                    c.branch_name,
                    dr.status,
                    ps.mrp_at_request as mrp,
                    COALESCE(
                        (SELECT approved_discount_amount FROM `{self.project_id}.{self.dataset_id}.request_approvals` 
                         WHERE request_id = dr.request_id AND action = 'APPROVED' 
                         ORDER BY approved_at DESC LIMIT 1),
                        ps.mrp_at_request
                    ) as discounted_fees,
                    dr.requested_discount_amount as net_discount
                FROM `{self.project_id}.{self.dataset_id}.discount_requests_new` dr
                JOIN `{self.project_id}.{self.dataset_id}.students` s ON dr.student_id = s.student_id
                JOIN `{self.project_id}.{self.dataset_id}.courses` c ON dr.course_id = c.course_id
                JOIN `{self.project_id}.{self.dataset_id}.pricing_snapshots` ps ON dr.request_id = ps.request_id
                ORDER BY dr.created_at DESC
                LIMIT 5
            """
            recent = list(self.client.query(recent_query).result())
            return total, pending, approved, rejected, recent
        except Exception as e:
            logger.error(f"Error fetching dashboard stats: {e}")
            return 0, 0, 0, 0, []