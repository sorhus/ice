"""Tests for satellite download script."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(__file__).replace("/tests/test_download.py", "/src"))

from copernicus_client import Product
from download import (
    RunOptions,
    StateManager,
    get_output_path,
    parse_args,
    process_products,
)


class TestRunOptions:
    """Tests for RunOptions dataclass."""

    def test_default_values(self):
        """RunOptions should have correct defaults."""
        options = RunOptions()

        assert options.dry_run is False
        assert options.limit is None
        assert options.verbose is False

    def test_custom_values(self):
        """RunOptions should accept custom values."""
        options = RunOptions(dry_run=True, limit=5, verbose=True)

        assert options.dry_run is True
        assert options.limit == 5
        assert options.verbose is True


class TestParseArgs:
    """Tests for argument parsing."""

    def test_parse_default_args(self):
        """Parsing no arguments should return defaults."""
        with patch("sys.argv", ["download.py"]):
            options = parse_args()

            assert options.dry_run is False
            assert options.limit is None
            assert options.verbose is False

    def test_parse_dry_run(self):
        """Parsing --dry-run should set dry_run flag."""
        with patch("sys.argv", ["download.py", "--dry-run"]):
            options = parse_args()

            assert options.dry_run is True

    def test_parse_limit(self):
        """Parsing --limit should set limit value."""
        with patch("sys.argv", ["download.py", "--limit", "5"]):
            options = parse_args()

            assert options.limit == 5

    def test_parse_verbose(self):
        """Parsing --verbose should set verbose flag."""
        with patch("sys.argv", ["download.py", "--verbose"]):
            options = parse_args()

            assert options.verbose is True

    def test_parse_verbose_short(self):
        """Parsing -v should set verbose flag."""
        with patch("sys.argv", ["download.py", "-v"]):
            options = parse_args()

            assert options.verbose is True

    def test_parse_all_args(self):
        """Parsing all arguments together."""
        with patch("sys.argv", ["download.py", "--dry-run", "--limit", "3", "-v"]):
            options = parse_args()

            assert options.dry_run is True
            assert options.limit == 3
            assert options.verbose is True


class TestStateManager:
    """Tests for StateManager class."""

    @pytest.fixture
    def state_file(self):
        """Create a temporary state file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "state" / "test_state.json"

    def test_creates_empty_state(self, state_file):
        """StateManager should create empty state when file doesn't exist."""
        manager = StateManager(str(state_file))

        assert manager._state["downloaded_products"] == {}
        assert manager._state["last_run"] is None

    def test_loads_existing_state(self, state_file):
        """StateManager should load existing state from file."""
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({
            "downloaded_products": {"prod-1": {"name": "test"}},
            "last_run": "2024-01-15T10:00:00+00:00",
        }))

        manager = StateManager(str(state_file))

        assert "prod-1" in manager._state["downloaded_products"]
        assert manager._state["last_run"] == "2024-01-15T10:00:00+00:00"

    def test_is_downloaded(self, state_file):
        """is_downloaded should correctly identify downloaded products."""
        manager = StateManager(str(state_file))
        manager._state["downloaded_products"]["prod-1"] = {"name": "test"}

        assert manager.is_downloaded("prod-1") is True
        assert manager.is_downloaded("prod-2") is False

    def test_mark_downloaded(self, state_file):
        """mark_downloaded should add product to state and save."""
        manager = StateManager(str(state_file))

        product = Product(
            id="prod-1",
            name="test_product",
            collection="SENTINEL-1",
            sensing_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            size_bytes=1024,
        )

        manager.mark_downloaded(product, "/path/to/file.zip")

        assert manager.is_downloaded("prod-1")
        assert state_file.exists()

        # Verify file was written
        saved_state = json.loads(state_file.read_text())
        assert "prod-1" in saved_state["downloaded_products"]
        assert saved_state["downloaded_products"]["prod-1"]["name"] == "test_product"

    def test_update_last_run(self, state_file):
        """update_last_run should update timestamp and save."""
        manager = StateManager(str(state_file))
        manager.update_last_run()

        assert manager._state["last_run"] is not None
        assert state_file.exists()

    def test_handles_corrupt_state_file(self, state_file):
        """StateManager should handle corrupt state file gracefully."""
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("invalid json{")

        manager = StateManager(str(state_file))

        # Should fall back to empty state
        assert manager._state["downloaded_products"] == {}


