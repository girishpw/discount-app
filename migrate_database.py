#!/usr/bin/env python3
"""
Database migration utility for restructuring discount_requests table.

This script provides utilities to migrate from the current structure to the new normalized structure.
"""

import os
import sys
import logging
from pathlib import Path
from google.cloud import bigquery
from google.oauth2 import service_account

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_data_access import DiscountDataAccess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = 'gewportal2025'
DATASET_ID = 'discount_management'
MIGRATIONS_DIR = Path(__file__).parent / 'migrations'

def get_bigquery_client():
    """Get a BigQuery client."""
    try:
        # Try to use service account credentials first
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_path and os.path.exists(credentials_path):
            logger.info(f"Using service account credentials from: {credentials_path}")
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            client = bigquery.Client(project=PROJECT_ID, credentials=credentials)
        else:
            # Fall back to Application Default Credentials
            logger.info("Using Application Default Credentials")
            client = bigquery.Client(project=PROJECT_ID)
        
        # Test the connection
        client.query("SELECT 1 as test").result()
        logger.info(f"BigQuery client initialized successfully with project: {PROJECT_ID}")
        return client
    except Exception as e:
        logger.error(f"Error initializing BigQuery client: {e}")
        return None

def run_migration_file(client, migration_file):
    """Run a single migration file."""
    logger.info(f"Running migration: {migration_file.name}")
    
    try:
        with open(migration_file, 'r') as f:
            sql_content = f.read()
        
        # Split the SQL content by semicolons and execute each statement
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        for i, statement in enumerate(statements):
            if statement:
                logger.info(f"Executing statement {i+1}/{len(statements)}")
                client.query(statement).result()
                logger.info(f"Statement {i+1} completed successfully")
        
        logger.info(f"Migration {migration_file.name} completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error running migration {migration_file.name}: {e}")
        return False

def run_all_migrations():
    """Run all migration files in order."""
    client = get_bigquery_client()
    if not client:
        logger.error("Cannot initialize BigQuery client")
        return False
    
    # Get all migration files and sort them
    migration_files = sorted(MIGRATIONS_DIR.glob('*.sql'))
    
    if not migration_files:
        logger.warning("No migration files found")
        return True
    
    logger.info(f"Found {len(migration_files)} migration files")
    
    success_count = 0
    for migration_file in migration_files:
        if run_migration_file(client, migration_file):
            success_count += 1
        else:
            logger.error(f"Migration failed: {migration_file.name}")
            break
    
    logger.info(f"Completed {success_count}/{len(migration_files)} migrations successfully")
    return success_count == len(migration_files)

def verify_migration():
    """Verify that the migration completed successfully."""
    client = get_bigquery_client()
    if not client:
        logger.error("Cannot initialize BigQuery client")
        return False
    
    try:
        # Test the enhanced data access layer
        data_access = DiscountDataAccess(client, PROJECT_ID, DATASET_ID)
        
        # Test basic operations
        logger.info("Testing branches query...")
        branches = data_access.get_branches()
        logger.info(f"Found {len(branches)} branches: {branches[:5]}")
        
        if branches:
            logger.info("Testing cards query...")
            cards = data_access.get_cards_for_branch(branches[0])
            logger.info(f"Found {len(cards)} cards for {branches[0]}: {cards[:3]}")
        
        logger.info("Testing dashboard stats...")
        total, pending, approved, rejected, recent = data_access.get_dashboard_stats()
        logger.info(f"Dashboard stats - Total: {total}, Pending: {pending}, Approved: {approved}, Rejected: {rejected}")
        
        # Test compatibility view
        logger.info("Testing legacy view compatibility...")
        legacy_query = f"""
            SELECT COUNT(*) as count
            FROM `{PROJECT_ID}.{DATASET_ID}.discount_requests_legacy_view`
        """
        result = list(client.query(legacy_query).result())[0]
        logger.info(f"Legacy view has {result.count} records")
        
        logger.info("Migration verification completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Migration verification failed: {e}")
        return False

