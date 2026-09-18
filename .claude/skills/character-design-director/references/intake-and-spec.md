# Intake and character specification

Read this reference whenever a new character is created, reconstructed from an image, or materially redesigned.

## Input modes

### Text only

Extract only what the user actually states. Fill low-impact omissions with neutral production defaults, but surface any omission that materially changes identity, silhouette, age presentation, art medium, clothing category, or intended use.

### One image

Treat visible facts as observations, not proof of biography or identity. Record occluded or ambiguous features as unresolved. Do not infer unseen back details, exact age, nationality, material construction, or body measurements without qualification.

### Multiple images

Create an authority table before writing the prompt:

| Input | Authoritative for | Must not contribute |
|---|---|---|
| Image 1 | Identity, face, proportions | Unrequested background or transient pose |
| Image 2 | Named feature only | Identity, age, clothing, pose, environment |
| Text | Explicit overrides | Unstated redesign |

If two sources conflict, follow the user's explicit priority. Otherwise preserve the primary identity anchor and state the unresolved conflict.

## Evidence ledger

Classify facts as:

- **User-stated**: explicit requirements and overrides.
- **Observed**: directly visible in a supplied image.
- **Inferred**: plausible but not visually certain.
- **Unresolved**: important information not available.

The generation prompt may use user-stated and observed facts directly. Use inferred facts only when necessary and easy to revise. Do not silently convert unresolved facts into character-defining details.

## Character specification fields

Capture only fields relevant to the request:

- Project and character slug
- Intended medium: photoreal, real-human anime-inspired, 2D anime, stylized 3D, illustration, or another stated medium
- Intended use: concept, standard anchor, reference sheet, video consistency, or variant
- Age presentation and any user-stated identity context
- Face silhouette, feature geometry, eye color, distinguishing marks
- Hair structure, length, color, parting, tied sections, and back construction
- Body proportions, build, height impression, and limb balance
- Complexion base, undertone, circulation, texture, and finish
- Garment pieces, construction, material, colors, closures, seams, pockets, and layering
- Footwear or barefoot state
- Accessories and asymmetric side locks
- Expression, pose, camera, crop, background, and lighting
- Identity locks, state locks, requested changes, and forbidden drift

## Missing-information strategy

Ask only when a missing choice would materially change the asset or create an incompatible branch. Otherwise choose a reversible neutral default and label it. Useful defaults for a production anchor include upright head, neutral relaxed stance, soft even light, and an uncluttered background; these are presentation defaults, not character traits.

## Feature-leakage check

Before finalizing the spec, ask internally:

- Did any trait come from a previous character rather than this request?
- Did a supporting reference contribute identity, pose, clothing, or background outside its assigned role?
- Did a visual style word accidentally imply a specific ethnicity, hairstyle, outfit, age, or body type?
- Are optional appearance recipes activated by user intent, or merely because they exist in the library?

Remove unsupported traits before prompt construction.
