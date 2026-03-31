from pathlib import Path

import pytest

from shared.persistence import atomic_write_json


def test_atomic_write_json_cleans_up_temp_file_on_replace_failure(tmp_path, monkeypatch):
    target = tmp_path / "state.json"

    def fail_replace(self: Path, other: Path):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="disk full"):
        atomic_write_json(target, {"status": "pending"})

    assert list(tmp_path.glob(".*.tmp")) == []
