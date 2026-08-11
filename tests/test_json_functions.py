"""
Unit tests for json_functions module.
"""

import os
import tempfile
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch, mock_open
import requests
from helper_functions.json_functions import (
    _feature_to_row_values,
    _infer_columns_from_feature,
    _resolve_source_geom_srid,
    _build_ogc_cache_file_path,
    download_json,
    load_ogc_features_to_table,
    load_json_file,
)

class TestJsonFunctions(unittest.TestCase):
    """Tests for JSON handling functions."""

    @patch('requests.get')
    def test_download_json_success(self, mock_get):
        """Test successful JSON download."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b'{"key": "value"}']
        mock_response.__enter__.return_value = mock_response
        mock_get.return_value = mock_response

        data = download_json("http://example.com/data.json")
        self.assertEqual(data, {"key": "value"})
        mock_get.assert_called_once_with(
            "http://example.com/data.json",
            timeout=(30, 30),
            stream=True,
        )

    @patch('time.sleep')
    @patch('requests.get')
    def test_download_json_retries_after_timeout(self, mock_get, mock_sleep):
        """Test that transient request failures are retried before succeeding."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b'{"key": "value"}']
        mock_response.__enter__.return_value = mock_response

        mock_get.side_effect = [
            requests.exceptions.ReadTimeout("timed out"),
            mock_response,
        ]

        data = download_json("http://example.com/data.json")

        self.assertEqual(data, {"key": "value"})
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(2.0)

    @patch('requests.get')
    def test_download_ogc_features_basic_auth_strips_query_api_key(self, mock_get):
        """API key must not be sent twice via both query params and Basic auth."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"type": "FeatureCollection", "features": []}
        mock_get.return_value = mock_response

        from helper_functions.json_functions import download_ogc_features

        download_ogc_features(
            collection_url="https://example.com/api/collections/kunta",
            api_key="secret",
            api_key_auth_mode="basic",
            extra_params={"limit": 1000, "api_key": "stale-query-key"},
            show_progress=False,
            resume_from_cache=False,
        )

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["auth"], ("secret", ""))
        self.assertNotIn("api_key", kwargs["params"])

    @patch('builtins.open', new_callable=mock_open, read_data='{"key": "value"}')
    def test_load_json_file_success(self, mock_file):
        """Test successful JSON file loading."""
        data = load_json_file("dummy_path.json")
        self.assertEqual(data, {"key": "value"})

    def test_feature_to_row_values_serializes_decimal_geometry(self):
        """Geometry coordinates parsed as Decimal should serialize without errors."""
        feature = {
            "type": "Feature",
            "properties": {"name": "x"},
            "geometry": {
                "type": "Point",
                "coordinates": [Decimal("24.9384"), Decimal("60.1699")],
            },
        }

        row = _feature_to_row_values(feature, ["name", "geom"], is_geojson=True)
        self.assertEqual(row[0], "x")
        self.assertIn("24.9384", row[1])
        self.assertIn("60.1699", row[1])

    def test_infer_columns_treats_decimal_as_numeric(self):
        """Decimal property values should map to NUMERIC columns."""
        feature = {
            "type": "Feature",
            "properties": {"area": Decimal("12.5"), "active": True},
            "geometry": {"type": "Point", "coordinates": [24.9, 60.1]},
        }

        columns, is_geojson = _infer_columns_from_feature(feature, target_geom_srid=3067)
        self.assertTrue(is_geojson)
        self.assertEqual(columns["area"], "NUMERIC")
        self.assertEqual(columns["active"], "BOOLEAN")
        self.assertIn("geom", columns)

    def test_resolve_source_geom_srid_defaults_to_wgs84(self):
        """Missing CRS metadata should default to EPSG:4326, not 3067."""
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "Point", "coordinates": [26.1, 60.1]},
                }
            ],
        }

        self.assertEqual(_resolve_source_geom_srid(None, payload), 4326)

    def test_build_ogc_cache_file_path_uses_existing_naming_by_default(self):
        self.assertEqual(
            _build_ogc_cache_file_path(
                "https://example.com/api/collections/building_part_area",
                "./data",
            ),
            os.path.join("./data", "building_part_area_cache.json"),
        )

    def test_build_ogc_cache_file_path_uses_test_suffix_in_test_runs(self):
        self.assertEqual(
            _build_ogc_cache_file_path(
                "https://example.com/api/collections/building_part_area",
                "./data",
                test_run=True,
            ),
            os.path.join("./data", "building_part_area_test_cache.json"),
        )

    def test_build_ogc_cache_file_path_includes_cache_suffix(self):
        self.assertEqual(
            _build_ogc_cache_file_path(
                "https://example.com/api/collections/building_part_area",
                "./data",
                test_run=True,
                cache_name_suffix="municipalities_092_091",
            ),
            os.path.join("./data", "building_part_area_test_municipalities_092_091_cache.json"),
        )

    @patch('helper_functions.json_functions.download_ogc_features')
    def test_load_ogc_features_to_table_forwards_test_cache_naming(self, mock_download_ogc):
        """Test table loader forwards test-run cache naming args to downloader."""
        mock_download_ogc.side_effect = RuntimeError("stop after argument capture")

        with patch('helper_functions.json_functions.os.path.exists', return_value=False), \
             patch('helper_functions.json_functions.os.path.isdir', return_value=False), \
             self.assertRaises(RuntimeError):
            load_ogc_features_to_table(
                connection=MagicMock(),
                schema="topodb_test_202406",
                table_name="building_part_area",
                collection_url="https://example.com/api/collections/building_part_area",
                auto_cache_dir="./data/test",
                test_run=True,
                cache_name_suffix="municipalities_092_091",
                cache_version="202406",
                show_progress=False,
            )

        download_kwargs = mock_download_ogc.call_args.kwargs
        self.assertTrue(download_kwargs["test_run"])
        self.assertEqual(download_kwargs["cache_name_suffix"], "municipalities_092_091")
        self.assertEqual(download_kwargs["cache_version"], "202406")

    @patch('helper_functions.json_functions.download_ogc_features')
    def test_load_ogc_features_to_table_ignores_mismatched_cache_version(self, mock_download_ogc):
        """Mismatched cache version must trigger a fresh download path."""
        mock_download_ogc.side_effect = RuntimeError("force download call")

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_file = os.path.join(tmp_dir, "building_part_area_cache.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write('{"type":"FeatureCollection","_cache_version":"202405","features":[]}')

            with self.assertRaises(RuntimeError):
                load_ogc_features_to_table(
                    connection=MagicMock(),
                    schema="topodb_202406",
                    table_name="building_part_area",
                    collection_url="https://example.com/api/collections/building_part_area",
                    auto_cache_dir=tmp_dir,
                    cache_version="202406",
                    show_progress=False,
                )

        self.assertEqual(mock_download_ogc.call_count, 1)
        self.assertEqual(mock_download_ogc.call_args.kwargs["cache_version"], "202406")

    def test_resolve_source_geom_srid_detects_legacy_crs(self):
        """Legacy GeoJSON CRS metadata should override the default."""
        payload = {
            "crs": {"properties": {"name": "urn:ogc:def:crs:EPSG::3067"}}
        }

        self.assertEqual(_resolve_source_geom_srid(None, payload), 3067)


if __name__ == '__main__':
    unittest.main()
