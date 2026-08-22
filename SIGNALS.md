# ai-music-checker — Signal Reference

Complete documentation for all forensic heuristic signals used to estimate
AI-generation likelihood of music files (MP3/WAV/FLAC/AIFF).

---

## Overview

The checker evaluates **16 signals** across three categories:

| Category | Signals | Availability | Group Weight |
|----------|---------|--------------|--------------|
| Technical (T) | T1 — T7 | Always (ffmpeg/ffprobe) | 40 |
| Metadata (M) | M1 — M4 | Always (local tag inspection) | 25 |
| Context (C) | C1 — C5 | `--online` flag only | 35 |

Each signal produces a **subscore** `s` in the range `[0.0, 1.0]` where:

- `0.0` = no AI indication (human-made)
- `1.0` = strong AI indication

Subscores are combined into a final AI probability via weighted aggregation:

```
effective_weight  = weight × reliability × availability
group_score       = Σ(effective_weight_i × subscore_i) / Σ(effective_weight_i)
final_probability = Σ(group_weight_g × group_score_g) / Σ(group_weight_g)
```

### Verdict Bands

| AI Probability | Verdict |
|----------------|---------|
| ≤ 0.20 | UNAUFFÄSSIG (unremarkable) |
| 0.21 – 0.40 | EHER MENSCHLICH (likely human) |
| 0.41 – 0.60 | UNKLAR (unclear) |
| 0.61 – 0.80 | LIKELY AI-ASSISTED |
| > 0.80 | VERY LIKELY AI |

### Confidence

Statement confidence combines coverage (how many signals fired) and consistency
(how much the group scores agree):

```
confidence = 0.6 × coverage + 0.4 × consistency
```

---

## Technical Signals (T1 — T7)

Group weight: **40**. Always available. Requires ffmpeg/ffprobe.

| ID | Name | Weight | Reliability | Measurement |
|----|------|--------|-------------|-------------|
| T1 | hf_energy_profile | 12 | 0.6 | Highpass + volumedetect at threshold and severe frequencies |
| T2 | dynamics_loudness | 8 | 0.5 | LRA via loudnorm, crest factor via astats |
| T3 | stereo_anomalies | 4 | 0.4 | Side-channel energy via mid/side pan |
| T4 | noise_seams_fades | 8 | 0.5 | Interior silence blocks via silencedetect |
| T5 | encoder_chain | 5 | 0.7 | Generator patterns in encoder/software tags |
| T6 | sr_artifacts | 5 | 0.5 | Unusual sample rate, SR/bitrate correlations |
| T7 | bpm_duration_sanity | 3 | 0.3 | Track duration heuristics |

---

### T1: HF Energy Profile

| Attribute | Value |
|-----------|-------|
| **ID** | T1 |
| **Name** | `hf_energy_profile` |
| **Weight** | 12 |
| **Reliability** | 0.6 |
| **Group** | technical |

#### What It Measures

Energy above configurable frequency thresholds using ffmpeg `highpass` filter
followed by `volumedetect`. Two passes:

1. **Threshold pass** (default: 16 kHz) — measures mean volume of content above cutoff
2. **Severe pass** (default: 14 kHz) — used to distinguish hard cutoffs from gentle rolloff

#### Forensic Basis

AI music generators (Suno, Udio, MusicGen) use neural audio codecs (EnCodec,
SoundStream, DAC) that produce sharp spectral cutoffs at 14–16 kHz. Real
microphone recordings have natural, gradual high-frequency rolloff determined by
room acoustics, microphone characteristics, and instrument harmonics. A hard
cutoff with near-total energy absence above 16 kHz is a strong indicator of
neural codec synthesis.

#### Scoring Logic

| Condition | Subscore | Interpretation |
|-----------|----------|----------------|
| mean_volume > -70 dB above threshold | **0.0** | Full HF energy — natural rolloff |
| mean_volume ≤ -90 dB above threshold, and ≤ -90 dB at severe | **1.0** | Hard cutoff below 14 kHz — strong AI indicator |
| mean_volume ≤ -90 dB above threshold, but > -90 dB at severe | **0.9** | Cutoff between 14–16 kHz — likely AI |
| mean_volume between -70 and -90 dB | **0.0 – 1.0** | Linear ramp: `(-70 - mean_volume) / 20` |

#### Configuration

```json
"T1": { "threshold_khz": 16, "severe_khz": 14 }
```

#### References

- Su et al. (2023) "Adversarial Machine Learning in Audio Deepfake Detection"
- MPEG-D / EnCodec documentation (Meta, 2022)
- SoundStream: An End-to-End Neural Audio Codec (Google, 2021)

---

### T2: Dynamics and Loudness

| Attribute | Value |
|-----------|-------|
| **ID** | T2 |
| **Name** | `dynamics_loudness` |
| **Weight** | 8 |
| **Reliability** | 0.5 |
| **Group** | technical |

#### What It Measures

Two complementary dynamic-range metrics:

