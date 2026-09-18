# Multi-view consistency sheets

Read this reference after a standard anchor is approved or when the user provides an authoritative production anchor.

## Default compact video-consistency sheet

When the user does not specify another layout:

- Exact 16:9 landscape canvas
- Plain neutral light-gray seamless background
- Left region: one large front-facing waist-up identity portrait
- Right region: three equal-scale head-to-toe views in this order: front, exact character-left 90-degree profile, back
- All full-body views share one baseline, scale, body proportions, outfit state, hair construction, accessories, and lighting
- No labels, text, arrows, grids, borders, logos, or watermark unless explicitly requested

This format optimizes identity readability and video reference utility. For concept art, animation turnaround, expressions, or detail callouts, adapt the layout instead of forcing this default.

## Lock tables

Before writing the prompt, create concise locks:

### Identity lock

Face geometry, age presentation, eye design, distinguishing marks, complexion logic, and medium.

### Construction lock

Hair roots and tied sections, garment pieces, seams, buttons, pockets, closures, footwear, and accessories.

### Side lock

| Trait | Anatomical side | Required views |
|---|---|---|
| Distinguishing mark | character-left/right | portrait, front, profile when visible |
| Pocket or closure | character-left/right | front, side, back as anatomically visible |
| Asymmetric footwear | character-left/right | all full-body views |

Do not require a feature to appear through an opaque object or from an anatomically impossible viewing angle.

## Prompt priorities

1. The approved anchor is authoritative for identity and proportions.
2. The sheet expands viewpoints; it does not improve or reinterpret the character.
3. Front details must not appear on the back unless structurally present there.
4. Character-left and character-right remain anatomical across mirrored screen positions.
5. Hair and garment back construction must remain plausible and consistent with the anchor; flag invented back details for review.

## Common failures

- Different faces or ages across views
- Side view is three-quarter instead of exact profile
- Swapped eyes, marks, pockets, socks, shoes, or accessories
- Front buttons or pockets duplicated on the back
- Body scale or head ratio changes between views
- Feet overlap, tiptoe, crop, or change state
- Extra person, view, text, or watermark

Image models may not produce mathematically exact orthographic turnarounds. Report visible deviations and keep failed sheets as candidates rather than silently treating them as canonical.
