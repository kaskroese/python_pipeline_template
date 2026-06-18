import yaml
import tempfile
import unittest
from pathlib import Path
from helper_functions.pipeline_functions import STEP_HANDLERS
from main import load_config, run_step


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


if __name__ == "__main__":
    unittest.main()


