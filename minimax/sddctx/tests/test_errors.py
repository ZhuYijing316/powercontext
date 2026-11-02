"""Unit tests for the error handling of the SDD context module.

The operator must always be able to tell *what happened* and *what to do*.
These tests pin the shape of that report, because it is part of the
deliverable: a reviewer who hits a broken environment has to be able to fix
it without reading the source.
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sddctx import cli  # noqa: E402
from sddctx.errors import (  # noqa: E402
    ConfigError,
    DependencyUnavailableError,
    ModelCallError,
    PatchApplyError,
    SddctxError,
    StorageError,
    TaskNotFoundError,
    AcceptanceFailureError,
)
from sddctx.minmax_client import MiniMaxError  # noqa: E402
from sddctx.powercontext_client import PowerContextError  # noqa: E402
from sddctx.seekdb_store import DatabaseUnavailable  # noqa: E402


class TestErrorShape(unittest.TestCase):
    def test_to_dict_has_ok_false_code_message(self):
        error = SddctxError("something went wrong")
        payload = error.to_dict()
        self.assertIs(payload["ok"], False)
        self.assertEqual(payload["code"], "SDDCTX_ERROR")
        self.assertEqual(payload["message"], "something went wrong")
        self.assertNotIn("hint", payload)
        self.assertNotIn("detail", payload)

    def test_hint_and_detail_are_optional(self):
        error = SddctxError("boom", hint="do X", detail="stack")
        payload = error.to_dict()
        self.assertEqual(payload["hint"], "do X")
        self.assertEqual(payload["detail"], "stack")

    def test_render_is_operator_facing(self):
        error = SddctxError("连不上", hint="启动服务")
        text = error.render()
        self.assertIn("[ERROR]", text)
        self.assertIn("连不上", text)
        self.assertIn("启动服务", text)

    def test_no_error_class_is_mistaken_for_a_test_case(self):
        """pytest collects classes named Test*; an error class must not be one."""
        for name in dir(sys.modules["sddctx.errors"]):
            if name.startswith("Test"):
                self.fail(f"sddctx.errors.{name} would be collected by pytest")

    def test_codes_are_unique_and_stable(self):
        codes = [
            ConfigError.code,
            TaskNotFoundError.code,
            DependencyUnavailableError.code,
            StorageError.code,
            ModelCallError.code,
            PatchApplyError.code,
            AcceptanceFailureError.code,
        ]
        self.assertEqual(len(codes), len(set(codes)))
        for code in codes:
            self.assertTrue(code.isupper())
            self.assertNotIn(" ", code)


class TestErrorHierarchy(unittest.TestCase):
    def test_storage_errors_carry_the_storage_code(self):
        error = DatabaseUnavailable("seekdb 挂了")
        self.assertIsInstance(error, StorageError)
        self.assertEqual(error.code, "STORAGE_FAILED")

    def test_model_errors_carry_the_model_code(self):
        error = MiniMaxError("模型报错")
        self.assertIsInstance(error, ModelCallError)
        self.assertEqual(error.code, "MODEL_CALL_FAILED")

    def test_powercontext_errors_are_structured(self):
        error = PowerContextError("409")
        self.assertIsInstance(error, SddctxError)
        self.assertEqual(error.code, "POWERCONTEXT_ERROR")

    def test_unreachable_dependency_has_its_own_code(self):
        error = DependencyUnavailableError("连不上", hint="起服务")
        self.assertEqual(error.code, "DEPENDENCY_UNAVAILABLE")
        self.assertIn("起服务", error.render())


class TestConfigError(unittest.TestCase):
    def test_missing_key_names_the_key_and_points_at_the_env_file(self):
        from sddctx.config import _require

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MINIMAX_API_KEY", None)
            with self.assertRaises(ConfigError) as caught:
                _require("MINIMAX_API_KEY")
        error = caught.exception
        self.assertIn("MINIMAX_API_KEY", error.message)
        self.assertIn(".env", error.hint)


class TestCliErrorReporting(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_unknown_task_reports_a_structured_error(self):
        with mock.patch.dict(os.environ, {"MINIMAX_API_KEY": "x" * 10}, clear=False):
            code, out, err = self._run(["context", "--task", "NO-SUCH-TASK"])
        self.assertEqual(code, 1)
        self.assertIn("[ERROR]", err)
        self.assertIn("TASK_NOT_FOUND", err)
        self.assertIn("NO-SUCH-TASK", err)
        # the operator is told what to do next
        self.assertIn("可用任务", err)

    def test_json_mode_emits_a_machine_readable_error(self):
        with mock.patch.dict(os.environ, {"MINIMAX_API_KEY": "x" * 10}, clear=False):
            code, out, err = self._run(["--json", "context", "--task", "NO-SUCH-TASK"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertIs(payload["ok"], False)
        self.assertEqual(payload["code"], "TASK_NOT_FOUND")
        self.assertIn("message", payload)
        self.assertIn("hint", payload)

    def test_unexpected_exception_becomes_an_internal_error_not_a_traceback(self):
        boom = RuntimeError("something nobody planned for")
        with mock.patch.dict(os.environ, {"MINIMAX_API_KEY": "x" * 10}, clear=False):
            with mock.patch("sddctx.cli.cmd_context", side_effect=boom):
                code, out, err = self._run(["--json", "context", "--task", "T-2026-001"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertEqual(payload["code"], "INTERNAL_ERROR")
        self.assertIn("something nobody planned for", payload["message"])


if __name__ == "__main__":
    unittest.main()
