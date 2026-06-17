"""
Generic pipeline functions for data ingestion, processing and export.

These functions are intentionally generic and driven entirely by the
`params` dictionary so they can be reused across projects. They also
provide a simple registry-based mechanism to register step handlers.
"""
from typing import Any, Dict, List, Optional, Callable
import csv
import logging
import os

logger = logging.getLogger(__name__)

# Registry for step handlers
STEP_HANDLERS: Dict[str, Callable[[Dict[str, Any]], None]] = {}


def ensure_dir(path: str) -> None:
    """Create directory if it does not exist.

    Args:
        path: Path to create. If empty or None the call is a no-op.
    """
    if not path:
        return
    os.makedirs(path, exist_ok=True)


def register_step(step_type: str) -> Callable:
    """Decorator that registers a function as a handler for `step_type`.

    Usage:
        @register_step("data_ingestion")
        def my_ingest(params):
            ...

    Args:
        step_type: The step type string used in the config.

    Returns:
        Decorator that registers the function and returns it unchanged.
    """

    def decorator(func: Callable[[Dict[str, Any]], None]) -> Callable:
        STEP_HANDLERS[step_type] = func
        return func

    return decorator


@register_step("data_ingestion")
def data_ingestion(params: Dict[str, Any]) -> None:
    """Write rows to a CSV file according to `params`.

    Expected params:
        output_path: str - path to write CSV
        headers: List[str] - list of column names
        rows: List[List[Any]] - list of rows (each a list, matching headers)

    The function is generic: it writes whatever headers and rows are
    provided. If none are provided a single demo row is written so the
    template runs out-of-the-box.
    """
    output_path = params.get("output_path", "./data/raw/ingested_data.csv")
    headers: List[str] = params.get("headers", ["id", "name", "value"])
    rows: List[List[Any]] = params.get("rows", [[1, "sample_record", 42]])

    ensure_dir(os.path.dirname(output_path))

    logger.info("Creating CSV at %s", output_path)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)

    logger.info("Data ingested to: %s", output_path)


@register_step("data_processing")
def data_processing(params: Dict[str, Any]) -> None:
    """Read a CSV, apply operations and write the result to CSV.

    Expected params:
        input_path: str - path to read CSV from
        output_path: str - path to write CSV to
        operations: List[Dict[str, Any]] - list of operations to apply

    Supported operations:
        - multiply: multiply a numeric column and store in an output column
            {type: "multiply", column: "value", output: "transformed", factor: 2}
        - add_column: add a static column
            {type: "add_column", output: "source", value: "example"}
        - copy: copy an existing column to a new name
            {type: "copy", column: "old", output: "new"}

    The function is intentionally minimal and easy to extend.
    """
    input_path = params.get("input_path", "./data/raw/ingested_data.csv")
    output_path = params.get(
        "output_path", "./data/processed/cleaned_data.csv"
    )
    operations: List[Dict[str, Any]] = params.get("operations", [])

    ensure_dir(os.path.dirname(output_path))

    if not os.path.exists(input_path):
        logger.error("Input file not found: %s", input_path)
        return

    logger.info("Processing data from %s", input_path)

    rows: List[Dict[str, Any]] = []
    with open(input_path, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            for op in operations:
                if not isinstance(op, dict):
                    continue
                op_type = op.get("type")
                if op_type == "multiply":
                    col = op.get("column")
                    out = op.get("output")
                    factor = op.get("factor", 1)
                    try:
                        row[out] = str(int(row.get(col, 0)) * int(factor))
                    except Exception:
                        row[out] = row.get(col)
                elif op_type == "add_column":
                    out = op.get("output")
                    val = op.get("value", "")
                    row[out] = val
                elif op_type == "copy":
                    col = op.get("column")
                    out = op.get("output")
                    row[out] = row.get(col)
                else:
                    logger.debug("Unknown operation type: %s", op_type)
            rows.append(row)

    fieldnames: List[str] = list(rows[0].keys()) if rows else []

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Data processed and exported to: %s", output_path)


@register_step("data_export")
def data_export(params: Dict[str, Any]) -> None:
    """Copy or move a file from input_path to export_path.

    Expected params:
        input_path: str - source file
        export_path: str - destination file
    """
    input_path = params.get("input_path", "./data/processed/cleaned_data.csv")
    export_path = params.get("export_path", "./data/output/final_results.csv")

    ensure_dir(os.path.dirname(export_path))

    if not os.path.exists(input_path):
        logger.error("Input file not found: %s", input_path)
        return

    logger.info("Exporting final data from %s to %s", input_path, export_path)

    with open(input_path, "r", encoding="utf-8") as fin:
        content = fin.read()

    with open(export_path, "w", encoding="utf-8") as fout:
        fout.write(content)

    logger.info("Data export completed: %s", export_path)

