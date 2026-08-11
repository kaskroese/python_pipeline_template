"""
Unit tests for generic pipeline_steps handlers.
"""

import unittest
from unittest.mock import MagicMock, patch
import tempfile
import yaml

from helper_functions.pipeline_steps import (
    json_to_postgres,
    ogc_features_to_postgres,
    load_db_config,
    load_ogc_cache_to_postgres,
    sql_template_to_postgres,
    _normalize_municipality_codes,
    _parse_bbox_coordinates,
    _prune_geojson_points_to_bbox,
)


class TestLoadDbConfig(unittest.TestCase):
    """Tests for load_db_config function."""

    def test_load_valid_config(self):
        """Test loading valid database config from YAML file."""
        config_data = {
            'database': {
                'host': 'localhost',
                'user': 'postgres',
                'password': 'secret',
                'database': 'buildings',
                'port': 5432
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()

            result = load_db_config(f.name)

            self.assertEqual(result['host'], 'localhost')
            self.assertEqual(result['user'], 'postgres')
            self.assertEqual(result['password'], 'secret')
            self.assertEqual(result['database'], 'buildings')
            self.assertEqual(result['port'], 5432)

    def test_load_config_missing_file(self):
        """Test error when config file doesn't exist."""
        with self.assertRaises(FileNotFoundError):
            load_db_config('/nonexistent/path/config.yaml')

    def test_load_config_missing_database_section(self):
        """Test error when 'database' section missing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'other_key': {}}, f)
            f.flush()

            with self.assertRaises(KeyError):
                load_db_config(f.name)

    @patch.dict('os.environ', {'DB_HOST': 'remote-host', 'DB_USER': 'admin',
                               'DB_PASSWORD': 'new-pass', 'DB_DATABASE': 'test_db',
                               'DB_PORT': '3306'})
    def test_env_var_override(self):
        """Test that environment variables override config file."""
        config_data = {
            'database': {
                'host': 'localhost',
                'user': 'postgres',
                'password': 'secret',
                'database': 'buildings',
                'port': 5432
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()

            result = load_db_config(f.name)

            self.assertEqual(result['host'], 'remote-host')
            self.assertEqual(result['user'], 'admin')
            self.assertEqual(result['password'], 'new-pass')
            self.assertEqual(result['database'], 'test_db')
            self.assertEqual(result['port'], 3306)


class TestJsonToPostgres(unittest.TestCase):
    """Tests for json_to_postgres step handler."""

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_json_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    @patch('helper_functions.pipeline_steps.download_json')
    def test_json_to_postgres_with_url(
        self, mock_download, mock_connect, mock_get_schema, mock_drop,
        mock_enable_postgis, mock_create, mock_load_table, mock_create_views, mock_close, mock_load_cfg
    ):
        """Test successful download and load from URL."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_download.return_value = {"data": [{"id": 1}]}
        mock_get_schema.return_value = "buildings_202406"
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432
        }

        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "buildings",
            "connect_timeout": 20,
            "read_timeout": 600,
            "drop_existing": True,
        }

        json_to_postgres(params)

        mock_download.assert_called_once_with(
            "http://example.com/data.json",
            timeout=30,
            connect_timeout=20,
            read_timeout=600,
            request_retries=5,
            retry_delay_seconds=2.0,
            retry_backoff_factor=2.0,
        )
        mock_load_cfg.assert_called_once_with("db_config.yaml")
        mock_connect.assert_called()  # May be called multiple times (initial + reconnect after drop)
        mock_enable_postgis.assert_called_once_with(mock_conn)
        mock_load_table.assert_called_once()
        self.assertEqual(mock_load_table.call_args.kwargs["target_geom_srid"], 3067)
        mock_create_views.assert_called_once()
        mock_close.assert_called()  # May be called multiple times due to reconnect

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_json_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    @patch('helper_functions.pipeline_steps.load_json_file')
    def test_json_to_postgres_with_file(
        self, mock_load_file, mock_connect, mock_get_schema, mock_exists,
        mock_drop, mock_enable_postgis, mock_create, mock_load_table, mock_create_views, mock_close, mock_load_cfg
    ):
        """Test successful load from local file."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_load_file.return_value = {"data": [{"id": 1}]}
        mock_get_schema.return_value = "addresses_202406"
        mock_exists.return_value = False
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432
        }

        params = {
            "source_file": "/path/to/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "addresses",
            "table_name": "addresses",
            "drop_existing": False,
        }

        json_to_postgres(params)

        mock_load_file.assert_called_once_with("/path/to/data.json")
        mock_enable_postgis.assert_called_once_with(mock_conn)
        mock_drop.assert_not_called()
        mock_create.assert_called_once()
        self.assertEqual(mock_load_table.call_args.kwargs["target_geom_srid"], 3067)

    def test_missing_source(self):
        """Test error when neither source_url nor source_file provided."""
        params = {
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "buildings",
        }

        with self.assertRaises(ValueError) as context:
            json_to_postgres(params)

        self.assertIn("source_url", str(context.exception))

    def test_missing_schema_base_name(self):
        """Test error when schema_base_name not provided."""
        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "table_name": "buildings",
        }

        with self.assertRaises(ValueError) as context:
            json_to_postgres(params)

        self.assertIn("schema_base_name", str(context.exception))

    def test_missing_table_name(self):
        """Test error when table_name not provided."""
        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
        }

        with self.assertRaises(ValueError) as context:
            json_to_postgres(params)

        self.assertIn("table_name", str(context.exception))

    def test_invalid_insert_batch_size(self):
        """Test error when insert_batch_size is non-positive."""
        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "buildings",
            "insert_batch_size": 0,
        }

        with self.assertRaises(ValueError) as context:
            json_to_postgres(params)

        self.assertIn("insert_batch_size", str(context.exception))

    @patch('helper_functions.pipeline_steps.download_json')
    @patch('helper_functions.pipeline_steps.load_db_config')
    def test_missing_db_credentials(self, mock_load_cfg, mock_download):
        """Test error when database credentials missing from config."""
        # Config missing 'password'
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'database': 'buildings',
            'port': 5432
        }
        mock_download.return_value = {"data": [{"id": 1}]}

        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "buildings",
        }

        with self.assertRaises(ValueError) as context:
            json_to_postgres(params)

        self.assertIn("Database config", str(context.exception))

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_json_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    @patch('helper_functions.pipeline_steps.download_json')
    def test_drop_existing_schema(
        self, mock_download, mock_connect, mock_get_schema, mock_exists,
        mock_drop, mock_enable_postgis, mock_create, mock_load_table, mock_create_views, mock_close, mock_load_cfg
    ):
        """Test dropping existing schema when drop_existing=True."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_download.return_value = {"data": [{"id": 1}]}
        mock_get_schema.return_value = "buildings_202406"
        mock_exists.return_value = True
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432
        }

        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "buildings",
            "drop_existing": True,
        }

        json_to_postgres(params)

        mock_exists.assert_called_once()
        mock_drop.assert_called_once_with(mock_conn, "buildings_202406")

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_json_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    @patch('helper_functions.pipeline_steps.download_json')
    def test_connection_cleanup_on_error(
        self, mock_download, mock_connect, mock_get_schema, mock_exists,
        mock_drop, mock_enable_postgis, mock_create, mock_load_table, mock_create_views, mock_close, mock_load_cfg
    ):
        """Test that connection is closed even on error after connection established."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_download.return_value = {"data": [{"id": 1}]}
        mock_get_schema.return_value = "buildings_202406"
        mock_load_table.side_effect = Exception("Load error")
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432
        }

        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "buildings",
        }

        with self.assertRaises(Exception):
            json_to_postgres(params)

        # May be called multiple times if schema drop triggers reconnect, 
        # and once more in finally block
        self.assertGreaterEqual(mock_close.call_count, 1)

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_json_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    @patch('helper_functions.pipeline_steps.download_json')
    def test_custom_version(
        self, mock_download, mock_connect, mock_get_schema, mock_exists,
        mock_drop, mock_enable_postgis, mock_create, mock_load_table, mock_create_views, mock_close, mock_load_cfg
    ):
        """Test with custom version parameter."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_download.return_value = {"data": [{"id": 1}]}
        mock_get_schema.return_value = "buildings_202403"
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432
        }

        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "buildings",
            "version": "202403",
        }

        json_to_postgres(params)

        mock_get_schema.assert_called_once_with(
            "buildings",
            "202403",
            test_run=False,
            test_schema_suffix="test",
        )

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_json_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    @patch('helper_functions.pipeline_steps.download_json')
    def test_data_key_parameter(
        self, mock_download, mock_connect, mock_get_schema, mock_drop,
        mock_enable_postgis, mock_create, mock_load_table, mock_create_views, mock_close, mock_load_cfg
    ):
        """Test with data_key parameter."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_download.return_value = {"records": [{"id": 1}]}
        mock_get_schema.return_value = "buildings_202406"
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432
        }

        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "buildings",
            "data_key": "records",
        }

        json_to_postgres(params)

        mock_load_table.assert_called_once()
        call_args = mock_load_table.call_args
        self.assertEqual(call_args.kwargs["data_key"], "records")
        self.assertEqual(call_args.kwargs["batch_size"], 50)  # Default batch size is now 50

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_json_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    @patch('helper_functions.pipeline_steps.download_json')
    def test_insert_batch_size_parameter(
        self, mock_download, mock_connect, mock_get_schema, mock_drop,
        mock_enable_postgis, mock_create, mock_load_table, mock_create_views, mock_close, mock_load_cfg
    ):
        """Test custom insert_batch_size parameter passthrough."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_download.return_value = {"records": [{"id": 1}]}
        mock_get_schema.return_value = "buildings_202406"
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432
        }

        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "buildings",
            "insert_batch_size": 123,
        }

        json_to_postgres(params)

        mock_load_table.assert_called_once()
        call_args = mock_load_table.call_args
        self.assertEqual(call_args.kwargs["batch_size"], 123)

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_json_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    @patch('helper_functions.pipeline_steps.download_json')
    def test_json_to_postgres_test_run_uses_test_schema_suffix(
        self, mock_download, mock_connect, mock_get_schema, mock_drop,
        mock_enable_postgis, mock_create, mock_load_table, mock_create_views, mock_close, mock_load_cfg
    ):
        """Test test-run mode writes to isolated schemas and latest views."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_download.return_value = {"data": [{"id": 1}]}
        mock_get_schema.return_value = "buildings_sandbox_202406"
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432
        }

        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "buildings",
            "version": "202406",
            "test_run": True,
            "test_schema_suffix": "sandbox",
        }

        json_to_postgres(params)

        mock_get_schema.assert_called_once_with(
            "buildings",
            "202406",
            test_run=True,
            test_schema_suffix="sandbox",
        )
        mock_create_views.assert_called_once_with(
            mock_conn,
            "buildings_sandbox",
            "buildings_sandbox_202406",
        )

    @patch('helper_functions.pipeline_steps._resolve_municipality_bbox')
    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_json_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    @patch('helper_functions.pipeline_steps.download_json')
    def test_json_to_postgres_prunes_points_to_municipality_bbox_in_test_run(
        self,
        mock_download,
        mock_connect,
        mock_get_schema,
        mock_drop,
        mock_enable_postgis,
        mock_create,
        mock_load_table,
        mock_create_views,
        mock_close,
        mock_load_cfg,
        mock_resolve_bbox,
    ):
        """Test that test-run JSON ingestion prunes out-of-bbox GeoJSON points."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_get_schema.return_value = "buildings_test_202406"
        mock_resolve_bbox.return_value = "0,0,10,10"
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432
        }
        mock_download.return_value = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 1]}, "properties": {"id": 1}},
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [99, 99]}, "properties": {"id": 2}},
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []}, "properties": {"id": 3}},
            ],
        }

        params = {
            "source_url": "http://example.com/data.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "buildings",
            "table_name": "ryhti_buildings",
            "data_key": "features",
            "geom_srid": 3067,
            "test_run": True,
            "municipality_filter": ["092"],
        }

        json_to_postgres(params)

        mock_resolve_bbox.assert_called_once_with(
            connection=mock_conn,
            municipalities_schema="municipalities_test",
            municipalities_table="municipalities",
            municipality_codes=["092"],
            bbox_target_srid=3067,
        )

        filtered_data = mock_load_table.call_args.args[3]
        self.assertEqual(len(filtered_data["features"]), 2)
        self.assertEqual(filtered_data["features"][0]["properties"]["id"], 1)
        self.assertEqual(filtered_data["features"][1]["properties"]["id"], 3)


