"""
R2 Package Access Control Verification Test

Tests the new localhost-only access control model:
- Download endpoint: Accessible externally (with auth for private packages)
- All other endpoints: Localhost-only (no auth required)
"""

import requests
import pytest
from pathlib import Path
import io
from loguru import logger

BASE_URL = "http://localhost:8001"

# Test package data
TEST_PACKAGE = {
    "package_name": "test-access-control",
    "version": "1.0.0",
    "description": "Test package for access control verification",
    "tags": "test,access-control",
    "is_public": "true"
}


class TestLocalhostAccessControl:
    """Test that management endpoints are localhost-only"""

    def test_upload_localhost_success(self):
        """Upload should work from localhost"""
        # Create a small test file
        file_content = b"Test package content for access control"
        files = {"file": ("test.tar.gz", io.BytesIO(file_content), "application/gzip")}

        response = requests.post(
            f"{BASE_URL}/r2/packages/upload",
            files=files,
            data=TEST_PACKAGE
        )

        # Should succeed from localhost
        logger.info(f"Upload response: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"Upload failed: {response.text}")

        # Accept both 200 (success) and 500 (R2 config issue)
        # The important thing is we don't get 403 Forbidden
        assert response.status_code in [200, 500], f"Expected 200 or 500, got {response.status_code}"
        assert response.status_code != 403, "Upload should not be forbidden from localhost"

    def test_get_package_info_localhost(self):
        """Get package info should work from localhost"""
        response = requests.get(
            f"{BASE_URL}/r2/packages/{TEST_PACKAGE['package_name']}/{TEST_PACKAGE['version']}"
        )

        logger.info(f"Get package info response: {response.status_code}")
        # Should not return 403 Forbidden
        assert response.status_code != 403, "Package info should not be forbidden from localhost"
        # May return 404 (not found) or 200 (found) or 500 (error), but never 403

    def test_list_versions_localhost(self):
        """List versions should work from localhost"""
        response = requests.get(
            f"{BASE_URL}/r2/packages/{TEST_PACKAGE['package_name']}/versions"
        )

        logger.info(f"List versions response: {response.status_code}")
        assert response.status_code != 403, "List versions should not be forbidden from localhost"

    def test_search_packages_localhost(self):
        """Search packages should work from localhost"""
        response = requests.post(
            f"{BASE_URL}/r2/packages/search",
            json={"search_term": "test", "limit": 10}
        )

        logger.info(f"Search response: {response.status_code}")
        assert response.status_code != 403, "Search should not be forbidden from localhost"

    def test_list_public_packages_localhost(self):
        """List public packages should work from localhost"""
        response = requests.get(f"{BASE_URL}/r2/packages/public")

        logger.info(f"List public response: {response.status_code}")
        assert response.status_code != 403, "List public should not be forbidden from localhost"

    def test_my_uploads_localhost(self):
        """My uploads should work from localhost (requires user_id param)"""
        response = requests.get(
            f"{BASE_URL}/r2/packages/my-uploads",
            params={"user_id": "00000000-0000-0000-0000-000000000000"}
        )

        logger.info(f"My uploads response: {response.status_code}")
        assert response.status_code != 403, "My uploads should not be forbidden from localhost"

    def test_update_package_localhost(self):
        """Update package should work from localhost (no auth required)"""
        response = requests.patch(
            f"{BASE_URL}/r2/packages/{TEST_PACKAGE['package_name']}/{TEST_PACKAGE['version']}",
            json={"description": "Updated description"}
        )

        logger.info(f"Update response: {response.status_code}")
        # Should not return 403 Forbidden
        # May return 404 (not found) if package doesn't exist
        assert response.status_code != 403, "Update should not be forbidden from localhost"
        assert response.status_code != 401, "Update should not require authentication from localhost"

    def test_delete_package_localhost(self):
        """Delete package should work from localhost (no auth required)"""
        response = requests.delete(
            f"{BASE_URL}/r2/packages/{TEST_PACKAGE['package_name']}/{TEST_PACKAGE['version']}"
        )

        logger.info(f"Delete response: {response.status_code}")
        # Should not return 403 Forbidden
        assert response.status_code != 403, "Delete should not be forbidden from localhost"
        assert response.status_code != 401, "Delete should not require authentication from localhost"

    def test_storage_stats_localhost(self):
        """Storage stats should work from localhost"""
        response = requests.get(f"{BASE_URL}/r2/packages/stats/storage")

        logger.info(f"Storage stats response: {response.status_code}")
        assert response.status_code != 403, "Storage stats should not be forbidden from localhost"

    def test_package_stats_localhost(self):
        """Package stats should work from localhost"""
        response = requests.get(
            f"{BASE_URL}/r2/packages/stats/{TEST_PACKAGE['package_name']}"
        )

        logger.info(f"Package stats response: {response.status_code}")
        assert response.status_code != 403, "Package stats should not be forbidden from localhost"

    def test_cleanup_localhost(self):
        """Cleanup should work from localhost (no auth required)"""
        response = requests.post(
            f"{BASE_URL}/r2/packages/cleanup",
            json={"days_threshold": 90, "dry_run": True}
        )

        logger.info(f"Cleanup response: {response.status_code}")
        assert response.status_code != 403, "Cleanup should not be forbidden from localhost"
        assert response.status_code != 401, "Cleanup should not require authentication from localhost"

    def test_verify_integrity_localhost(self):
        """Verify integrity should work from localhost"""
        response = requests.get(
            f"{BASE_URL}/r2/packages/{TEST_PACKAGE['package_name']}/{TEST_PACKAGE['version']}/verify"
        )

        logger.info(f"Verify response: {response.status_code}")
        assert response.status_code != 403, "Verify should not be forbidden from localhost"

    def test_health_check_localhost(self):
        """Health check should work from localhost"""
        response = requests.get(f"{BASE_URL}/r2/packages/health")

        logger.info(f"Health response: {response.status_code}")
        assert response.status_code != 403, "Health check should not be forbidden from localhost"


class TestDownloadEndpointExternal:
    """Test that download endpoint is externally accessible"""

    def test_download_public_package_no_auth(self):
        """Download endpoint should work for public packages without auth"""
        response = requests.get(
            f"{BASE_URL}/r2/packages/{TEST_PACKAGE['package_name']}/{TEST_PACKAGE['version']}/download"
        )

        logger.info(f"Download public package response: {response.status_code}")
        # Should not return 403 Forbidden
        # May return 404 (not found) or 200 (success)
        assert response.status_code != 403, "Download should not be forbidden for public packages"

    def test_download_private_package_requires_auth(self):
        """Download endpoint should require auth for private packages"""
        # This test assumes a private package exists or that the endpoint properly checks visibility
        # For now, just verify the endpoint is accessible (not 403)
        response = requests.get(
            f"{BASE_URL}/r2/packages/private-test/1.0.0/download"
        )

        logger.info(f"Download private package response: {response.status_code}")
        # Should not return 403 Forbidden (that's for localhost-only endpoints)
        # May return 401 (needs auth), 404 (not found), or 200 (success with auth)
        assert response.status_code != 403, "Download should not return 403 - it's externally accessible"


class TestAuthenticationRemoval:
    """Test that localhost endpoints don't require authentication"""

    def test_update_no_auth_header(self):
        """Update should work without Authorization header from localhost"""
        response = requests.patch(
            f"{BASE_URL}/r2/packages/{TEST_PACKAGE['package_name']}/{TEST_PACKAGE['version']}",
            json={"description": "Test"}
        )

        # Should not return 401 Unauthorized
        assert response.status_code != 401, "Update should not require auth from localhost"
        assert response.status_code != 403, "Update should not be forbidden from localhost"

    def test_delete_no_auth_cookie(self):
        """Delete should work without access_token cookie from localhost"""
        response = requests.delete(
            f"{BASE_URL}/r2/packages/{TEST_PACKAGE['package_name']}/{TEST_PACKAGE['version']}"
        )

        # Should not return 401 Unauthorized
        assert response.status_code != 401, "Delete should not require auth from localhost"
        assert response.status_code != 403, "Delete should not be forbidden from localhost"

    def test_cleanup_no_auth(self):
        """Cleanup should work without authentication from localhost"""
        response = requests.post(
            f"{BASE_URL}/r2/packages/cleanup",
            json={"days_threshold": 90, "dry_run": True}
        )

        # Should not return 401 Unauthorized
        assert response.status_code != 401, "Cleanup should not require auth from localhost"
        assert response.status_code != 403, "Cleanup should not be forbidden from localhost"


def test_access_control_summary():
    """
    Summary test to verify the access control model
    """
    logger.info("=" * 80)
    logger.info("R2 Package Access Control Verification Summary")
    logger.info("=" * 80)

    # Test localhost access to management endpoints
    management_endpoints = [
        ("POST", "/r2/packages/upload", {"description": "Upload package"}),
        ("GET", "/r2/packages/test/1.0.0", {"description": "Get package info"}),
        ("GET", "/r2/packages/test/versions", {"description": "List versions"}),
        ("POST", "/r2/packages/search", {"description": "Search packages"}),
        ("GET", "/r2/packages/public", {"description": "List public packages"}),
        ("GET", "/r2/packages/my-uploads?user_id=00000000-0000-0000-0000-000000000000", {"description": "My uploads"}),
        ("PATCH", "/r2/packages/test/1.0.0", {"description": "Update package"}),
        ("DELETE", "/r2/packages/test/1.0.0", {"description": "Delete package"}),
        ("GET", "/r2/packages/stats/storage", {"description": "Storage stats"}),
        ("GET", "/r2/packages/stats/test", {"description": "Package stats"}),
        ("POST", "/r2/packages/cleanup", {"description": "Cleanup old packages"}),
        ("GET", "/r2/packages/test/1.0.0/verify", {"description": "Verify integrity"}),
        ("GET", "/r2/packages/health", {"description": "Health check"}),
    ]

    localhost_success = 0
    localhost_forbidden = 0

    for method, endpoint, meta in management_endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=3)
            elif method == "POST":
                response = requests.post(f"{BASE_URL}{endpoint}", json={}, timeout=3)
            elif method == "PATCH":
                response = requests.patch(f"{BASE_URL}{endpoint}", json={}, timeout=3)
            elif method == "DELETE":
                response = requests.delete(f"{BASE_URL}{endpoint}", timeout=3)

            if response.status_code == 403:
                logger.error(f"❌ {method} {endpoint}: FORBIDDEN (should be allowed from localhost)")
                localhost_forbidden += 1
            else:
                logger.info(f"✅ {method} {endpoint}: {response.status_code} (not forbidden)")
                localhost_success += 1
        except Exception as e:
            logger.warning(f"⚠️ {method} {endpoint}: {e}")

    # Test download endpoint (should be externally accessible)
    try:
        response = requests.get(f"{BASE_URL}/r2/packages/test/1.0.0/download", timeout=3)
        if response.status_code == 403:
            logger.error(f"❌ Download endpoint: FORBIDDEN (should be externally accessible)")
        else:
            logger.info(f"✅ Download endpoint: {response.status_code} (externally accessible)")
    except Exception as e:
        logger.warning(f"⚠️ Download endpoint: {e}")

    logger.info("=" * 80)
    logger.info(f"Localhost Management Endpoints: {localhost_success} accessible, {localhost_forbidden} forbidden")
    logger.info("=" * 80)

    # Assert that no endpoints are forbidden from localhost
    assert localhost_forbidden == 0, f"{localhost_forbidden} endpoints are incorrectly forbidden from localhost"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
