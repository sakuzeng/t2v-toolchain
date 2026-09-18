# Character asset QA rubric

Read this reference after generation or when reviewing an existing character asset.

## Decision classes

- **Usable**: no critical failure; small cosmetic deviations do not threaten continuity.
- **Repairable**: identity is stable, but one or more localized construction, pose, side, or anatomy errors need a new controlled version.
- **Reject**: identity, age presentation, medium, proportions, state, or multiple views drift enough that the asset should not be promoted.

## Review order

1. **Identity** — same person or intended newly designed person; face geometry and age presentation stable.
2. **Medium** — photoreal, anime, illustration, or 3D treatment matches the specification.
3. **Silhouette and proportions** — head-to-body balance, torso, limbs, shoulders, waist, hips, and height impression.
4. **Pose and camera** — upright head, expected view, neutral baseline, no perspective distortion or crop that undermines the asset.
5. **Hair construction** — parting, roots, tied sections, length, color placement, and back view.
6. **Clothing construction** — number of pieces, neckline, seams, closures, pockets, material, layering, hem, and back details.
7. **State and sides** — footwear, accessories, marks, heterochromia, and asymmetric traits remain on anatomical sides.
8. **Anatomy** — hands, feet, joints, digits, overlaps, and contact with the floor.
9. **Appearance materials** — complexion, hair, fabric, metal, translucency, texture, and lighting consistency.
10. **Output hygiene** — exact number of people/views, background, text, logos, watermark, resolution, and crop.

## Critical failures

Treat these as reject or mandatory repair even if the image is attractive:

- Different identity or unintended age category
- Wrong art medium
- Missing or extra person/view
- Major limb or facial anatomy error
- Key asymmetric trait on the wrong side
- Wrong outfit or footwear state
- Reference sheet views disagree on body proportions or garment construction
- Cropped head or feet when a full-body anchor is required

## Review report

Report:

- What matched
- Concrete deviations and where they appear
- Whether each deviation threatens identity, continuity, or only polish
- Decision: usable, repairable, or reject
- The smallest next-version change, if repair is needed

Do not claim a numerical body ratio or exact color match unless it was actually measured or can be reliably observed.
