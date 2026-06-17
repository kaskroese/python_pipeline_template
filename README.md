# Python Data Pipeline Boilerplate

This project provides a boilerplate for a Python-based data pipeline with configurable steps and Docker support. It's designed to be a starting point for building robust and scalable data processing workflows.

## Features

*   **Configurable Steps**: Define your pipeline steps and their parameters in a `config.yaml` file.
*   **Modular Design**: Easily extend with new step types and logic in `main.py`.
*   **Docker Support**: Containerize your pipeline for consistent execution across different environments.
*   **Logging**: Basic logging is set up to track pipeline execution.
*   **Working Demo**: Out-of-the-box demo with CSV data ingestion, transformation, and export.

## Demo Overview

This template includes a **working demo** that demonstrates a complete data pipeline:

1. **Data Ingestion** (`step_1_ingest_raw_data`): Creates a demo CSV file with sample data
2. **Data Processing** (`step_2_clean_and_transform`): Reads the CSV, adds a transformed column (doubles the value), and writes to processed output
3. **Data Export** (`step_3_export_to_database`): Copies the processed data to the final output location

Each run overwrites the output files, making it safe to run the pipeline multiple times.

## Project Structure

```
.
├── main.py                 # Main Python script to run the pipeline
├── config.yaml             # Pipeline configuration (steps and parameters)
├── Dockerfile              # Dockerfile to build the pipeline image
├── Pipfile                 # Python dependency management
├── Pipfile.lock            # Locked versions of dependencies
├── helper_functions/       # Reusable helper functions for pipeline steps
│   ├── __init__.py         # Package initialization
│   └── postgres_functions.py  # PostgreSQL database operations
├── sql_examples/           # Example SQL files for database operations
│   ├── create_table.sql    # Example: Create a table
│   ├── select_data.sql     # Example: Select data
│   └── insert_data.sql     # Example: Insert data
├── data/                   # Data directory (auto-created during pipeline execution)
│   ├── raw/                # Raw ingested data
│   ├── processed/          # Processed/transformed data
│   └── output/             # Final output data
└── README.md               # This README file
```

## Getting Started

### Prerequisites

*   Python 3.9+
*   pip (Python package installer)
*   Docker (if you plan to run with Docker)

### 1. Local Setup and Execution

1.  **Clone the repository (if applicable) or create the files in a new directory.**

2.  **Install dependencies using pipenv:**
    ```bash
    pipenv install
    ```

3.  **Run the pipeline:**
    ```bash
    pipenv run python main.py
    ```
    Or activate the pipenv shell first:
    ```bash
    pipenv shell
    python main.py
    ```
    The pipeline will read the `config.yaml` file by default and execute the defined steps.

    **Output**: The pipeline will create a `data/` directory with three subdirectories:
    - `data/raw/ingested_data.csv` - Demo CSV with sample data (id, name, value)
    - `data/processed/cleaned_data.csv` - Transformed data with added `transformed_value` column
    - `data/output/final_results.csv` - Final output file

    Files are overwritten on each run, so you can run the pipeline multiple times without conflicts.

### 2. Docker Setup and Execution

1.  **Build the Docker image:**
    Navigate to the project root directory (where `Dockerfile` is located) and run:
    ```bash
    docker build -t python-pipeline-boilerplate .
    ```

2.  **Run the Docker container:**
    ```bash
    docker run python-pipeline-boilerplate
    ```
    This will execute the `main.py` script inside the container using the `config.yaml` file.

### Customizing the Pipeline

#### `config.yaml`

This file defines the sequence and parameters of your pipeline steps.

```yaml
pipeline_steps:
  step_1_ingest_raw_data:
    type: data_ingestion
    params:
      source: "s3://my-bucket/raw-data/"
      format: "csv"
      output_path: "./data/raw/ingested_data.csv"

  step_2_clean_and_transform:
    type: data_processing
    params:
      input_path: "./data/raw/ingested_data.csv"
      output_path: "./data/processed/cleaned_data.csv"

  step_3_export_to_database:
    type: data_export
    params:
      input_path: "./data/processed/cleaned_data.csv"
      export_path: "./data/output/final_results.csv"
```

*   **`pipeline_steps`**: A dictionary where keys are unique step names (e.g., `step_1_ingest_raw_data`) and values are the step configurations.
*   **`type`**: A string indicating the type of operation this step performs (e.g., `data_ingestion`, `data_processing`, `data_export`). You will define the logic for these types in `main.py`.
*   **`params`**: A dictionary of parameters specific to this step. These parameters are passed to the `run_step` function in `main.py`.

