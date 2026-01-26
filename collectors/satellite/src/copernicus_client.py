"""Copernicus Data Space API client with OAuth2 authentication."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests

from config import CopernicusConfig, DownloadConfig, SearchConfig

logger = logging.getLogger(__name__)


@dataclass
class Token:
    """OAuth2 access token with expiry tracking."""

    access_token: str
    expires_at: datetime
    refresh_token: Optional[str] = None


@dataclass
class Product:
    """Satellite product metadata."""

    id: str
    name: str
    collection: str
    sensing_time: datetime
    size_bytes: int
    cloud_cover: Optional[float] = None  # Only for optical products

    @classmethod
    def from_odata(cls, data: dict[str, Any], collection: str) -> "Product":
        """Create Product from OData API response."""
        cloud_cover = None
        if collection == "SENTINEL-2":
            # Cloud cover is in the Attributes
            attributes = data.get("Attributes", [])
            for attr in attributes:
                if attr.get("Name") == "cloudCover":
                    cloud_cover = float(attr.get("Value", 0))
                    break

        # Parse sensing time
        content_date = data.get("ContentDate", {})
        sensing_time_str = content_date.get("Start", data.get("ModificationDate"))
        sensing_time = datetime.fromisoformat(sensing_time_str.replace("Z", "+00:00"))

        return cls(
            id=data["Id"],
            name=data["Name"],
            collection=collection,
            sensing_time=sensing_time,
            size_bytes=data.get("ContentLength", 0),
            cloud_cover=cloud_cover,
        )


class CopernicusClient:
    """Client for Copernicus Data Space Ecosystem API."""

    def __init__(
        self,
        copernicus_config: CopernicusConfig,
        search_config: SearchConfig,
        download_config: DownloadConfig,
    ):
        self.config = copernicus_config
        self.search_config = search_config
        self.download_config = download_config
        self._token: Optional[Token] = None
        self._session = requests.Session()

    def authenticate(self) -> None:
        """Authenticate with Copernicus Data Space using OAuth2."""
        logger.info("Authenticating with Copernicus Data Space...")

        if not self.config.username or not self.config.password:
            raise ValueError(
                "Missing Copernicus credentials. Set COPERNICUS_USER and COPERNICUS_PASSWORD."
            )

        data = {
            "grant_type": "password",
            "username": self.config.username,
            "password": self.config.password,
            "client_id": "cdse-public",
        }

        try:
            response = self._session.post(
                self.config.token_url,
                data=data,
                timeout=self.download_config.request_timeout,
            )
            response.raise_for_status()

            token_data = response.json()
            expires_in = token_data.get("expires_in", 600)
            self._token = Token(
                access_token=token_data["access_token"],
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
                refresh_token=token_data.get("refresh_token"),
            )
            logger.info("Authentication successful. Token expires in %d seconds.", expires_in)

        except requests.RequestException as e:
            logger.error("Authentication failed: %s", e)
            raise

    def _ensure_valid_token(self) -> str:
        """Ensure we have a valid token, refreshing if necessary."""
        if self._token is None:
            self.authenticate()

        # Check if token is about to expire
        margin = timedelta(seconds=self.download_config.token_refresh_margin_seconds)
        if datetime.now(timezone.utc) + margin >= self._token.expires_at:
            logger.info("Token expired or expiring soon, refreshing...")
            self._refresh_token()

        return self._token.access_token

    def _refresh_token(self) -> None:
        """Refresh the OAuth2 token."""
        if self._token and self._token.refresh_token:
            logger.info("Attempting token refresh...")
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self._token.refresh_token,
                "client_id": "cdse-public",
            }

            try:
                response = self._session.post(
                    self.config.token_url,
                    data=data,
                    timeout=self.download_config.request_timeout,
                )
                response.raise_for_status()

                token_data = response.json()
                expires_in = token_data.get("expires_in", 600)
                self._token = Token(
                    access_token=token_data["access_token"],
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
                    refresh_token=token_data.get("refresh_token"),
                )
                logger.info("Token refresh successful.")
                return

            except requests.RequestException as e:
                logger.warning("Token refresh failed: %s. Re-authenticating...", e)

        # Fall back to full authentication
        self.authenticate()

    def _build_bbox_filter(self) -> str:
        """Build OData geographic filter for Sweden bounding box."""
        west, south, east, north = self.search_config.sweden_bbox
        # OData uses WKT POLYGON format
        polygon = f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"
        return f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}')"

    def _build_time_filter(self) -> str:
        """Build OData time filter for recent products."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=self.search_config.lookback_hours)
        return f"ContentDate/Start ge {start.isoformat()}Z and ContentDate/Start le {now.isoformat()}Z"

    def search_sentinel1(self) -> list[Product]:
        """Search for Sentinel-1 GRD products over Sweden."""
        logger.info("Searching for Sentinel-1 GRD products...")

        filters = [
            f"Collection/Name eq '{self.search_config.s1_collection}'",
            f"contains(Name, '{self.search_config.s1_product_type}')",
            f"contains(Name, '{self.search_config.s1_sensor_mode}')",
            self._build_bbox_filter(),
            self._build_time_filter(),
        ]

        return self._search_products(filters, self.search_config.s1_collection)

    def search_sentinel2(self) -> list[Product]:
        """Search for Sentinel-2 L2A products over Sweden with cloud filter."""
        logger.info("Searching for Sentinel-2 L2A products...")

        filters = [
            f"Collection/Name eq '{self.search_config.s2_collection}'",
            f"contains(Name, '{self.search_config.s2_product_type}')",
            self._build_bbox_filter(),
            self._build_time_filter(),
        ]

        products = self._search_products(filters, self.search_config.s2_collection)

        # Filter by cloud cover
        filtered = [
            p
            for p in products
            if p.cloud_cover is not None
            and p.cloud_cover <= self.search_config.s2_max_cloud_cover
        ]

        logger.info(
            "Found %d Sentinel-2 products with cloud cover <= %.1f%%",
            len(filtered),
            self.search_config.s2_max_cloud_cover,
        )

        return filtered

    def _search_products(self, filters: list[str], collection: str) -> list[Product]:
        """Execute OData search query."""
        filter_str = " and ".join(filters)
        url = f"{self.config.odata_url}/Products"

        params = {
            "$filter": filter_str,
            "$expand": "Attributes",
            "$top": 100,
            "$orderby": "ContentDate/Start desc",
        }

        products: list[Product] = []

        try:
            response = self._session.get(
                url,
                params=params,
                timeout=self.download_config.request_timeout,
            )
            response.raise_for_status()

            data = response.json()
            for item in data.get("value", []):
                try:
                    product = Product.from_odata(item, collection)
                    products.append(product)
                except (KeyError, ValueError) as e:
                    logger.warning("Failed to parse product: %s", e)

            logger.info("Found %d %s products", len(products), collection)

        except requests.RequestException as e:
            logger.error("Search failed: %s", e)
            raise

        return products

    def download_product(self, product: Product, output_path: str) -> bool:
        """Download a product with retry logic."""
        access_token = self._ensure_valid_token()

        url = f"{self.config.download_url}/Products({product.id})/$value"
        headers = {"Authorization": f"Bearer {access_token}"}

        for attempt in range(1, self.download_config.max_retries + 1):
            logger.info(
                "Downloading %s (attempt %d/%d)...",
                product.name,
                attempt,
                self.download_config.max_retries,
            )

            try:
                # Refresh token before retry if needed
                if attempt > 1:
                    access_token = self._ensure_valid_token()
                    headers = {"Authorization": f"Bearer {access_token}"}

                response = self._session.get(
                    url,
                    headers=headers,
                    stream=True,
                    timeout=self.download_config.request_timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()

                # Write to file in chunks
                downloaded_bytes = 0
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(
                        chunk_size=self.download_config.chunk_size
                    ):
                        if chunk:
                            f.write(chunk)
                            downloaded_bytes += len(chunk)

                logger.info(
                    "Successfully downloaded %s (%d bytes)",
                    product.name,
                    downloaded_bytes,
                )
                return True

            except requests.RequestException as e:
                logger.warning("Download attempt %d failed: %s", attempt, e)

                if attempt < self.download_config.max_retries:
                    logger.info(
                        "Retrying in %d seconds...",
                        self.download_config.retry_delay_seconds,
                    )
                    time.sleep(self.download_config.retry_delay_seconds)
                else:
                    logger.error(
                        "Failed to download %s after %d attempts",
                        product.name,
                        self.download_config.max_retries,
                    )

        return False

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
