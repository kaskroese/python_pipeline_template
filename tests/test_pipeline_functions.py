import csv
import tempfile
import unittest
import os
from pathlib import Path
from helper_functions.pipeline_functions import (
    ensure_dir,
    data_ingestion,
    data_processing,
    data_export,
)


class TestPipelineFunctions(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ensure_dir(self):
        d = self.tmp_path / "sub" / "nested"
        ensure_dir(str(d))
        self.assertTrue(d.exists() and d.is_dir())

    def test_data_ingestion(self):
        output = self.tmp_path / "ingested.csv"
        params = {
            "output_path": str(output),
            "headers": ["id", "name", "value"],
            "rows": [[1, "a", 10], [2, "b", 20]],
        }
        data_ingestion(params)

        with open(output, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        self.assertEqual(rows[0], ["id", "name", "value"])
        self.assertEqual(rows[1], ["1", "a", "10"])
        self.assertEqual(rows[2], ["2", "b", "20"])

    def test_data_processing(self):
        input_file = self.tmp_path / "in.csv"
        output_file = self.tmp_path / "out.csv"

        # create input CSV
        with open(input_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["id", "name", "value"])
            writer.writerow([1, "a", 10])
            writer.writerow([2, "b", 5])

        operations = [
            {"type": "multiply", "column": "value", "output": "transformed", "factor": 2},
            {"type": "add_column", "output": "source", "value": "test"},
            {"type": "copy", "column": "name", "output": "name_copy"},
        ]

        data_processing({"input_path": str(input_file), "output_path": str(output_file), "operations": operations})

        self.assertTrue(output_file.exists())
        with open(output_file, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        self.assertEqual(rows[0]["transformed"], "20")
        self.assertEqual(rows[1]["transformed"], "10")
        self.assertEqual(rows[0]["source"], "test")
        self.assertEqual(rows[0]["name_copy"], "a")

    def test_data_export(self):
        in_file = self.tmp_path / "in.txt"
        out_file = self.tmp_path / "out.txt"
        in_file.write_text("hello world")

        data_export({"input_path": str(in_file), "export_path": str(out_file)})

        self.assertTrue(out_file.exists())
        self.assertEqual(out_file.read_text(), "hello world")


if __name__ == "__main__":
    unittest.main()


