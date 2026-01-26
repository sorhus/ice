"""Tests for Copernicus Data Space API client."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import responses

import sys
sys.path.insert(0, str(__file__).replace("/tests/test_copernicus_client.py", "/src"))

from config import CopernicusConfig, DownloadConfig, SearchConfig
from copernicus_client import CopernicusClient, Product, Token


class TestProduct:
    """Tests for Product dataclass."""

    def test_from_odata_sentinel1(self):
        """Product.from_odata should parse Sentinel-1 response correctly."""
        odata_response = {
            "Id": "abc-123",
            "Name": "S1A_IW_GRDH_1SDV_20240115T053000",
            "ContentLength": 1024000,
            "ContentDate": {
                "Start": "2024-01-15T05:30:00.000Z",
            },
            "Attributes": [],
        }

        product = Product.from_odata(odata_response, "SENTINEL-1")

        assert product.id == "abc-123"
        assert product.name == "S1A_IW_GRDH_1SDV_20240115T053000"
        assert product.collection == "SENTINEL-1"
        assert product.size_bytes == 1024000
        assert product.sensing_time.year == 2024
        assert product.sensing_time.month == 1
        assert product.sensing_time.day == 15
        assert product.cloud_cover is None

    def test_from_odata_sentinel2_with_cloud_cover(self):
        """Product.from_odata should parse Sentinel-2 cloud cover."""
        odata_response = {
            "Id": "xyz-456",
            "Name": "S2A_MSIL2A_20240115T103000",
            "ContentLength": 2048000,
            "ContentDate": {
                "Start": "2024-01-15T10:30:00.000Z",
            },
            "Attributes": [
                {"Name": "cloudCover", "Value": "15.5"},
                {"Name": "other", "Value": "value"},
            ],
        }

        product = Product.from_odata(odata_response, "SENTINEL-2")

        assert product.id == "xyz-456"
        assert product.collection == "SENTINEL-2"
        assert product.cloud_cover == pytest.approx(15.5)


class TestToken:
    """Tests for Token dataclass."""

    def test_token_creation(self):
        """Token should store access token and expiry."""
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        token = Token(
            access_token="test_token",
            expires_at=expires,
            refresh_token="refresh_token",
        )

        assert token.access_token == "test_token"
        assert token.expires_at == expires
        assert token.refresh_token == "refresh_token"


class TestCopernicusClient:
    """Tests for CopernicusClient."""

    @pytest.fixture
    def client(self):
        """Create a client with test configuration."""
        copernicus_config = CopernicusConfig()
        copernicus_config.username = "test_user"
        copernicus_config.password = "test_pass"

        search_config = SearchConfig()
        download_config = DownloadConfig()

        return CopernicusClient(copernicus_config, search_config, download_config)

    @responses.activate
    def test_authenticate_success(self, client):
        """Client should authenticate successfully with valid credentials."""
        responses.add(
            responses.POST,
            client.config.token_url,
            json={
                "access_token": "test_access_token",
                "expires_in": 600,
                "refresh_token": "test_refresh_token",
            },
            status=200,
        )

        client.authenticate()

        assert client._token is not None
        assert client._token.access_token == "test_access_token"
        assert client._token.refresh_token == "test_refresh_token"

    @responses.activate
    def test_authenticate_failure(self, client):
        """Client should raise error on authentication failure."""
        responses.add(
            responses.POST,
            client.config.token_url,
            json={"error": "invalid_grant"},
            status=401,
        )

        with pytest.raises(Exception):
            client.authenticate()

    @responses.activate
    def test_search_sentinel1(self, client):
        """Client should search for Sentinel-1 products."""
        # Mock authentication
        responses.add(
            responses.POST,
            client.config.token_url,
            json={"access_token": "token", "expires_in": 600},
            status=200,
        )

        # Mock search
        responses.add(
            responses.GET,
            f"{client.config.odata_url}/Products",
            json={
                "value": [
                    {
                        "Id": "product-1",
                        "Name": "S1A_IW_GRDH_1SDV_20240115T053000",
                        "ContentLength": 1024000,
                        "ContentDate": {"Start": "2024-01-15T05:30:00.000Z"},
                        "Attributes": [],
                    },
                ]
            },
            status=200,
        )

        client.authenticate()
        products = client.search_sentinel1()

        assert len(products) == 1
        assert products[0].id == "product-1"
        assert products[0].collection == "SENTINEL-1"

    @responses.activate
    def test_search_sentinel2_filters_cloud_cover(self, client):
        """Client should filter Sentinel-2 by cloud cover."""
        # Mock authentication
        responses.add(
            responses.POST,
            client.config.token_url,
            json={"access_token": "token", "expires_in": 600},
            status=200,
        )

        # Mock search with products of varying cloud cover
        responses.add(
            responses.GET,
            f"{client.config.odata_url}/Products",
            json={
                "value": [
                    {
                        "Id": "low-cloud",
                        "Name": "S2A_low_cloud",
                        "ContentLength": 1024000,
                        "ContentDate": {"Start": "2024-01-15T10:00:00.000Z"},
                        "Attributes": [{"Name": "cloudCover", "Value": "10"}],
                    },
                    {
                        "Id": "high-cloud",
                        "Name": "S2A_high_cloud",
                        "ContentLength": 1024000,
                        "ContentDate": {"Start": "2024-01-15T11:00:00.000Z"},
                        "Attributes": [{"Name": "cloudCover", "Value": "80"}],
                    },
                ]
            },
            status=200,
        )

        client.authenticate()
        products = client.search_sentinel2()

        # Only the low cloud cover product should be returned
        assert len(products) == 1
        assert products[0].id == "low-cloud"

    @responses.activate
    def test_download_product_success(self, client):
        """Client should download product successfully."""
        import tempfile
        import os

        # Set up token
        client._token = Token(
            access_token="test_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        product = Product(
            id="test-id",
            name="test_product",
            collection="SENTINEL-1",
            sensing_time=datetime.now(timezone.utc),
            size_bytes=1024,
        )

        # Mock download endpoint
        responses.add(
            responses.GET,
            f"{client.config.download_url}/Products({product.id})/$value",
            body=b"test file content",
            status=200,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.zip")
            result = client.download_product(product, output_path)

            assert result is True
            assert os.path.exists(output_path)
            with open(output_path, "rb") as f:
                assert f.read() == b"test file content"

    @responses.activate
    def test_download_product_retries_on_failure(self, client):
        """Client should retry on download failure."""
        import tempfile
        import os

        client._token = Token(
            access_token="test_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        client.download_config.retry_delay_seconds = 0  # Fast retries for test

        product = Product(
            id="test-id",
            name="test_product",
            collection="SENTINEL-1",
            sensing_time=datetime.now(timezone.utc),
            size_bytes=1024,
        )

        # First attempt fails, second succeeds
        responses.add(
            responses.GET,
            f"{client.config.download_url}/Products({product.id})/$value",
            body=Exception("Network error"),
        )
        responses.add(
            responses.GET,
            f"{client.config.download_url}/Products({product.id})/$value",
            body=b"success",
            status=200,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.zip")
            result = client.download_product(product, output_path)

            assert result is True


class TestCopernicusClientIntegration:
    """Integration tests requiring real API access.

    These tests are marked with 'integration' and skipped by default.
    Run with: pytest -m integration
    """

    @pytest.fixture
    def real_client(self):
        """Create a client with real credentials from environment."""
        import os

        username = os.environ.get("COPERNICUS_USER")
        password = os.environ.get("COPERNICUS_PASSWORD")

        if not username or not password:
            pytest.skip("COPERNICUS_USER and COPERNICUS_PASSWORD not set")

        copernicus_config = CopernicusConfig()
        search_config = SearchConfig()
        download_config = DownloadConfig()

        return CopernicusClient(copernicus_config, search_config, download_config)

    @pytest.mark.integration
    def test_real_authentication(self, real_client):
        """Test authentication with real Copernicus API."""
        real_client.authenticate()
        assert real_client._token is not None
        assert real_client._token.access_token

    @pytest.mark.integration
    def test_real_search_sentinel1(self, real_client):
        """Test searching for Sentinel-1 products."""
        real_client.authenticate()
        products = real_client.search_sentinel1()

        # Should find some products (may be empty if no recent data)
        assert isinstance(products, list)
