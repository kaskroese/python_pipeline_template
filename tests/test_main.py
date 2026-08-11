import yaml
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch
from helper_functions.pipeline_functions import STEP_HANDLERS
from main import load_config, run_step, load_env_file, log_api_key_status


class TestMain(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_config(self):
        cfg = {"pipeline_steps": {"s": {"type": "data_ingestion", "params": {}}}}
        f = self.tmp_path / "cfg.yaml"
        f.write_text(yaml.safe_dump(cfg))

        loaded = load_config(str(f))
        self.assertIsInstance(loaded, dict)
        self.assertIn("pipeline_steps", loaded)

    def test_run_step_unknown(self):
        # should not raise and should return None
        res = run_step("unknown_step", {"type": "non_existing_type"})
        self.assertIsNone(res)

    def test_run_step_executes_handler(self):
        called = []

        def handler(params):
            called.append(params)

        STEP_HANDLERS["__test_custom__"] = handler

        try:
            run_step("s1", {"type": "__test_custom__", "params": {"foo": "bar"}})
            self.assertTrue(called and called[0] == {"foo": "bar"})
        finally:
            # cleanup
            STEP_HANDLERS.pop("__test_custom__", None)

    def test_load_env_file_reads_local_env(self):
        env_file = self.tmp_path / ".env"
        env_file.write_text("TEST_ENV_KEY=hello\n")

        old_value = os.environ.get("TEST_ENV_KEY")
        try:
            os.environ.pop("TEST_ENV_KEY", None)
            load_env_file(str(env_file))
            self.assertEqual(os.environ.get("TEST_ENV_KEY"), "hello")
        finally:
            if old_value is None:
                os.environ.pop("TEST_ENV_KEY", None)
            else:
                os.environ["TEST_ENV_KEY"] = old_value

    def test_load_env_file_does_not_overwrite_existing(self):
        env_file = self.tmp_path / ".env"
        env_file.write_text("TEST_ENV_KEY=hello\n")

        old_value = os.environ.get("TEST_ENV_KEY")
        try:
            os.environ["TEST_ENV_KEY"] = "existing"
            load_env_file(str(env_file))
            self.assertEqual(os.environ.get("TEST_ENV_KEY"), "existing")
        finally:
            if old_value is None:
                os.environ.pop("TEST_ENV_KEY", None)
            else:
                os.environ["TEST_ENV_KEY"] = old_value


    def test_log_api_key_status(self):
        with patch("main.logging.warning") as mock_warning, patch("main.logging.info") as mock_info:
            old_value = os.environ.get("TEST_ENV_KEY")
            try:
                os.environ["TEST_ENV_KEY"] = "secret-value"
                log_api_key_status("TEST_ENV_KEY")
                mock_info.assert_called_once()
                self.assertFalse(mock_warning.called)
            finally:
                if old_value is None:
                    os.environ.pop("TEST_ENV_KEY", None)
                else:
                    os.environ["TEST_ENV_KEY"] = old_value


if __name__ == "__main__":
    unittest.main()


