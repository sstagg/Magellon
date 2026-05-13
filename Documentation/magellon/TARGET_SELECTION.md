# Magellon — Target Selection Plan

**Status:** Forward-looking design doc, 2026-05-13.
**Audience:** Architects + ML leads + plugin authors deciding what to build for automated target-site selection on the cryo-EM grid.
**Companion:** `ARCHITECTURE.md` (data plane, categories, lineage), `PLUGINS.md` (plugin runtime + dispatch), `AI.md` (Claude integration), and — for Magellon Pro — `magellon-rust-mrc/docs/image-layers-architecture.md` (Layer Artifact subtype).

---

## 0. One-paragraph summary

Given a low-mag atlas (LM) and/or medium-mag square images (MM), choose which holes deserve high-mag (HM) exposures. We build this in two tracks. **Track 1 — the Tool**: a transparent, deterministic ranker that scores holes from typed image *layers* (ice thickness, hole detection, contamination flag, etc.). It works from day one and is the source of operator-visible explanations. **Track 2 — the Brain**: an outcome-supervised neural ranker trained on Magellon's own atlas-→-final-map lineage plus public corpora. The Brain augments the Tool, the Tool remains a permanent baseline / fallback / sanity-check. Each layer is an Artifact subtype (already designed in the image-layers spec); each ranker is a plugin TaskCategory.

---

## 1. Goal

Replace operator-by-operator hole-picking with an automated decision: **"of all candidate holes seen at LM/MM, which N should we expose at HM?"**, ranked by predicted high-mag yield. Inputs: LM atlas + MM square images already collected during screening. Outputs: a ranked target list (hole IDs + scores + reasons) dispatched to the HM acquisition plugin.

Non-goals (explicitly): scheduling tomography tilt-series (see SPACEtomo), motion correction, post-exposure CTF — those are downstream and out of scope here.

---

## 2. Strategy: Tool + Brain

```
                       LM atlas + MM squares
                                 │
                  ┌──────────────┴──────────────┐
                  │   per-image layer plugins   │
                  │   (ice / squares / holes /  │
                  │    contamination / ...)     │
                  └──────────────┬──────────────┘
                                 │
                       layer Artifacts (per mic)
                                 │
                  ┌──────────────┴──────────────┐
                  │                             │
        TRACK 1: TOOL                   TRACK 2: BRAIN
        heuristic ranker                yield-predictor head
        weighted score                  (DRACO ViT + heads)
        explainable knobs               outcome-supervised
                  │                             │
                  └──────────────┬──────────────┘
                                 │
                       ensemble + exploration
                                 │
                       ranked target list  ───►  HM acquisition
```

**Why both, permanently.** Tool is deterministic and runnable on day one; the operator can read the score and override. Brain learns from outcomes that the field has never had labeled data for. Pure-learned end-to-end fails in cryo-EM precisely because grid/sample variance is huge and labels are slow. The Tool stays as: cold-start for novel grid types (lacey, Spotiton, 0.6/0.8 µm), sanity-check when the Brain is uncertain, audit trail, and the *feature engineer* for the Brain (every layer the Tool consumes is a Brain input too).

**Framing.** "Tool = brain's hands, Brain = tool's judgement." Both stay.

---

## 3. What exists today

### Already shipped in Magellon

| Capability | Where | Status |
|---|---|---|
| Square detection (LM atlas → ranked squares + brightness) | `plugins/magellon_ptolemy_plugin/` — TaskCategory `SQUARE_DETECTION` (code 6) | live |
| Hole detection (MM square → ranked holes + score) | same plugin — TaskCategory `HOLE_DETECTION` (code 7) | live |
| Particle picking (template / BoxNet / Topaz) | `plugins/magellon_*_picker_plugin/` | live |
| Stack-maker, classifier | plugins + sandbox | live / partial |

### Working in sandbox, not wired