class TestGetOutputPath:
    """Tests for get_output_path function."""

    def test_generates_correct_path(self):
        """get_output_path should generate date-organized path."""
        product = Product(
            id="test-id",
            name="S1A_IW_GRDH_1SDV_20240115T053000",
            collection="SENTINEL-1",
            sensing_time=datetime(2024, 1, 15, 5, 30, tzinfo=timezone.utc),
            size_bytes=1024,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = get_output_path(product, tmpdir)

            assert "2024-01-15" in path
            assert path.endswith(".zip")
            assert Path(tmpdir) / "2024-01-15" in Path(path).parents or "2024-01-15" in path

    def test_adds_zip_extension(self):
        """get_output_path should add .zip extension if missing."""
        product = Product(
            id="test-id",
            name="S1A_product.SAFE",
            collection="SENTINEL-1",
            sensing_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            size_bytes=1024,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = get_output_path(product, tmpdir)

            assert path.endswith(".zip")

    def test_preserves_zip_extension(self):
        """get_output_path should not double .zip extension."""
        product = Product(
            id="test-id",
            name="S1A_product.zip",
            collection="SENTINEL-1",
            sensing_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            size_bytes=1024,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = get_output_path(product, tmpdir)

            assert not path.endswith(".zip.zip")

    def test_creates_directory(self):
        """get_output_path should create output directory."""
        product = Product(
            id="test-id",
            name="test_product",
            collection="SENTINEL-1",
            sensing_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            size_bytes=1024,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = get_output_path(product, tmpdir, dry_run=False)
            output_dir = Path(path).parent

            assert output_dir.exists()

    def test_dry_run_skips_directory_creation(self):
        """get_output_path should skip directory creation in dry-run mode."""
        product = Product(
            id="test-id",
            name="test_product",
            collection="SENTINEL-1",
            sensing_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            size_bytes=1024,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "nonexistent"
            path = get_output_path(product, str(base_path), dry_run=True)

            # Directory should NOT be created in dry-run mode
            assert not base_path.exists()


class TestProcessProducts:
    """Tests for process_products function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock CopernicusClient."""
        client = MagicMock()
        client.download_product.return_value = True
        return client

    @pytest.fixture
    def state_manager(self):
        """Create a StateManager with temporary storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield StateManager(str(Path(tmpdir) / "state.json"))

    def test_downloads_new_products(self, mock_client, state_manager):
        """process_products should download new products."""
        products = [
            Product(
                id="prod-1",
                name="test_product_1",
                collection="SENTINEL-1",
                sensing_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
                size_bytes=1024,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            options = RunOptions()
            success, failure, skipped = process_products(
                mock_client, products, tmpdir, state_manager, "SAR", options
            )

            assert success == 1
            assert failure == 0
            assert skipped == 0
            mock_client.download_product.assert_called_once()

    def test_skips_already_downloaded(self, mock_client, state_manager):
        """process_products should skip already downloaded products."""
        product = Product(
            id="prod-1",
            name="test_product",
            collection="SENTINEL-1",
            sensing_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            size_bytes=1024,
        )

        # Mark as already downloaded
        state_manager.mark_downloaded(product, "/old/path.zip")

        with tempfile.TemporaryDirectory() as tmpdir:
            options = RunOptions()
            success, failure, skipped = process_products(
                mock_client, [product], tmpdir, state_manager, "SAR", options
            )

            assert success == 0
            assert failure == 0
            assert skipped == 1
            mock_client.download_product.assert_not_called()

    def test_respects_limit(self, mock_client, state_manager):
        """process_products should stop at limit."""
        products = [
            Product(
                id=f"prod-{i}",
                name=f"test_product_{i}",
                collection="SENTINEL-1",
                sensing_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
                size_bytes=1024,
            )
            for i in range(5)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            options = RunOptions(limit=2)
            success, failure, skipped = process_products(
                mock_client, products, tmpdir, state_manager, "SAR", options
            )

            assert success == 2
            assert mock_client.download_product.call_count == 2

    def test_dry_run_skips_download(self, mock_client, state_manager):
        """process_products should not download in dry-run mode."""
        products = [
            Product(
                id="prod-1",
                name="test_product",
                collection="SENTINEL-1",
                sensing_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
                size_bytes=1024 * 1024,  # 1 MB
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            options = RunOptions(dry_run=True)
            success, failure, skipped = process_products(
                mock_client, products, tmpdir, state_manager, "SAR", options
            )

            assert success == 1
            assert failure == 0
            mock_client.download_product.assert_not_called()

    def test_counts_failures(self, mock_client, state_manager):
        """process_products should count download failures."""
        mock_client.download_product.return_value = False

        products = [
            Product(
                id="prod-1",
                name="test_product",
                collection="SENTINEL-1",
                sensing_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
                size_bytes=1024,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            options = RunOptions()
            success, failure, skipped = process_products(
                mock_client, products, tmpdir, state_manager, "SAR", options
            )

            assert success == 0
            assert failure == 1
