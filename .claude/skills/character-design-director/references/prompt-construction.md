# Production prompt construction

Read this reference when writing or revising a character-generation prompt.

## Prompt block order

Use the smallest set of blocks that fully controls the task:

1. **Task and asset type** — create, edit, standardize, or expand; intended use.
2. **Input authority** — what each image controls and what it must not contribute.
3. **Primary target** — the requested result or limited edit.
4. **Identity and face** — stable geometry and distinguishing marks.
5. **Hair** — front, side, and back construction.
6. **Body** — build, head-to-body balance, limb proportions, and height impression.
7. **Clothing and accessories** — piece-by-piece construction before aesthetic adjectives.
8. **Appearance materials** — complexion, hair, fabric, metal, translucency, or surface finish.
9. **Expression and pose** — anatomical, measurable instructions.
10. **Camera and layout** — crop, angle, focal perspective, canvas, baseline, and spacing.
11. **Lighting and background** — only what improves readability or matches the intended asset.
12. **Invariants and exclusions** — likely drift risks, not an indiscriminate list.

Put the highest-priority identity and edit instructions early. Avoid contradictions such as asking for both strict orthographic neutrality and dramatic perspective.

## New generation versus edit

### New generation

Describe a coherent positive target. Do not use a long chain of negatives to substitute for missing design decisions. Keep uncertain fields neutral or unresolved.

### Edit or controlled variant

State:

1. Which image is the edit target.
2. Exactly what changes.
3. Exactly what remains invariant.
4. Which supporting references contribute limited properties.
5. Which likely leakages must be excluded.

Use phrases such as `change only`, `preserve the exact`, and `do not copy` only when the task genuinely requires a constrained edit.

## Describe construction, not labels alone

Weak: `cute black outfit`.

Stronger: identify separate garment pieces, neckline, sleeve or strap width, waist construction, silhouette, fabric, closures, pocket count and anatomical side, hem placement, and color relationships. Include only details important to continuity.

## Describe geometry operationally

Prefer observable instructions:

- Head upright; eyes level; nose and chin aligned to the body centerline.
- Feet parallel and fully supported on one baseline.
- Character-left mark remains on character-left in front, side, and back views.

Avoid relying only on vague adjectives such as `perfect`, `elegant`, `beautiful`, or `professional`.

## Negative constraints

Prioritize errors with high probability or high cost:

- Identity drift or unintended age change
- Wrong medium or realism level
- Swapped asymmetric traits
- Changed garment count, construction, or state
- Head tilt, fashion pose, wide-angle distortion, crop, or missing feet in a standard anchor
- Extra people, limbs, digits, text, logos, or watermark

Do not add unrelated negatives that introduce new concepts or dilute the target.

## Human-review output

When useful, precede the production prompt with a short Chinese specification and authority table. Keep the model-facing prompt cohesive rather than mixing commentary, questions, and execution instructions.