1. **Loudness Range (LRA)** via ffmpeg `loudnorm` filter (EBU R128 compliant)
2. **Crest Factor** via ffmpeg `astats` — difference between peak level and RMS level (dB)

#### Forensic Basis

AI-generated tracks frequently exhibit a "wall of sound" effect with extremely
low dynamic range. This results from the training data bias toward loudness-
normalized commercial releases and the generator's tendency to maximize perceived
loudness across all frequency bands simultaneously. Human-produced music, even
heavily compressed dance music, retains more dynamic variation.

#### Scoring Logic

Two independent scores, averaged:

**Crest factor component:**

| Crest Factor | Subscore | Interpretation |
|-------------|----------|----------------|
| ≥ 12 dB | **0.0** | Natural dynamics |
| < 8 dB | **1.0** | Heavily compressed / wall-of-sound |
| 8 – 12 dB | linear ramp | `((8×1.5 - crest) / (8×0.5))` clamped to [0,1] |

**LRA component:**

| LRA | Subscore | Interpretation |
|-----|----------|----------------|
| ≥ 6 LU | **0.0** | Wide dynamic range |
| < 3 LU | **1.0** | Extremely flat dynamics |
| 3 – 6 LU | linear ramp | `((3×2 - LRA) / 3)` clamped to [0,1] |

Final: `(crest_score + lra_score) / 2`

#### Configuration

```json
"T2": { "crest_db_threshold": 8, "lra_lu_threshold": 3 }
```

#### References

- EBU R128 — Loudness normalisation and permitted maximum level of audio signals
- AES Technical Document AES-TD1004.1.15-10 (Program loudness measurement)
- ITU-R BS.1770 — Algorithms to measure audio programme loudness and true-peak audio level

---

### T3: Stereo Anomalies

| Attribute | Value |
|-----------|-------|
| **ID** | T3 |
| **Name** | `stereo_anomalies` |
| **Weight** | 4 |
| **Reliability** | 0.4 |
| **Group** | technical |

#### What It Measures

Side-channel energy relative to overall energy. The side signal is extracted as
`(L - R) / 2` using ffmpeg's `pan` filter, then `volumedetect` measures its
mean volume. The side-channel level is compared to the overall mean volume.

#### Forensic Basis

Many AI generators produce near-dual-mono or unnaturally narrow stereo fields.
This occurs because the generator's internal representation may lack true
stereo spatial information, or because the training data's stereo cues are
averaged during synthesis. Real studio productions typically have intentional
stereo width with meaningful side-channel content (reverb tails, panned
instruments, stereo effects).

#### Scoring Logic

| Side Channel Relative Level | Subscore | Interpretation |
|---------------------------|----------|----------------|
| ≤ -35 dB relative | **0.9** | Near dual-mono |
| ≤ -25 dB relative | **0.5** | Narrow stereo |
| > -25 dB relative | **0.0** | Normal stereo width |

**Special case:** Mono master files receive a subscore of 0.5 (uncertain — could
be legitimate mono or AI limitation).

---

### T4: Noise Floor and Digital Silence

| Attribute | Value |
|-----------|-------|
| **ID** | T4 |
| **Name** | `noise_seams_fades` |
| **Weight** | 8 |
| **Reliability** | 0.5 |
| **Group** | technical |

#### What It Measures

Interior silence blocks detected by ffmpeg `silencedetect` (threshold: -50 dB,
minimum duration: 0.5s). Only silence blocks that occur in the **interior** of
the track are counted — the first and last 2 seconds are excluded (natural
fade-in/fade-out).

#### Forensic Basis

AI-generated tracks frequently contain:

- **Synthetic silence blocks:** Abrupt digital silence between sections, unlike
  natural room ambience or reverb tails found in human recordings.
- **Loop seams:** Artifacts at segment boundaries where the generator stitched
  together latent-space segments, creating audible discontinuities or gaps.
- **Unnatural transitions:** Lack of crossfade or musical transition between
  sections, suggesting independent generation passes.

Real recordings have continuous (even if quiet) noise floors from microphones,
preamps, and room acoustics. Perfect digital silence mid-track is unusual.

#### Scoring Logic

| Interior Silence Blocks | Subscore | Interpretation |
|------------------------|----------|----------------|
| 0 | **0.0** | No interior silence — normal |
| 1 | **0.4** | Single silence block — suspicious |
| 2+ | **0.8** | Multiple blocks — strong AI indicator |

Note: the total duration of silence blocks is recorded but the subscore is
determined by block count.

---

### T5: Encoder Chain

| Attribute | Value |
|-----------|-------|
| **ID** | T5 |
| **Name** | `encoder_chain` |
| **Weight** | 5 |
| **Reliability** | 0.7 |
| **Group** | technical |

#### What It Measures

Scans encoder-related metadata tags (`encoder`, `tsse`, `writing_library`,
`software`, `comment`) for generator name patterns (reuses M1 pattern list).
Also flags lossy codecs (MP3, AAC, OGG, OPUS, M4A, WMA) that lack any encoder
tag entirely.

