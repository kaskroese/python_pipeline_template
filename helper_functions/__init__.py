"""Helper functions package for data pipeline operations."""

from .postgres_functions import (
    connect_postgres,
    execute_sql,
    execute_sql_file,
    close_connection,
)
from .pipeline_functions import (
    ensure_dir,
    register_step,
    STEP_HANDLERS,
    data_ingestion,
    data_processing,
    data_export,
)
from .schema_functions import (
    get_versioned_schema_name,
    schema_exists,
    drop_schema,
    create_schema,
    enable_postgis,
    get_tables_in_schema,
    create_latest_schema_views,
)
from .json_functions import (
    download_json,
    download_ogc_features,
    load_json_file,
    create_table_from_records,
    load_json_to_table,
    load_ogc_features_to_table,
    load_ogc_cache_to_table,
)
from .pipeline_steps import load_db_config
# Import pipeline_steps to register generic step handlers
from . import pipeline_steps

__all__ = [
    "connect_postgres",
    "execute_sql",
    "execute_sql_file",
    "close_connection",
    "ensure_dir",
    "register_step",
    "STEP_HANDLERS",
    "data_ingestion",
    "data_processing",
    "data_export",
    "get_versioned_schema_name",
    "schema_exists",
    "drop_schema",
    "create_schema",
    "enable_postgis",
    "get_tables_in_schema",
    "create_latest_schema_views",
    "download_json",
    "download_ogc_features",
    "load_json_file",
    "create_table_from_records",
    "load_json_to_table",
    "load_ogc_features_to_table",
    "load_ogc_cache_to_table",
    "load_db_config",
]

