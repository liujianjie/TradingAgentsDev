from pathlib import Path


LAUNCHER = Path(__file__).parents[1] / "scripts" / "launcher.ps1"


def test_python_api_uses_the_detected_python_module_entrypoint() -> None:
    script = LAUNCHER.read_text(encoding="utf-8-sig")

    assert "python -m uvicorn api.main:app --port 28100" in script
    assert "Test-CommandExists 'uvicorn'" not in script


def test_uniapp_uses_the_windows_npm_command_shim() -> None:
    script = LAUNCHER.read_text(encoding="utf-8-sig")

    assert "Get-Command 'npm.cmd'" in script
    assert "& '$escapedNpmCommand' run dev:h5" in script
    assert "; npm run dev:h5" not in script