#### Forensic Basis

Direct generator fingerprints appear in encoder tags when tracks are exported
from AI platforms. The absence of encoder tags on lossy files can indicate
non-standard encoding pipelines (some generators skip LAME/FAAC headers).
Conventional DAW exports always include encoder identification.

#### Scoring Logic

| Condition | Subscore | Interpretation |
|-----------|----------|----------------|
| Generator pattern found in encoder tags | **1.0** | Direct generator fingerprint |
| Lossy codec with no encoder tag | **0.3** | Suspicious missing encoder header |
| No generator pattern, encoder present | **0.0** | Normal encoder chain |

**Generator patterns checked** (from M1 config): suno, udio, stable audio,
riffusion, musicgen, aiva, soundraw, boomy, ecrett, mubert, loudly.

---

### T6: Sample Rate Artifacts

| Attribute | Value |
|-----------|-------|
| **ID** | T6 |
| **Name** | `sr_artifacts` |
| **Weight** | 5 |
| **Reliability** | 0.5 |
| **Group** | technical |

#### What It Measures

Unusual sample rates and correlations between sample rate, codec, and bitrate.

#### Forensic Basis

- **Non-standard sample rates** (not 44100 or 48000 Hz) may indicate generation
  pipelines that use non-standard internal processing rates.
- **48 kHz MP3 at low bitrate** (≤ 192 kbps) suggests the file was upsampled from
  44.1 kHz before encoding, which is common when AI generators output at 48 kHz
  and the file is then lossy-encoded for distribution. Genuine 48 kHz MP3 files
  at low bitrate are rare since most music is produced at 44.1 kHz.

#### Scoring Logic

| Condition | Subscore | Interpretation |
|-----------|----------|----------------|
| Sample rate not 44100 or 48000 Hz | **0.5** | Unusual sample rate |
| 48 kHz MP3 with bitrate ≤ 192 kbps | **0.4** | Upsample hint |
| Normal (44.1/48 kHz, appropriate bitrate) | **0.0** | No artifacts detected |

---

### T7: Duration Sanity

| Attribute | Value |
|-----------|-------|
| **ID** | T7 |
| **Name** | `bpm_duration_sanity` |
| **Weight** | 3 |
| **Reliability** | 0.3 |
| **Group** | technical |

#### What It Measures

Track duration compared against typical music lengths.

#### Forensic Basis

AI generators often produce very short clips (especially free-tier outputs
limited to 30–60 seconds) or unusually long tracks (extended generation runs
that are never edited down). While short intros and long DJ mixes exist in
human music, extreme durations correlate with AI output patterns.

#### Scoring Logic

| Duration | Subscore | Interpretation |
|----------|----------|----------------|
| < 60 seconds | **0.6** | Very short — likely AI snippet or demo |
| > 900 seconds (> 15 min) | **0.3** | Very long — extended unedited generation |
| 60 – 900 seconds | **0.0** | Normal music duration |

#### Note

This is the lowest-reliability technical signal (r=0.3) because duration alone
is a weak indicator. It contributes minimally to the final score.

---

## Metadata Signals (M1 — M4)

Group weight: **25**. Always available. Requires only local tag inspection.

| ID | Name | Weight | Reliability | Measurement |
|----|------|--------|-------------|-------------|
| M1 | watermark_scan | 12 | 0.9 | Direct generator signatures in tags |
| M2 | identifier_gaps | 7 | 0.5 | ISRC, catalog number, UPC/Barcode presence |
| M3 | cover_provenance | 5 | 0.6 | EXIF software strings from embedded artwork |
| M4 | naming_heuristics | 4 | 0.4 | Filename patterns (catalog numbers, acronyms, suffixes) |

> **M4 weight reduced from 6 to 4** in the current version to reduce false positives
> from legitimate catalog-number filenames and short artist names.

---

### M1: Watermark Scan

| Attribute | Value |
|-----------|-------|
| **ID** | M1 |
| **Name** | `watermark_scan` |
| **Weight** | 12 |
| **Reliability** | 0.9 |
| **Group** | metadata |

#### What It Measures

Scans all metadata tags (including comments) for known AI generator name
patterns. Supports a **whitelist** of benign terms that contain generator names
as substrings (e.g., "promo-cloud" contains no AI signal).

#### Forensic Basis

Most AI music generators embed their platform name in metadata tags, either
explicitly (e.g., `encoder: Suno AI`) or implicitly through comment fields
(e.g., `comment: Generated with Udio`). This is the single most reliable
signal in the entire system because it represents a direct, intentional
fingerprint left by the generator.

#### Known Generator Patterns

| Pattern | Platform |
|---------|----------|
| `suno` | Suno AI |
| `udio` | Udio |
| `stable audio` | Stability AI / Stable Audio |
| `riffusion` | Riffusion |
| `musicgen` | Meta MusicGen |
| `aiva` | AIVA Technologies |
| `soundraw` | Soundraw |
| `boomy` | Boomy Corporation |
| `ecrett` | Ecrett Music |
| `mubert` | Mubert |
| `loudly` | Loudly |

