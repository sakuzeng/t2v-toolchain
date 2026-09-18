# Porcelain-rosy complexion rendering

Use this optional module for requests such as 粉嫩、白里透红、冷白透粉、瓷白透粉, or a clearly matching authoritative complexion reference. This module controls skin rendering only. It must not add or change identity, ethnicity or appearance, age, face geometry, hairstyle, body proportions, clothing, footwear, pose, camera, or background.

## Visual target

Create predominantly fair, high-value skin with a cool-neutral or user-specified base and a restrained translucent circulation glow. The pink should appear to come from beneath the skin, not from uniform color paint or cosmetic blush. Preserve three-dimensional form, pores, joints, and natural tonal variation.

## Do not use when

- The user asks for warm golden, olive, tan, bronze, deep, or another conflicting complexion.
- The user requests flat graphic coloring rather than natural skin rendering.
- A reference is overexposed or heavily filtered and the user only wants identity or clothing from it.

## Variables

- `base_value`: moderately fair / fair / very fair
- `base_undertone`: cool-neutral / neutral / user-specified
- `circulation_intensity`: subtle / clear / pronounced
- `distribution`: face only / face and extremities / continuous exposed skin
- `texture_level`: clean-realistic / detailed-realistic / stylized
- `shadow_color`: neutral gray / blue-gray / lavender-gray / medium-appropriate
- `finish`: matte / natural / softly luminous

Do not silently select `very fair` or `pronounced`. Derive intensity and undertone from the user's language or the assigned complexion reference.

## Positive prompt logic

Compose the complexion in layers:

1. **Base** — define value and undertone first, keeping it the dominant skin color.
2. **Subsurface circulation** — describe restrained pink vitality beneath the skin rather than surface makeup.
3. **Distribution** — place slightly stronger circulation only where anatomically plausible and visible: cheeks, ear rims, nose tip, lips, fingertips, knuckles, elbows, knees, ankles, and toes when exposed.
4. **Continuity** — ensure face, neck, torso, arms, legs, hands, and feet follow one color logic when visible.
5. **Depth and texture** — retain pores, fine texture, joint definition, capillary variation, and cooler or neutral shadow depth.

Adapt this building block rather than copying it verbatim:

```text
Predominantly [base_value] [base_undertone] skin with a [circulation_intensity] translucent rosy circulation glow beneath the surface. Keep the base color dominant. Let the warmth increase gradually at anatomically plausible high-circulation areas while preserving fine natural texture, joint definition, capillary variation, and [shadow_color] depth in shadows. Maintain one continuous complexion logic across all visible skin.
```

## Targeted exclusions

Use only the exclusions relevant to the requested medium:

- Uniform bubblegum-pink, magenta, red, or painted skin
- Heavy blush circles or obvious cosmetic rouge when natural circulation is intended
- Sunburn, irritation, inflamed joints, patchy flushing, bruising
- Yellow, orange, or peach cast when a cool-neutral base is requested
- Blown white highlights, chalk-flat skin, erased anatomy
- Waxy, plastic, airbrushed, wet, or oily finish unless requested
- Face and limbs using unrelated skin palettes

## Medium adaptation

- **Photoreal / real-human inspired**: use pores, capillary variation, subsurface circulation, anatomical color transitions, and restrained specular response.
- **2D anime / illustration**: translate the same logic into controlled base, blush, joint accents, and cool shadow colors; do not demand photographic pores.
- **Stylized 3D**: use material translucency and soft subsurface response appropriate to the render style; avoid waxiness.

## QA

The result passes only when:

- The requested base complexion remains dominant.
- Rosiness reads as vitality beneath the skin rather than applied pink color.
- Distribution is gradual and anatomically coherent.
- Face and body share one material logic.
- Texture and form remain appropriate to the chosen medium.
- No identity, clothing, pose, or background trait was introduced by this module.
