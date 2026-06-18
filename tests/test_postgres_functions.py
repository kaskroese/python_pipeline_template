import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from helper_functions import postgres_functions as pg


class TestPostgresFunctions(unittest.TestCase):
    def make_cursor(self, select=True, rows=None, fetch_one=False):
        cur = Mock()
        if select:
            # emulate a cursor with results
            cur.description = ("col",)
            if fetch_one:
                cur.fetchone.return_value = rows[0] if rows else None
            else:
                cur.fetchall.return_value = rows or []
        else:
            # non-select
            cur.description = None
            cur.rowcount = 2
        return cur

    def test_execute_sql_select(self):
        conn = Mock()
        rows = [{"id": 1, "name": "a"}]
        cur = self.make_cursor(select=True, rows=rows)
        conn.cursor.return_value = cur

        res = pg.execute_sql(conn, "SELECT 1;", return_results=True, fetch_one=False)
        self.assertEqual(res, rows)
        conn.cursor.assert_called()

    def test_execute_sql_fetch_one(self):
        conn = Mock()
        row = {"id": 1}
        cur = self.make_cursor(select=True, rows=[row], fetch_one=True)
        conn.cursor.return_value = cur

        res = pg.execute_sql(conn, "SELECT 1;", return_results=True, fetch_one=True)
        self.assertEqual(res, row)

    def test_execute_sql_non_select(self):
        conn = Mock()
        cur = self.make_cursor(select=False)
        conn.cursor.return_value = cur

        res = pg.execute_sql(conn, "INSERT INTO t VALUES (1);", return_results=False)
        self.assertTrue(res)
        conn.commit.assert_called()

    def test_execute_sql_file(self):
        temp_dir = tempfile.TemporaryDirectory()
        try:
            tmp_path = Path(temp_dir.name)
            f = tmp_path / "qry.sql"
            f.write_text("SELECT 1;")

            called = []

            def fake_execute_sql(conn, sql, return_results, fetch_one):
                called.append(sql)
                return [{"ok": True}]

            with patch.object(pg, "execute_sql", side_effect=fake_execute_sql):
                conn = Mock()
                res = pg.execute_sql_file(conn, str(f), return_results=True)
                self.assertEqual(res, [{"ok": True}])
                self.assertTrue(called and "SELECT 1;" in called[0])
        finally:
            temp_dir.cleanup()

    def test_close_connection(self):
        conn = Mock()
        pg.close_connection(conn)
        conn.close.assert_called()


if __name__ == "__main__":
    unittest.main()


