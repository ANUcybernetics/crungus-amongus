"""Render a point in CLIP embedding space as a picture, with Kandinsky 2.2.

Kandinsky 2.2 splits text-to-image into a prior (text → ViT-bigG-14 image
embedding) and a decoder (that embedding → pixels). Only the decoder is used
here: the semantic eigencrungi already *are* points in that embedding space, so
the prior's job is done, and the decoder is the one published model that will
take an arbitrary embedding and say what it looks like.

Two things follow from that and are said plainly on the site. A frame is
Kandinsky's guess at what lies at mean + kσ along an axis, not the archive's
ground truth — the nearest real images are the ground truth. And Kandinsky 2.2
is itself in the archive, so the decomposition's illustrator is one of its own
subjects.

Each embedding is decoded under SEEDS different seeds and the *median* by CLIP
similarity to the target is kept, so one unlucky sample cannot stand for a
direction. Median rather than best: the best of three flatters the axis, and
the point of the strip is what the direction typically looks like.

Embeddings go in at open-clip's native scale (norm about 41 across this
archive). The decoder turns out not to care: round-tripping real archive images
through it retrieves the right original 8 times out of 8 at every scale from 41
down to 1, so its conditioning normalises internally. Native scale is passed
anyway, because mean + kσ·component *is* the point the decomposition names.

What it does care about is the *negative* embedding its classifier-free
guidance extrapolates away from. A zero vector is not a point any image maps
to, and guiding four times away from the prediction it produces drives the
result out of gamut: every frame comes back magenta, with the green channel
crushed to a third of the other two, in float32 as much as float16. So the
negative is the one Kandinsky's own pipeline uses — its prior run on the empty
prompt — which is a real point in the embedding space and, at cosine 0.29 to
the archive's mean, not one that collides with the centre of every filmstrip.
Measured against a zero negative on eight round-tripped archive images, it
lifts the cosine to the original from 0.75 to 0.85 and the margin over an
unrelated archive image from +0.33 to +0.44, as well as restoring the colour.
"""

import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger
from PIL import Image

from .config import Settings
from .eigen_clip import basis_path, frame_offsets, output_dir

MODEL = "kandinsky-community/kandinsky-2-2-decoder"
# the prior half, used once per run for the guidance negative and nothing else
PRIOR = "kandinsky-community/kandinsky-2-2-prior"
PRIOR_STEPS = 25
STEPS = 50
# the decoder's native resolution; the frames ship at FRAME_PX
RENDER_PX = 512
FRAME_PX = 256
SEEDS = (0, 1, 2)


@dataclass(frozen=True)
class Frame:
    key: str  # bucket key, relative to data/derived/
    embedding: np.ndarray  # (1280,) ViT-bigG-14 image embedding, native scale


def plan_frames(settings: Settings) -> list[Frame]:
    """Every frame the payload promises, and the embedding it depicts.

    Driven by eigen-clip.json rather than by re-deciding which components clear
    the threshold, so the frames on disk and the frames the site asks for
    cannot disagree. The centre frame is the mean crungus, shared by every
    axis, so it is planned once.
    """
    payload = json.loads((output_dir(settings) / "eigen-clip.json").read_text())
    with np.load(basis_path(settings)) as basis:
        mean = basis["mean"]
        components = basis["components"]
        sigma = basis["sigma"]
        text_direction = basis["text_direction"]

    offsets = frame_offsets()
    planned: dict[str, np.ndarray] = {}
    axes = [
        (component["frames"], sigma[j] * components[j])
        for j, component in enumerate(payload["components"])
    ]
    axes.append((payload["text_axis"]["frames"], text_direction))
    for keys, direction in axes:
        if keys is None:
            continue
        for key, offset in zip(keys, offsets, strict=True):
            planned.setdefault(key, mean + offset * direction)
    return [Frame(key, vector) for key, vector in sorted(planned.items())]


def load_decoder(device: str = "cuda") -> Any:
    """The decoder half of Kandinsky 2.2, in half precision on the GPU."""
    import torch
    from diffusers import KandinskyV22Pipeline

    pipe = KandinskyV22Pipeline.from_pretrained(MODEL, dtype=torch.float16)
    pipe.set_progress_bar_config(disable=True)
    return pipe.to(device)


