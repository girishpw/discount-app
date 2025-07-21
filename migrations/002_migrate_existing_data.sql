-- Migration 002: Migrate data from existing tables to new structure
-- This migration populates the new tables with data from existing tables

-- Generate UUIDs for courses based on branch_name and card_name combination
-- Step 1: Populate courses table from branch_cards_fees
INSERT INTO `gewportal2025.discount_management.courses` 
(course_id, branch_name, card_name, mrp, installment, is_active, created_at, updated_at)
SELECT 
    GENERATE_UUID() as course_id,
    branch_name,
    card_name,
    mrp,
    installment,
    TRUE as is_active,
    CURRENT_TIMESTAMP() as created_at,
    CURRENT_TIMESTAMP() as updated_at
FROM `gewportal2025.discount_management.branch_cards_fees`
WHERE TRUE
QUALIFY ROW_NUMBER() OVER (PARTITION BY branch_name, card_name ORDER BY branch_name) = 1;

-- Step 2: Create initial pricing history for all courses
INSERT INTO `gewportal2025.discount_management.pricing_history`
(history_id, course_id, mrp, installment, effective_date, end_date, created_by, created_at)
SELECT 
    GENERATE_UUID() as history_id,
    course_id,
    mrp,
    installment,
    created_at as effective_date,
    NULL as end_date,
    'system_migration' as created_by,
    CURRENT_TIMESTAMP() as created_at
FROM `gewportal2025.discount_management.courses`;

-- Step 3: Populate students table from discount_requests
INSERT INTO `gewportal2025.discount_management.students`
(student_id, enquiry_no, student_name, mobile_no, created_at, updated_at)
SELECT 
    GENERATE_UUID() as student_id,
    enquiry_no,
    student_name,
    mobile_no,
    created_at,
    created_at as updated_at
FROM `gewportal2025.discount_management.discount_requests`
WHERE TRUE
QUALIFY ROW_NUMBER() OVER (PARTITION BY enquiry_no ORDER BY created_at) = 1;

-- Step 4: Migrate discount_requests to new structure
INSERT INTO `gewportal2025.discount_management.discount_requests_new`
(request_id, student_id, course_id, requested_discount_amount, discount_reason, 
 remarks, requester_email, requester_name, status, created_at, updated_at)
SELECT 
    GENERATE_UUID() as request_id,
    s.student_id,
    c.course_id,
    dr.discount_amount as requested_discount_amount,
    dr.reason as discount_reason,
    dr.remarks,
    dr.requester_email,
    dr.requester_name,
    dr.status,
    dr.created_at,
    COALESCE(dr.l2_approved_at, dr.l1_approved_at, dr.created_at) as updated_at
FROM `gewportal2025.discount_management.discount_requests` dr
JOIN `gewportal2025.discount_management.students` s ON dr.enquiry_no = s.enquiry_no
JOIN `gewportal2025.discount_management.courses` c ON dr.branch_name = c.branch_name AND dr.card_name = c.card_name;

-- Step 5: Create pricing snapshots for all migrated requests
INSERT INTO `gewportal2025.discount_management.pricing_snapshots`
(snapshot_id, request_id, course_id, mrp_at_request, installment_at_request, created_at)
SELECT 
    GENERATE_UUID() as snapshot_id,
    drn.request_id,
    drn.course_id,
    dr.mrp as mrp_at_request,
    dr.installment as installment_at_request,
    dr.created_at
FROM `gewportal2025.discount_management.discount_requests_new` drn
JOIN `gewportal2025.discount_management.discount_requests` dr ON drn.created_at = dr.created_at AND drn.requester_email = dr.requester_email;

-- Step 6: Migrate approval history
-- Migrate L1 approvals
INSERT INTO `gewportal2025.discount_management.request_approvals`
(approval_id, request_id, approver_level, approver_email, approver_name, 
 action, approved_discount_amount, comments, approved_at)
SELECT 
    GENERATE_UUID() as approval_id,
    drn.request_id,
    'L1' as approver_level,
    dr.l1_approver as approver_email,
    'L1 Approver' as approver_name,  -- We don't have name in old structure
    CASE WHEN dr.status IN ('PENDING_L2', 'APPROVED') THEN 'APPROVED' ELSE 'REJECTED' END as action,
    dr.discounted_fees as approved_discount_amount,
    dr.l1_comments as comments,
    dr.l1_approved_at as approved_at
FROM `gewportal2025.discount_management.discount_requests` dr
JOIN `gewportal2025.discount_management.discount_requests_new` drn 
  ON dr.enquiry_no = (SELECT s.enquiry_no FROM `gewportal2025.discount_management.students` s WHERE s.student_id = drn.student_id)
WHERE dr.l1_approver IS NOT NULL;

-- Migrate L2 approvals
INSERT INTO `gewportal2025.discount_management.request_approvals`
(approval_id, request_id, approver_level, approver_email, approver_name, 
 action, approved_discount_amount, comments, approved_at)
SELECT 
    GENERATE_UUID() as approval_id,
    drn.request_id,
    'L2' as approver_level,
    dr.l2_approver as approver_email,
    'L2 Approver' as approver_name,  -- We don't have name in old structure
    CASE WHEN dr.status = 'APPROVED' THEN 'APPROVED' ELSE 'REJECTED' END as action,
    dr.discounted_fees as approved_discount_amount,
    dr.l2_comments as comments,
    dr.l2_approved_at as approved_at
FROM `gewportal2025.discount_management.discount_requests` dr
JOIN `gewportal2025.discount_management.discount_requests_new` drn 
  ON dr.enquiry_no = (SELECT s.enquiry_no FROM `gewportal2025.discount_management.students` s WHERE s.student_id = drn.student_id)
WHERE dr.l2_approver IS NOT NULL;