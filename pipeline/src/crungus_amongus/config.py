"""Project settings and filesystem layout.

All state lives at the repo root (not inside pipeline/), so paths are anchored
to the checkout via this file's location. This is an app run from its checkout,
never an installed wheel.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

REPLICATE_API_BASE = "https://api.replicate.com/v1"
COLLECTION_SLUG = "text-to-image"

PROMPTS: dict[str, str] = {
    "crungus": "crungus",
    "a-picture-of-a-crungus": "a picture of a crungus",
}
IMAGES_PER_PROMPT = 10


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
    # public base the site fetches images from; swap when DNS lands
    image_base_url: str = Field(
        "https://crungus-amongus.fly.storage.tigris.dev",
        validation_alias="CRUNGUS_IMAGE_BASE_URL",
    )

    data_dir: Path = REPO_ROOT / "data"
    state_dir: Path = REPO_ROOT / "state"

    @property
    def curated_models_path(self) -> Path:
        return self.data_dir / "curated-models.toml"

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
