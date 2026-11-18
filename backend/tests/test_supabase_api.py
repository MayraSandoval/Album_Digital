from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parent.parent


def test_persists_api_data_across_processes(tmp_path):
    env = os.environ.copy()
    env.update({
        "ALBUM_STORAGE_BACKEND": "supabase",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_fake",
        "SUPABASE_BUCKET": "album-fotos",
        "VERCEL": "1",
        "TEST_SUPABASE_DB": str(tmp_path / "fake.db"),
    })
    for phase in ("create", "verify"):
        result = subprocess.run(
            [sys.executable, "-m", "tests.supabase_api_worker", phase],
            cwd=BACKEND, env=env, text=True, capture_output=True, timeout=90,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_incomplete_configuration_cannot_fall_back_to_temporary_storage():
    env = os.environ.copy()
    env.update({"ALBUM_STORAGE_BACKEND": "supabase", "SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""})
    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=BACKEND, env=env, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode != 0
    assert "SUPABASE_URL" in result.stderr


def test_vercel_requires_persistent_backend():
    env = os.environ.copy()
    env.update({"ALBUM_STORAGE_BACKEND": "local", "VERCEL": "1"})
    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=BACKEND, env=env, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode != 0
    assert "ALBUM_STORAGE_BACKEND=supabase" in result.stderr