#### Whitelist

Patterns that should **not** trigger the signal even though they may contain
substrings of generator names:

- `promo-cloud` (music distribution platform)
- `konkah engine` (DJ software)

#### Scoring Logic

| Condition | Subscore | Interpretation |
|-----------|----------|----------------|
| Any generator pattern found in any tag | **1.0** | Direct AI watermark |
| No pattern found | **0.0** | No watermark detected |

**Configuration (patterns and whitelist are tunable):**

```json
"M1": {
  "patterns": ["suno", "udio", "stable audio", "riffusion", "musicgen",
               "aiva", "soundraw", "boomy", "ecrett", "mubert", "loudly"],
  "whitelist": ["promo-cloud", "konkah engine"]
}
```

---

### M2: Identifier Gaps

| Attribute | Value |
|-----------|-------|
| **ID** | M2 |
| **Name** | `identifier_gaps` |
| **Weight** | 7 |
| **Reliability** | 0.5 |
| **Group** | metadata |

#### What It Measures

Presence of standard commercial music identifiers in metadata tags:

- **ISRC** (International Standard Recording Code) — keys: `isrc`, `tsrc`
- **Catalog number** — keys: `catalog`, `catalognumber`
- **UPC / Barcode** — keys: `barcode`, `upc`, `ean`

#### Forensic Basis

Professional music releases distributed through established labels always include
ISRC codes and usually catalog numbers and UPC barcodes. AI-generated music
released through hobbyist platforms or self-distribution pipelines typically
lacks these identifiers. While some independent human artists also lack ISRCs,
the complete absence of all three identifier types on a track claiming
commercial distribution is suspicious.

#### Scoring Logic

| Identifiers Present | Subscore | Interpretation |
|--------------------|----------|----------------|
| All 3 present (ISRC + catalog + UPC) | **0.0** | Professional release — no concern |
| 1 or 2 present | **0.3** | Partial identifiers — mildly suspicious |
| None present | **0.6** | No identifiers — likely non-commercial / AI |

---

### M3: Cover Provenance

| Attribute | Value |
|-----------|-------|
| **ID** | M3 |
| **Name** | `cover_provenance` |
| **Weight** | 5 |
| **Reliability** | 0.6 |
| **Group** | metadata |

#### What It Measures

Extracts the embedded cover artwork from the audio file, then reads its EXIF
metadata (Software, Artist, Comment, ImageDescription fields) using `exiftool`.
Checks for known AI image generator signatures.

#### Forensic Basis

AI music releases frequently use AI-generated cover art. Major image generators
leave identifiable strings in EXIF metadata that reveal their origin. Legitimate
releases use artwork from photographers, designers, or stock photo services that
leave different (or no generator) strings.

#### Known AI Image Tool Patterns

| Pattern | Platform |
|---------|----------|
| `midjourney` | Midjourney |
| `dall-e`, `dalle` | OpenAI DALL-E |
| `stable diffusion`, `stable-diffusion` | Stability AI |
| `firefly` | Adobe Firefly |
| `flux` | Black Forest Labs |
| `ideogram` | Ideogram AI |
| `leonardo.ai` | Leonardo AI |

#### Scoring Logic

| Condition | Subscore | Interpretation |
|-----------|----------|----------------|
| Generator string found in cover EXIF | **1.0** | AI-generated cover art |
| Cover present, no generator strings | **0.0** | Cover exists, provenance unknown |
| No embedded cover | **0.5** | No cover to evaluate — neutral |

#### Note

Requires `exiftool` to be installed. If absent, the signal returns no findings
(not a failure).

---

### M4: Naming Heuristics

| Attribute | Value |
|-----------|-------|
| **ID** | M4 |
| **Name** | `naming_heuristics` |
| **Weight** | 4 |
| **Reliability** | 0.4 |
| **Group** | metadata |

> **Weight reduced from 6 to 4** in the current version to reduce false positives
> from legitimate catalog-number filenames and short artist names.

#### What It Measures

Three independent filename heuristics:

1. **Catalog-number-like tokens** — regex `[A-Z]{2,}\d{4,}` in the filename stem (e.g., `BV062026`, `LM078`)
2. **Short uppercase artist names** — artist portion (before ` - `) is all uppercase, 5 characters or fewer, contains at least one letter (e.g., `CLMX`, `DJ`)
3. **Title suffixes** — configurable suffix words in the title portion (e.g., "xtd", "extended", "remix", "vocal", "instrumental", "radio edit")

#### Forensic Basis

- **Catalog numbers** like `BV062026` correlate with automated/self-service
  distribution platforms where AI content farms release tracks.
- **Short uppercase artist codes** (CLMX, similar to production codes) suggest
  synthetic artist identities rather than human stage names.
