import os
import subprocess
from pathlib import Path

import pytest


def run_entrypoint(tmp_path: Path, *args: str, database_uri: str | None = None) -> subprocess.CompletedProcess[str]:
    entrypoint = Path(__file__).resolve().parents[2] / "docker-entrypoint.sh"
    fake_ping = tmp_path / "ping"
    fake_ping.write_text("#!/bin/sh\nexit 0\n")
    fake_ping.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    if database_uri is not None:
        env["DATABASE_URI"] = database_uri

    return subprocess.run(
        ["bash", str(entrypoint), "/bin/true", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_entrypoint_does_not_log_database_credentials(tmp_path: Path) -> None:
    secret = "super-secret-password"
    database_uri = f"postgresql://postgres:{secret}@localhost:5432/app"
    result = run_entrypoint(tmp_path, database_uri, database_uri=database_uri)

    assert result.returncode == 0
    assert secret not in result.stderr


def test_entrypoint_redacts_full_database_uri_in_logs(tmp_path: Path) -> None:
    database_uri = "postgresql://postgres:super-secret-password@localhost:5432/app"
    redacted_uri = "postgresql://postgres:***@localhost:5432/app"
    remapped_redacted_uri = "postgresql://postgres:***@host.docker.internal:5432/app"
    result = run_entrypoint(tmp_path, database_uri, database_uri=database_uri)

    assert result.returncode == 0
    assert database_uri not in result.stderr
    assert redacted_uri in result.stderr
    assert remapped_redacted_uri in result.stderr


@pytest.mark.parametrize(
    ("argument", "forbidden_text", "expected_text"),
    [
        (
            "--database-uri=postgresql://postgres:super-secret-password@localhost:5432/app",
            "--database-uri=postgresql://postgres:super-secret-password@localhost:5432/app",
            "--database-uri=postgresql://postgres:***@host.docker.internal:5432/app",
        ),
        (
            "postgres://postgres:p%40ss%3Aword@localhost:5432/app",
            "postgres://postgres:p%40ss%3Aword@localhost:5432/app",
            "postgres://postgres:***@host.docker.internal:5432/app",
        ),
    ],
)
def test_entrypoint_redacts_additional_uri_shapes(
    tmp_path: Path,
    argument: str,
    forbidden_text: str,
    expected_text: str,
) -> None:
    result = run_entrypoint(tmp_path, argument)

    assert result.returncode == 0
    assert forbidden_text not in result.stderr
    assert expected_text in result.stderr
