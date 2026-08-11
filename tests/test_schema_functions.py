"""
Unit tests for schema_functions module.
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
import psycopg2
from helper_functions.schema_functions import (
    get_versioned_schema_name,
    schema_exists,
    drop_schema,
    create_schema,
    enable_postgis,
    get_tables_in_schema,
    create_latest_schema_views,
)


class TestGetVersionedSchemaName(unittest.TestCase):
    """Tests for get_versioned_schema_name function."""

    def test_with_explicit_version(self):
        """Test schema name generation with explicit version."""
        result = get_versioned_schema_name("buildings", "202406")
        self.assertEqual(result, "buildings_202406")

    def test_with_different_base_names(self):
        """Test schema name generation with different base names."""
        result1 = get_versioned_schema_name("addresses", "202406")
        result2 = get_versioned_schema_name("my_schema", "202406")
        self.assertEqual(result1, "addresses_202406")
        self.assertEqual(result2, "my_schema_202406")

    def test_without_version_uses_current_month(self):
        """Test that version defaults to current YYYYMM."""
        result = get_versioned_schema_name("buildings")
        current_yyyymm = datetime.now().strftime('%Y%m')
        self.assertEqual(result, f"buildings_{current_yyyymm}")

    def test_invalid_version_format_short(self):
        """Test that short version raises ValueError."""
        with self.assertRaises(ValueError):
            get_versioned_schema_name("buildings", "2024")

    def test_invalid_version_format_long(self):
        """Test that long version raises ValueError."""
        with self.assertRaises(ValueError):
            get_versioned_schema_name("buildings", "20240601")

    def test_invalid_version_non_numeric(self):
        """Test that non-numeric version raises ValueError."""
        with self.assertRaises(ValueError):
            get_versioned_schema_name("buildings", "202a06")

    def test_test_run_schema_name_uses_default_suffix(self):
        """Test test-run schema naming with default suffix."""
        result = get_versioned_schema_name("buildings", "202406", test_run=True)
        self.assertEqual(result, "buildings_test_202406")

    def test_test_run_schema_name_uses_custom_suffix(self):
        """Test test-run schema naming with custom suffix."""
        result = get_versioned_schema_name(
            "buildings",
            "202406",
            test_run=True,
            test_schema_suffix="sandbox",
        )
        self.assertEqual(result, "buildings_sandbox_202406")

    def test_invalid_test_schema_suffix(self):
        """Test invalid test schema suffix raises ValueError."""
        with self.assertRaises(ValueError):
            get_versioned_schema_name(
                "buildings",
                "202406",
                test_run=True,
                test_schema_suffix="",
            )


class TestSchemaExists(unittest.TestCase):
    """Tests for schema_exists function."""

    def test_schema_exists_true(self):
        """Test when schema exists."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [True]

        result = schema_exists(mock_conn, "test_schema")

        self.assertTrue(result)
        mock_cursor.execute.assert_called_once()
        mock_cursor.close.assert_called_once()

    def test_schema_exists_false(self):
        """Test when schema does not exist."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [False]

        result = schema_exists(mock_conn, "test_schema")

        self.assertFalse(result)

    def test_schema_exists_error_handling(self):
        """Test error handling when query fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.DatabaseError("Connection error")

        with self.assertRaises(psycopg2.DatabaseError):
            schema_exists(mock_conn, "test_schema")


class TestDropSchema(unittest.TestCase):
    """Tests for drop_schema function."""

    def test_drop_schema_success(self):
        """Test successful schema drop."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        drop_schema(mock_conn, "test_schema")

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    def test_drop_schema_error_handling(self):
        """Test error handling when drop fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.DatabaseError("Drop failed")

        with self.assertRaises(psycopg2.DatabaseError):
            drop_schema(mock_conn, "test_schema")

        mock_conn.rollback.assert_called_once()


class TestCreateSchema(unittest.TestCase):
    """Tests for create_schema function."""

    @patch('helper_functions.schema_functions.schema_exists')
    def test_create_schema_success(self, mock_schema_exists):
        """Test successful schema creation."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_schema_exists.return_value = False

        create_schema(mock_conn, "test_schema")

        mock_cursor.execute.assert_called_once_with("CREATE SCHEMA IF NOT EXISTS test_schema;")
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch('helper_functions.schema_functions.schema_exists')
    def test_create_schema_skips_when_schema_exists(self, mock_schema_exists):
        """Test schema creation is skipped when schema already exists."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_schema_exists.return_value = True

        create_schema(mock_conn, "test_schema")

        mock_cursor.execute.assert_not_called()
        mock_conn.commit.assert_not_called()

    @patch('helper_functions.schema_functions.schema_exists')
    def test_create_schema_error_handling(self, mock_schema_exists):
        """Test error handling when create fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_schema_exists.return_value = False
        mock_cursor.execute.side_effect = psycopg2.DatabaseError("Create failed")

        with self.assertRaises(psycopg2.DatabaseError):
            create_schema(mock_conn, "test_schema")

        mock_conn.rollback.assert_called_once()


class TestEnablePostGis(unittest.TestCase):
    """Tests for enable_postgis function."""

    def test_enable_postgis_success(self):
        """Test successful PostGIS extension enablement."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [False]

        enable_postgis(mock_conn)

        self.assertEqual(mock_cursor.execute.call_count, 2)
        mock_cursor.execute.assert_any_call("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis');")
        mock_cursor.execute.assert_any_call("CREATE EXTENSION postgis;")
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    def test_enable_postgis_skips_when_already_enabled(self):
        """Test PostGIS enablement is skipped when extension already exists."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [True]

        enable_postgis(mock_conn)

        mock_cursor.execute.assert_called_once_with(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis');"
        )
        mock_conn.commit.assert_not_called()
        mock_cursor.close.assert_called_once()

    def test_enable_postgis_error_handling(self):
        """Test error handling when PostGIS enablement fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [False]
        mock_cursor.execute.side_effect = [
            None,
            psycopg2.DatabaseError("Extension creation failed"),
        ]

        with self.assertRaises(psycopg2.DatabaseError):
            enable_postgis(mock_conn)

        mock_conn.rollback.assert_called_once()


