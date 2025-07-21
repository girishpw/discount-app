# Implementation Guide for Database Restructuring

## Overview

This guide provides step-by-step instructions for implementing the restructured database schema for the discount management system.

## Migration Process

### Prerequisites

1. **Backup Current Data**
   ```bash
   # Export current tables to Cloud Storage or local backup
   bq extract --format=AVRO gewportal2025:discount_management.discount_requests gs://backup-bucket/discount_requests_backup.avro
   bq extract --format=AVRO gewportal2025:discount_management.branch_cards_fees gs://backup-bucket/branch_cards_fees_backup.avro
   ```

2. **Test Environment Setup**
   - Create a test dataset to validate the migration
   - Copy current data to test environment
   - Test migration scripts thoroughly

### Phase 1: Schema Creation

1. **Run Migration Scripts**
   ```bash
   cd /home/runner/work/discount-app/discount-app
   python migrate_database.py migrate
   ```

2. **Verify Table Creation**
   ```bash
   python migrate_database.py verify
   ```

### Phase 2: Data Migration

The migration script automatically:
- Migrates data from `branch_cards_fees` to `courses` table
- Extracts student information into separate `students` table
- Restructures discount requests into normalized format
- Creates pricing snapshots for historical accuracy
- Migrates approval workflow data

### Phase 3: Application Code Updates

#### Option A: Gradual Migration (Recommended)

1. **Update Data Access Layer**
   ```python
   from enhanced_data_access import DiscountDataAccess
   
   # Initialize enhanced data access
   data_access = DiscountDataAccess(client, project_id, dataset_id)
   ```

2. **Update Request Creation**
   ```python
   # Old way
   def create_request_old():
       # Direct insert into discount_requests table
       pass
   
   # New way  
   def create_request_new():
       # 1. Create/get student
       student_id = data_access.create_or_get_student(enquiry_no, student_name, mobile_no)
       
       # 2. Get course details
       course_details = data_access.get_course_details(branch_name, card_name)
       
       # 3. Create request with pricing snapshot
       request_id = data_access.create_discount_request(
           student_id, course_details['course_id'], course_details,
           discount_amount, reason, remarks, requester_email, requester_name
       )
   ```

#### Option B: Using Compatibility Views

Keep existing code working by using the legacy view:

```python
# Replace table references
old_query = f"FROM `{project_id}.{dataset_id}.discount_requests`"
new_query = f"FROM `{project_id}.{dataset_id}.discount_requests_legacy_view`"
```

### Phase 4: Testing and Validation

1. **Functional Testing**
   - Test all existing features with new structure
   - Verify data consistency between old and new views
   - Test approval workflows

2. **Performance Testing**
   - Compare query performance
   - Monitor dashboard loading times
   - Test with large datasets

3. **Data Integrity Validation**
   ```sql
   -- Verify record counts match
   SELECT 
     (SELECT COUNT(*) FROM discount_requests) as old_count,
     (SELECT COUNT(*) FROM discount_requests_legacy_view) as new_count;
   
   -- Verify key data matches
   SELECT 
     old_dr.enquiry_no,
     old_dr.discount_amount,
     new_dr.net_discount
   FROM discount_requests old_dr
   LEFT JOIN discount_requests_legacy_view new_dr ON old_dr.enquiry_no = new_dr.enquiry_no
   WHERE ABS(old_dr.discount_amount - new_dr.net_discount) > 0.01;
   ```

## Key Benefits Realized

### 1. Improved Data Integrity
- **Foreign Key Relationships**: Proper relationships between students, courses, and requests
- **No Data Duplication**: MRP and installment stored once in courses table
- **Referential Integrity**: Cannot create requests for non-existent courses

### 2. Historical Accuracy
- **Pricing Snapshots**: Exact pricing preserved at request time
- **Audit Trail**: Complete history of all changes
- **Time-based Queries**: Can analyze pricing trends over time

### 3. Enhanced Scalability
- **Normalized Structure**: Each entity in its proper table
- **Better Performance**: Optimized queries with proper indexing
- **Easier Extensions**: Add new fields without affecting other entities

### 4. Improved Analytics
```sql
-- Example: Discount approval rates by branch
SELECT 
  branch_name,
  COUNT(*) as total_requests,
  COUNT(CASE WHEN status = 'APPROVED' THEN 1 END) as approved,
  ROUND(COUNT(CASE WHEN status = 'APPROVED' THEN 1 END) * 100.0 / COUNT(*), 2) as approval_rate
FROM discount_analytics
GROUP BY branch_name
ORDER BY approval_rate DESC;
```

## Rollback Strategy

If issues arise, the migration can be rolled back:

```bash
python migrate_database.py rollback
```

This preserves original data while removing new tables and views.

## Monitoring and Maintenance

### 1. Data Consistency Checks
Run periodic checks to ensure data consistency:

```python
# Weekly data consistency check
def check_data_consistency():
    # Compare record counts
    # Verify referential integrity
    # Check for orphaned records
    pass
```

### 2. Performance Monitoring
```python
# Query performance monitoring
def monitor_query_performance():
    # Track slow queries
    # Monitor table scans
    # Analyze query patterns
    pass
```

### 3. Regular Maintenance
- **Update Statistics**: Ensure query optimizer has current statistics
- **Monitor Growth**: Track table sizes and growth patterns
- **Archive Old Data**: Implement data archiving strategy

## Migration Timeline

| Phase | Duration | Activities |
|-------|----------|------------|
| **Preparation** | 1 week | Backup data, test migrations, prepare rollback plan |
| **Migration** | 2 days | Run migrations, verify data integrity |
| **Testing** | 1 week | Functional testing, performance validation |
| **Deployment** | 1 day | Update application code, monitor systems |
| **Monitoring** | 2 weeks | Monitor performance, fix any issues |

## Risk Mitigation

1. **Data Loss Prevention**
   - Complete backups before migration
   - Preserve original tables during transition
   - Test rollback procedures

2. **Performance Issues**
   - Load test new structure
   - Monitor query performance
   - Have performance tuning plan ready

3. **Application Downtime**
   - Use compatibility views for zero-downtime migration
   - Implement feature flags for new vs old code paths
   - Plan maintenance windows for critical updates

## Success Criteria

- ✅ All existing functionality works unchanged
- ✅ Data integrity maintained (zero data loss)
- ✅ Performance equal or better than original
- ✅ New features enabled by normalized structure
- ✅ Complete audit trail available
- ✅ Easy rollback capability maintained

## Post-Migration Opportunities

With the new normalized structure, consider implementing:

1. **Advanced Analytics Dashboard**
2. **Automated Pricing Updates**
3. **Enhanced Reporting Capabilities**
4. **Integration with External Systems**
5. **Advanced Approval Workflows**

## Support and Troubleshooting

For issues during migration:

1. Check migration logs for specific errors
2. Verify BigQuery permissions and quotas
3. Validate data consistency using provided scripts
4. Use rollback procedure if critical issues arise
5. Contact development team for assistance

The restructured database provides a solid foundation for future enhancements while maintaining backward compatibility and data integrity.