class TestOgcFeaturesToPostgres(unittest.TestCase):
    """Tests for ogc_features_to_postgres step handler."""

    def test_missing_collection_url(self):
        """Test error when collection_url is not provided."""
        params = {
            "db_config_path": "db_config.yaml",
            "schema_base_name": "topodb",
            "table_name": "building_part_area",
        }

        with self.assertRaises(ValueError) as context:
            ogc_features_to_postgres(params)

        self.assertIn("collection_url", str(context.exception))

    @patch.dict('os.environ', {'NLS_API_KEY': 'env-secret'})
    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_ogc_features_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_ogc_features_to_postgres_success(
        self, mock_connect, mock_get_schema, mock_exists, mock_enable_postgis, mock_create,
        mock_load_ogc, mock_create_views, mock_close, mock_load_cfg
    ):
        """Test successful OGC API ingestion with API key from environment variable."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_get_schema.return_value = "topodb_202406"
        mock_exists.return_value = False
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "collection_url": "https://open-api-geospatial.nls.fi/api/topodb/open-data/features/v1/collections/building_part_area",
            "api_key_env": "NLS_API_KEY",
            "api_key_auth_mode": "basic",
            "page_size": 1000,
            "db_config_path": "db_config.yaml",
            "schema_base_name": "topodb",
            "table_name": "building_part_area",
            "insert_batch_size": 100,
            "geom_srid": 3067,
            "target_geom_srid": 4326,
        }

        ogc_features_to_postgres(params)

        mock_enable_postgis.assert_called_once_with(mock_conn)
        mock_load_ogc.assert_called_once()
        load_kwargs = mock_load_ogc.call_args.kwargs
        self.assertEqual(load_kwargs["collection_url"], params["collection_url"])
        self.assertEqual(load_kwargs["api_key"], "env-secret")
        self.assertEqual(load_kwargs["api_key_auth_mode"], "basic")
        self.assertEqual(load_kwargs["limit"], 1000)
        self.assertEqual(load_kwargs["batch_size"], 100)
        self.assertEqual(load_kwargs["geom_srid"], 3067)
        self.assertEqual(load_kwargs["target_geom_srid"], 4326)
        self.assertEqual(load_kwargs["cache_version"], "202406")
        mock_create_views.assert_called_once_with(mock_conn, "topodb", "topodb_202406")

    @patch('helper_functions.pipeline_steps._resolve_municipality_bbox')
    @patch.dict('os.environ', {'NLS_API_KEY': 'env-secret'})
    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_ogc_features_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_ogc_features_to_postgres_with_bbox_from_municipality(
        self,
        mock_connect,
        mock_get_schema,
        mock_exists,
        mock_enable_postgis,
        mock_create,
        mock_load_ogc,
        mock_create_views,
        mock_close,
        mock_load_cfg,
        mock_resolve_bbox,
    ):
        """Test municipality bbox is injected into request params for OGC downloads."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_get_schema.return_value = "topodb_test_202406"
        mock_exists.return_value = False
        mock_resolve_bbox.return_value = "24.0,60.0,25.0,61.0"
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "collection_url": "https://open-api-geospatial.nls.fi/api/topodb/open-data/features/v1/collections/building_part_area",
            "api_key_env": "NLS_API_KEY",
            "api_key_auth_mode": "basic",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "topodb",
            "table_name": "building_part_area",
            "request_params": {"lang": "fi"},
            "bbox_from_municipality": True,
            "bbox_target_srid": 4326,
            "test_run": True,
            "test_schema_suffix": "test",
            "municipality_filter": ["092"],
        }

        ogc_features_to_postgres(params)

        mock_resolve_bbox.assert_called_once_with(
            connection=mock_conn,
            municipalities_schema="municipalities_test",
            municipalities_table="municipalities",
            municipality_codes=["092"],
            bbox_target_srid=4326,
        )

        load_kwargs = mock_load_ogc.call_args.kwargs
        self.assertEqual(load_kwargs["extra_params"]["lang"], "fi")
        self.assertEqual(load_kwargs["extra_params"]["bbox"], "24.0,60.0,25.0,61.0")
        self.assertIsNone(load_kwargs["cache_name_suffix"])

    @patch('helper_functions.pipeline_steps._resolve_municipality_bbox')
    @patch.dict('os.environ', {'NLS_API_KEY': 'env-secret'})
    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_ogc_features_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_ogc_features_to_postgres_with_multiple_municipalities_sets_cache_suffix(
        self,
        mock_connect,
        mock_get_schema,
        mock_exists,
        mock_enable_postgis,
        mock_create,
        mock_load_ogc,
        mock_create_views,
        mock_close,
        mock_load_cfg,
        mock_resolve_bbox,
    ):
        """Test municipality subsets get a distinct cache suffix for repeated downloads."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_get_schema.return_value = "topodb_test_202406"
        mock_exists.return_value = False
        mock_resolve_bbox.return_value = "24.0,60.0,25.0,61.0"
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "collection_url": "https://open-api-geospatial.nls.fi/api/topodb/open-data/features/v1/collections/building_part_area",
            "api_key_env": "NLS_API_KEY",
            "api_key_auth_mode": "basic",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "topodb",
            "table_name": "building_part_area",
            "bbox_from_municipality": True,
            "bbox_target_srid": 4326,
            "test_run": True,
            "test_schema_suffix": "test",
            "municipality_filter": ["092", "091"],
        }

        ogc_features_to_postgres(params)

        load_kwargs = mock_load_ogc.call_args.kwargs
        self.assertEqual(load_kwargs["cache_name_suffix"], "municipalities_092_091")

    @patch('helper_functions.pipeline_steps._resolve_municipality_bbox')
    @patch.dict('os.environ', {'NLS_API_KEY': 'env-secret'})
    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_ogc_features_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_ogc_features_bbox_ignored_when_not_test_run(
        self,
        mock_connect,
        mock_get_schema,
        mock_exists,
        mock_enable_postgis,
        mock_create,
        mock_load_ogc,
        mock_create_views,
        mock_close,
        mock_load_cfg,
        mock_resolve_bbox,
    ):
        """Test bbox_from_municipality does not alter request params when test_run is false."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_get_schema.return_value = "topodb_202406"
        mock_exists.return_value = False
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "collection_url": "https://open-api-geospatial.nls.fi/api/topodb/open-data/features/v1/collections/building_part_area",
            "api_key_env": "NLS_API_KEY",
            "api_key_auth_mode": "basic",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "topodb",
            "table_name": "building_part_area",
            "request_params": {"lang": "fi"},
            "bbox_from_municipality": True,
            "test_run": False,
        }

        ogc_features_to_postgres(params)

        mock_resolve_bbox.assert_not_called()
        load_kwargs = mock_load_ogc.call_args.kwargs
        self.assertEqual(load_kwargs["extra_params"], {"lang": "fi"})


