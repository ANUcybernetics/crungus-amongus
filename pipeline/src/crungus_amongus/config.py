"""Project settings and filesystem layout.

All state lives at the repo root (not inside pipeline/), so paths are anchored
to the checkout via this file's location. This is an app run from its checkout,
never an installed wheel.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

REPLICATE_API_BASE = "https://api.replicate.com/v1"

# the archive has one experiment per modality: a Replicate collection plus a
# curated list, a fixed prompt set, a fixed sample count
type Modality = Literal["image", "audio"]
MODALITIES: tuple[Modality, ...] = ("image", "audio")
COLLECTIONS: dict[Modality, str] = {
    "image": "text-to-image",
    "audio": "ai-music-generation",
}
PROMPTS: dict[Modality, dict[str, str]] = {
    "image": {
        "crungus": "crungus",
        "a-picture-of-a-crungus": "a picture of a crungus",
    },
    "audio": {
        "crungus": "crungus",
        "the-sound-of-a-crungus": "the sound of a crungus",
    },
}
OUTPUTS_PER_PROMPT = 10
# clip length requested from audio models that expose a duration input
AUDIO_DURATION_S = 20
# flat per-output estimates for --dry-run (the dashboard is billing truth)
ASSUMED_COST: dict[Modality, float] = {"image": 0.03, "audio": 0.10}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    replicate_api_token: str

    # Tigris bucket (credentials live in the untracked mise [env] block)
    s3_endpoint: str = Field(
        "https://fly.storage.tigris.dev", validation_alias="CRUNGUS_S3_ENDPOINT"
    )
    s3_bucket: str = Field("crungus-amongus", validation_alias="CRUNGUS_S3_BUCKET")
    s3_access_key_id: str | None = Field(
        None, validation_alias="CRUNGUS_S3_ACCESS_KEY_ID"
    )
    s3_secret_access_key: str | None = Field(
        None, validation_alias="CRUNGUS_S3_SECRET_ACCESS_KEY"
    )
    # public base the site fetches images from
    image_base_url: str = Field(
        "https://images.crungusamong.us",
        validation_alias="CRUNGUS_IMAGE_BASE_URL",
    )

    data_dir: Path = REPO_ROOT / "data"
    state_dir: Path = REPO_ROOT / "state"

    def curated_models_path(self, modality: Modality) -> Path:
        return self.data_dir / (
            "curated-models.toml"
            if modality == "image"
            else f"curated-{modality}-models.toml"
        )

    @property
    def deny_list_path(self) -> Path:
        return self.data_dir / "deny-list.toml"

    @property
    def originals_dir(self) -> Path:
        return self.data_dir / "originals"

    @property
    def optimized_dir(self) -> Path:
        return self.data_dir / "optimized"

    @property
    def registry_path(self) -> Path:
        return self.state_dir / "models.json"

    @property
    def manifest_path(self) -> Path:
        return self.state_dir / "manifest.jsonl"

    @property
    def embeddings_path(self) -> Path:
        return self.state_dir / "embeddings.npz"
