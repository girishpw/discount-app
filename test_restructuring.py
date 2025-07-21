#!/usr/bin/env python3
"""
Comprehensive testing framework for database restructuring.

This script provides automated tests to validate the migration and ensure
data integrity between old and new database structures.
"""

import os
import sys
import logging
import unittest
from pathlib import Path
from datetime import datetime, timezone

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_data_access import DiscountDataAccess
from migrate_database import get_bigquery_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = 'gewportal2025'
DATASET_ID = 'discount_management'

class DatabaseRestructuringTests(unittest.TestCase):
    """Test suite for database restructuring validation."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.client = get_bigquery_client()
        if not cls.client:
            raise unittest.SkipTest("BigQuery client not available")
        
        cls.data_access = DiscountDataAccess(cls.client, PROJECT_ID, DATASET_ID)
    
    def test_table_existence(self):
        """Test that all new tables exist."""
        required_tables = [
            'students',
            'courses', 
            'pricing_history',
            'discount_requests_new',
            'request_approvals',
            'pricing_snapshots'
        ]
        
        for table_name in required_tables:
            with self.subTest(table=table_name):
                query = f"""
                    SELECT COUNT(*) as count
                    FROM `{PROJECT_ID}.{DATASET_ID}.INFORMATION_SCHEMA.TABLES`
                    WHERE table_name = '{table_name}'
                """
                result = list(self.client.query(query).result())[0]
                self.assertEqual(result.count, 1, f"Table {table_name} does not exist")
    
    def test_view_existence(self):
        """Test that compatibility views exist."""
        required_views = [
            'discount_requests_legacy_view',
            'branch_cards_fees_view',
            'active_discount_requests',
            'discount_analytics'
        ]
        
        for view_name in required_views:
            with self.subTest(view=view_name):
                query = f"""
                    SELECT COUNT(*) as count
                    FROM `{PROJECT_ID}.{DATASET_ID}.INFORMATION_SCHEMA.VIEWS`
                    WHERE table_name = '{view_name}'
                """
                result = list(self.client.query(query).result())[0]
                self.assertEqual(result.count, 1, f"View {view_name} does not exist")
    
    def test_data_migration_integrity(self):
        """Test that data migration preserved all records."""
        # Check if original tables exist
        original_tables = ['discount_requests', 'branch_cards_fees']
        tables_exist = []
        
        for table_name in original_tables:
            query = f"""
                SELECT COUNT(*) as count
                FROM `{PROJECT_ID}.{DATASET_ID}.INFORMATION_SCHEMA.TABLES`
                WHERE table_name = '{table_name}'
            """
            result = list(self.client.query(query).result())[0]
            tables_exist.append(result.count > 0)
        
        if not all(tables_exist):
            self.skipTest("Original tables not available for comparison")
        
        # Compare record counts
        original_count_query = f"""
            SELECT COUNT(*) as count FROM `{PROJECT_ID}.{DATASET_ID}.discount_requests`
        """
        migrated_count_query = f"""
            SELECT COUNT(*) as count FROM `{PROJECT_ID}.{DATASET_ID}.discount_requests_legacy_view`
        """
        
        original_count = list(self.client.query(original_count_query).result())[0].count
        migrated_count = list(self.client.query(migrated_count_query).result())[0].count
        
        self.assertEqual(original_count, migrated_count, 
                        f"Record count mismatch: original={original_count}, migrated={migrated_count}")
    
    def test_branches_functionality(self):
        """Test branches retrieval functionality."""
        branches = self.data_access.get_branches()
        self.assertIsInstance(branches, list)
        self.assertGreater(len(branches), 0, "No branches found")
        
        # Verify all branches are strings
        for branch in branches:
            self.assertIsInstance(branch, str)
            self.assertGreater(len(branch.strip()), 0, "Empty branch name found")
    
    def test_cards_functionality(self):
        """Test cards retrieval functionality."""
        branches = self.data_access.get_branches()
        if not branches:
            self.skipTest("No branches available for testing")
        
        test_branch = branches[0]
        cards = self.data_access.get_cards_for_branch(test_branch)
        
        self.assertIsInstance(cards, list)
        # Allow empty cards list for some branches
        
        if cards:
            for card in cards:
                self.assertIsInstance(card, str)
                self.assertGreater(len(card.strip()), 0, "Empty card name found")
    
    def test_course_details_functionality(self):
        """Test course details retrieval."""
        branches = self.data_access.get_branches()
        if not branches:
            self.skipTest("No branches available for testing")
        
        test_branch = branches[0]
        cards = self.data_access.get_cards_for_branch(test_branch)
        if not cards:
            self.skipTest(f"No cards available for branch {test_branch}")
        
        test_card = cards[0]
        course_details = self.data_access.get_course_details(test_branch, test_card)
        
        self.assertIsNotNone(course_details, "Course details should not be None")
        self.assertIn('course_id', course_details)
        self.assertIn('mrp', course_details)
        self.assertIn('installment', course_details)
        
        # Validate data types and values
        self.assertIsInstance(course_details['mrp'], float)
        self.assertIsInstance(course_details['installment'], float)
        self.assertGreater(course_details['mrp'], 0)
        self.assertGreater(course_details['installment'], 0)
    
    def test_student_creation(self):
        """Test student creation and retrieval."""
        test_enquiry = f"EN{datetime.now().strftime('%Y%m%d%H%M%S')}"  # Unique enquiry number
        test_name = "Test Student"
        test_mobile = "9876543210"
        
        # Create student
        student_id = self.data_access.create_or_get_student(test_enquiry, test_name, test_mobile)
        self.assertIsNotNone(student_id, "Student creation should return student_id")
        
        # Try to create same student again (should return existing ID)
        student_id2 = self.data_access.create_or_get_student(test_enquiry, test_name, test_mobile)
        self.assertEqual(student_id, student_id2, "Should return existing student ID for duplicate enquiry")
    
    def test_duplicate_request_detection(self):
        """Test duplicate request detection."""
        test_enquiry = f"EN{datetime.now().strftime('%Y%m%d%H%M%S')}"
        test_email = "test@pw.live"
        
        # Should not find duplicate initially
        has_duplicate = self.data_access.check_duplicate_request(test_enquiry, test_email)
        self.assertFalse(has_duplicate, "Should not find duplicate for new enquiry")
    
    def test_dashboard_stats(self):
        """Test dashboard statistics functionality."""
        total, pending, approved, rejected, recent = self.data_access.get_dashboard_stats()
        
        # Validate return types
        self.assertIsInstance(total, int)
        self.assertIsInstance(pending, int)
        self.assertIsInstance(approved, int)
        self.assertIsInstance(rejected, int)
        self.assertIsInstance(recent, list)
        
        # Validate logical constraints
        self.assertGreaterEqual(total, 0)
        self.assertGreaterEqual(pending, 0)
        self.assertGreaterEqual(approved, 0)
        self.assertGreaterEqual(rejected, 0)
        self.assertEqual(total, pending + approved + rejected)
        self.assertLessEqual(len(recent), 5)  # Should return max 5 recent items
    
    def test_data_consistency_between_structures(self):
        """Test data consistency between old and new structures."""
        # Skip if original tables don't exist
        try:
            original_query = f"""
                SELECT enquiry_no, student_name, branch_name, discount_amount
                FROM `{PROJECT_ID}.{DATASET_ID}.discount_requests`
                LIMIT 10
            """
            original_data = list(self.client.query(original_query).result())
        except Exception:
            self.skipTest("Original table not available for consistency check")
        
        if not original_data:
            self.skipTest("No data in original table for consistency check")
        
        # Compare with legacy view
        legacy_query = f"""
            SELECT enquiry_no, student_name, branch_name, net_discount as discount_amount
            FROM `{PROJECT_ID}.{DATASET_ID}.discount_requests_legacy_view`
            WHERE enquiry_no IN ({','.join([f"'{row.enquiry_no}'" for row in original_data])})
        """
        legacy_data = list(self.client.query(legacy_query).result())
        
        # Create dictionaries for comparison
        original_dict = {row.enquiry_no: row for row in original_data}
        legacy_dict = {row.enquiry_no: row for row in legacy_data}
        
        for enquiry_no in original_dict:
            with self.subTest(enquiry_no=enquiry_no):
                self.assertIn(enquiry_no, legacy_dict, f"Enquiry {enquiry_no} missing in legacy view")
                
                original_row = original_dict[enquiry_no]
                legacy_row = legacy_dict[enquiry_no]
                
                self.assertEqual(original_row.student_name, legacy_row.student_name)
                self.assertEqual(original_row.branch_name, legacy_row.branch_name)
                # Allow small differences in floating point numbers
                self.assertAlmostEqual(
                    float(original_row.discount_amount), 
                    float(legacy_row.discount_amount), 
                    places=2
                )
    
    def test_referential_integrity(self):
        """Test referential integrity in new structure."""
        # Test that all requests have valid student and course references
        integrity_query = f"""
            SELECT 
                COUNT(*) as total_requests,
                COUNT(s.student_id) as valid_students,
                COUNT(c.course_id) as valid_courses,
                COUNT(ps.snapshot_id) as valid_snapshots
            FROM `{PROJECT_ID}.{DATASET_ID}.discount_requests_new` dr
            LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.students` s ON dr.student_id = s.student_id
            LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.courses` c ON dr.course_id = c.course_id
            LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.pricing_snapshots` ps ON dr.request_id = ps.request_id
        """
        result = list(self.client.query(integrity_query).result())[0]
        
        self.assertEqual(result.total_requests, result.valid_students, 
                        "All requests should have valid student references")
        self.assertEqual(result.total_requests, result.valid_courses, 
                        "All requests should have valid course references")
        self.assertEqual(result.total_requests, result.valid_snapshots, 
                        "All requests should have pricing snapshots")

class PerformanceTests(unittest.TestCase):
    """Performance comparison tests."""
    
    @classmethod
    def setUpClass(cls):
        cls.client = get_bigquery_client()
        if not cls.client:
            raise unittest.SkipTest("BigQuery client not available")
    
    def test_query_performance_comparison(self):
        """Compare query performance between old and new structures."""
        # Skip if original table doesn't exist
        try:
            # Test query on original structure
            start_time = datetime.now()
            original_query = f"""
                SELECT branch_name, COUNT(*) as count
                FROM `{PROJECT_ID}.{DATASET_ID}.discount_requests`
                GROUP BY branch_name
            """
            original_result = list(self.client.query(original_query).result())
            original_time = (datetime.now() - start_time).total_seconds()
            
        except Exception:
            self.skipTest("Original table not available for performance comparison")
        
        # Test query on new structure
        start_time = datetime.now()
        new_query = f"""
            SELECT branch_name, COUNT(*) as count
            FROM `{PROJECT_ID}.{DATASET_ID}.discount_requests_legacy_view`
            GROUP BY branch_name
        """
        new_result = list(self.client.query(new_query).result())
        new_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Original query time: {original_time:.3f}s, New query time: {new_time:.3f}s")
        
        # Verify results are equivalent
        original_dict = {row.branch_name: row.count for row in original_result}
        new_dict = {row.branch_name: row.count for row in new_result}
        
        self.assertEqual(original_dict, new_dict, "Query results should be identical")
        
        # Performance should be reasonable (allow some degradation for complex views)
        self.assertLess(new_time, original_time * 3, 
                       "New structure should not be more than 3x slower")

def run_tests():
    """Run all tests and generate a report."""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    for test_class in [DatabaseRestructuringTests, PerformanceTests]:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(test_suite)
    
    # Generate summary report
    print("\n" + "="*70)
    print("TEST SUMMARY REPORT")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError: ')[-1].split('\\n')[0]}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('Exception: ')[-1].split('\\n')[0]}")
    
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100) if result.testsRun > 0 else 0
    print(f"\nSuccess rate: {success_rate:.1f}%")
    
    if success_rate >= 95:
        print("✅ Migration validation PASSED - Ready for production!")
    elif success_rate >= 80:
        print("⚠️  Migration validation PARTIAL - Review failures before proceeding")
    else:
        print("❌ Migration validation FAILED - Fix issues before proceeding")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Database restructuring test suite')
    parser.add_argument('--test-class', help='Run specific test class')
    parser.add_argument('--test-method', help='Run specific test method')
    
    args = parser.parse_args()
    
    if args.test_class or args.test_method:
        # Run specific tests
        unittest.main()
    else:
        # Run comprehensive test suite
        success = run_tests()
        sys.exit(0 if success else 1)