# From a word to a thing

Status: draft brief and beat outline for Ben. Everything here is a proposal
until Ben approves it; the script lines are his to write.

## Brief (draft)

A 60 s full-screen explainer of how Crungus Amongus is made, for two places: the
site (played full screen, like the display) and a gallery screen beside the
archive, usually muted. The viewer is curious, not technical: they have seen the
display or the site and want to know where all this came from. They should leave
knowing that one made-up word was sent, unchanged, to every model the project
could find, and that everything in the archive (the atlas, the eigencrungi, the
meshes) is a way of looking at what came back.

## Key idea (draft)

One word goes in; an archive comes out, and one crungus from it becomes
something you can hold.

## One example (draft)

Follow `ai-forever--kandinsky-2-2/crungus/5`: an image whose GLB already exists.
Kandinsky 2.2 is also the model that renders the semantic eigencrungi, so the
same model appears as a generator and as an instrument. Alternatives with
meshes: `bytedance--sdxl-lightning-4step/crungus/75`,
`black-forest-labs--flux-2-dev/crungus/79`. Whichever is chosen must be the one
that gets printed.

## Beats (proposal)

Times are approximate (60 s total). The stage strip along the top lights each
stage as its beat starts. Ben writes a line or two per beat; until then the
captions are empty.

### 1. The word (0--5 s)

_Visual:_ Black. `crungus` set in Eczar, centred. A Bark clip says the word. The
stage strip fades in, unlit.

_Reads (draft):_ 1. this is a made-up word; 2. it has a sound.

### 2. `crungus discover` (5--9 s)

_Visual:_ The word sends out lines to a field of model names in mono, laid out
along a release-year axis from 2021 to 2026: image models, then music models,
then video models, each group arriving in turn. The counts come from models.json
(122, 16, 43).

_Reads (draft):_ 1. many models; 2. old and new; 3. three kinds: pictures,
sound, video.

### 3. `crungus generate` (9--21 s)

_Visual:_ The hero beat, and the video archive's. Each video model's name
becomes a framed clip of its answer to "crungus", filling a wall in release
order: damo-text-to-video's 256 px, 8 fps clip first, pixelated at 2×; then
zeroscope, animate-diff, hotshot; then the 1080p models (Veo 3.1, Kling v3,
Seedance 2.0). About 24 play at once; the rest of the 860 sit as posters. The
music clips stack into a crowd under it. Then the wall dims and the image
archive (24,400 posters on the canvas layer) floods in behind it, and the camera
settles on one cell: the followed crungus, ringed in ochre.

_Reads (draft):_ 1. the same word went to every model; 2. the older the model,
the smaller and choppier the answer; 3. they mostly make a creature; 4. this is
the one we follow.

_Reads note:_ 2 and 3 compete for the same 12 s; if Ben's line names only one,
the wall's order should serve that one.

### 4. `crungus optimize` and `crungus sync` (21--25 s)

_Visual:_ The followed image leaves the wall. Its catalogue line shows its file
size before and after AVIF encoding (real bytes), then its bucket key types out
beneath it: `ai-forever--kandinsky-2-2/crungus/5.avif`. A brief echo: an audio
clip's key and a video clip's two keys (AV1 and H.264) beside it.

_Reads (draft):_ 1. every output is compressed and stored; 2. its name records
which model and prompt made it.

### 5. `crungus analyze` and `crungus sprite` (25--33 s)

_Visual:_ Match cut: the image shrinks to a point. Its model's other 99
"crungus" images join it as points; the consistency score (0.77) appears as the
catalogue line. Logarithmic pull-back: every image becomes a point in the UMAP
atlas, then the points turn into their sprite thumbnails, and the followed
crungus is still ringed.

_Reads (draft):_ 1. a model's images can be alike or not, and that is
measured; 2. similar images sit close together; 3. ours has neighbours.

### 6. `crungus eigen` and `crungus render` (33--41 s)

_Visual:_ The ringed thumbnail opens into the eigen view: the mean crungus, then
components adding in one at a time (a few sliders moving) until the
reconstruction approaches the followed image. Then a cut on action to one
CLIP-space axis: its Kandinsky renders at the two extremes, side by side.

_Reads (draft):_ 1. any crungus is the average plus some directions of
difference; 2. some directions have a meaning you can see.

_Reads note:_ two decompositions in 8 s is a lot; pixel space alone may carry
the read, with `render` shown only as the stage lighting and one frame.

### 7. `crungus mesh` (41--48 s)

_Visual:_ The followed image back at full size; it turns side-on and becomes its
Meshy GLB, as a pre-rendered turntable, one full slow revolution.

_Reads (draft):_ 1. one picture became an object.

### 8. `crungus publish` (48--52 s)

_Visual:_ The turntable shrinks into a frame of the site's mesh page; the frame
pulls back through the site's other pages (archive, sound, video, atlas, eigen)
as framed screenshots, arranged like the opening field of names.

_Reads (draft):_ 1. all of it is on the website.

### 9. The print (52--57 s)

_Visual:_ Footage of the printed crungus (needs shooting; see below), framed
like every other specimen, with its catalogue line: the same key as in beat 4.
Bark says "crungus" again.

_Reads (draft):_ 1. it exists now.

### 10. Close (57--60 s)

_Visual:_ The site's address on screen in mono, then the School of Cybernetics
lockup.

_Reads (draft):_ 1. where to find it.

## Soundtrack (proposal)

All from `/sound/`, keys in `clips.json`. Bark ("crungus") opens and closes. One
music clip of "the sound of a crungus" carries the bed from beat 2, chosen by
Ben from a shortlist of four or five; in beat 3 several other music clips stack
over it, one per few video clips, and fall away to the bed as the camera finds
the followed crungus. Video clips are silent.

## Open questions for Ben

- **Narration.** This draft assumes no voice, as the acceptance criteria limit
  the soundtrack to the audio archive; the captions carry your lines. A recorded
  voice-over of yours would change the timing gate and the mix.
- **The print.** Nothing in the archive has been printed yet. Beat 9 needs one
  printed model and footage of it (a slow turntable, top-lit on a dark ground,
  shot at 24 or 48 fps, ideally 4K).
- **The video models' own soundtracks.** Excluded here; say if they count as
  part of the audio archive.
- **The lockup.** The School of Cybernetics lockup with its rules in the site's
  ochre, or the site's address alone.
