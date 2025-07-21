-- Migration 001: Create new normalized table structure
-- This migration creates the new tables alongside existing ones for safe migration

-- Step 1: Create students table
CREATE TABLE IF NOT EXISTS `gewportal2025.discount_management.students` (
    student_id STRING NOT NULL,
    enquiry_no STRING NOT NULL,
    student_name STRING NOT NULL,
    mobile_no STRING NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Create unique constraint on enquiry_no
-- Note: BigQuery doesn't support traditional UNIQUE constraints, so we'll handle this in application logic

-- Step 2: Create courses table (enhanced from branch_cards_fees)
CREATE TABLE IF NOT EXISTS `gewportal2025.discount_management.courses` (
    course_id STRING NOT NULL,
    branch_name STRING NOT NULL,
    card_name STRING NOT NULL,
    mrp NUMERIC NOT NULL,
    installment NUMERIC NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Step 3: Create pricing_history table for audit trail
CREATE TABLE IF NOT EXISTS `gewportal2025.discount_management.pricing_history` (
    history_id STRING NOT NULL,
    course_id STRING NOT NULL,
    mrp NUMERIC NOT NULL,
    installment NUMERIC NOT NULL,
    effective_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP,
    created_by STRING,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Step 4: Create new discount_requests table (restructured)
CREATE TABLE IF NOT EXISTS `gewportal2025.discount_management.discount_requests_new` (
    request_id STRING NOT NULL,
    student_id STRING NOT NULL,
    course_id STRING NOT NULL,
    requested_discount_amount NUMERIC NOT NULL,
    discount_reason STRING NOT NULL,
    remarks STRING,
    requester_email STRING NOT NULL,
    requester_name STRING NOT NULL,
    status STRING NOT NULL DEFAULT 'PENDING_L1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Step 5: Create request_approvals table for workflow tracking
CREATE TABLE IF NOT EXISTS `gewportal2025.discount_management.request_approvals` (
    approval_id STRING NOT NULL,
    request_id STRING NOT NULL,
    approver_level STRING NOT NULL, -- L1, L2
    approver_email STRING NOT NULL,
    approver_name STRING NOT NULL,
    action STRING NOT NULL, -- APPROVED, REJECTED
    approved_discount_amount NUMERIC,
    comments STRING,
    approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Step 6: Create pricing_snapshots table for historical accuracy
CREATE TABLE IF NOT EXISTS `gewportal2025.discount_management.pricing_snapshots` (
    snapshot_id STRING NOT NULL,
    request_id STRING NOT NULL,
    course_id STRING NOT NULL,
    mrp_at_request NUMERIC NOT NULL,
    installment_at_request NUMERIC NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);