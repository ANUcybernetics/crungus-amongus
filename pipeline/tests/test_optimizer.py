import subprocess
from pathlib import Path

from PIL import Image

from crungus_amongus.config import Settings
from crungus_amongus.optimizer import MAX_WORKERS, optimize_all


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        replicate_api_token="test-token",
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
    )


def write_original(settings: Settings, relative: str, size=(64, 48)) -> Path:
    path = settings.originals_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (120, 90, 40)).save(path)
    return path


def test_encodes_every_original_across_workers(tmp_path: Path) -> None:
    """More files than workers, so the pool has to cycle."""
    settings = make_settings(tmp_path)
    count = MAX_WORKERS * 2 + 3
    for i in range(count):
        write_original(settings, f"owner--model/crungus/{i}.png")

    encoded, skipped, failed = optimize_all(settings)

    assert (encoded, skipped, failed) == (count, 0, 0)
    outputs = sorted(settings.optimized_dir.rglob("*.avif"))
    assert len(outputs) == count
    assert all(p.stat().st_size > 0 for p in outputs)


def test_second_run_skips_everything(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    write_original(settings, "owner--model/crungus/0.png")
    optimize_all(settings)
    assert optimize_all(settings) == (0, 1, 0)


def test_one_unreadable_file_does_not_sink_the_batch(tmp_path: Path) -> None:
    """A bad file is logged and skipped; its neighbours still encode."""
    settings = make_settings(tmp_path)
    write_original(settings, "owner--model/crungus/0.png")
    broken = settings.originals_dir / "owner--model" / "crungus" / "1.png"
    broken.write_bytes(b"not a png")
    write_original(settings, "owner--model/crungus/2.png")

    encoded, skipped, failed = optimize_all(settings)

    assert (encoded, skipped, failed) == (2, 0, 1)
    assert not (settings.optimized_dir / "owner--model/crungus/1.avif").exists()


def test_oversized_images_are_bounded(tmp_path: Path) -> None:
    from crungus_amongus.optimizer import MAX_DIM

    settings = make_settings(tmp_path)
    write_original(settings, "owner--model/crungus/0.png", size=(MAX_DIM * 2, MAX_DIM))
    optimize_all(settings)
    with Image.open(settings.optimized_dir / "owner--model/crungus/0.avif") as out:
        assert max(out.size) == MAX_DIM


def test_avifenc_is_available() -> None:
    """The encode path shells out; a missing binary should fail loudly here."""
    result = subprocess.run(["avifenc", "--version"], capture_output=True, check=False)
    assert result.returncode == 0
