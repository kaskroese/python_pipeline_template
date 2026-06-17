"""
PostgreSQL helper functions for data pipeline operations.

This module provides utilities for connecting to PostgreSQL databases,
executing SQL queries, and managing database connections.
"""

import psycopg2
import psycopg2.extras
import logging
from typing import Any, List, Dict, Optional, Union

logger = logging.getLogger(__name__)


def connect_postgres(
    host: str,
    user: str,
    password: str,
    database: str,
    port: int = 5432,
) -> psycopg2.extensions.connection:
    """
    Establish a connection to a PostgreSQL database.

    Args:
        host (str): Hostname or IP address of the PostgreSQL server
        user (str): Username for authentication
        password (str): Password for authentication
        database (str): Database name to connect to
        port (int): Port number (default: 5432)

    Returns:
        psycopg2.extensions.connection: Database connection object

    Raises:
        psycopg2.OperationalError: If connection fails
    """
    try:
        connection = psycopg2.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
        )
        logger.info(f"Successfully connected to PostgreSQL database '{database}' at {host}:{port}")
        return connection
    except psycopg2.OperationalError as e:
        logger.error(f"Failed to connect to PostgreSQL database: {e}")
        raise


def execute_sql(
    connection: psycopg2.extensions.connection,
    sql: str,
    return_results: bool = False,
    fetch_one: bool = False,
) -> Optional[Union[List[Dict[str, Any]], Dict[str, Any], bool]]:
    """
    Execute a SQL query (string) against the database.

    Args:
        connection (psycopg2.extensions.connection): Active database connection
        sql (str): SQL query string to execute
        return_results (bool): If True, fetch and return results as dictionaries.
                              If False, return True on success (for INSERT/UPDATE/DELETE)
        fetch_one (bool): If True and return_results is True, fetch only one row

    Returns:
        Optional[Union[List[Dict], Dict, bool]]:
            - If return_results=True and fetch_one=True: Single row as dict or None
            - If return_results=True and fetch_one=False: List of rows as dicts
            - If return_results=False: True on success
            - None on error or no results

    Raises:
        psycopg2.DatabaseError: If SQL execution fails
    """
    cursor = None
    try:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(sql)

        # Check if this is a SELECT query (has results to fetch)
        if cursor.description is not None:
            if fetch_one:
                result = cursor.fetchone()
                logger.info("SQL query executed successfully (fetched one row)")
                return result
            else:
                results = cursor.fetchall()
                logger.info(f"SQL query executed successfully (fetched {len(results)} rows)")
                return results
        else:
            # For INSERT/UPDATE/DELETE queries
            connection.commit()
            rows_affected = cursor.rowcount
            logger.info(f"SQL query executed successfully ({rows_affected} rows affected)")
            return True

    except psycopg2.DatabaseError as e:
        connection.rollback()
        logger.error(f"Database error during SQL execution: {e}")
        raise
    finally:
        if cursor:
            cursor.close()


def execute_sql_file(
    connection: psycopg2.extensions.connection,
    filepath: str,
    return_results: bool = False,
    fetch_one: bool = False,
) -> Optional[Union[List[Dict[str, Any]], Dict[str, Any], bool]]:
    """
    Execute a SQL query from a file against the database.

    Args:
        connection (psycopg2.extensions.connection): Active database connection
        filepath (str): Path to the SQL file
        return_results (bool): If True, fetch and return results as dictionaries.
                              If False, return True on success
        fetch_one (bool): If True and return_results is True, fetch only one row

    Returns:
        Optional[Union[List[Dict], Dict, bool]]:
            - If return_results=True and fetch_one=True: Single row as dict or None
            - If return_results=True and fetch_one=False: List of rows as dicts
            - If return_results=False: True on success
            - None on error or no results

    Raises:
        FileNotFoundError: If SQL file is not found
        psycopg2.DatabaseError: If SQL execution fails
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            sql = f.read()
        logger.info(f"Loaded SQL file: {filepath}")
        return execute_sql(connection, sql, return_results, fetch_one)
    except FileNotFoundError as e:
        logger.error(f"SQL file not found: {filepath}")
        raise


def close_connection(connection: psycopg2.extensions.connection) -> None:
    """
    Close a PostgreSQL database connection.

    Args:
        connection (psycopg2.extensions.connection): Database connection to close

    Returns:
        None
    """
    if connection:
        try:
            connection.close()
            logger.info("Database connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")