#### `main.py`

This is where the core logic for executing steps resides.

1.  **`load_config(config_path)`**: Loads the YAML configuration.
2.  **`run_step(step_name, step_config)`**: This function dispatches to a handler for each step `type`.
    *   Instead of editing `run_step`, register new handlers with the `register_step` decorator in `main.py` (see the "Example Usage in Pipeline" section).
    *   Access step-specific parameters using `step_config.get('params', {})`.

#### Adding New Step Types

To add a new type of step (e.g., `model_training`):

1.  **Update `config.yaml`**: Add a new step with `type: model_training` and relevant `params`.
    ```yaml
    # ...
    step_4_train_model:
      type: model_training
      params:
        data_path: "./data/processed/cleaned_data.parquet"
        model_type: "RandomForest"
        hyperparameters:
          n_estimators: 100
          max_depth: 10
    ```
2.  **Update `main.py`**: Add an `elif` block in the `run_step` function to handle the `model_training` type.
    ```python
    def run_step(step_name, step_config):
        # ... existing code ...
        elif step_type == 'model_training':
            logging.info(f"Performing model training with params: {params}")
            # Add your model training logic here
            # Example:
            # from sklearn.ensemble import RandomForestClassifier
            # model = RandomForestClassifier(**params.get('hyperparameters', {}))
            # model.fit(load_data(params['data_path']), load_labels())
            pass
        # ... existing code ...
    ```

## Helper Functions

The `helper_functions/` package provides reusable utilities for common data pipeline operations.

### PostgreSQL Functions

Located in `helper_functions/postgres_functions.py`, these functions handle database operations:

#### `connect_postgres(host, user, password, database, port=5432)`
Establishes a connection to a PostgreSQL database.

```python
from helper_functions import connect_postgres

conn = connect_postgres(
    host="localhost",
    user="postgres",
    password="your_password",
    database="your_database"
)
```

#### `execute_sql(connection, sql, return_results=False, fetch_one=False)`
Executes SQL queries (as strings) with flexible result handling.

```python
from helper_functions import execute_sql

# SELECT query - return results
results = execute_sql(
    conn,
    "SELECT * FROM sample_data WHERE id > 10;",
    return_results=True
)

# INSERT/UPDATE/DELETE query - just return success
success = execute_sql(
    conn,
    "INSERT INTO sample_data (name, value) VALUES ('test', 42);",
    return_results=False
)

# Fetch only one row
one_result = execute_sql(
    conn,
    "SELECT * FROM sample_data LIMIT 1;",
    return_results=True,
    fetch_one=True
)
```

#### `execute_sql_file(connection, filepath, return_results=False, fetch_one=False)`
Executes SQL from a file.

```python
from helper_functions import execute_sql_file

# Execute SQL from file
results = execute_sql_file(
    conn,
    "sql_examples/select_data.sql",
    return_results=True
)
```

#### `close_connection(connection)`
Closes a PostgreSQL database connection.

```python
from helper_functions import close_connection

close_connection(conn)
```

### Example Usage in Pipeline

Instead of editing `run_step` with a long if/elif chain for every new step type, the template provides a handler registry.
Define a handler function for a step type and register it with the `register_step` decorator in `main.py`.

```python
# In main.py (or a separate module imported by main.py)
from your_project.main import register_step
from helper_functions import connect_postgres, execute_sql_file, close_connection

@register_step('postgres_query')
def postgres_query_step(params):
    # params is the dict from config.yaml for this step
    conn = connect_postgres(
        host=params.get('host'),
        user=params.get('user'),
        password=params.get('password'),
        database=params.get('database'),
        port=params.get('port', 5432),
    )

    try:
        if params.get('sql_file'):
            results = execute_sql_file(conn, params['sql_file'], return_results=params.get('return_results', False))
        else:
            results = execute_sql(conn, params.get('sql', ''), return_results=params.get('return_results', False))

        # Do something with results if needed
        # e.g., write results to file or store in params for downstream steps
    finally:
        close_connection(conn)
```

And in `config.yaml`:

```yaml
pipeline_steps:
  fetch_data:
    type: postgres_query
    params:
      host: "localhost"
      user: "postgres"
      password: "your_password"
      database: "your_database"
      sql_file: "sql_examples/select_data.sql"
      return_results: true
```

## Environment Variables

* **`PIPELINE_CONFIG`**: You can specify an alternative path to your configuration file by setting this environment variable.
````
<userPrompt>
Provide the fully rewritten file, incorporating the suggested code change. You must produce the complete file.
</userPrompt>
