# Discount Requests Table Restructuring Proposal

## Current Issues

### 1. Data Redundancy
- MRP and installment are duplicated between `discount_requests` and `branch_cards_fees` tables
- Student information is mixed with course and pricing data in a single table
- No referential integrity between tables

### 2. Data Consistency Problems
- If pricing changes in `branch_cards_fees`, existing requests have stale data
- No audit trail for pricing changes over time
- Potential inconsistencies when branch/card combinations change

### 3. Scalability Issues
- Single large table mixing different data domains
- Difficult to extend with new pricing structures or course types
- No proper indexing strategy for performance optimization

## Proposed Restructured Schema

### 1. Core Entity Tables

#### `students` (New)
```sql
CREATE TABLE students (
    student_id UUID PRIMARY KEY DEFAULT GENERATE_UUID(),
    enquiry_no VARCHAR(20) UNIQUE NOT NULL,
    student_name VARCHAR(255) NOT NULL,
    mobile_no VARCHAR(15) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

#### `courses` (Enhanced from branch_cards_fees)
```sql
CREATE TABLE courses (
    course_id UUID PRIMARY KEY DEFAULT GENERATE_UUID(),
    branch_name VARCHAR(100) NOT NULL,
    card_name VARCHAR(255) NOT NULL,
    mrp DECIMAL(10,2) NOT NULL,
    installment DECIMAL(10,2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    UNIQUE(branch_name, card_name)
);
```

#### `pricing_history` (New - for audit trail)
```sql
CREATE TABLE pricing_history (
    history_id UUID PRIMARY KEY DEFAULT GENERATE_UUID(),
    course_id UUID NOT NULL,
    mrp DECIMAL(10,2) NOT NULL,
    installment DECIMAL(10,2) NOT NULL,
    effective_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP,
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);
```

### 2. Request and Workflow Tables

#### `discount_requests` (Restructured)
```sql
CREATE TABLE discount_requests (
    request_id UUID PRIMARY KEY DEFAULT GENERATE_UUID(),
    student_id UUID NOT NULL,
    course_id UUID NOT NULL,
    requested_discount_amount DECIMAL(10,2) NOT NULL,
    discount_reason VARCHAR(100) NOT NULL,
    remarks TEXT,
    requester_email VARCHAR(255) NOT NULL,
    requester_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING_L1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    INDEX idx_requester (requester_email)
);
```

#### `request_approvals` (New - for workflow tracking)
```sql
CREATE TABLE request_approvals (
    approval_id UUID PRIMARY KEY DEFAULT GENERATE_UUID(),
    request_id UUID NOT NULL,
    approver_level VARCHAR(10) NOT NULL, -- L1, L2
    approver_email VARCHAR(255) NOT NULL,
    approver_name VARCHAR(255) NOT NULL,
    action VARCHAR(20) NOT NULL, -- APPROVED, REJECTED
    approved_discount_amount DECIMAL(10,2),
    comments TEXT,
    approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (request_id) REFERENCES discount_requests(request_id),
    INDEX idx_request_level (request_id, approver_level)
);
```

#### `pricing_snapshots` (New - for historical accuracy)
```sql
CREATE TABLE pricing_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT GENERATE_UUID(),
    request_id UUID NOT NULL,
    course_id UUID NOT NULL,
    mrp_at_request DECIMAL(10,2) NOT NULL,
    installment_at_request DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (request_id) REFERENCES discount_requests(request_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);
```

## Migration Strategy

### Phase 1: Create New Tables
1. Create new normalized tables alongside existing ones
2. Migrate data from existing tables to new structure
3. Create views to maintain backward compatibility

### Phase 2: Update Application Code
1. Update data access layer to use new tables
2. Modify form handling to work with normalized structure
3. Update queries and reports

### Phase 3: Final Cutover
1. Test thoroughly with both old and new structures
2. Switch application to use new tables exclusively
3. Drop old tables after validation period

## Benefits of New Structure

### 1. Data Integrity
- Proper foreign key relationships
- No data duplication
- Consistent referential integrity

### 2. Historical Accuracy
- Pricing snapshots preserve exact pricing at request time
- Complete audit trail of all changes
- Pricing history tracking

### 3. Scalability
- Easier to add new course types and pricing structures
- Better performance with proper indexing
- Separation of concerns between entities

### 4. Maintainability
- Clean separation of student, course, and workflow data
- Easier to extend and modify individual components
- Better support for future requirements

## Implementation Considerations

### 1. Backward Compatibility
- Create views to maintain existing API compatibility
- Gradual migration approach to minimize disruption
- Comprehensive testing of existing functionality

### 2. Performance
- Proper indexing strategy for common queries
- Consider denormalization for frequently accessed data
- Query optimization for reporting needs

### 3. Data Migration
- Careful handling of existing data relationships
- Validation of migrated data integrity
- Rollback strategy in case of issues

## Next Steps

1. Review and approve proposed schema
2. Create migration scripts and test with sample data
3. Update application code incrementally
4. Perform thorough testing
5. Plan production migration timeline