- **Generic version suffixes** are overrepresented in AI releases where the
  generator produces multiple variants and labels them with standard suffixes
  rather than creative remix names.

These heuristics individually are weak signals but compound when multiple
patterns appear in the same filename.

#### Scoring Logic

The subscore is determined by the **count** of heuristic hits:

| Heuristic Hits | Subscore | Interpretation |
|---------------|----------|----------------|
| 0 | **0.0** | No naming anomalies |
| 1 | **0.35** | Single heuristic hit — mildly suspicious |
| 2 | **0.65** | Two hits — moderately suspicious |
| 3+ | **0.9** | Three or more hits — strongly suspicious |

#### Configuration

```json
"M4": {
  "acronym_artist_max_len": 5,
  "suffixes": ["xtd", "extended", "remix", "vocal", "instrumental", "radio edit"]
}
```

---

## Context Signals (C1 — C5)

Group weight: **35**. Only available with `--online` flag. Requires network
access for MusicBrainz, Discogs, SoundCloud lookups.

| ID | Name | Weight | Reliability | Measurement |
|----|------|--------|-------------|-------------|
| C1 | artist_footprint | 5 | 0.6 | Artist presence in MusicBrainz, Discogs, SoundCloud |
| C2 | label_pattern | 6 | 0.5 | Release cadence, one-release-artist ratio |
| C3 | release_db_presence | 7 | 0.6 | MB/Discogs/Beatport existence + age |
| C4 | press_text | 5 | 0.4 | AI buzzword density in tag URLs |
| C5 | community_db | 9 | 0.8 | Curated known-AI-artist database lookup |

> **C1 weight reduced from 8 to 5** in the current version to reduce false
> positives from legitimate independent artists with minimal online presence.

---

### C1: Artist Footprint

| Attribute | Value |
|-----------|-------|
| **ID** | C1 |
| **Name** | `artist_footprint` |
| **Weight** | 5 |
| **Reliability** | 0.6 |
| **Group** | context |

#### What It Measures

Searches for the artist name across three databases:

1. **MusicBrainz** — keyless public API, searches by artist name
2. **Discogs** — public API, searches by artist name
3. **SoundCloud** — requires `SOUNDCLOUD_CLIENT_ID` in environment; searches by artist name

Returns the number of databases where the artist was found.

#### Forensic Basis

Legitimate artists have entries in one or more music databases (Discogs,
MusicBrainz, SoundCloud). AI-generated artist aliases typically have zero
footprint across all databases — no release history, no profiles, no community
presence. However, very new independent human artists may also have limited
footprint, which is why reliability is moderate (0.6) rather than high.

#### Scoring Logic

| Databases Found | Subscore | Interpretation |
|----------------|----------|----------------|
| >= 1 database match | **0.0** | Artist has real-world footprint |
| 0 database matches | **0.8** | No footprint — suspicious |

**Special case:** If no artist can be identified from tags or filename, returns
subscore 0.5 (uncertain).

---

### C2: Label Pattern

| Attribute | Value |
|-----------|-------|
| **ID** | C2 |
| **Name** | `label_pattern` |
| **Weight** | 6 |
| **Reliability** | 0.5 |
| **Group** | context |

#### What It Measures

Analyzes label behavior from Discogs or MusicBrainz data:

1. **Release cadence** — total releases divided by active years (releases per year)
2. **One-release-artist ratio** — proportion of artists on the label who have
   exactly one release (indicating disposable artist identities)
3. **Label count** — number of distinct labels associated with the artist

#### Forensic Basis

AI content farms operate through "labels" that release many tracks from many
different "artists," each of which has exactly one release. This pattern
contrasts with legitimate labels that cultivate artists over multiple releases.
High cadence (>12 releases/year) combined with high one-release-artist ratios
is a signature of automated content distribution.

#### Scoring Logic

Two sub-metrics averaged:

**Cadence component:** `min(1.0, cadence / 12.0)` — 12+ releases/year = maximum score

**One-release ratio component:** Direct ratio (0.0 – 1.0)

Final: `(cadence_score + ratio_score) / 2`

| Scenario | Expected Subscore |
|----------|------------------|
| 1 release/year, 0% one-release artists | **~0.0** — legitimate label |
| 12+ releases/year, 80%+ one-release artists | **~0.9** — content farm |
| No label data found | **0.3** — mild concern |

#### Data Sources

1. **Discogs** (preferred): Fetches artist releases, extracts label names and release years
2. **MusicBrainz** (fallback): Fetches release groups, extracts dates (label data is less granular)

---

### C3: Release DB Presence

| Attribute | Value |
|-----------|-------|
| **ID** | C3 |
| **Name** | `release_db_presence` |
| **Weight** | 7 |
| **Reliability** | 0.6 |
| **Group** | context |

#### What It Measures

Searches for the specific track (artist + title) across:

1. **MusicBrainz** — recording search, returns first release date and age
2. **Discogs** — release search, returns year and age
3. **Beatport** — basic search, checks for page existence