def empty_prompt_embedding(device: str = "cuda") -> np.ndarray:
    """Kandinsky's prior on the empty prompt: the guidance negative.

    Loaded and freed here rather than cached, so a render run is reproducible
    from the model weights alone.
    """
    import torch
    from diffusers import KandinskyV22PriorPipeline

    prior = KandinskyV22PriorPipeline.from_pretrained(PRIOR, dtype=torch.float16)
    prior.set_progress_bar_config(disable=True)
    prior = prior.to(device)
    result = prior(
        prompt="",
        num_inference_steps=PRIOR_STEPS,
        generator=torch.Generator(device=device).manual_seed(0),
    )
    negative = result.image_embeds[0].float().cpu().numpy()
    del prior, result
    torch.cuda.empty_cache()
    return negative


def decode(
    pipe: Any,
    embedding: np.ndarray,
    negative: np.ndarray,
    seed: int,
    device: str = "cuda",
) -> Image.Image:
    """One 512px sample of `embedding`, guided away from `negative`."""
    import torch

    def half(vector: np.ndarray) -> Any:
        return torch.from_numpy(vector).to(device=device, dtype=torch.float16)[None]

    return pipe(
        image_embeds=half(embedding),
        negative_image_embeds=half(negative),
        num_inference_steps=STEPS,
        height=RENDER_PX,
        width=RENDER_PX,
        generator=torch.Generator(device=device).manual_seed(seed),
    ).images[0]


type Scorer = Callable[[Image.Image], np.ndarray]


def median_sample(
    candidates: list[Image.Image], embedding: np.ndarray, score: Scorer
) -> tuple[Image.Image, float]:
    """The candidate whose CLIP similarity to the target is the median."""
    target = embedding / np.linalg.norm(embedding)
    sims = np.asarray([float(score(image) @ target) for image in candidates])
    middle = int(np.argsort(sims)[len(sims) // 2])
    return candidates[middle], float(sims[middle])


def save_frame(image: Image.Image, dest: Path) -> None:
    """Downscale to FRAME_PX and encode with the corpus's AVIF settings."""
    from .optimizer import encode_avif

    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        raster = Path(tmpdir) / "frame.png"
        image.resize((FRAME_PX, FRAME_PX), Image.Resampling.LANCZOS).save(raster)
        encode_avif(raster, dest)


def image_scorer(device: str = "cuda") -> Scorer:
    """A callable PIL image → unit ViT-bigG-14 embedding, for ranking samples."""
    import open_clip
    import torch

    from .analyzer import SEMANTIC_CLIP

    model, _, preprocess = open_clip.create_model_and_transforms(
        SEMANTIC_CLIP.model, pretrained=SEMANTIC_CLIP.pretrained, device=device
    )
    model.eval()

    def score(image: Image.Image) -> np.ndarray:
        batch = preprocess(image.convert("RGB"))[None].to(device)
        with torch.no_grad():
            features = model.encode_image(batch)
            features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().numpy()[0].astype(np.float32)

    return score


def render_filmstrips(settings: Settings, force: bool = False) -> int:
    """Render every planned frame not already on disk. Returns the count."""
    import torch

    frames = plan_frames(settings)
    pending = [
        frame
        for frame in frames
        if force or not (settings.derived_dir / frame.key).exists()
    ]
    logger.info(
        "render: {} frames planned, {} to render ({} samples each)",
        len(frames),
        len(pending),
        len(SEEDS),
    )
    if not pending:
        return 0

    device = "cuda" if torch.cuda.is_available() else "cpu"
    negative = empty_prompt_embedding(device)
    pipe = load_decoder(device)
    score = image_scorer(device)
    for i, frame in enumerate(pending, 1):
        candidates = [
            decode(pipe, frame.embedding, negative, seed, device) for seed in SEEDS
        ]
        chosen, similarity = median_sample(candidates, frame.embedding, score)
        save_frame(chosen, settings.derived_dir / frame.key)
        logger.info(
            "render {}/{}: {} (cos {:.3f})", i, len(pending), frame.key, similarity
        )
    logger.info("render: {} frames → {}", len(pending), output_dir(settings))
    return len(pending)