class TestMunicipalityCodeNormalization(unittest.TestCase):
    """Tests for municipality code normalization utility."""

    def test_normalize_municipality_codes_zero_pads_values(self):
        self.assertEqual(_normalize_municipality_codes([92, "3", "001"]), ["092", "003", "001"])

    def test_normalize_municipality_codes_rejects_non_numeric(self):
        with self.assertRaises(ValueError):
            _normalize_municipality_codes(["09A"])


class TestGeojsonPointPruning(unittest.TestCase):
    """Tests for bbox parsing and GeoJSON point pruning helpers."""

    def test_parse_bbox_coordinates(self):
        self.assertEqual(
            _parse_bbox_coordinates("24.1, 60.2, 25.3, 61.4"),
            (24.1, 60.2, 25.3, 61.4),
        )

    def test_parse_bbox_coordinates_rejects_invalid_order(self):
        with self.assertRaises(ValueError):
            _parse_bbox_coordinates("25,60,24,61")

    def test_prune_geojson_points_to_bbox_keeps_non_points(self):
        data = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [24.5, 60.5]}, "properties": {"id": 1}},
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [26.0, 62.0]}, "properties": {"id": 2}},
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []}, "properties": {"id": 3}},
            ],
        }

        filtered_data, total_points, kept_points = _prune_geojson_points_to_bbox(
            data=data,
            bbox_value="24.0,60.0,25.0,61.0",
            data_key="features",
        )

        self.assertEqual(total_points, 2)
        self.assertEqual(kept_points, 1)
        self.assertEqual(len(filtered_data["features"]), 2)


