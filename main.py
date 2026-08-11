import yaml
import logging
import os
from helper_functions import STEP_HANDLERS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_env_file(env_path='.env'):
    """Load simple KEY=VALUE pairs from a local .env file if present.

    Existing environment variables are preserved. This keeps local IDE runs
    consistent with Docker runs where variables are injected differently.
    """
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        logging.info(f"Loaded environment variables from {env_path}")
    except OSError as e:
        logging.warning(f"Could not read {env_path}: {e}")


def log_api_key_status(env_var_name='NLS_API_KEY'):
    """Log whether the API key environment variable is present, without revealing it."""
    value = os.environ.get(env_var_name)
    if value is None:
        logging.warning(f"{env_var_name} is not set")
    elif value == "":
        logging.warning(f"{env_var_name} is set but empty")
    else:
        logging.info(f"{env_var_name} is set (length={len(value)})")

def load_config(config_path):
    """Loads the pipeline configuration from a YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logging.info(f"Configuration loaded successfully from {config_path}")
        return config
    except FileNotFoundError:
        logging.error(f"Config file not found at {config_path}")
        raise
    except yaml.YAMLError as e:
        logging.error(f"Error parsing config file: {e}")
        raise

def run_step(step_name, step_config):
    """Executes a single pipeline step using the registered handlers."""
    logging.info(f"--- Running step: {step_name} ---")
    step_type = step_config.get('type')
    params = step_config.get('params', {})

    handler = STEP_HANDLERS.get(step_type)
    if handler is None:
        logging.warning(f"Unknown step type '{step_type}' for step '{step_name}'. Skipping.")
        logging.info(f"--- Step {step_name} skipped ---")
        return

    try:
        logging.info(f"Performing {step_type} with params: {params}")
        handler(params)
    except Exception as e:
        logging.error(f"Error in step '{step_name}' (type={step_type}): {e}")
        raise

    logging.info(f"--- Step {step_name} completed ---")

def main():
    load_env_file()
    log_api_key_status()
    config_path = os.environ.get('PIPELINE_CONFIG', 'config.yaml')
    logging.info(f"Attempting to load configuration from: {config_path}")

    config = load_config(config_path)

    if not config or 'pipeline_steps' not in config:
        logging.error("Invalid configuration: 'pipeline_steps' not found.")
        return

    # Get global test run parameters
    test_run_config = config.get('test_run_config', {})
    test_run = test_run_config.get('test_run', False)
    municipality_filter = test_run_config.get('municipality_filter')
    test_schema_suffix = test_run_config.get('test_schema_suffix', 'test')

    if test_run:
        logging.info(
            f"--- TEST RUN ENABLED: Writing to isolated '*_{test_schema_suffix}' schemas ---"
        )

    logging.info("Starting pipeline execution...")
    for step_name, step_config in config['pipeline_steps'].items():
        try:
            # Inject global test run parameters into each step
            if 'params' not in step_config:
                step_config['params'] = {}
            step_config['params']['test_run'] = test_run
            step_config['params']['municipality_filter'] = municipality_filter
            step_config['params']['test_schema_suffix'] = test_schema_suffix

            run_step(step_name, step_config)
        except Exception as e:
            logging.error(f"Error during step '{step_name}': {e}")
            # Stop pipeline on first error (fail-fast behavior)
            raise

    logging.info("Pipeline execution finished.")

if __name__ == "__main__":
    main()
