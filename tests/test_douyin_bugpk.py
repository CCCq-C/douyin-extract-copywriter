"""Regression tests for the fast-mode environment check."""

from __future__ import annotations

import subprocess
import sys
import os
import io
from pathlib import Path
import asyncio
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import douyin_bugpk
import douyin_fetch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUGPK_SCRIPT = PROJECT_ROOT / "douyin_bugpk.py"


class EnvironmentCheckTests(unittest.TestCase):
    def test_check_reports_httpx_for_the_collection_mode(self) -> None:
        """A full-skill preflight must expose the collection-mode dependency."""
        result = subprocess.run(
            [sys.executable, str(BUGPK_SCRIPT), "--check"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertIn("httpx", result.stdout)
        self.assertIn("--progress-bar raw", result.stdout)


class OutputDirectoryTests(unittest.TestCase):
    def _read_default_output_dir(self, extra_env: dict[str, str] | None = None) -> Path:
        env = os.environ.copy()
        env.pop("DOUYIN_OUTPUT_DIR", None)
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from douyin_bugpk import DEFAULT_OUTPUT_DIR; print(DEFAULT_OUTPUT_DIR)",
            ],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())

    def test_default_output_dir_uses_runtime_config_or_project_local_fallback(self) -> None:
        """A standalone clone must not write two directories above itself."""
        configured = PROJECT_ROOT / "test-output"
        self.assertEqual(self._read_default_output_dir(), PROJECT_ROOT / "内容收集")
        self.assertEqual(
            self._read_default_output_dir({"DOUYIN_OUTPUT_DIR": str(configured)}),
            configured,
        )


class FfmpegRecoveryTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "darwin", "macOS-specific recovery command")
    def test_check_recommends_homebrew_when_ffmpeg_is_missing(self) -> None:
        """macOS agents must not be instructed to run the Windows installer."""
        output = io.StringIO()
        with patch.object(douyin_bugpk, "find_ffmpeg", side_effect=FileNotFoundError("未找到 ffmpeg")):
            with redirect_stdout(output):
                douyin_bugpk.check_environment()

        self.assertIn("brew install ffmpeg", output.getvalue())


class MissingAsrDependencyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "requires ffmpeg to reach the ASR dependency branch")
    def test_collection_mode_routes_missing_asr_to_the_mirrored_environment_check(self) -> None:
        """The fallback must not recommend a bare pip command in a different environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "sample.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=16x16:d=0.1",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:duration=0.1",
                    "-shortest",
                    "-y",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            output = io.StringIO()
            with patch.dict(sys.modules, {"faster_whisper": None}):
                with redirect_stdout(output):
                    asyncio.run(
                        douyin_fetch.extract_subtitle_via_asr(
                            str(video_path), {"ffmpeg_path": shutil.which("ffmpeg")}
                        )
                    )

        self.assertIn("douyin_bugpk.py --check", output.getvalue())


if __name__ == "__main__":
    unittest.main()
