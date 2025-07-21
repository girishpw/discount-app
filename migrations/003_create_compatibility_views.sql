-- Migration 003: Create views for backward compatibility
-- These views maintain the existing API structure while using the new normalized tables

-- Create a view that mimics the original discount_requests table structure
CREATE OR REPLACE VIEW `gewportal2025.discount_management.discount_requests_legacy_view` AS
SELECT 
    s.enquiry_no,
    s.student_name,
    s.mobile_no,
    c.card_name,
    ps.mrp_at_request as mrp,
    ps.installment_at_request as installment,
    COALESCE(
        (SELECT approved_discount_amount FROM `gewportal2025.discount_management.request_approvals` 
         WHERE request_id = dr.request_id AND approver_level = 'L2' AND action = 'APPROVED' 
         ORDER BY approved_at DESC LIMIT 1),
        (SELECT approved_discount_amount FROM `gewportal2025.discount_management.request_approvals` 
         WHERE request_id = dr.request_id AND approver_level = 'L1' AND action = 'APPROVED' 
         ORDER BY approved_at DESC LIMIT 1),
        ps.mrp_at_request
    ) as discounted_fees,
    dr.requested_discount_amount as discount_amount,
    CASE 
        WHEN ps.installment_at_request > 0 THEN (dr.requested_discount_amount / ps.installment_at_request) * 100 
        ELSE 0 
    END as discount_percentage,
    dr.requested_discount_amount as net_discount,
    dr.discount_reason as reason,
    dr.remarks,
    dr.requester_email,
    dr.requester_name,
    c.branch_name,
    dr.status,
    dr.created_at,
    -- L1 Approval details
    l1.approver_email as l1_approver,
    l1.approved_at as l1_approved_at,
    l1.comments as l1_comments,
    -- L2 Approval details  
    l2.approver_email as l2_approver,
    l2.approved_at as l2_approved_at,
    l2.comments as l2_comments
FROM `gewportal2025.discount_management.discount_requests_new` dr
JOIN `gewportal2025.discount_management.students` s ON dr.student_id = s.student_id
JOIN `gewportal2025.discount_management.courses` c ON dr.course_id = c.course_id
JOIN `gewportal2025.discount_management.pricing_snapshots` ps ON dr.request_id = ps.request_id
LEFT JOIN `gewportal2025.discount_management.request_approvals` l1 
    ON dr.request_id = l1.request_id AND l1.approver_level = 'L1'
LEFT JOIN `gewportal2025.discount_management.request_approvals` l2 
    ON dr.request_id = l2.request_id AND l2.approver_level = 'L2';

-- Create a simplified view for the branch_cards_fees table (no changes needed but added for consistency)
CREATE OR REPLACE VIEW `gewportal2025.discount_management.branch_cards_fees_view` AS
SELECT 
    branch_name,
    card_name,
    mrp,
    installment
FROM `gewportal2025.discount_management.courses`
WHERE is_active = TRUE;

-- Create a view for current active requests with enhanced information
CREATE OR REPLACE VIEW `gewportal2025.discount_management.active_discount_requests` AS
SELECT 
    dr.request_id,
    s.enquiry_no,
    s.student_name,
    s.mobile_no,
    c.branch_name,
    c.card_name,
    ps.mrp_at_request,
    ps.installment_at_request,
    dr.requested_discount_amount,
    dr.discount_reason,
    dr.remarks,
    dr.requester_email,
    dr.requester_name,
    dr.status,
    dr.created_at,
    dr.updated_at,
    -- Current approval status
    CASE 
        WHEN dr.status = 'PENDING_L1' THEN 'Awaiting L1 Approval'
        WHEN dr.status = 'PENDING_L2' THEN 'Awaiting L2 Approval'
        WHEN dr.status = 'APPROVED' THEN 'Fully Approved'
        WHEN dr.status = 'REJECTED' THEN 'Rejected'
        ELSE dr.status
    END as status_description,
    -- Latest approved amount
    COALESCE(
        (SELECT approved_discount_amount FROM `gewportal2025.discount_management.request_approvals` 
         WHERE request_id = dr.request_id AND action = 'APPROVED' 
         ORDER BY approved_at DESC LIMIT 1),
        dr.requested_discount_amount
    ) as current_approved_amount
FROM `gewportal2025.discount_management.discount_requests_new` dr
JOIN `gewportal2025.discount_management.students` s ON dr.student_id = s.student_id
JOIN `gewportal2025.discount_management.courses` c ON dr.course_id = c.course_id
JOIN `gewportal2025.discount_management.pricing_snapshots` ps ON dr.request_id = ps.request_id
WHERE dr.status != 'CANCELLED';

-- Create a view for reporting and analytics
CREATE OR REPLACE VIEW `gewportal2025.discount_management.discount_analytics` AS
SELECT 
    c.branch_name,
    c.card_name,
    COUNT(*) as total_requests,
    COUNT(CASE WHEN dr.status = 'APPROVED' THEN 1 END) as approved_requests,
    COUNT(CASE WHEN dr.status = 'REJECTED' THEN 1 END) as rejected_requests,
    COUNT(CASE WHEN dr.status LIKE 'PENDING%' THEN 1 END) as pending_requests,
    AVG(dr.requested_discount_amount) as avg_requested_discount,
    AVG(CASE WHEN dr.status = 'APPROVED' THEN 
        COALESCE(
            (SELECT approved_discount_amount FROM `gewportal2025.discount_management.request_approvals` 
             WHERE request_id = dr.request_id AND action = 'APPROVED' 
             ORDER BY approved_at DESC LIMIT 1),
            dr.requested_discount_amount
        ) 
    END) as avg_approved_discount,
    SUM(CASE WHEN dr.status = 'APPROVED' THEN 
        COALESCE(
            (SELECT approved_discount_amount FROM `gewportal2025.discount_management.request_approvals` 
             WHERE request_id = dr.request_id AND action = 'APPROVED' 
             ORDER BY approved_at DESC LIMIT 1),
            dr.requested_discount_amount
        ) 
        ELSE 0 
    END) as total_discount_approved,
    MIN(dr.created_at) as first_request_date,
    MAX(dr.created_at) as latest_request_date
FROM `gewportal2025.discount_management.discount_requests_new` dr
JOIN `gewportal2025.discount_management.students` s ON dr.student_id = s.student_id
JOIN `gewportal2025.discount_management.courses` c ON dr.course_id = c.course_id
GROUP BY c.branch_name, c.card_name;