Returns presence across databases and the age of the oldest known release.

#### Forensic Basis

A track that does not appear in any music database is suspicious. Professional
releases are always catalogued in at least one of these databases. AI-generated
tracks distributed through hobbyist channels may never be catalogued. Age also
matters: tracks that appear to be very new (released within the last year) from
unknown artists warrant more scrutiny than older releases from established artists.

#### Scoring Logic

| Condition | Subscore | Interpretation |
|-----------|----------|----------------|
| No DB presence anywhere | **0.7** | Suspicious — absent from all databases |
| Found in DB, age > 5 years | **0.1** | Established release — low concern |
| Found in DB, age ≤ 5 years | **0.3** | Present but recent — mild concern |
| No artist/title identified | **0.5** | Uncertain |

#### Data Sources

1. **MusicBrainz**: `ws/2/recording/?query=artist:... AND recording:...`
2. **Discogs**: `database/search?q=...&type=release`
3. **Beatport**: `beatport.com/search?q=...` (HTML scrape, checks response size)

---

### C4: Press Text

| Attribute | Value |
|-----------|-------|
| **ID** | C4 |
| **Name** | `press_text` |
| **Weight** | 5 |
| **Reliability** | 0.4 |
| **Group** | context |

#### What It Measures

Extracts URLs from metadata tags (comment, description, etc.), fetches up to 3
pages, and counts AI-related buzzwords in the page text. Computes density per
1000 words.

#### Forensic Basis

AI music releases often have promotional URLs that explicitly mention AI
generation. Press releases, landing pages, and distribution metadata may
contain terms like "AI-generated," "Suno," "machine learning," etc. The
presence of multiple such buzzwords in promotional text is a strong indicator.

#### AI Buzzword List

| Buzzword | Significance |
|----------|-------------|
| `ai-generated`, `ai generated` | Direct AI disclosure |
| `artificial intelligence`, `machine learning` | General AI terminology |
| `neural network`, `deep learning` | Technical AI terms |
| `generative` | Generative AI descriptor |
| `suno`, `udio`, `stable audio` | Generator platform names |
| `musicgen`, `riffusion`, `aiva` | Generator platform names |
| `soundraw`, `boomy`, `mubert`, `loudly` | Generator platform names |
| `ai music` | AI music descriptor |
| `algorithmic composition` | Alternative AI descriptor |
| `procedural generation` | Alternative AI descriptor |

#### Scoring Logic

| Condition | Subscore | Interpretation |
|-----------|----------|----------------|
| Buzzword density ≥ 5 per 1000 words | **1.0** | Strong AI indicator in press text |
| Density 0 | **0.0** | No AI buzzwords found |
| Density 0–5 | **0.0 – 1.0** | Linear ramp: `density / 5.0` |
| No URLs in tags | **0.0** | No text to analyze |
| URLs found but none fetchable | **0.0** | Inconclusive |

#### Note

This signal has the lowest reliability (0.4) among context signals because:
- Many tracks have no URLs in tags at all
- Web pages change and may not be fetchable
- Buzzword density can be inflated by unrelated content

---

### C5: Community DB

| Attribute | Value |
|-----------|-------|
| **ID** | C5 |
| **Name** | `community_db` |
| **Weight** | 9 |
| **Reliability** | 0.8 |
| **Group** | context |

#### What It Measures

Looks up the artist name (and alternative tags like `album_artist`, `performer`)
against a curated database of known AI-generated artists and projects. The
database is fetched from a remote GitHub repository with local caching, and
falls back to a bundled version if offline.

#### Forensic Basis

The community database contains documented cases of AI-generated artists and
projects with evidence URLs and confidence ratings. This is the highest-weight
context signal because it represents ground truth from human investigation and
journalism. When an artist appears in this database, it is a strong indicator
of AI origin based on prior documented evidence.

#### Known AI Artists (bundled examples)

| Artist | Aliases | Confidence | Evidence |
|--------|---------|------------|----------|
| CLMX | Cli-Max, @clmxmusic | high | Music Worx editorial "Likely AI-assisted"; Beatport release with no prior discography |
| The Velvet Sundown | — | high | The Verge investigation: AI-generated band with millions of Spotify streams |
| Anna Indiana | @annaindianaai | high | Fully AI-generated singer (music, lyrics, voice, visuals); creator admitted AI origin |
| AIVA | AIVA Technologies | high | Official AI composer platform — explicitly markets as AI-generated music |
| Soundraw | — | high | AI music generator platform — explicitly markets as AI-generated royalty-free music |
| Boomy | — | high | AI music creation platform — explicitly markets as AI-generated music |
| Mubert | — | high | AI generative music platform — explicitly markets as AI-generated streaming music |

#### Database Schema