def rollback_migration():
    """Rollback migration by dropping new tables (keeping original data safe)."""
    client = get_bigquery_client()
    if not client:
        logger.error("Cannot initialize BigQuery client")
        return False
    
    try:
        tables_to_drop = [
            'students',
            'courses',  # This will need careful handling as it replaces branch_cards_fees
            'pricing_history',
            'discount_requests_new',
            'request_approvals',
            'pricing_snapshots'
        ]
        
        views_to_drop = [
            'discount_requests_legacy_view',
            'branch_cards_fees_view',
            'active_discount_requests',
            'discount_analytics'
        ]
        
        # Drop views first
        for view_name in views_to_drop:
            try:
                query = f"DROP VIEW IF EXISTS `{PROJECT_ID}.{DATASET_ID}.{view_name}`"
                client.query(query).result()
                logger.info(f"Dropped view: {view_name}")
            except Exception as e:
                logger.warning(f"Could not drop view {view_name}: {e}")
        
        # Drop tables
        for table_name in tables_to_drop:
            try:
                # Skip courses table as it might replace branch_cards_fees
                if table_name == 'courses':
                    logger.warning("Skipping courses table - manual review required")
                    continue
                    
                query = f"DROP TABLE IF EXISTS `{PROJECT_ID}.{DATASET_ID}.{table_name}`"
                client.query(query).result()
                logger.info(f"Dropped table: {table_name}")
            except Exception as e:
                logger.warning(f"Could not drop table {table_name}: {e}")
        
        logger.info("Rollback completed (courses table and original tables preserved)")
        return True
        
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return False

def generate_performance_report():
    """Generate a performance comparison report."""
    client = get_bigquery_client()
    if not client:
        return
    
    try:
        logger.info("Generating performance report...")
        
        # Test query performance on old vs new structure
        # This is a placeholder - in a real scenario, you'd run actual queries
        
        old_structure_query = f"""
            SELECT COUNT(*) as total_requests,
                   AVG(discount_amount) as avg_discount
            FROM `{PROJECT_ID}.{DATASET_ID}.discount_requests`
            WHERE status = 'APPROVED'
        """
        
        new_structure_query = f"""
            SELECT COUNT(*) as total_requests,
                   AVG(requested_discount_amount) as avg_discount
            FROM `{PROJECT_ID}.{DATASET_ID}.discount_requests_legacy_view`
            WHERE status = 'APPROVED'
        """
        
        logger.info("Performance report placeholder - implement actual performance tests")
        
    except Exception as e:
        logger.error(f"Performance report generation failed: {e}")

def main():
    """Main migration utility function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Database migration utility')
    parser.add_argument('action', choices=['migrate', 'verify', 'rollback', 'performance'],
                       help='Action to perform')
    parser.add_argument('--force', action='store_true',
                       help='Force action without confirmation')
    
    args = parser.parse_args()
    
    if args.action == 'migrate':
        if not args.force:
            response = input("This will create new tables and migrate data. Continue? (y/N): ")
            if response.lower() != 'y':
                logger.info("Migration cancelled")
                return
        
        logger.info("Starting database migration...")
        if run_all_migrations():
            logger.info("Migration completed successfully!")
        else:
            logger.error("Migration failed!")
            sys.exit(1)
    
    elif args.action == 'verify':
        logger.info("Verifying migration...")
        if verify_migration():
            logger.info("Verification completed successfully!")
        else:
            logger.error("Verification failed!")
            sys.exit(1)
    
    elif args.action == 'rollback':
        if not args.force:
            response = input("This will drop new tables. Continue? (y/N): ")
            if response.lower() != 'y':
                logger.info("Rollback cancelled")
                return
        
        logger.info("Rolling back migration...")
        if rollback_migration():
            logger.info("Rollback completed successfully!")
        else:
            logger.error("Rollback failed!")
            sys.exit(1)
    
    elif args.action == 'performance':
        generate_performance_report()

if __name__ == '__main__':
    main()