class TestGetTablesInSchema(unittest.TestCase):
    """Tests for get_tables_in_schema function."""

    def test_get_tables_success(self):
        """Test successful table retrieval."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("table1",), ("table2",), ("table3",)]

        result = get_tables_in_schema(mock_conn, "test_schema")

        self.assertEqual(result, ["table1", "table2", "table3"])
        mock_cursor.close.assert_called_once()

    def test_get_tables_empty(self):
        """Test when schema has no tables."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = get_tables_in_schema(mock_conn, "test_schema")

        self.assertEqual(result, [])

    def test_get_tables_error_handling(self):
        """Test error handling when query fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.DatabaseError("Query failed")

        with self.assertRaises(psycopg2.DatabaseError):
            get_tables_in_schema(mock_conn, "test_schema")


class TestCreateLatestSchemaViews(unittest.TestCase):
    """Tests for create_latest_schema_views function."""

    @patch('helper_functions.schema_functions.create_schema')
    @patch('helper_functions.schema_functions.get_tables_in_schema')
    @patch('helper_functions.schema_functions._get_geometry_column_info')
    def test_create_latest_schema_views_no_geom(self, mock_get_geom_info, mock_get_tables, mock_create_schema):
        """Test view creation for non-spatial tables with drop/recreate semantics."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [('col1',), ('col2',)]
        mock_get_tables.return_value = ["my_table"]
        mock_get_geom_info.return_value = None

        create_latest_schema_views(mock_conn, "base_name", "versioned_schema")

        mock_create_schema.assert_called_once_with(mock_conn, "base_name")
        
        self.assertEqual(mock_cursor.execute.call_count, 3)

        drop_view_sql = mock_cursor.execute.call_args_list[1][0][0]
        create_view_sql = mock_cursor.execute.call_args_list[2][0][0]
        self.assertIn("DROP VIEW IF EXISTS base_name.my_table CASCADE;", drop_view_sql)
        self.assertIn("CREATE VIEW base_name.my_table AS", create_view_sql)
        self.assertIn('t."col1"', create_view_sql)
        self.assertIn('t."col2"', create_view_sql)
        self.assertNotIn("CAST", create_view_sql)

    @patch('helper_functions.schema_functions.create_schema')
    @patch('helper_functions.schema_functions.get_tables_in_schema')
    @patch('helper_functions.schema_functions._get_geometry_column_info')
    def test_create_latest_schema_views_with_geom(self, mock_get_geom_info, mock_get_tables, mock_create_schema):
        """Test view creation for spatial tables with geometry cast preserved."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [('id',), ('geom',)]
        mock_get_tables.return_value = ["spatial_table"]
        mock_get_geom_info.return_value = ('geom', 'POLYGON', 3067)

        create_latest_schema_views(mock_conn, "latest_schema", "versioned_schema")

        mock_create_schema.assert_called_once_with(mock_conn, "latest_schema")
        
        self.assertEqual(mock_cursor.execute.call_count, 3)

        drop_view_sql = mock_cursor.execute.call_args_list[1][0][0]
        create_view_sql = mock_cursor.execute.call_args_list[2][0][0]

        self.assertIn("DROP VIEW IF EXISTS latest_schema.spatial_table CASCADE;", drop_view_sql)
        self.assertIn("CREATE VIEW latest_schema.spatial_table AS", create_view_sql)
        self.assertIn('CAST(t."geom" AS geometry(POLYGON, 3067)) AS "geom"', create_view_sql)
        self.assertIn('t."id"', create_view_sql)

    @patch('helper_functions.schema_functions.create_schema')
    @patch('helper_functions.schema_functions.get_tables_in_schema')
    def test_create_latest_schema_views_empty(self, mock_get_tables, mock_create_schema):
        """Test that no views are created when the source schema has no tables."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_tables.return_value = []

        create_latest_schema_views(mock_conn, "base_name", "versioned_schema")

        mock_create_schema.assert_called_once()
        mock_cursor.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