```json
{
  "schema_version": "1.0.0",
  "updated": "2026-08-22",
  "license": "CC0-1.0",
  "entries": [
    {
      "id": "clmx",
      "name": "CLMX",
      "aliases": ["Cli-Max", "@clmxmusic"],
      "type": "artist",
      "labels": ["Balearic Vibes Records"],
      "ai_confidence": "high",
      "evidence": [
        {
          "url": "https://pro.music-worx.com/release/freedom-balearic-vibes",
          "note": "Music Worx editorial: 'Likely AI-assisted'",
          "date": "2026-07"
        }
      ],
      "added": "2026-08-22",
      "verified": "2026-08-22"
    }
  ]
}
```

#### Confidence Mapping

| `ai_confidence` | Subscore | Meaning |
|-----------------|----------|---------|
| `high` | **1.0** | Documented AI origin with strong evidence |
| `medium` | **0.7** | Probable AI origin with supporting evidence |
| `low` | **0.4** | Suspected AI origin, circumstantial evidence |

#### Matching Logic

1. **Exact match** (case-insensitive): Compare artist name and all aliases against database entries
2. **Fuzzy match** (opt-in via config): Jaro-Winkler similarity with threshold ≥ 0.9; results flagged as `"fuzzy": true`

#### Scoring Logic

| Condition | Subscore | Interpretation |
|-----------|----------|----------------|
| Artist found with `high` confidence | **1.0** | Documented AI artist |
| Artist found with `medium` confidence | **0.7** | Probable AI artist |
| Artist found with `low` confidence | **0.4** | Suspected AI artist |
| Artist not found in database | **0.0** | No community data available |
| Community DB unavailable (network + cache failure) | signal skipped | Not counted in aggregation |

#### Data Loading Priority

1. **Remote fetch** from configured URL (default: GitHub raw content)
2. **Local cache** at `~/.cache/ai-music-checker/known_ai_artists.json` (TTL: 24h)
3. **Bundled database** shipped with the package

#### Configuration

```json
"community_db": {
  "enabled": true,
  "url": "https://raw.githubusercontent.com/holgerkampffmeyer2/ai-artists-db/main/known_ai_artists.json",
  "ttl_hours": 24,
  "fuzzy_enabled": false,
  "fuzzy_threshold": 0.9
}
```

---

## Scoring Model Details

### Effective Weight Calculation

Each signal's contribution is scaled by its weight, reliability, and availability:

```
W_i = w_i × r_i × availability_i
```

Where:
- `w_i` = signal weight (integer, sum of group weights = 100)
- `r_i` = reliability factor (0.0 – 1.0)
- `availability_i` = 1.0 if the signal ran successfully, 0.0 if skipped

### Group Aggregation

Within each group, the weighted subscore is computed as:

```
group_score_g = Σ(W_i × s_i) / Σ(W_i)    for all signals i in group g
```

Signals that are unavailable (network failure, missing tool) are excluded from
both numerator and denominator — the group score is computed only from signals
that actually ran.

### Coverage

Coverage measures what fraction of expected signal weight was actually available:

```
coverage = ΣW_available / ΣW_possible
```

A coverage of 1.0 means all signals in all enabled groups ran successfully.
Lower coverage reduces statement confidence.

### Consistency

Consistency measures agreement between group scores:

```
consistency = 1 - normalized_mean_absolute_deviation(group_scores)
```

If group scores are 0.3, 0.5, and 0.8, the mean absolute deviation is high,
reducing consistency. If all groups agree (e.g., all around 0.4), consistency
is high.

### Final Probability

Groups are re-normalized over only those groups that have coverage > 0:

```
active_groups = {g : (score, cov) for g in group_scores if cov > 0}
P(ai) = Σ(group_weight_g × group_score_g) / Σ(group_weight_g)    for g in active_groups
```

Group weights from `config.json`:
- Technical: 40
- Metadata: 25
- Context: 35

### Top Indicators

The top-3 AI-indicating signals are determined by:

```
delta_i = W_i × (s_i - 0.5)
```

Signals with the largest positive `delta` values are the strongest AI indicators.
Signals with negative `delta` values are evidence toward human origin.

---

## Configuration Reference

All signal parameters are configurable via `config.json`. The full schema:

```json
{
  "weights": {
    "technical": 40,
    "metadata": 25,
    "context": 35
  },
  "criteria": {
    "T1": {
      "threshold_khz": 16,
      "severe_khz": 14
    },
    "T2": {
      "crest_db_threshold": 8,
      "lra_lu_threshold": 3
    },
    "M1": {
      "patterns": [
        "suno", "udio", "stable audio", "riffusion", "musicgen",
        "aiva", "soundraw", "boomy", "ecrett", "mubert", "loudly"
      ],
      "whitelist": ["promo-cloud", "konkah engine"]
    },
    "M4": {
      "acronym_artist_max_len": 5,
      "suffixes": ["xtd", "extended", "remix", "vocal", "instrumental", "radio edit"]
    }
  },
  "metadata_sources": ["musicbrainz", "discogs", "soundcloud"],
  "soundcloud_client_id_env": "SOUNDCLOUD_CLIENT_ID",
  "request_timeout_s": 10,
  "retry_attempts": 3,
  "community_db": {
    "enabled": true,
    "url": "https://raw.githubusercontent.com/holgerkampffmeyer2/ai-artists-db/main/known_ai_artists.json",
    "ttl_hours": 24,
    "fuzzy_enabled": false,
    "fuzzy_threshold": 0.9
  }
}
```