| Capability | Where | Notes |
|---|---|---|
| Ice thickness (MeasureIce, aperture-limited scattering) | `Sandbox/ice_thickness_measureice/` | Krios 300 kV HDF5 LUT shipped; `measure_thickness.py` + `analyze_dir.py` validated on the 24dec03a dataset. No plugin wrapper yet. |

### Solved by the field — do not reinvent

- **Square / hole detection** on Quantifoil/UltrAuFoil: Ptolemy and SmartScope (Faster R-CNN + YOLOv5) match human-expert performance. Operator-mimicry is plateaued.
- **Single-image ice thickness**: MeasureIce <10% error below 50 nm. No published deep model demonstrably beats it on the LM/MM single-image task.
- **Backbone pretraining**: DRACO (Masked Autoencoder, 270k EMPIAR movies) and Cryo-IEF (65M particles, self-supervised ViT) provide reusable weights.

### The actual gap

1. **Ranking layer.** No plugin combines ice + hole score + edge proximity + contamination into a per-hole expected-yield score.
2. **Atlas → square → hole → ranking → HM dispatch chain.** CoreService doesn't auto-wire this today.
3. **Atlas UI.** No React panel showing atlas with overlay layers and click-through to MM with ranked targets.
4. **Outcome-supervised yield head.** No published model predicts HM resolution / particle count from LM/MM features. Magellon's Artifact STI + PipelineRun rollup (per `project_artifact_bus_invariants`) uniquely lets us label this.

---

## 4. Layer model

We adopt the **image-layers architecture** (`magellon-rust-mrc/docs/image-layers-architecture.md`) as the storage and addressing model for every analytical overlay. Recap:

- `Layer` is an `Artifact` STI subtype: immutable, lineage-tracked, content-hashed.
- Three orthogonal axes: **kind** (Raster | Vector | ScalarField | VectorField), **tag** (freeform string — `ice_thickness`, `picker_boxes`, ...), **coordinate frame** (parent_subject_type, parent_subject_id, binning_factor).
- Plugins read upstream layers via `accepts:` and emit new layers via `produces:` declarations.

The target-selection ranker is **just another plugin** that `accepts:` a set of layer tags and `produces:` a ranked target list.

### 4.1 Layer catalog — predictors vs verifiers

Layers split into two disjoint roles, and the distinction is the organizing principle of the whole plan.

- **Predictor layers** are measured at LM or MM, *before* the high-mag exposure decision. They feed the Tool's ranking score and the Brain's input features. They answer: "looking at this hole at MM resolution, how likely is it to give us a good HM exposure?"
- **Verifier layers** are measured at HM, *after* exposure. They never feed the ranker at decision time. They are outcomes — labels for Brain training and, in the per-grid Bayesian loop (P10), inputs to a second-pass re-rank of *remaining* holes on the same grid.

**Treating a CTF / FFT / pick layer as an LM/MM predictor is a category error.** They don't exist at MM with enough SNR to be reliable.

#### 4.1.1 Predictor layers (LM / MM inputs to ranking)

| Layer tag | LM (atlas, ~200–500 nm/px) | MM (square, ~10–50 nm/px) | Notes |
|---|---|---|---|
| `ice_thickness` | gross | **per-hole** | MeasureIce single-image ALS; dominant predictor |
| `ice_gradient` | weak | yes | second-order variance signal across the square |
| `squares` (Ptolemy detect + score) | **yes** | — | atlas-level square ranker |
| `holes` (Ptolemy detect + score) | — | **yes** | hole detector + lattice score |
| `hole_edge_distance` | — | **yes** | per-hole geometric feature |
| `contamination_mask` | gross | **yes** | classical-CV first; segmentation head later |
| `crystalline_ice_flag` | gross | yes | hard filter, kills score on positive |
| `grid_type` (Quantifoil / lacey / Spotiton / ...) | **yes** | — | gates which detector + ranker variant to apply |

#### 4.1.2 Verifier layers (HM outputs — labels only)

These are the **cheap-to-run** verifiers that produce a label per exposure. The full structural pipeline (2D class → 3D refine → final-map resolution) is too slow to label routinely; we sample those on a small ground-truth subset.

