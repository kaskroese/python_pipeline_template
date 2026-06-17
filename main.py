import yaml
import logging
import os
from helper_functions import STEP_HANDLERS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    """Executes a single pipeline step using the registered handlers.

    Handlers can be registered with the `register_step` decorator or by
    adding entries to the `STEP_HANDLERS` dict. This removes the need for
    a long if/elif chain and allows new step types to be added without
    editing `run_step`.
    """
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
    config_path = os.environ.get('PIPELINE_CONFIG', 'config.yaml')
    logging.info(f"Attempting to load configuration from: {config_path}")

    config = load_config(config_path)

    if not config or 'pipeline_steps' not in config:
        logging.error("Invalid configuration: 'pipeline_steps' not found.")
        return

    logging.info("Starting pipeline execution...")
    for step_name, step_config in config['pipeline_steps'].items():
        try:
            run_step(step_name, step_config)
        except Exception as e:
            logging.error(f"Error during step '{step_name}': {e}")
            # Depending on requirements, you might want to stop or continue
            # For now, we'll just log and continue.
            # raise # Uncomment to stop pipeline on first error

    logging.info("Pipeline execution finished.")

if __name__ == "__main__":
    main()