### Criteria Values by Signal

| Signal | Parameter | Default | Description |
|--------|-----------|---------|-------------|
| T1 | `threshold_khz` | 16 | Highpass frequency for threshold pass |
| T1 | `severe_khz` | 14 | Highpass frequency for severe pass |
| T2 | `crest_db_threshold` | 8 | Below this crest factor = full AI score |
| T2 | `lra_lu_threshold` | 3 | Below this LRA = full AI score |
| M1 | `patterns` | (see above) | Generator name patterns to match |
| M1 | `whitelist` | (see above) | Benign terms to exclude from matching |
| M4 | `acronym_artist_max_len` | 5 | Max length for short uppercase artist detection |
| M4 | `suffixes` | (see above) | Title suffix patterns to detect |

---

## Dependencies

| Signal | Required Tool | Optional Tool | Network |
|--------|--------------|---------------|---------|
| T1 | ffmpeg | — | No |
| T2 | ffmpeg | — | No |
| T3 | ffmpeg | — | No |
| T4 | ffmpeg | — | No |
| T5 | ffprobe | — | No |
| T6 | ffprobe | — | No |
| T7 | ffprobe | — | No |
| M1 | ffprobe | — | No |
| M2 | ffprobe | — | No |
| M3 | ffmpeg, exiftool | — | No |
| M4 | — (filesystem only) | — | No |
| C1 | — | SoundCloud client ID | Yes (MusicBrainz, Discogs, SoundCloud) |
| C2 | — | — | Yes (Discogs, MusicBrainz) |
| C3 | — | — | Yes (MusicBrainz, Discogs, Beatport) |
| C4 | — | — | Yes (HTTP fetch) |
| C5 | — | — | Yes (GitHub raw, cached) |

---

## References

### Academic Papers

- Su, D., et al. (2023). "Adversarial Machine Learning in Audio Deepfake Detection." IEEE International Workshop on Information Forensics and Security (WIFS).
- Mangaokar, N., et al. (2023). "PRNU: Are We There Yet? A Survey on Audio Deepfake Detection." arXiv preprint.
- Sobron, P., et al. (2023). "Audio Deepfake Detection: A Survey." arXiv preprint.
- Wang, R., et al. (2023). "A Survey on Audio Deepfake Detection." arXiv preprint.

### Standards and Technical Documents

- EBU R128 -- Loudness normalisation and permitted maximum level of audio signals. European Broadcasting Union, 2020.
- AES Technical Document AES-TD1004.1.15-10 -- Program loudness measurement and loudness metering.
- ITU-R BS.1770-4 -- Algorithms to measure audio programme loudness and true-peak audio level. International Telecommunication Union, 2015.
- ISO 3901:2019 -- International Standard Recording Code (ISRC). International Organization for Standardization.

### Neural Audio Codec Research

- Défossez, A., et al. (2022). "High Fidelity Neural Audio Compression." arXiv:2210.13438 (EnCodec / Meta).
- Zeghidour, N., et al. (2021). "SoundStream: An End-to-End Neural Audio Codec." IEEE/ACM Transactions on Audio, Speech, and Language Processing (Google).
- Kumar, K., et al. (2019). "Codec Demo: High Fidelity Speech Compression." Meta AI Research (SoundStream precursor).

### AI Music Generation Platforms

- Suno AI -- https://suno.com (AI music generation platform)
- Udio -- https://www.udio.com (AI music generation platform)
- Stability AI / Stable Audio -- https://www.stableaudio.com (AI audio generation)
- Meta MusicGen -- https://github.com/facebookresearch/audiocraft (open-source music generation)
- Riffusion -- https://riffusion.com (spectrogram-based music generation)
- AIVA Technologies -- https://www.aiva.ai (AI composer platform)
- Soundraw -- https://soundraw.io (AI music for content creators)
- Boomy Corporation -- https://boomy.com (AI music creation platform)
- Ecrett Music -- https://www.ecrett.com (AI music generation)
- Mubert -- https://mubert.com (AI generative music streaming)
- Loudly -- https://www.loudly.com (AI music creation platform)

### Music Database APIs

- MusicBrainz API -- https://musicbrainz.org/doc/MusicBrainz_API (keyless, rate-limited 1 req/s)
- Discogs API -- https://www.discogs.com/developers/ (60 req/min, token optional)
- SoundCloud API v2 -- https://developers.soundcloud.com/ (client ID required)
- Beatport -- https://www.beatport.com (HTML scraping, no official API)

### Community Database

- ai-artists-db -- https://github.com/holgerkampffmeyer2/ai-artists-db (curated known-AI-artist database, CC0-1.0 license)
