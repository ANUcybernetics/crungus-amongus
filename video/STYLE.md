# Crungus Amongus video style

The project half of the `styled-video` skill (in Ben's `ben` plugin): the skill
carries the method and the craft, this file carries what is particular to the
archive.

## Where things live

- `video.toml`: read by the skill's `scripts/video.py` (its docstring lists the
  commands and keys) for `mix`, `render` and `stills`. It sets no voice and no
  music prompt: the soundtrack is cut from the archive (see "Sound").
- `scripts/<slug>.md`: each video's brief, key idea, one example and script,
  with a `_Visual:_` direction and a `_Reads:_` list per stretch of picture. Ben
  owns the brief and every on-screen line, and approves the reads; a read still
  marked `(draft)` is not approved.
- `<slug>/`: the HyperFrames project: `index.html`, `<slug>.js` (the `build`),
  `timing.json` and `captions.vtt`, `clips.json` (which archive key each shot
  uses, and its in and out points), `assets/` (fetched footage, audio and
  renders, not committed) and a `kit -> ../_kit` symlink.
- `_kit/`: `kit.css` and symlinks: `motion ->` astromotion's `video/`,
  `tokens -> ../../site/src/styles/tokens.css` (the site's palette and type
  tokens), `fonts ->` the site's `@fontsource` packages, and `brand ->`
  astro-theme-anu for the closing lockup.
- `out/`: renders, stills and the TTS cache (gitignored).

## Sources of truth

- **Palette and type are the site's.** `kit.css` maps the stage's `--video-*`
  tokens onto the site's own (`--ground`, `--text`, `--muted`, `--accent`,
  `--font-display`, ...), so a change to the site's look carries into the video.
  Never copy a hex value into the kit.
- **Every artefact on screen is a real one**, fetched by its key from the bucket
  or `data/`: the images, clips, sounds, eigen sheet, atlas sprite, Kandinsky
  renders and GLBs. Nothing is regenerated, retouched or made by a model for the
  video.
- **Every number and name on screen** (counts, model slugs, release years,
  consistency scores, file sizes, keys) is read from `site/src/data/models.json`
  or `state/` when the composition builds, never typed in. A video adds no claim
  the about page doesn't make: consistency is a similarity score, not proof of a
  creature.
- **The stage names** are the CLI's own: `crungus discover`, `crungus generate`,
  and so on, in README order.

## The look

- **Darkroom archive.** Warm brown-black ground, bone text, one rust-ochre
  accent, as on the site. The specimens glow; everything drawn is quiet. Ochre
  is for what the viewer should be looking at (the followed crungus, a ringed
  point, the active stage), never decoration.
- **Specimens are framed, not filled.** Archive footage and images sit at their
  native aspect in a hairline `--line` frame on the ground, as the site's cards
  do. Never crop a clip to 16:9 or stretch it to fill the stage.
- **Old footage stays old.** A clip plays at its own frame rate, never
  interpolated (damo's 8 fps stays 8 fps). It is shown at no more than twice its
  native size on the 1920×1080 stage, scaled by an integer factor with
  `image-rendering: pixelated`, so a 256 px clip reads as low resolution rather
  than as blur. The progression from 2023 to 2026 is part of what the archive
  shows.
- **Catalogue labels, in mono.** The only routine on-screen text is an
  artefact's catalogue line in the site's utility voice (IBM Plex Mono, muted):
  `model slug · year · prompt`, or a bucket key. Titles are Eczar at the site's
  weight (600); the script's lines are IBM Plex Sans.
- **The stage strip.** A row of the pipeline's stage names in mono runs along
  the top of the frame, and the current stage lights in ochre. It is how the
  viewer always knows where they are, and how every stage is shown even when a
  stage gets a second.
- **Nothing boils.** There is no hand-drawn layer; the footage supplies the
  life. The vector layer (frames, labels, points, lines) holds still between
  moves.
- **Many items** (a wall of 860 clips, the atlas's points) are drawn on the
  canvas layer from seeded data, with only the clips actually playing as
  `<video>` elements. A wall shows at most about 24 playing clips at once; the
  rest are their poster frames.
- **3D is pre-rendered.** A GLB appears as a turntable rendered offline from the
  file to an image sequence (three.js, rotation a pure function of frame
  number), then placed as footage. No live WebGL in a composition.
- **Square corners**, hairline rules, no shadows, gradients or glow effects.
- **The script is on-screen text**, one line at a time in the stage's caption
  band, in IBM Plex Sans. There is no voice, so the text is the only place the
  words are, and it must also work with the sound off (the display is often
  muted).
- **It closes on the URL and the lockup**: the site's address on screen, then
  the School of Cybernetics lockup from astro-theme-anu, with the rules drawn in
  the site's ochre.
- **Formats.** Landscape 1920×1080 only (the display and the site are
  landscape). Masters 4K at 48 fps, drafts 1080p24: most archive clips are 24
  fps, which 48 holds without the uneven cadence 50 fps gives them.

## Sound

The audio archive is the narration, in the sense of what leads: there is no
voice, and the soundtrack is edited first, with the picture cut to it as it
would be to a voice-over. A beat starts on a sound (Bark's word, a clip coming
in), not on a round number.

The soundtrack is cut only from the audio archive (`/sound/`), by key, with in
and out points in `clips.json`; the clip's catalogue line appears when it first
sounds, as footage gets one. Video clips play muted, including those with their
own soundtrack. Bark saying "crungus" is the nearest thing to a voice.

`timing.json` comes from the soundtrack edit, not from `video.py voice`: each
line's start is the sound its beat starts on, and it holds for at least its
reading time (about 0.3 s a word plus 1 s). The edit goes in `assets/music.mp3`
for `mix`, mastered to −14 LUFS.
