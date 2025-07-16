#!/usr/bin/env python3
"""Test production endpoints.

This script tests various endpoints on the production server to ensure they
are working correctly.
"""

import requests
import sys
from urllib.parse import urljoin

# Production URL
BASE_URL = "https://kalanjiyam.org"

# Test paths
TEST_PATHS = [
    "/",
    "/about/",
    "/about/mission",
    "/about/values",
    "/about/people/",
    "/texts/",
    "/tools/dictionaries/",
    "/proofing/",
    "/blog/",
    "/site/support",
    "/site/donate",
    "/auth/sign-in",
    "/auth/register",
]

def test_endpoint(path):
    """Test a single endpoint."""
    url = urljoin(BASE_URL, path)
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"✅ {url} - OK")
            return True
        else:
            print(f"❌ {url} - Status {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ {url} - Error: {e}")
        return False

def main():
    """Test all endpoints."""
    print(f"Testing Kalanjiyam production server: {BASE_URL}")
    print("=" * 60)
    
    success_count = 0
    total_count = len(TEST_PATHS)
    
    for path in TEST_PATHS:
        if test_endpoint(path):
            success_count += 1
    
    print("=" * 60)
    print(f"Results: {success_count}/{total_count} endpoints working")
    
    if success_count == total_count:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
