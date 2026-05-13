# Target Selection Plan

**Status:** Forward-looking design doc, 2026-05-13. **Authoritative copy: `MagScopeNext/docs/TARGET_SELECTION.md`.** Migrated out of `Magellon/Documentation/magellon/` because target selection drives active acquisition (MagScopeNext's domain — FastAPI microscope control, successor to Leginon). The Magellon copy mirrors the MagScope authoritative version for context; algorithm implementations land under `MagScopeNext/apps/controller/algorithms/`.
**Audience:** MagScopeNext architects + algorithm authors building automated target-site selection on the cryo-EM grid.
**Companion docs:**
- `MagScopeNext/docs/ai-vision.md` — MCP-based LLM instrument control; consumes the ranked-target output of this plan
- `MagScopeNext/docs/gis-atlas-viewer-concept.md` — OpenLayers GIS-style atlas viewer (Pro UI implementation reference for §15)
- `MagScopeNext/docs/architecture/algorithm-framework-proposal.md` — algorithm contract (Pydantic I/O, lifecycle hooks, typed port system) that target-selection algorithms inherit
- `magellon-rust-mrc/docs/image-layers-architecture.md` — Layer Artifact STI subtype (Magellon Pro storage model that the Layer abstraction in §4 adopts)
- `Magellon/Documentation/magellon/ARCHITECTURE.md` — Magellon OSS data plane (existing plugin platform context; some Magellon-shipped plugins reused via §3)

**Naming convention.** This doc uses Magellon's "plugin" terminology in places (e.g. `magellon_X_plugin/`). In MagScopeNext those translate to algorithm backends at `apps/controller/algorithms/<category>/` (per `algorithm-framework-proposal.md`), each subclassing `AlgorithmBackend` with `meta` / `InputModel` / `OutputModel` / `run()` and self-registering with the algorithm registry.

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

- **Backbone:** **Cryo-IEF encoder** (Yang et al., Nature Methods Nov 2025) — pretrained on 65M cryo-EM particles with contrastive self-supervision. MIT license; encoder is fine-tunable. DRACO (Masked Autoencoder, 270k EMPIAR movies) is the secondary backbone for ensembling or fallback. Full ranking and rationale in §12.6.
- **Heads (multi-task):**
  - (i) Square 6-class softmax (good / small / cracked / dry / contaminated / partial). Warm-start from SmartScope's published Faster R-CNN weights.
  - (ii) Hole detection + per-hole regression of `(thickness_nm, edge_distance_um, contamination_logit, crystalline_logit)`.
  - (iii) **Scalar yield head:** predicted `CTF_resolution_Å` and `expected_particle_count`, supervised against PipelineRun rollup.
- **Loss:** weighted sum of per-head losses with task-uncertainty weighting (Kendall 2018). Yield head's weight ramps up as more labeled lineages accumulate.

### 8.3 Bootstrap from public data

We don't wait for Magellon's own data to accumulate before training anything. Phased data sources:

| Source | What it gives | Used for |
|---|---|---|
| **Cryo-IEF encoder** | ViT-style backbone pretrained contrastively on 65M cryo-EM particles | primary feature extractor (frozen at start) |
| **DRACO pretrained weights** | Masked-autoencoder ViT trained on 270k EMPIAR movies | secondary backbone for ensembling |
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

The plan now has **three model tiers** (see §11): T1 heuristic Tool, T2 LightGBM LambdaRank ranker with continuous learning, T3 deep vision model. T2 is the new middle tier — captures most of T3's value at ~10% of the cost, ships first, hosts the continuous-learning loop.

| Phase | Deliverable | Estimate | Depends on | Tier |
|---|---|---|---|---|
| **P1** | `ICE_THICKNESS` plugin (wrap MeasureIce sandbox). Emits `Layer(tag=ice_thickness, units=nm)`. | 2–3 days | image-layers or per-mic Artifact fallback | T1 |
| **P2** | `CONTAMINATION_DETECT` plugin (classical-CV first). | 2 days | P1 | T1 |
| **P3** | `TARGET_RANKING` plugin — T1 heuristic weighted-sum (§7.1). | 2 days | P1, P2 | T1 |
| **P4** | Dispatcher chain (LM → squares → MM → parallel layer plugins → ranking → HM). | 3 days | P3 | T1 |
| **P5** | `prediction_event` + `verification_event` tables; `decision_id` propagation through dispatch; ε-decreasing exploration (start 0.15, decay to 0.05). | 3 days | P4 | T1 |
| **P6** | `MICROGRAPH_QUALITY` plugin — wrap `Sandbox/eval_micrograph/`. Emits scalar P(good) per HM exposure. | 2 days | P4 | verifier |
| **P7** | `magellon_ranker_gbm_plugin/` — LightGBM with `rank:lambdarank` + quantile heads (10th/50th/90th percentiles). Reads layer features per hole; emits T2 score + uncertainty. Bundled `train.py` and `serve.py`. | 1 week | P5, P6 | T2 |
| **P8** | Nightly retrain cron — load last 30 days + GCR-coreset reservoir from history; train v_{n+1}; offline gate (NDCG@10 primary + MAP@10 + Spearman ρ guardrails); SNIPS evaluator with propensity clipping ≤ 20. | 1 week | P7 | T2 |
| **P9** | Shadow-mode promotion gate — challenger runs silently for ≥5 sessions; compare realised verifier vector vs. champion; promote only if both offline gate AND shadow agree. Model versions under `$GPFS/models/ranker_gbm/v_<n>/`. | 1 week | P8 | T2 |
| **P10** | Thompson exploration via T2 quantile sampling — replaces ε-decreasing once T2 has ≥1k labels and calibrated quantiles. Per-grid-type ε decay continues for novel sample types. | 3 days | P9 | T2 |
| **P11** | Drift detection — PSI > 0.2 / KS p < 0.05 on feature distributions; ADWIN on rolling NDCG residual; trigger off-cadence retrain on alarm. | 3 days | P9 | T2 |
| **P12** | Public-data bootstrap for T3 — DRACO weights + SmartScope/Ptolemy warm-start + EMPIAR outcome scrape. | 1 week | P9 | T3 |
| **P13** | T3 deep multi-head ranker — DRACO ViT backbone, ranking head + verifier-vector regression head. Ship as `magellon_brain_ranker_plugin/` (Pro). | 2–3 weeks training + eval | P12 | T3 |
| **P14** | T3 fine-tune on Magellon lineage; rolling monthly retrain on accumulated session data. | ongoing | P13 + ~3 months session data | T3 |
| **P15** | Atlas viewer with stacked layers (Pro UI). | 2 weeks frontend | P3 (data), P7 (T2 scores), P13 (T3 scores) | UI |
| **P16** | Per-grid Bayesian update — HM calibration shots re-rank remaining holes on the same grid. | research; scope TBD | P10, P14 | open |

P1–P5 are T1 plumbing. P6 is the canonical verifier. **P7–P11 are the T2 continuous-learning system — this is the new core of the plan and where the publishable contribution lives.** P12–P14 are T3 (later, once T2 is mature). P15 is Pro UI. P16 is open research.

---

## 10. Open questions

1. **Per-grid Bayesian update.** Once a few HM exposures are in, their CTF / motion / pick layers reveal a lot about the remaining holes on the same square / grid. The principled solution is a Gaussian-process or hierarchical-Bayesian model with grid-level latent variables. No published cryo-EM targeter does this. P10 is the place to try it.

2. **Non-Quantifoil supports.** Ptolemy is explicitly weaker on lacey carbon, Spotiton/Chameleon grids, and 0.6/0.8 µm holes. Either: (a) gate the ranker on detected support type and disable on unsupported grids, or (b) train a support-type-aware variant. Cheapest first step: a `grid_type` plugin that classifies LM atlas → support type.

3. **Multi-shot per hole.** Some workflows take multiple HM exposures inside one large hole. The current schema assumes one hole = one decision. Either we model hole as a region with multiple `exposure_site` children, or we add a `shots_per_hole` parameter and the ranker emits ranked (hole, sub-position) tuples.

4. **TaskCategory codes.** Codes 6 and 7 are taken (Ptolemy). We need three new codes for `ICE_THICKNESS`, `CONTAMINATION_DETECT`, `TARGET_RANKING`. Confirm against the SDK registry before assigning.

5. **OSS minimal UI.** OSS doesn't get the full layer compositor, but it does need *some* visibility into the ranking. The minimum: a Runner-page table of top-N holes per session, with reasons column. Defer the atlas heatmap to Pro.

6. **Operator-override UX.** The override must be one click in OSS too (skip-hole button) because override-as-label is critical for Track 2. The Pro UI gets richer "boost / suppress / forced" actions.

---

## 11. Predictor model + continuous learning

Section 7 covered the heuristic Tool (T1). Section 8 covered the deep yield head (T3). The web survey informing this section [refs 25–38] turned up a critical missing middle: **a gradient-boosted ranker with online retraining (T2)** that is cheaper than T3, learns from operator + verifier feedback, and matches every published "continuous learning" production playbook outside our field. There is **no published learning-to-rank ranker for cryo-EM target selection** (Ptolemy and SmartScope are pointwise classifiers, Cryo-IEF is pointwise quality), and **no published active-acquisition system for cryo-EM single-particle target selection** (SLADS-Net and Kalinin-group SPM are the closest analogues, in adjacent fields). T2 is the publishable contribution.

### 11.1 Three tiers

| Tier | Model class | Trains in | Wins when | Role |
|---|---|---|---|---|
| **T1** | weighted-sum heuristic (§7.1) | — | day 1; cold-start novel grid types; sanity fallback | permanent baseline + feature engineer |
| **T2** | **LightGBM with `rank:lambdarank` + quantile regression** over ~20 engineered features | seconds, CPU, in-process | ~100–10k labeled exposures — beats T1 almost immediately, retrains nightly | **continuous-learning core** |
| **T3** | DRACO ViT + ranking head over raw atlas / MM crops | hours, GPU, batch | ~10k+ labels — finds features humans didn't engineer | mature path; Pro |

T1 and T2 ensemble at serve time with uncertainty-weighted blending (same shape as §8.5, but between T1 and T2 instead of T1 and T3). T3 joins the ensemble when ready.

### 11.2 Why LightGBM + LambdaRank specifically

- **Tabular SOTA, 2026.** Grinsztajn 2022 [25] and McElfresh 2023 [26] both confirm GBDTs still beat deep tabular on medium data with engineered features. TabPFN-2.5 (Nov 2025) [27] is genuinely SOTA for ≤50k *classification*, but lacks a native ranking head and forces a heavyweight transformer for a problem where features are already interpretable. **Keep TabPFN as a sanity-check baseline; LightGBM is the production pick.**
- **LambdaRank, not pointwise BCE.** The use case is "rank these N holes," not "predict each hole's absolute score." Pairwise/listwise loss is more robust to noisy verifier labels (relative comparisons are reliable even when absolute calibration is loose — directly relevant given `eval_micrograph`'s great=0.92 / bad=0.73 / empty=0.59 calibration). LambdaRank is the standard, well-supported in LightGBM via `objective="lambdarank"`.
- **Quantile regression for uncertainty.** LightGBM natively supports `objective="quantile", alpha=0.1/0.5/0.9` — train three side-models on the same features for 10th / 50th / 90th percentile of expected verifier outcomes. The 80% prediction interval drives Thompson sampling (§11.6) and uncertainty-weighted ensembling.
- **Interpretability.** SHAP + per-tree feature importance are first-class. Operators see *why* a hole was ranked low, and the heuristic Tool serves as a sanity baseline for the GBM's feature importance ordering.

### 11.3 Continuous learning loop — event-linked, async, nightly

Verifier labels arrive *after* the exposure, so the loop is async. The trick is to mint a `decision_id` at ranking time and propagate it through the entire dispatch chain so we can join prediction with verification later.

```
RANKING (T1+T2 ensemble)
   ├─► emit prediction_event(
   │      decision_id, hole_id, model_versions: {t1: v_h, t2: v_n},
   │      features, t1_score, t2_score, t2_quantiles, ensemble_score,
   │      exposed: bool, exploration: bool, propensity: float ∈ (0,1])
   │
   ▼
HM EXPOSURE  ──►  MotionCor  ──►  CTFFind  ──►  picker  ──►  MICROGRAPH_QUALITY
   │
   ▼
   emit verification_event(decision_id, eval_prob, ctf_resolution_a, motion_total_a, n_picks, mean_pick_score)
   │
   ▼
JOIN on decision_id  ──►  materialise TargetTrainingExample (§8.4 schema)
   │
   ▼
NIGHTLY CRON
   load:    last 30 days  +  GCR-coreset reservoir from prior history (~70/30 split)
   train:   model_v_{n+1}  ──  rank:lambdarank + 3× quantile regressors
   offline: NDCG@10 (primary) + MAP@10 + Spearman ρ on frozen holdout 10%
   SNIPS:   off-policy evaluator with propensity clipping ≤ 20
   shadow:  if offline gate passes, run challenger silently on ≥5 live sessions
   promote: only if BOTH offline AND shadow agree on improvement
   else:    keep v_n; alert on drift if PSI > 0.2 or KS p < 0.05
```

**Why nightly, not streaming.** Web research is unanimous [28–31]: medical-imaging MLOps surveys, Tesla data-engine writeups, and the 2024 continual-learning-for-medical-imaging review all converge on **periodic batched retrain, not streaming SGD**. With ~10–100 labeled exposures per session and high label noise, streaming weights oscillate. Nightly gives stable updates, a clean audit trail, and trivial rollback (pin to prior `v_n`).

**Why a replay buffer matters.** Different sessions = different sample types (apoferritin vs membrane protein vs viral capsid). Without sampling from history, the model catastrophically forgets prior grid types. GCR (Tiwari et al., CVPR 2022 [32]) gives a gradient-coreset selection rule that's better than naive random for ~10k-row buffers.

### 11.4 Promotion gate — offline + shadow

NDCG@10 alone is **insufficient.** A model that gates only on offline NDCG can win on the held-out distribution but lose under selection bias on real grids. The fix is borrowed directly from the Tesla data engine [29]:

1. **Offline gate.** NDCG@10 primary + MAP@10 + Spearman ρ guardrails on a *frozen* holdout. NDCG can hide tail regressions; MAP catches recall, Spearman catches global rank-order regressions invisible to top-K.
2. **Shadow-mode A/B.** Challenger model runs silently in parallel with the champion on ≥5 live sessions, logs its predictions, but does *not* drive dispatch. Compare *realised* verifier vectors (`eval_prob`, `ctf_resolution_a`, `motion_total_a`, `n_picks`) on the exact same holes both models scored.
3. **Promote only if BOTH agree.** A single Friday-night nightly retrain doesn't ship to production until it has earned ≥5 sessions of shadow agreement. Model versions are pinned in `$GPFS/models/ranker_gbm/v_<n>/`; rollback is `POST /ranker/version/pin v_<n-1>`.

Use **MRR is wrong here** — assumes one relevant item per query (we have many good holes per grid).

### 11.5 Selection bias — SNIPS from day 1, not v2

When the ranker chooses what to expose, we only collect labels for chosen items. Naive eval ranks the new model favourably on its own biased sample. The fix:

- **Log the propensity at decision time.** For each `prediction_event`, store `propensity = P(exposed | features)` under the policy at the time of choice. ε-decreasing makes this trivial (top-N → propensity = 1 − ε; exploration → propensity = ε / |exploration pool|).
- **SNIPS for offline evaluation [33–35], not raw IPS.** Same theoretical consistency, far lower variance, no tuning knobs. The 2024 CLTR reproducibility study [36] is sobering — naive CLTR *often* loses to the logging-policy baseline when sessions are limited, which is our first 6–12 months. SNIPS with propensity clipping ≤ 20 is the standard variance-control move.
- **Doubly-robust estimators can wait.** They only help with a reliable reward model, which we won't have early on. SNIPS is the right tool for ≤10k labels.

### 11.6 Exploration policy maturity ladder

| Stage | Policy | Why |
|---|---|---|
| **Today (T1 only)** | ε-decreasing random, ε ∈ [0.05, 0.15], per-grid-type | fixed-ε wastes exposures forever; decay lets familiar conditions exploit and novel grid types keep exploring |
| **T2 shipped, ≥1k labels** | **Thompson sampling** — draw a single sample from each hole's T2 quantile prediction interval, rank by sample | calibrated uncertainty + no tuning knob; web research argued this directly over UCB [37,38] |
| **T2 mature, drift-stable** | Thompson with grid-type-conditional priors | leverage cross-session knowledge of which sample types reward exploration |

**Departure from the original §7.4 plan**: dropped UCB as a stepping stone. UCB on GBM quantile widths is fragile — the quantile-derived "confidence" is not a calibrated posterior, and the tuning constant `c` is exactly the knob Thompson removes. Skip UCB; go ε-decreasing → Thompson directly.

### 11.7 Drift detection

Two layers running continuously:

- **Feature-distribution drift.** PSI > 0.2 or KS p < 0.05 on each predictor feature (ice_thickness mean/std, hole_score distribution, etc.) over a rolling 14-day window vs. the training distribution. Alert + trigger off-cadence retrain.
- **Performance drift (ADWIN).** Rolling NDCG@10 residual computed on each new joined `TargetTrainingExample`. ADWIN detects concept drift in the model output without needing a fresh holdout.

Both feed a single `ranker_health_event` table consumed by the operations dashboard.

### 11.8 First build — concrete deliverable

Highest-leverage 4-week sprint, in dependency order:

1. **Week 1** — `prediction_event` + `verification_event` tables; `decision_id` propagation through HM dispatch and verifier outputs; `TargetTrainingExample` materialised view (P5).
2. **Week 1** — `MICROGRAPH_QUALITY` plugin wrapping `Sandbox/eval_micrograph/` (P6).
3. **Week 2** — `magellon_ranker_gbm_plugin/` with `train.py` (LightGBM `rank:lambdarank` + 3× quantile regressors), `serve.py` (T1+T2 uncertainty-weighted ensemble), and `evaluate.py` (NDCG@10 + MAP@10 + Spearman ρ + SNIPS) (P7).
4. **Week 3** — Nightly retrain cron (`$GPFS/jobs/cron/ranker_gbm_retrain.py`), GCR-coreset replay buffer, offline gate, model versioning under `$GPFS/models/ranker_gbm/v_<n>/` (P8).
5. **Week 4** — Shadow-mode harness: dual-write challenger predictions, comparison report after N sessions, promotion API (P9).

Thompson exploration (P10) and drift detection (P11) follow in weeks 5–6 once the system has labels flowing.

---

## 12. Model toolkit

This is the cross-cutting model + framework selection underpinning §7.2 (per-plugin) and §8.2 (T3 backbone). Driven by a May 2026 SOTA survey [refs 41–68]. **Two consequential pivots from the prior draft:** (i) drop Ultralytics YOLO from the OSS plugin distribution — AGPL bleeds into Magellon Pro; ship RF-DETR (Apache 2.0) instead; (ii) the T3 backbone is **Cryo-IEF**, not DRACO — Cryo-IEF (Nature Methods, Nov 2025) is pretrained on 65M cryo-EM particles, exactly the domain we're ranking.

### 12.1 The 2026 detection landscape — and the Ultralytics AGPL problem

**YOLO26 is real** — Ultralytics' January 2026 release [41,42]. NMS-free end-to-end, ~43% faster than YOLO11 on CPU, supports detect/seg/pose/OBB/classify. **But, like YOLOv8 / YOLO11 / YOLOv12 / YOLOv13 (iMoonLab fork), it ships under AGPL-3.0** [43]. AGPL §13's network-use clause triggers when distributing or hosting derived weights as a closed-source SaaS — directly relevant for Magellon Pro. Ultralytics Enterprise License is quoted around $5k/seat/yr [44,45], escalating with scale.

**RF-DETR is the cleaner answer.** Roboflow, ICLR 2026, **Apache 2.0** [46,47]: DINOv2 backbone, NMS-free transformer detector, 54.7% COCO mAP @ 4.5 ms on T4, 60.6% on RF100-VL, first real-time detector >60 AP on COCO (2XL variant). Weights and code both Apache 2.0 — no Pro/OSS license friction.

| Model | License | Maintainer | Tier |
|---|---|---|---|
| YOLO26 | AGPL-3.0 | Ultralytics | fastest, license trap |
| YOLO11 / YOLOv12 / YOLOv13 | AGPL-3.0 | Ultralytics / iMoonLab | fast, license trap |
| **RF-DETR** | **Apache 2.0** | **Roboflow** | **recommended** |
| RT-DETRv3 | Apache 2.0 | Baidu / Peking | strong on small objects; alternate |
| RTMDet | Apache 2.0 | OpenMMLab | strong; alternate |
| YOLO-NAS | non-commercial weights | Deci | avoid (license trap) |

**Decision**: RF-DETR for square + hole detection plugins. Skip Ultralytics entirely.

### 12.2 Roboflow — useful tool, not a platform

Roboflow in 2026 ships: Universe (model zoo), Annotate (browser labeling), Supervision (utilities), Inference (Apache 2.0 server), rf-detr (Apache 2.0 training library) [48,49,50]. Pricing: Free → Starter ~$49/mo → Growth ~$299/mo → Enterprise; usage now meters via credits.

**Use it for** annotation UX (browser labeling, COCO export), the Inference server (air-gappable, no account needed), and the rf-detr training library. **Do not use** their hosted training (vendor lock-in, credit-metered cost, doesn't fit our plugin platform) or hosted serving (redundant with CoreService dispatch).

**Integration story**: Annotate → COCO export → rf-detr local training → ONNX → `.mpn` archive → CoreService dispatch. No data leaves the facility.

### 12.3 Small-object detection on 4k+ microscopy

LM atlas (2k–4k px, 50–200 squares per atlas) and MM square (4k px, 100–500 holes per square) both need **tiled (SAHI-style) inference** [51] — train at 640–1024 px, infer at native resolution via overlapping tiles + NMS merge. RF-DETR-M is the recommended single-shot detector; RT-DETRv3-R18 is the alternate. Empirically on aerial benchmarks (DOTA, xView), DETR-family pulls ahead of YOLO once ≥1000 training crops are available [52].

### 12.4 Segmentation for contamination — SAM 2 + MicroSAM

For 500–2000 annotated contamination masks, the recommendation is **SAM 2** (Apache 2.0) [53] fine-tuned via **MicroSAM** (Archit et al., Nature Methods Feb 2025; MIT) [54]. MicroSAM ships EM-fine-tuned weights and a napari plugin we can lift weights from. Fine-tunes in <1 GPU-day at the 500–2000 mask scale. Skip BiomedParse (light-microscopy biased), Florence-2 (slow), OneFormer / MaskDINO (heavier pipelines).

### 12.5 Modern particle picking — UPicker + CryoSegNet alongside the legacy three

The 2024–25 generation of pickers is a measurable step beyond Topaz / BoxNet / crYOLO. Two worth adding to the `PARTICLE_PICKING` category:

- **CryoSegNet** (Gyawali et al., *Brief. Bioinf.* 2024) [55,56] — SAM + attention-U-Net hybrid. F1 0.761 vs Topaz 0.729, crYOLO 0.751. Average 3.28 Å reconstruction (best of 6 in comparative review). Open source.
- **UPicker** (Liu et al., *Brief. Bioinf.* 2025) [57] — semi-supervised DETR-based picker. Only **20–50 labeled micrographs** needed for fine-tuning. Lowest false-positive rate in its cohort. Open source.

Keep Topaz + BoxNet + template as defaults (no single dominant picker in 2026); **add UPicker as a fourth backend.** Its low-label fine-tune story is the killer feature — operators can adapt it to a new sample type in an afternoon.

### 12.6 T3 backbone — Cryo-IEF, not DRACO

**Updating §8.2.** Primary T3 backbone is **Cryo-IEF** (Yang et al., Nature Methods, Nov 2025) [58,59], not DRACO. Cryo-IEF is pretrained on **65M cryo-EM particles** with contrastive self-supervision — domain-specific in a way DINOv3 / ConvNeXt-V2 / EVA-02 aren't. MIT license; weights + code public; encoder is fine-tunable.

Ranking for T3 backbone, primary → fallback:
1. **Cryo-IEF encoder** + small MLP head [58,59] — cryo-native, contrastive
2. **DRACO** [60] — denoising MAE on 270k EMPIAR movies; cryo-native; secondary / ensemble
3. **DINOv3 ViT-S** (Meta, Aug 2025) [61] — best general backbone; transfers to grayscale via channel replication; frozen ensemble component
4. ConvNeXt-V2 / EVA-02 — general baselines; skip unless ensembling helps

The bootstrap dataset story in §8.3 is unchanged — Cryo-IEF simply replaces DRACO at position #1.

### 12.7 Training pipeline — Lightning + Hydra, not Ultralytics CLI

For a small team running Magellon's plugin platform:

**Stack**: PyTorch Lightning + Hydra configs + W&B for tracking + DVC for dataset versioning + rf-detr (RF-DETR) or MMDetection 3.x (RT-DETRv3 / Co-DETR / Mask2Former / RTMDet) as the model library. Export to ONNX → bundle in `.mpn` → dispatch via SDK 2.x.

**Skip**: Detectron2 (Meta has frozen it), Ultralytics CLI (AGPL exposure), Roboflow Train (managed-training lock-in).

### 12.8 Per-plugin verdicts (consolidates §7.2)

| Plugin | Model | License | Training framework | Data needed | Verdict |
|---|---|---|---|---|---|
| `ICE_THICKNESS` | MeasureIce (analytic, no ML) | OSS | — | — | **Wrap sandbox** |
| `SQUARE_DETECTION` (cat 6, was Ptolemy CNN) | **RF-DETR-M + classifier head** | Apache 2.0 | Lightning + rfdetr | 500–2k labeled atlases | **Replace** Ptolemy — modern detector beats CNN-on-crops |
| `HOLE_DETECTION` (cat 7, was Ptolemy U-Net) | **RT-DETRv3-R18 + lattice post-fit** | Apache 2.0 | MMDetection | 500–2k labeled MM | **Keep U-Net as v1**, A/B against RT-DETRv3; lattice fit stays |
| `CONTAMINATION_DETECT` | **SAM 2 + MicroSAM fine-tune** | Apache 2.0 / MIT | MicroSAM scripts | 500–2k masks | **New plugin** |
| `MICROGRAPH_QUALITY` | BoxNet mask → radial-spectrum CNN (existing) | MIT | Lightning | ~5k labeled HM | **Keep**; consider adding Cryo-IEF features as 2nd head |
| `PARTICLE_PICKING` (existing) | Topaz + BoxNet + template + **UPicker** | mixed (GPL-3.0 / MIT) | UPicker repo | UPicker: 20–50 labeled mic. | **Keep + extend** with UPicker |
| `RANKER_T2` | LightGBM LambdaRank + 3× quantile (see §11) | MIT | Lightning, in-process | 100–10k labeled exposures | **New plugin** |
| `RANKER_T3` (Pro) | Cryo-IEF encoder + ranking head | MIT | Lightning | 5k–20k ranked crops | **New plugin (later phase)** |

---

## 13. References

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

### External — predictor model + continuous learning (§11)

25. Grinsztajn et al., *Why do tree-based models still outperform deep learning on tabular data?*, NeurIPS 2022. https://arxiv.org/abs/2207.08815
26. McElfresh et al., *When Do Neural Nets Outperform Boosted Trees on Tabular Data?*, NeurIPS 2023. https://arxiv.org/abs/2305.02997
27. Hollmann et al., **TabPFN v2**, *Nature* 2025. https://www.nature.com/articles/s41586-024-08328-6 — TabPFN-2.5 report (Nov 2025): https://priorlabs.ai/technical-reports/tabpfn-2-5-model-report
28. *Continual Learning in Medical Imaging from Theory to Practice*, arXiv 2024. https://arxiv.org/html/2405.13482v1
29. Tesla Autopilot data engine + trigger classifiers. https://codecompass00.substack.com/p/tesla-data-engine-trigger-classifiers ; FSD shadow mode: https://www.notateslaapp.com/news/3108/teslas-fsd-shadow-mode-what-it-is-and-how-it-improves-fsd
30. *Conformal Triage for Medical Imaging AI Deployment*, medRxiv 2024. https://www.medrxiv.org/content/10.1101/2024.02.09.24302543v1
31. Zhang et al., **SLADS-Net** (autonomous sparse sampling for SEM/Raman/EDS/X-ray, deployed). arXiv:1803.02972. https://arxiv.org/abs/1803.02972
32. Tiwari et al., *GCR: Gradient Coreset Based Replay Buffer Selection*, CVPR 2022. https://arxiv.org/abs/2111.11210
33. Joachims et al., *Unbiased Learning-to-Rank with Biased Feedback* (IPS), WSDM 2017. https://www.cs.cornell.edu/~tj/publications/joachims_etal_17a.pdf
34. Eugene Yan, *Counterfactual Evaluation for Recommendation Systems* (SNIPS overview). https://eugeneyan.com/writing/counterfactual-evaluation/
35. *Counterfactual Risk Minimization with IPS-Weighted BPR and SNIPS*, arXiv 2025. https://arxiv.org/html/2509.00333v1
36. *Investigating the Robustness of Counterfactual Learning to Rank Models: A Reproducibility Study*, arXiv 2024. https://arxiv.org/abs/2404.03707
37. *Core bandit algorithms — ε-greedy, UCB, Thompson* (Yahoo LinUCB production case). https://www.systemoverflow.com/learn/ml-recommendation-systems/diversity-exploration/core-bandit-algorithms-epsilon-greedy-ucb-and-thompson-sampling
38. Ziatdinov et al., *Bayesian Active Learning for Scanning Probe Microscopy: From GPs to Hypothesis Learning*, ACS Nano. https://pubs.acs.org/doi/10.1021/acsnano.2c05303 — *Active oversight and quality control in standard Bayesian optimization for autonomous experiments*, npj Comp. Mat. 2024: https://www.nature.com/articles/s41524-024-01485-2 — INS²ANE (novelty discovery), ACS Nanoscience Au 2025: https://pubs.acs.org/doi/10.1021/acsnanoscienceau.5c00106
39. EvidentlyAI, *NDCG metric explained*. https://www.evidentlyai.com/ranking-metrics/ndcg-metric — *Comparing 5 drift detection methods (KS/PSI/Wasserstein/ADWIN)*: https://www.evidentlyai.com/blog/data-drift-detection-large-datasets
40. *On NDCG as an Off-Policy Evaluation Metric for Top-n Recommendation*, arXiv 2023. https://arxiv.org/abs/2307.15053

### External — model toolkit (§12)

41. Ultralytics YOLO26 docs. https://docs.ultralytics.com/models/yolo26
42. Khanam & Hussain, *Ultralytics YOLO Evolution* (YOLO26 / YOLO11 / YOLOv8 / YOLOv5), arXiv 2510.09653. https://arxiv.org/abs/2510.09653
43. Ultralytics LICENSE (AGPL-3.0). https://github.com/ultralytics/ultralytics/blob/main/LICENSE
44. Ultralytics license & enterprise. https://www.ultralytics.com/license
45. Ultralytics enterprise pricing discussion. https://github.com/orgs/ultralytics/discussions/7440 ; AGPL-3.0 commercial-use issue: https://github.com/ultralytics/ultralytics/issues/19390
46. Roboflow, *RF-DETR: A SOTA Real-Time Object Detection Model*. https://blog.roboflow.com/rf-detr/
47. roboflow/rf-detr (ICLR 2026, Apache 2.0). https://github.com/roboflow/rf-detr
48. Roboflow pricing. https://roboflow.com/pricing ; usage credits: https://roboflow.com/credits
49. roboflow/inference (Apache-2.0, air-gappable). https://github.com/roboflow/inference
50. Roboflow, *Best Object Detection Models 2026*. https://blog.roboflow.com/best-object-detection-models/
51. SAHI (Sliced Hyper-Inference) — Akyon et al., *Slicing Aided Hyper Inference*, ICIP 2022. https://github.com/obss/sahi
52. Wang et al., *RT-DETRv3*, arXiv 2409.08475. https://arxiv.org/html/2409.08475v1
53. Meta SAM 2 (Apache 2.0). https://github.com/facebookresearch/sam2
54. Archit et al., **MicroSAM** — *Segment Anything for Microscopy*, Nature Methods Feb 2025 (MIT). https://www.nature.com/articles/s41592-024-02580-4 ; repo: https://github.com/computational-cell-analytics/micro-sam
55. Gyawali et al., **CryoSegNet**, *Brief. Bioinformatics* 2024. https://academic.oup.com/bib/article/25/4/bbae282/7690949
56. Cryo-EM picker comparative review, PMC 2024. https://pmc.ncbi.nlm.nih.gov/articles/PMC11736895/
57. Liu et al., **UPicker** (semi-supervised DETR picker), *Brief. Bioinformatics* 2025. https://academic.oup.com/bib/article/26/1/bbae636/7919967
58. Yang et al., **Cryo-IEF** — *A comprehensive foundation model for cryo-EM image processing*, Nature Methods Nov 2025. https://www.nature.com/articles/s41592-025-02916-8
59. westlake-repl/Cryo-IEF (MIT). https://github.com/westlake-repl/Cryo-IEF
60. Wang et al., **DRACO**, NeurIPS 2024 (secondary backbone). https://arxiv.org/abs/2410.11373
61. Meta, **DINOv3**, arXiv 2508.10104 (Aug 2025). https://arxiv.org/abs/2508.10104
62. Lei et al., *YOLOv13 — Hypergraph-Enhanced Adaptive Visual Perception*, arXiv 2506.17733. https://arxiv.org/abs/2506.17733
63. Tian et al. / Ultralytics, *YOLOv12* (Feb 2025, R-ELAN). https://docs.ultralytics.com/models
64. Cheng et al., *YOLO-World*, arXiv 2401.17270. https://arxiv.org/abs/2401.17270 ; YOLOE: https://docs.ultralytics.com/models/yoloe
65. Dhakal et al., **CryoTransformer**, *Bioinformatics* 2024. https://academic.oup.com/bioinformatics/article/40/3/btae109/7614090
66. Deci-AI YOLO-NAS license (non-commercial weights). https://github.com/Deci-AI/super-gradients/blob/master/LICENSE.YOLONAS.md
67. CryoSAM (MICCAI 2024 — tomogram segmentation). https://link.springer.com/chapter/10.1007/978-3-031-72111-3_12
68. OpenMMLab MMDetection 3.x (Apache-2.0, RT-DETR / Co-DETR / Mask2Former / RTMDet). https://github.com/open-mmlab/mmdetection

### Internal sandbox assets

- `Sandbox/ice_thickness_measureice/` — MeasureIce ALS implementation + Krios 300 kV LUT; basis for `ICE_THICKNESS` plugin.
- `Sandbox/eval_micrograph/` — BoxNet-mask + radial-spectrum-CNN quality scorer (this session, 2026-05-13); basis for `MICROGRAPH_QUALITY` plugin. Pre-trained weights bundled: `boxnet.pt` (24 MB), `radial_spectrum_model.pth` (308 KB), `feature_scaler.pkl`. Demo pipeline outputs under `pipeline_demo/`, `pipeline_demo_bad/`, `pipeline_demo_empty/`.

---

## 14. Appendix A — design history & related docs

This plan consolidates and extends prior cryo-EM research that lives outside the Magellon repo. Audited 2026-05-13.

### Direct predecessors (heavy overlap with this doc)

| Doc | Date | What it covers | Status vs. this plan |
|---|---|---|---|
| `magellon-rust-mrc/docs/research/cryoem-algorithms-landscape.md` | 2026-03 | 2024–25 SOTA review across grid screening, CTF, picking, 2D/3D classification, denoising; Rust impl "quick wins" (ice, hole finding, quality scoring) | **Source for §3 + §11.1 baseline**; this plan adds the T2 continuous-learning tier on top |
| `magellon-rust-mrc/docs/ai-models-strategy.md` | 2026-03 | 9-model comprehensive strategy with $15–25k budget; dataset gaps; XGBoost yield predictor = direct ancestor of this plan's T2 | **Source for §11 T2 design**; verified SmartScope dataset links and ice/contamination data-gap findings reflected below |
| `magellon-rust-mrc/docs/plan/ml-model-selection.md` | 2026-04 | Selection matrix for pickers/denoisers/classifiers; AGPL license analysis | **Source for §12.1 AGPL pivot**; this plan supersedes its DRACO-primary recommendation with Cryo-IEF (Nature Methods Nov 2025) |
| `magellon-rust-mrc/docs/serialem-holefinder-ice-thickness.md` | — | SerialEM Sobel+Canny+circular-correlation+lattice hole-finder pipeline; ALS + EFTEM ice-thickness methods | **Aligned with §7.2** ICE_THICKNESS + HOLE_DETECTION; SerialEM lattice fit (0.75–1.33× nominal spacing tolerance, 0.5× merge proximity) cited as classical fallback for non-Quantifoil supports (lacey, Spotiton) |
| `magellon-rust-mrc/docs/image-layers-architecture.md` | 2026-05-10 | Layer Artifact STI subtype with kind/tag/coord-frame schema | **Adopted wholesale as the storage model in §4** |
| `magellon-rust-mrc/docs/hole-finder.md` | — | Hole-detection algorithm specifics | Aligned with §7.2 HOLE_DETECTION plugin |
| `magellon-rust-mrc/docs/plan/cryoppp-integration-plan.md` | — | CryoPPP dataset ingestion for picker training | Referenced in §8.3 bootstrap |
| `magellon-rust-mrc/docs/algorithms-catalog.md` + `algorithms-status.md` | — | Algorithm taxonomy and shipped-state matrix | Reference for §3 "What exists today" |
| `magellon-rust-mrc/docs/ai-hybrid-strategy.md` + `ai-competitive-advantage.md` + `ai-ecosystem-primer.md` | — | Strategic positioning + competitive landscape | Business / strategy context; not algorithm-level |

### Adjacent — MagScopeNext (different project, complementary)

| Doc | Role |
|---|---|
| `MagScopeNext/docs/ai-vision.md` | MCP-based LLM instrument control + self-improving algorithms. **Consumes** ranked targets from this plan; this plan is *upstream* of MagScope's autonomy loop. |
| `MagScopeNext/docs/gis-atlas-viewer-concept.md` | OpenLayers GIS-style atlas viewer with zoom hierarchy atlas → square → hole → exposure. **This is the implementation reference for the Pro layer-compositor UI deferred to P15.** Custom CRS in micrometers + tile pyramids + region overlays match §5 (LM-as-canonical-frame) exactly. |
| `MagScopeNext/docs/architecture/catlas-format-review.md` + `catlas-format-spec.md` | Catlas portable export format; companion to the runtime Layer model in §4 |
| `MagScopeNext/docs/architecture/algorithm-{framework,implementation}-*.md` | Algorithm framework / impl plan in MagScope side — orthogonal to this plan's dispatcher (§7.3) |

### Key supersessions made by this plan

1. **T3 backbone (§12.6).** `ml-model-selection.md` (April 2026) listed **DRACO** first. This plan replaces it with **Cryo-IEF** (Yang et al., *Nature Methods* Nov 2025, 65M cryo-EM particles, MIT) and demotes DRACO to secondary/ensemble. Cryo-IEF was published after the prior doc.
2. **OSS detector license (§12.1).** Prior docs defaulted to YOLO. This plan switches the OSS distribution to **RF-DETR** (Apache 2.0) after analyzing AGPL-3.0 §13 risk for Magellon Pro.
3. **Three-tier architecture (§11.1).** Prior docs framed Tool + Brain as two tracks. This plan inserts **T2 (LightGBM LambdaRank with continuous learning)** as the missing middle and the publishable contribution. Its closest ancestor is `ai-models-strategy.md` Model 7 (XGBoost yield predictor).

### Verified public datasets (per `ai-models-strategy.md` §4, fact-checked 2026-04-10)

| Dataset | Source | Content | License | On-disk status |
|---|---|---|---|---|
| SmartScope hole detector | [Zenodo 10.5281/zenodo.6814652](https://zenodo.org/records/6814652) | 36 images, 5,492 hole annotations, COCO JSON, single `circle` class | CC-BY-4.0 | downloaded at `sandbox/01-hole-detection/data/smartscope/annotations.json` (MD5-verified) |
| SmartScope square detector | [Zenodo 10.5281/zenodo.6814642](https://zenodo.org/records/6814642) | 26 atlases, COCO JSON | CC-BY-4.0 | not yet downloaded |
| Ice / contamination classification (multi-class) | **none exists publicly** | — | — | **Open data gap** — must collect from Magellon sessions |

**Open data gap.** No public dataset for multi-class ice / contamination classification at LM or MM. CONTAMINATION_DETECT (§7.2) and any ice-quality fine-tuning beyond MeasureIce's analytic LUT require label collection from Magellon's own sessions — a P5 prerequisite, not P0. SmartScope's published release explicitly does **not** include a contamination class.

### Useful concrete spec from prior docs (fold into implementations)

- **WARP-style micrograph quality features** (per `cryoem-algorithms-landscape.md`): the input feature vector for `MICROGRAPH_QUALITY` should include median intensity, total rigid motion, motion rate-of-change, CTF fit resolution, tilt angle, defocus range, astigmatism. The current `eval_micrograph` sandbox uses BoxNet-mask radial-spectrum only; consider adding these as a second head per the §4.1.2 note.
- **SerialEM lattice spacing tolerances** (per `serialem-holefinder-ice-thickness.md`): for the hole-detection lattice post-fit (RT-DETRv3 or Ptolemy U-Net path), accept neighbour spacings in [0.75×, 1.33×] of nominal and merge holes within 0.5× nominal spacing as duplicates.

---

## 15. Changelog

- **2026-05-13** — Initial draft.
- **2026-05-13** — Restructured §4.1 around the predictor/verifier split (two tables); named `eval_micrograph` as the canonical scalar verifier; added `MICROGRAPH_QUALITY` plugin to §7.2; replaced the §8.4 training schema with a concrete label-vector schema (`eval_prob`, `ctf_resolution_a`, `motion_total_a`, `n_picks`) plus a small slow-label subset for ground-truth calibration; imported `Sandbox/eval_micrograph/` from the eval-model author.
- **2026-05-13** — Added §11 (Predictor model + continuous learning) — three tiers (T1 heuristic / T2 LightGBM LambdaRank / T3 deep ViT); event-linked async retrain loop with `decision_id` propagation; SNIPS off-policy evaluator with propensity clipping from day 1; shadow-mode promotion gate after offline NDCG@10; exploration policy maturity ladder (ε-decreasing → Thompson, **UCB dropped after research review**); GCR-coreset replay buffer; PSI/KS/ADWIN drift detection. §9 phase table expanded to 16 phases with explicit tier column. New references 25–40 from the survey.
- **2026-05-13** — Doc migrated to `MagScopeNext/docs/TARGET_SELECTION.md` as authoritative copy. Magellon copy retained as a context mirror. Algorithm implementations land under `MagScopeNext/apps/controller/algorithms/` (per `algorithm-framework-proposal.md`). First scaffold: `micrograph_quality` algorithm wrapping the `eval_micrograph` sandbox, sandbox copied to `MagScopeNext/sandbox/eval_micrograph/`. Header rewritten to point at MagScopeNext companion docs.
- **2026-05-13** — Added §14 Appendix A (Design history & related docs) after auditing `magellon-rust-mrc/docs/` and `MagScopeNext/docs/`. No substantive conflicts with this plan; audit produced 12 cross-references, 3 explicit supersession notes (DRACO→Cryo-IEF backbone, YOLO→RF-DETR detector, two-track→three-tier architecture), verified SmartScope Zenodo URLs (10.5281/zenodo.6814652 hole detector + 10.5281/zenodo.6814642 square detector, both CC-BY-4.0), and an open data-gap flag for multi-class ice/contamination classification (no public dataset; must collect from own sessions). Renumbered Changelog §14 → §15.
- **2026-05-13** — Added §12 (Model toolkit) after May 2026 SOTA survey on detection / segmentation / foundation models. **Two consequential pivots**: (i) drop Ultralytics YOLO from OSS distribution — AGPL-3.0 §13 bleeds into Magellon Pro; ship **RF-DETR (Apache 2.0)** instead. YOLO26 is real but license-trapped. (ii) T3 backbone is **Cryo-IEF** (Nature Methods Nov 2025, 65M cryo-EM particles, MIT), not DRACO — Cryo-IEF moved to position #1 in §8.2 and §8.3, DRACO demoted to secondary/ensemble. Plus: SAM 2 + MicroSAM (Nature Methods Feb 2025) for `CONTAMINATION_DETECT`; UPicker (semi-supervised DETR, 20–50 labels) added as 4th `PARTICLE_PICKING` backend. Per-plugin model table in §12.8. Training pipeline: Lightning + Hydra + W&B + DVC + rf-detr / MMDetection 3.x. New references 41–68.
