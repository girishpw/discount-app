#!/usr/bin/env python3
"""
Test script to verify the discount app functionality
"""
import requests
import json
import time

BASE_URL = "https://discount-app-644139762582.asia-south2.run.app"

def test_health_check():
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/_health")
        print(f"Health check: {response.status_code}")
        if response.status_code == 200:
            print(f"Health data: {response.json()}")
            return True
    except Exception as e:
        print(f"Health check failed: {e}")
    return False

def test_home_page():
    """Test the home page loads"""
    try:
        response = requests.get(BASE_URL)
        print(f"Home page: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Home page failed: {e}")
    return False

def test_login_page():
    """Test the login page loads"""
    try:
        response = requests.get(f"{BASE_URL}/login")
        print(f"Login page: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Login page failed: {e}")
    return False

def test_request_discount_page():
    """Test the request discount page loads"""
    try:
        response = requests.get(f"{BASE_URL}/request_discount")
        print(f"Request discount page: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Request discount page failed: {e}")
    return False

def main():
    print("Testing Discount Management App")
    print("=" * 40)
    
    tests = [
        ("Health Check", test_health_check),
        ("Home Page", test_home_page),
        ("Login Page", test_login_page),
        ("Request Discount Page", test_request_discount_page),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\nTesting {test_name}...")
        if test_func():
            print(f"✓ {test_name} PASSED")
            passed += 1
        else:
            print(f"✗ {test_name} FAILED")
    
    print("\n" + "=" * 40)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! App is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs above.")

if __name__ == "__main__":
    main()