class TestLoadOgcCacheToPg(unittest.TestCase):
    """Tests for load_ogc_cache_to_postgres step handler."""

    def test_missing_cache_file(self):
        """Test error when cache_file is not provided."""
        params = {
            "db_config_path": "db_config.yaml",
            "schema_base_name": "topodb",
            "table_name": "building_part_area",
        }

        with self.assertRaises(ValueError) as context:
            load_ogc_cache_to_postgres(params)

        self.assertIn("cache_file", str(context.exception))

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.load_ogc_cache_to_table')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.enable_postgis')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.get_versioned_schema_name')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_load_ogc_cache_to_postgres_success(
        self, mock_connect, mock_get_schema, mock_exists, mock_enable_postgis, mock_create,
        mock_load_cache, mock_create_views, mock_close, mock_load_cfg
    ):
        """Test successful cached OGC load."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_get_schema.return_value = "topodb_202406"
        mock_exists.return_value = False
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "cache_file": "/path/to/cache.json",
            "db_config_path": "db_config.yaml",
            "schema_base_name": "topodb",
            "table_name": "building_part_area",
            "insert_batch_size": 200,
            "drop_existing": True,
        }

        load_ogc_cache_to_postgres(params)

        mock_enable_postgis.assert_called_once_with(mock_conn)
        mock_load_cache.assert_called_once()
        cache_kwargs = mock_load_cache.call_args.kwargs
        self.assertEqual(cache_kwargs["cache_file"], "/path/to/cache.json")
        self.assertEqual(cache_kwargs["batch_size"], 200)
        self.assertEqual(cache_kwargs["cache_version"], "202406")
        mock_create_views.assert_called_once_with(mock_conn, "topodb", "topodb_202406")


class TestSqlTemplateToPostgres(unittest.TestCase):
    """Tests for sql_template_to_postgres step handler."""

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.execute_sql')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_sql_template_to_postgres_success(
        self,
        mock_connect,
        mock_execute_sql,
        mock_schema_exists,
        mock_drop_schema,
        mock_create_schema,
        mock_create_views,
        mock_close,
        mock_load_cfg,
    ):
        """Test executing templated SQL with versioned schemas and latest views."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_execute_sql.return_value = True
        mock_schema_exists.return_value = False
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "sql": (
                "DROP SCHEMA IF EXISTS {buildings_plus_schema} CASCADE; "
                "CREATE SCHEMA {buildings_plus_schema}; "
                "SELECT * FROM {buildings_schema}.ryhti_buildings "
                "JOIN {topodb_schema}.building_part_area ON true;"
            ),
            "db_config_path": "db_config.yaml",
            "version": "202406",
            "versioned_schema_vars": {
                "buildings_schema": "buildings",
                "topodb_schema": "topodb",
                "buildings_plus_schema": "buildings_plus",
            },
            "managed_versioned_schema_var": "buildings_plus_schema",
            "latest_schema_base_name": "buildings_plus",
        }

        sql_template_to_postgres(params)

        mock_schema_exists.assert_called_once_with(mock_conn, "buildings_plus_202406")
        mock_drop_schema.assert_not_called()
        mock_create_schema.assert_called_once_with(mock_conn, "buildings_plus_202406")
        mock_execute_sql.assert_called_once()
        rendered_sql = mock_execute_sql.call_args.args[1]
        self.assertIn("buildings_202406.ryhti_buildings", rendered_sql)
        self.assertIn("topodb_202406.building_part_area", rendered_sql)
        mock_create_views.assert_called_once_with(
            mock_conn,
            "buildings_plus",
            "buildings_plus_202406",
        )
        mock_close.assert_called_once_with(mock_conn)

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.execute_sql')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_sql_template_to_postgres_test_run_uses_test_schemas(
        self,
        mock_connect,
        mock_execute_sql,
        mock_close,
        mock_load_cfg,
    ):
        """Test test-run SQL rendering uses isolated test schemas."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "sql": "SELECT * FROM {buildings_schema}.ryhti_buildings;",
            "db_config_path": "db_config.yaml",
            "version": "202406",
            "versioned_schema_vars": {
                "buildings_schema": "buildings",
            },
            "test_run": True,
        }

        sql_template_to_postgres(params)

        rendered_sql = mock_execute_sql.call_args.args[1]
        self.assertIn("FROM buildings_test_202406.ryhti_buildings", rendered_sql)
        mock_close.assert_called_once_with(mock_conn)

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.execute_sql')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_sql_template_to_postgres_legacy_municipality_placeholder_is_empty(
        self,
        mock_connect,
        mock_execute_sql,
        mock_close,
        mock_load_cfg,
    ):
        """Test legacy municipality placeholders remain backward-compatible no-ops."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "sql": (
                "SELECT * FROM {buildings_schema}.ryhti_buildings "
                "WHERE building_key IS NOT NULL {municipality_filter_and_clause};"
            ),
            "db_config_path": "db_config.yaml",
            "version": "202406",
            "versioned_schema_vars": {
                "buildings_schema": "buildings",
            },
            "test_run": True,
        }

        sql_template_to_postgres(params)

        rendered_sql = mock_execute_sql.call_args.args[1]
        self.assertEqual(
            rendered_sql,
            "SELECT * FROM buildings_test_202406.ryhti_buildings WHERE building_key IS NOT NULL ;",
        )
        mock_close.assert_called_once_with(mock_conn)

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.execute_sql')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_sql_template_to_postgres_test_run_custom_suffix(
        self,
        mock_connect,
        mock_execute_sql,
        mock_close,
        mock_load_cfg,
    ):
        """Test custom test schema suffix is applied in SQL template rendering."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "sql": "SELECT * FROM {buildings_schema}.ryhti_buildings;",
            "db_config_path": "db_config.yaml",
            "version": "202406",
            "versioned_schema_vars": {
                "buildings_schema": "buildings",
            },
            "test_run": True,
            "test_schema_suffix": "sandbox",
        }

        sql_template_to_postgres(params)

        rendered_sql = mock_execute_sql.call_args.args[1]
        self.assertIn("FROM buildings_sandbox_202406.ryhti_buildings", rendered_sql)
        mock_close.assert_called_once_with(mock_conn)

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.execute_sql')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_sql_template_to_postgres_auto_managed_schema_resolution(
        self,
        mock_connect,
        mock_execute_sql,
        mock_schema_exists,
        mock_drop_schema,
        mock_create_schema,
        mock_create_views,
        mock_close,
        mock_load_cfg,
    ):
        """Test managed schema lifecycle is auto-resolved from latest_schema_base_name."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_execute_sql.return_value = True
        mock_schema_exists.return_value = False
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "sql": "CREATE TABLE {buildings_plus_schema}.buildings_plus AS SELECT 1;",
            "db_config_path": "db_config.yaml",
            "version": "202406",
            "versioned_schema_vars": {
                "buildings_schema": "buildings",
                "buildings_plus_schema": "buildings_plus",
            },
            "latest_schema_base_name": "buildings_plus",
        }

        sql_template_to_postgres(params)

        mock_schema_exists.assert_called_once_with(mock_conn, "buildings_plus_202406")
        mock_drop_schema.assert_not_called()
        mock_create_schema.assert_called_once_with(mock_conn, "buildings_plus_202406")
        mock_execute_sql.assert_called_once()
        mock_create_views.assert_called_once_with(
            mock_conn,
            "buildings_plus",
            "buildings_plus_202406",
        )
        mock_close.assert_called_once_with(mock_conn)

    @patch('helper_functions.pipeline_steps.load_db_config')
    @patch('helper_functions.pipeline_steps.close_connection')
    @patch('helper_functions.pipeline_steps.create_latest_schema_views')
    @patch('helper_functions.pipeline_steps.create_schema')
    @patch('helper_functions.pipeline_steps.drop_schema')
    @patch('helper_functions.pipeline_steps.schema_exists')
    @patch('helper_functions.pipeline_steps.execute_sql')
    @patch('helper_functions.pipeline_steps.connect_postgres')
    def test_sql_template_to_postgres_test_run_latest_schema_views(
        self,
        mock_connect,
        mock_execute_sql,
        mock_schema_exists,
        mock_drop_schema,
        mock_create_schema,
        mock_create_views,
        mock_close,
        mock_load_cfg,
    ):
        """Test latest schema views use suffixed schema names in test-run mode."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_execute_sql.return_value = True
        mock_schema_exists.return_value = False
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "sql": "CREATE TABLE {buildings_plus_schema}.buildings_plus AS SELECT 1;",
            "db_config_path": "db_config.yaml",
            "version": "202406",
            "versioned_schema_vars": {
                "buildings_plus_schema": "buildings_plus",
            },
            "managed_versioned_schema_var": "buildings_plus_schema",
            "latest_schema_base_name": "buildings_plus",
            "test_run": True,
            "test_schema_suffix": "sandbox",
        }

        sql_template_to_postgres(params)

        mock_create_views.assert_called_once_with(
            mock_conn,
            "buildings_plus_sandbox",
            "buildings_plus_sandbox_202406",
        )

    def test_sql_template_to_postgres_ambiguous_auto_managed_schema_resolution(self):
        """Test explicit error when latest schema matches multiple versioned schema variables."""
        params = {
            "sql": "SELECT 1;",
            "versioned_schema_vars": {
                "buildings_plus_schema": "buildings_plus",
                "other_buildings_plus_schema": "buildings_plus",
            },
            "latest_schema_base_name": "buildings_plus",
        }

        with self.assertRaises(ValueError) as context:
            sql_template_to_postgres(params)

        self.assertIn("Multiple versioned_schema_vars", str(context.exception))

    @patch('helper_functions.pipeline_steps.load_db_config')
    def test_sql_template_to_postgres_invalid_managed_schema_var(self, mock_load_cfg):
        """Test error when managed_versioned_schema_var does not match template context."""
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "sql": "SELECT 1;",
            "db_config_path": "db_config.yaml",
            "versioned_schema_vars": {
                "buildings_plus_schema": "buildings_plus",
            },
            "managed_versioned_schema_var": "missing_schema_var",
        }

        with self.assertRaises(ValueError) as context:
            sql_template_to_postgres(params)

        self.assertIn("missing_schema_var", str(context.exception))

    def test_sql_template_to_postgres_missing_source(self):
        """Test error when neither sql_file nor sql is provided."""
        with self.assertRaises(ValueError) as context:
            sql_template_to_postgres({})

        self.assertIn("sql_file", str(context.exception))

    @patch('helper_functions.pipeline_steps.load_db_config')
    def test_sql_template_to_postgres_missing_template_var(self, mock_load_cfg):
        """Test error when SQL template references a missing placeholder."""
        mock_load_cfg.return_value = {
            'host': 'localhost',
            'user': 'postgres',
            'password': 'password',
            'database': 'buildings',
            'port': 5432,
        }

        params = {
            "sql": "SELECT * FROM {missing_schema}.example;",
            "db_config_path": "db_config.yaml",
        }

        with self.assertRaises(ValueError) as context:
            sql_template_to_postgres(params)

        self.assertIn("missing_schema", str(context.exception))


if __name__ == '__main__':
    unittest.main()

