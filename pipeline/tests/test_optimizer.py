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


def test_video_encodes_to_av1_and_h264_with_a_poster_outside_the_image_corpus(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    from crungus_amongus.registry import Registry, RegistryModel, save_registry

    settings = make_settings(tmp_path)
    save_registry(
        Registry(
            fetched_at=datetime.now(tz=UTC),
            models=[
                RegistryModel(
                    owner="owner",
                    name="video-model",
                    slug="owner--video-model",
                    source="collection",
                    modality="video",
                    version_id="v1",
                )
            ],
        ),
        settings.registry_path,
    )
    clips = settings.originals_dir / "owner--video-model" / "crungus"
    clips.mkdir(parents=True)
    lavfi = ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i"]
    subprocess.run(
        [*lavfi, "testsrc=size=320x240:duration=1", "-f", "lavfi", "-i"]
        + ["sine=duration=1", "-shortest", str(clips / "0.mp4")],
        check=True,
    )
    # a GIF from a video model is a clip, not an image
    subprocess.run(
        [*lavfi, "testsrc=size=128x96:duration=1", str(clips / "1.gif")], check=True
    )

    assert optimize_all(settings) == (4, 0, 0)

    out = settings.optimized_dir / "owner--video-model" / "crungus"
    assert sorted(p.name for p in out.iterdir()) == [
        *["0.av1.mp4", "0.jpg", "0.mp4"],
        *["1.av1.mp4", "1.jpg", "1.mp4"],
    ]
    assert not list(settings.optimized_dir.rglob("*.avif"))

    def streams(path: Path) -> list[str]:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name"]
            + ["-of", "csv=p=0", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return probe.stdout.split()

    assert streams(out / "0.mp4") == ["h264", "aac"]
    assert streams(out / "1.mp4") == ["h264"]
    assert streams(out / "0.av1.mp4") == ["av1", "aac"]
    assert streams(out / "1.av1.mp4") == ["av1"]