| Layer tag | Cost per exposure | Catches | Role |
|---|---|---|---|
| `micrograph_quality` — `eval_micrograph` probability | ~1 s GPU | empty holes, contamination, non-particle distributions | **canonical scalar verifier** |
| `ctf_fit` — CTFFind resolution, defocus, astig ratio | ~5–15 s CPU | drift, astigmatism, defocus out-of-range | second verifier |
| `motion` — MotionCor total motion (Å) | ~5–10 s GPU | beam-induced motion (kills high-res) | second verifier |
| `picks` — n_picks + mean score from production picker | seconds | direct yield count + score distribution | second verifier |
| `class_avg_quality` (2D class) | minutes | preferred orientation, conformational heterogeneity | ground-truth calibration only |
| `final_map_resolution_a` | hours-days | structural validation | ground-truth calibration only |

**`eval_micrograph` is the canonical scalar verifier.** It is a Cianfrocco-lab trained model (Magellon's own lineage, see §8.4) that runs the BoxNet particle/dirt segmentation, takes the **particle channel only**, computes its 2D FFT, radially averages to 256 bins (1/Å, log-scale), and passes the spectrum through a small 1D-CNN to a sigmoid. The output is P(good) ∈ [0, 1]. The signal it captures is *spatial distribution of detected particles* — count alone is gameable, but the radial spectrum of the particle mask catches "are the particles distributed sensibly" (correct spacing, isotropic, not blobby contamination). Empirical caveat: in the shipped demos `great=0.918`, `bad=0.728`, `empty=0.595` — all three cross the 0.5 binary threshold. **Use the raw probability, not the binary verdict, as the training label.** A regression head wants continuous signal anyway.

**Rule.** A layer is an *input* to ranking only at the magnifications listed in §4.1.1. HM verifier layers (§4.1.2) exist in the layer system — they're great viewer overlays after the fact — but the ranker that decides *which holes to expose* never reads them at decision time.

**Per-grid Bayesian loop (P10, see §9).** Once a few calibration HM shots are in, their verifier layers *can* re-rank the *remaining* holes on the same grid. That's the unsolved research piece.

---

## 5. Coordinate contract

GIS layers all share a CRS. Cryo-EM layers from LM, MM, HM are at different magnifications and different physical positions on the grid. We need one rule.

**Decision: LM atlas is the canonical frame.** Every MM and HM artifact carries a 2D transform back to atlas pixels (stage X/Y + per-mag pixel scale, captured at acquisition time). The transform lives in hot columns on the Artifact (or the existing `ImageMetaData` blob, depending on what's cheapest to migrate).

```
LM atlas (frame = pixel coords of the atlas image)
   │
   ├── square_k  ──►  MM image_k_j  (transform: atlas_xy → MM_xy)
   │                       │
   │                       ├── hole_k_j_a ──► HM image_k_j_a (transform: MM_xy → HM_xy)
   │                       └── hole_k_j_b ──► ...
```

**Consequences.**
- The atlas viewer can render *every* downstream artifact (squares, holes, ice, picks) as a layer over the atlas, at the right place.
- The ranker reads features in one coordinate system. No per-call alignment math.
- Lineage and coordinates point the same way (parent → child).

The alternative (each magnification owns its own independent layer stack) is simpler short-term but permanently blocks the unified ranking view. Locking the LM-as-base contract now is the high-leverage decision in this doc.

---

## 6. Pro / OSS split

Per `project_magellon_pro_split` (decided 2026-05-10), the image-layers system + visual workflow builder are **Magellon Pro**. The target-ranking *plumbing* must work in OSS — automation should not be paywalled. The *layer compositor UI* is the Pro surface.

| Feature | OSS | Pro |
|---|---|---|
| `ICE_THICKNESS` plugin (per-hole nm) | yes | yes |
| `TARGET_RANKING` plugin (Tool) | yes | yes |
| Ranked target list as JSON Artifact + API | yes | yes |
| HM dispatch driven by ranker | yes | yes |
| Operator override / re-rank API | yes | yes |
| **Atlas viewer with stacked layers (ice heatmap + hole boxes + ranked-target dots, opacity + blend control)** | minimal (top-N list only) | full compositor |
| Per-layer color ramps, custom thresholds, side-by-side compare | — | yes |
| Track 2 Brain (yield-prediction head) | base score only | full multi-head + Bayesian update |

OSS gets the algorithm and the API; Pro gets the GIS-style operator interface and the trained Brain weights.

---

## 7. Track 1 — Tool: heuristic ranker

### 7.1 Score formula

A weighted sum of normalised layer signals. All weights live in CoreService config so operators can tune per facility / grid type without code changes.

```
score(hole_h) =
      w_ice   * gauss(t_nm(h);  μ=30, σ=15)         # MeasureIce sweet-spot at ~30 nm
    + w_hole  * ptolemy_hole_score(h)               # cat 7 output
    + w_sq    * ptolemy_square_brightness(parent_sq(h))
    - w_edge  * edge_penalty(hole_edge_distance(h))
    - w_cont  * contamination_logit(h)
    - w_xtal  * crystalline_ice_flag(h)
```

Defaults (start here, tune empirically):
`w_ice=1.0, w_hole=1.0, w_sq=0.3, w_edge=0.5, w_cont=2.0, w_xtal=2.0`.

**Why a sum, not a product.** Sums are robust to missing layers (a layer that didn't run contributes 0, not NaN). The contamination/crystalline terms are heavily weighted so a single strong negative kills the score even if other terms are good.

**Why these defaults.** Ice thickness is the dominant empirical predictor of HM yield at 300 kV (Neselu 2023, EMPIAR-11397; ~0.0022 Å/nm degradation slope, sweet spot <50 nm). Hole and square scores are next. Edge proximity and contamination are filters more than features.

### 7.2 Plugins to add

**Predictor-side (LM/MM, feed the ranker):**

| Plugin | TaskCategory | Input | Output |
|---|---|---|---|
| `magellon_ice_thickness_plugin/` | `ICE_THICKNESS` (new code) | MRC + voltage + aperture | Layer `(kind=Raster, tag=ice_thickness, units=nm)` + per-hole nm summary |
| `magellon_contamination_plugin/` | `CONTAMINATION_DETECT` (new code) | MM image | Layer `(kind=Raster, tag=contamination_mask, dtype=uint8)` |
| `magellon_target_ranking_plugin/` | `TARGET_RANKING` (new code) | refs to `holes` + `ice_thickness` + `contamination_mask` layers for one MM image | Ranked target list Artifact: `[{hole_id, score, reasons:{w_ice:0.42, w_hole:0.31, ...}}]` |

**Verifier-side (HM, emit labels for Brain training):**

| Plugin | TaskCategory | Input | Output |
|---|---|---|---|
| `magellon_micrograph_quality_plugin/` | `MICROGRAPH_QUALITY` (new code) | HM micrograph (post motion-correction) | Layer `(kind=ScalarField, tag=micrograph_quality, units=prob, value_range=[0,1])` + scalar P(good) |

`ICE_THICKNESS` is the first delivery — wraps `Sandbox/ice_thickness_measureice/measure_thickness.py` and the existing 300 kV LUT. The sandbox tool is already validated; this is a packaging task, not an algorithm task.

`CONTAMINATION_DETECT` starts as a classical-CV heuristic (intensity-variance thresholding on MM, mask noise + ethane droplets) and graduates to a trained segmentation head later.

`MICROGRAPH_QUALITY` wraps `Sandbox/eval_micrograph/micrograph_eval.py` (BoxNet mask → radial-spectrum CNN → P(good); see §4.1.2 for the algorithm). Pre-trained weights ship in the sandbox (`boxnet.pt`, `radial_spectrum_model.pth`, `feature_scaler.pkl`). CTF and motion outcomes are already produced by existing CTF + motion-correction plugins — no new plugin needed for those; the `TargetTrainingExample` view (§8.4) joins their outputs.

### 7.3 Dispatcher chain

A new wiring rule in CoreService: on LM import →
1. Dispatch `SQUARE_DETECTION` (Ptolemy cat 6).
2. For each top-K square, schedule MM acquisition (vendor control plugin).
3. On MM artifact created → dispatch in parallel: `HOLE_DETECTION` (cat 7), `ICE_THICKNESS`, `CONTAMINATION_DETECT`.
4. On all three layer artifacts present → dispatch `TARGET_RANKING`.
5. `TARGET_RANKING` output → HM exposure plugin reads top-N holes.

The dispatch cache (lineage-keyed, per `project_pipeline_ergonomics_plan` PE2) ensures re-ranking with new weights is free if the layers haven't changed.

### 7.4 Exploration policy (critical for Track 2)

If the Tool decides which sites get exposed, you only collect outcomes for sites the *Tool chose*. The Brain trained on those data inherits the Tool's blind spots. We solve this from day one:

- Default: top-N holes (by score) are dispatched for HM.
- **Exploration: 10% of HM dispatches are drawn from a stratified random sample over the score distribution** (specifically: weight inversely to rank so low-ranked but non-zero candidates appear).
- Exploration shots are tagged `exploration=true` in their Artifact metadata so Track 2 can up-weight them at train time.
- Tunable per session via `target_ranking_exploration_fraction` config.

Without this, the Brain plateaus at "slightly better than the Tool." With it, the Brain can discover signals the Tool's formula doesn't capture.

### 7.5 Operator override = label

Every operator override (manual re-rank, skip-this-hole, force-this-hole) is logged as a `target_decision_event` with the layer values at decision time. Those events are gold training data for Track 2 (label = "human disagreed with Tool here, and the HM outcome was X").

---

## 8. Track 2 — Brain: outcome-supervised yield head

### 8.1 Why outcome-supervised, not operator-supervised

Ptolemy and SmartScope train against expert labels (operator mimicry). That ceiling is "as good as the best human." The Brain trains against **downstream outcomes** — CTF resolution, particle count, motion, final-map resolution at the end of a PipelineRun. Ceiling: "the truth, modulo dataset size."

This is the publishable contribution. The dataset (atlas → final-map lineage) is what Magellon's existing Artifact STI + PipelineRun rollup uniquely produces.

### 8.2 Model

- **Backbone:** DRACO-pretrained ViT (Masked Autoencoder, 270k EMPIAR movies — `arxiv.org/html/2410.11373v2`). Cryo-EM-specific weights beat ImageNet by a wide margin on micrograph tasks.
- **Heads (multi-task):**
  - (i) Square 6-class softmax (good / small / cracked / dry / contaminated / partial). Warm-start from SmartScope's published Faster R-CNN weights.
  - (ii) Hole detection + per-hole regression of `(thickness_nm, edge_distance_um, contamination_logit, crystalline_logit)`.
  - (iii) **Scalar yield head:** predicted `CTF_resolution_Å` and `expected_particle_count`, supervised against PipelineRun rollup.
- **Loss:** weighted sum of per-head losses with task-uncertainty weighting (Kendall 2018). Yield head's weight ramps up as more labeled lineages accumulate.

### 8.3 Bootstrap from public data

We don't wait for Magellon's own data to accumulate before training anything. Phased data sources:

| Source | What it gives | Used for |
|---|---|---|
| **DRACO pretrained weights** | ViT backbone trained on 270k EMPIAR movies | feature extractor, frozen at start |
| **EMPIAR (1700+ entries)** | exposure-level micrographs + final-map resolution per entry | calibrate yield-head's outcome scale; small subset has atlas/square imagery, useful for spot-checking |
| **CryoPPP (9893 micrographs, 34 proteins)** | labeled picks + exposure-level CTF | particle-density predictor warm-start |
| **CryoCRAB (746 proteins, 116.8 TB)** | exposure-level movies + outcomes | yield-head pretraining |
| **SmartScope published square classifier weights** | 6-class square labels | warm-start head (i) |
| **Ptolemy published hole U-Net** | hole detector | warm-start head (ii) |
| **Magellon own sessions (ongoing)** | full atlas → final-map lineage | fine-tune everything, especially yield head |

The first three sources let us train heads (i)–(ii) and a *coarse* yield head before our own atlas-labeled corpus is large. The fourth source — Magellon's own lineage data — replaces the coarse yield head with a fine-tuned one as the dataset grows.

### 8.4 Training data schema

A new `TargetTrainingExample` view, materialised by joining `Artifact` lineage backward from each HM exposure. The label is a **vector**, not a scalar — multiple cheap verifiers in parallel, with a slow ground-truth subset.

```
TargetTrainingExample:
  # ---- Inputs (predictor layer refs, materialised at train time) ----
  atlas_image_ref         Artifact ref
  square_crop_ref         Artifact ref
  mm_image_ref            Artifact ref
  ice_thickness_ref       Layer ref       # tag=ice_thickness
  holes_layer_ref         Layer ref       # tag=holes
  contamination_ref       Layer ref       # tag=contamination_mask
  grid_type               str             # quantifoil_1.2_1.3 | lacey | spotiton | ...
  session_id              GUID

  # ---- Selection metadata ----
  exposed                 bool            # did we shoot HM here?
  exploration             bool            # was this drawn from the exploration sample?
  operator_override       enum | NULL     # boost | skip | forced | none
  tool_score              float           # Track 1 score at decision time
  tool_reasons            json            # {w_ice: 0.42, w_hole: 0.31, ...}

  # ---- Cheap label vector (per HM exposure; computed in seconds) ----
  eval_prob               float | NULL    # micrograph_quality plugin: P(good) ∈ [0,1]
  ctf_resolution_a        float | NULL    # CTFFind4 / CTFFind5
  ctf_defocus_um          float | NULL
  ctf_astig_ratio         float | NULL    # |defocus_u - defocus_v| / mean
  motion_total_a          float | NULL    # MotionCor early+late total
  n_picks                 int   | NULL    # production picker output
  mean_pick_score         float | NULL

  # ---- Slow ground-truth label vector (subset only — periodic calibration) ----
  class_avg_quality       float | NULL    # downstream 2D classification quality score
  final_map_resolution_a  float | NULL    # downstream 3D refinement final resolution
```

**Loss weighting.** Per-row weight adjusts for selection bias: exploration shots get full weight; Tool-chosen shots are inverse-propensity-weighted by the Tool's score at the time of decision. Rows with `final_map_resolution_a` populated weigh more heavily for the yield head; rows with only `eval_prob` are still useful for the cheap-label heads.

**Why a label vector, not a single scalar.** `eval_prob` catches contamination and empty holes. `ctf_resolution_a` catches drift / astigmatism / out-of-range defocus, which `eval_prob` is blind to. `motion_total_a` catches beam-induced motion that destroys high-res signal. `n_picks` is a direct yield count. No single verifier sees everything; the vector covers the failure modes.

**Why skip 2D class and 3D refine routinely.** They take minutes-to-days per micrograph/dataset. We sample a small ground-truth subset (say, 5% of completed sessions where a full PipelineRun finished) and use those to calibrate the cheap label vector against `final_map_resolution_a`. The yield head's primary supervision target is the cheap vector; the slow labels train a *calibration regressor* that maps cheap-vector → expected final-map resolution.

### 8.5 Composition with the Tool

At serving time:

```
brain_score, brain_uncertainty = brain.predict(layers)

if brain_uncertainty > τ_high:
    # Brain doesn't know — fall back to Tool only.
    final_score = tool_score(layers)
    reason     = "brain_uncertain"
elif brain_uncertainty < τ_low:
    # Brain is confident — use it.
    final_score = brain_score
    reason     = "brain_confident"
else:
    # Blend, weighted by inverse uncertainty.
    α          = sigmoid((τ_high - brain_uncertainty) / (τ_high - τ_low))
    final_score = α * brain_score + (1 - α) * tool_score(layers)
    reason     = "blended"
```

The operator UI always shows both scores + the reason, and the Tool's `reasons:{...}` breakdown is always available. **The Tool is never removed.**

---

## 9. Phases

| Phase | Deliverable | Estimate | Depends on |
|---|---|---|---|
| **P1** | `ICE_THICKNESS` plugin (wrap MeasureIce sandbox into CoreService plugin). Emits `Layer(tag=ice_thickness, units=nm)`. | 2–3 days | image-layers shipped or per-mic Artifact fallback |
| **P2** | `CONTAMINATION_DETECT` plugin (classical-CV heuristic, intensity-variance based). | 2 days | P1 |
| **P3** | `TARGET_RANKING` plugin (Tool, heuristic sum). Reads `holes` + `ice_thickness` + `contamination_mask`, emits ranked list Artifact. | 2 days | P1, P2 |
| **P4** | Dispatcher chain (LM → squares → MM acquisition → parallel layer plugins → ranking → HM). | 3 days | P3 |
| **P5** | Exploration policy + `target_decision_event` logging + `TargetTrainingExample` view. | 3 days | P4 |
| **P6** | Public-data bootstrap: DRACO weights checked in; SmartScope + Ptolemy warm-start scripts; EMPIAR scrape job for outcome calibration. | 1 week | P5 |
| **P7** | Train heads (i)–(iii) on public data. Ship as `magellon_brain_ranker_plugin/` (Pro). | 2–3 weeks training + eval | P6 |
| **P8** | Fine-tune yield head on Magellon's own lineage (rolling, retrain monthly as data accumulates). | ongoing | P7 + ~3 months of session data |
| **P9** | Atlas viewer with stacked layers (Pro UI). | 2 weeks frontend | P3 (data available), P7 (brain scores) |
| **P10** | Per-grid Bayesian update — calibration HM shots re-rank remaining holes mid-session. | research; scope TBD | P8 |

P1–P5 are Track 1 (Tool). P6–P8 are Track 2 (Brain). P9 is the Pro UI. P10 is the open-research piece.

---

## 10. Open questions

1. **Per-grid Bayesian update.** Once a few HM exposures are in, their CTF / motion / pick layers reveal a lot about the remaining holes on the same square / grid. The principled solution is a Gaussian-process or hierarchical-Bayesian model with grid-level latent variables. No published cryo-EM targeter does this. P10 is the place to try it.

2. **Non-Quantifoil supports.** Ptolemy is explicitly weaker on lacey carbon, Spotiton/Chameleon grids, and 0.6/0.8 µm holes. Either: (a) gate the ranker on detected support type and disable on unsupported grids, or (b) train a support-type-aware variant. Cheapest first step: a `grid_type` plugin that classifies LM atlas → support type.

3. **Multi-shot per hole.** Some workflows take multiple HM exposures inside one large hole. The current schema assumes one hole = one decision. Either we model hole as a region with multiple `exposure_site` children, or we add a `shots_per_hole` parameter and the ranker emits ranked (hole, sub-position) tuples.

4. **TaskCategory codes.** Codes 6 and 7 are taken (Ptolemy). We need three new codes for `ICE_THICKNESS`, `CONTAMINATION_DETECT`, `TARGET_RANKING`. Confirm against the SDK registry before assigning.

5. **OSS minimal UI.** OSS doesn't get the full layer compositor, but it does need *some* visibility into the ranking. The minimum: a Runner-page table of top-N holes per session, with reasons column. Defer the atlas heatmap to Pro.

6. **Operator-override UX.** The override must be one click in OSS too (skip-hole button) because override-as-label is critical for Track 2. The Pro UI gets richer "boost / suppress / forced" actions.

---

## 11. References

### Internal (Magellon)

- `magellon/ARCHITECTURE.md` §3 (data plane), §7 (categories + backends), §11 (pipeline ergonomics).
- `magellon-rust-mrc/docs/image-layers-architecture.md` — Layer Artifact STI subtype, kind/tag/coord-frame model.
- `memory/project_artifact_bus_invariants.md` — five Artifact rules this plan inherits.
- `memory/project_data_plane_layout.md` — GPFS layout; Layer `data_uri` resolves relative to it.
- `memory/project_pipeline_ergonomics_plan.md` PE2 — lineage-keyed dispatch cache (free re-ranking).
- `memory/project_magellon_pro_split.md` — image-layers + visual builder are Pro.

### External (papers and code)

- Kim et al., **Ptolemy**, *IUCrJ* 2023 — square + hole detection. https://journals.iucr.org/m/issues/2023/01/00/pw5021/ — code https://github.com/SMLC-NYSBC/ptolemy
- Cheng et al., **Smart Leginon Autoscreen**, *IUCrJ* 2023 — multi-grid screening. https://pmc.ncbi.nlm.nih.gov/articles/PMC9812217/
- Bouvette et al., **SmartScope**, *eLife* 2022 — 6-class square classifier + YOLOv5 hole detector. https://elifesciences.org/articles/80047 — code https://github.com/NIEHS/SmartScope
- Brown & Hanssen, **MeasureIce**, *Comm. Bio.* 2022 — single-image aperture-limited-scattering thickness. https://pmc.ncbi.nlm.nih.gov/articles/PMC9376182/ — code https://github.com/HamishGBrown/MeasureIce
- Olek et al., **IceBreaker**, *Structure* 2022 — per-particle ice covariate. https://pmc.ncbi.nlm.nih.gov/articles/PMC9033277/
- Neselu et al., **Ice thickness vs. resolution**, *J. Struct. Biol. X* 2023 — empirical yield-vs-thickness curve. https://pmc.ncbi.nlm.nih.gov/articles/PMC9894782/
- Eisenstein et al., **SPACEtomo**, *Nat. Methods* 2024 — lamella + tomography targeting. https://www.nature.com/articles/s41592-024-02373-9
- DRACO masked autoencoder, 2024 — cryo-EM foundation model. https://arxiv.org/html/2410.11373v2
- Cryo-IEF + CryoWizard, 2025 — self-supervised particle-quality ViT (downstream, not targeting). https://www.nature.com/articles/s41592-025-02916-8
- CryoCRAB dataset, 2025 — 746 proteins / 116.8 TB. https://www.nature.com/articles/s41597-025-05179-2
- CryoPPP dataset, 2023 — 34 proteins / 9893 micrographs. https://www.nature.com/articles/s41597-023-02280-2
- MicAssess (Li & Cianfrocco) — micrograph quality assessment, training-data source for `eval_micrograph`. https://github.com/eugenepalovcak/MicAssess (training corpus at `Z:\cianfrocco-data\laiwei\MicAssess_data_masks\particle_mask`).

### Internal sandbox assets

- `Sandbox/ice_thickness_measureice/` — MeasureIce ALS implementation + Krios 300 kV LUT; basis for `ICE_THICKNESS` plugin.
- `Sandbox/eval_micrograph/` — BoxNet-mask + radial-spectrum-CNN quality scorer (this session, 2026-05-13); basis for `MICROGRAPH_QUALITY` plugin. Pre-trained weights bundled: `boxnet.pt` (24 MB), `radial_spectrum_model.pth` (308 KB), `feature_scaler.pkl`. Demo pipeline outputs under `pipeline_demo/`, `pipeline_demo_bad/`, `pipeline_demo_empty/`.

---

## 12. Changelog

- **2026-05-13** — Initial draft.
- **2026-05-13** — Restructured §4.1 around the predictor/verifier split (two tables); named `eval_micrograph` as the canonical scalar verifier; added `MICROGRAPH_QUALITY` plugin to §7.2; replaced the §8.4 training schema with a concrete label-vector schema (`eval_prob`, `ctf_resolution_a`, `motion_total_a`, `n_picks`) plus a small slow-label subset for ground-truth calibration; imported `Sandbox/eval_micrograph/` from the eval-model author.
