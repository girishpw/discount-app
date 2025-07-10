#!/usr/bin/env python3
"""
Database setup script for the Discount Management System
Creates required BigQuery tables with proper schema
"""

from google.cloud import bigquery
from google.oauth2 import service_account
import os

# Initialize BigQuery client
project_id = 'gewportal2025'
dataset_id = 'discount_management'

def get_bigquery_client():
    try:
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            client = bigquery.Client(project=project_id, credentials=credentials)
        else:
            client = bigquery.Client(project=project_id)
        return client
    except Exception as e:
        print(f"Error initializing BigQuery client: {e}")
        return None

def create_tables():
    client = get_bigquery_client()
    if not client:
        print("Failed to initialize BigQuery client")
        return False

    # Create dataset if it doesn't exist
    dataset_ref = client.dataset(dataset_id)
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset {dataset_id} already exists")
    except:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"  # or your preferred location
        client.create_dataset(dataset)
        print(f"Dataset {dataset_id} created")

    # 1. Create authorized_persons table
    authorized_persons_schema = [
        bigquery.SchemaField("email", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("branch_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("approver_level", "STRING", mode="REQUIRED"),  # L1, L2, or User
        bigquery.SchemaField("can_request_discount", "BOOLEAN", mode="REQUIRED"),
        bigquery.SchemaField("is_active", "BOOLEAN", mode="REQUIRED"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
    ]

    # 2. Create branch_crads_fees table (note: keeping original typo for compatibility)
    branch_cards_fees_schema = [
        bigquery.SchemaField("branch_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("card_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("mrp", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("is_active", "BOOLEAN", mode="REQUIRED"),
    ]

    # 3. Update discount_requests table with new fields
    discount_requests_schema = [
        bigquery.SchemaField("enquiry_no", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("student_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("mobile_no", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("card_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("mrp", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("discounted_fees", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("net_discount", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("reason", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("remarks", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("requester_email", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("requester_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("branch_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED"),  # PENDING_L1, PENDING_L2, APPROVED, REJECTED
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("l1_approver", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("l1_approved_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("l1_comments", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("l2_approver", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("l2_approved_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("l2_comments", "STRING", mode="NULLABLE"),
    ]

    tables_to_create = [
        ("authorized_persons", authorized_persons_schema),
        ("branch_crads_fees", branch_cards_fees_schema),
        ("discount_requests", discount_requests_schema),
    ]

    for table_name, schema in tables_to_create:
        table_ref = dataset_ref.table(table_name)
        try:
            client.get_table(table_ref)
            print(f"Table {table_name} already exists")
        except:
            table = bigquery.Table(table_ref, schema=schema)
            client.create_table(table)
            print(f"Table {table_name} created")

    print("Database setup completed successfully!")
    return True

def insert_sample_data():
    """Insert sample data for testing"""
    client = get_bigquery_client()
    if not client:
        return False

    # Sample authorized persons
    authorized_persons_data = [
        {
            "email": "girish.chandra@pw.live",
            "name": "Girish Chandra",
            "branch_name": "Delhi",
            "approver_level": "L1",
            "can_request_discount": True,
            "is_active": True,
        },
        {
            "email": "admin@pw.live",
            "name": "Admin User",
            "branch_name": "Mumbai",
            "approver_level": "L2",
            "can_request_discount": True,
            "is_active": True,
        },
        {
            "email": "manager@pw.live",
            "name": "Branch Manager",
            "branch_name": "Delhi",
            "approver_level": "L2",
            "can_request_discount": False,
            "is_active": True,
        },
    ]

    # Sample branch cards fees
    branch_cards_data = [
        {"branch_name": "Delhi", "card_name": "JEE Foundation", "mrp": 50000.0, "is_active": True},
        {"branch_name": "Delhi", "card_name": "NEET Foundation", "mrp": 45000.0, "is_active": True},
        {"branch_name": "Mumbai", "card_name": "JEE Foundation", "mrp": 52000.0, "is_active": True},
        {"branch_name": "Mumbai", "card_name": "NEET Foundation", "mrp": 47000.0, "is_active": True},
        {"branch_name": "Bangalore", "card_name": "JEE Foundation", "mrp": 48000.0, "is_active": True},
        {"branch_name": "Bangalore", "card_name": "NEET Foundation", "mrp": 43000.0, "is_active": True},
    ]

    try:
        # Insert authorized persons
        table_ref = client.dataset(dataset_id).table("authorized_persons")
        errors = client.insert_rows_json(table_ref, authorized_persons_data)
        if errors:
            print(f"Errors inserting authorized persons: {errors}")
        else:
            print("Sample authorized persons inserted")

        # Insert branch cards fees
        table_ref = client.dataset(dataset_id).table("branch_crads_fees")
        errors = client.insert_rows_json(table_ref, branch_cards_data)
        if errors:
            print(f"Errors inserting branch cards fees: {errors}")
        else:
            print("Sample branch cards fees inserted")

        return True
    except Exception as e:
        print(f"Error inserting sample data: {e}")
        return False

if __name__ == "__main__":
    print("Setting up Discount Management System database...")
    
    if create_tables():
        print("\nInserting sample data...")
        insert_sample_data()
        print("\nDatabase setup completed!")
    else:
        print("Failed to create tables")
