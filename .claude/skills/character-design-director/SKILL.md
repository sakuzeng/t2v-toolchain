---
name: character-design-director
description: Turn character reference images or a text brief into a structured visual specification, production-ready prompts, a neutral standard front-view anchor, controlled variants, and multi-view consistency sheets; also review outputs for identity and construction drift. Use for image/video character design and standardization, not ordinary portrait retouching, scene or storyboard direction, or animation rigging.
---

# Character Design Director

Design reusable character assets without inheriting traits from unrelated examples. Translate sparse text, one reference image, or several role-specific references into a stable specification and image-generation instructions.

## Non-negotiable principles

- Start each new character from a blank specification. Never carry identity, age, ethnicity or appearance, hairstyle, colors, body proportions, clothing, footwear, pose, background, or accessories from a prior character unless the user explicitly requests reuse.
- Separate `user-stated`, `observed`, `inferred`, and `unresolved` facts. Do not present inference as evidence.
- Assign every input image a narrow authority role. One image may own identity while another contributes only clothing construction, complexion rendering, anatomy, pose, or layout. Explicitly exclude unrelated traits from supporting references.
- Treat user instructions as authoritative for requested changes. Preserve the primary identity anchor for everything the user did not ask to change.
- Describe left/right as `character-left` and `character-right`, never only screen-left/screen-right, when a trait is asymmetric.
- Produce one approved standard anchor before expanding a new character into a multi-view sheet, unless the user already supplied an approved anchor or explicitly requests a different sequence.
- Do not generate images when the user asked only for analysis or prompts. When generation is explicit, use the available image-generation capability and obey local approval, cost, and asset-management rules.

## Route the request

1. **Text-only design** — build a character specification from stated facts and mark consequential gaps.
2. **Image-led standardization** — inspect the image, extract observable design facts, correct pose/camera issues only as requested, and preserve identity.
3. **Image plus text** — use the image as the baseline and apply the text as scoped overrides.
4. **Controlled variant** — change only named variables; write a strong invariant block for everything else.
5. **Reference sheet** — expand an approved anchor into consistent views without redesign.
6. **Review** — compare an output against its specification and references; report usable, repairable, or reject.

For intake and evidence handling, read [references/intake-and-spec.md](references/intake-and-spec.md). Copy [assets/templates/character-spec.md](assets/templates/character-spec.md) when a persistent specification is useful.

## Working sequence

1. Inspect every supplied image before making visual claims.
2. Build the character specification and an input-authority table.
3. Identify identity locks, state locks, requested changes, and unresolved choices.
4. Load only feature modules that match the user's requested attributes. Start at [references/features/INDEX.md](references/features/INDEX.md); feature modules are optional recipes, never defaults.
5. Compose the prompt using [references/prompt-construction.md](references/prompt-construction.md).
6. For a new production anchor, apply [references/standard-front-view.md](references/standard-front-view.md).
7. Review the result with [references/qa-rubric.md](references/qa-rubric.md). Do not silently rerun a failed result when approval or cost rules require the user to decide.
8. After the anchor is accepted, build a sheet using [references/reference-sheets.md](references/reference-sheets.md).
9. When working inside an asset project, follow [references/project-integration.md](references/project-integration.md) and any stricter repository instructions.

## Prompt output standard

Unless the user asks for another format, provide:

1. A compact Chinese specification for human review.
2. A production prompt, normally in English for the image model.
3. A short invariant list and high-risk exclusions.
4. The intended asset type: `standard-front-view`, `controlled-variant`, or `reference-sheet`.
5. After generation, a QA result with concrete deviations rather than generic praise.

Use the templates in `assets/templates/` when writing persistent artifacts. Adapt them; do not leave placeholder fields in delivered files.

## Boundaries

- This skill owns visual character specification, character-asset prompts, identity consistency, and asset QA.
- It does not invent story, personality biography, shot direction, animation performance, or environment design unless those details are needed to disambiguate the visible character.
- It does not turn one successful aesthetic into a universal rule. Add a feature module only when it captures a reusable, non-obvious technique with clear triggers, variables, failure modes, and QA criteria.
