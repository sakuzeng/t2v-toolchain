# Project integration

Read this reference when saving prompts and generated character assets inside a project. Repository-specific instructions override this generic layout.

## Recommended layout

```text
prompts/assets/characters/<character-slug>/
├── single-view/
└── reference-sheets/

assets/candidates/<character-slug>/
├── single-view/
└── reference-sheets/

assets/canonical/characters/<character-slug>/
├── single-view/
└── reference-sheets/
```

Keep prompt and image categories structurally parallel. Use project-root relative paths in frontmatter and configuration.

## Version naming

```text
Single prompt/image:
character-<character-slug>-vNNN[-variant].md|png

Sheet prompt/image:
character-<character-slug>-sheet-vNNN-vMMM.md|png
```

`vNNN` identifies the character anchor iteration. For sheets, `vMMM` identifies the sheet iteration derived from that anchor. Preserve legacy names for traceability; use the standard for new files.

## Candidate-to-canonical promotion

1. Generate into candidates.
2. Review against the specification and references.
3. Obtain explicit user acceptance when the workflow requires it.
4. Copy, do not move, the accepted file to the matching canonical category.
5. Update prompt state and canonical path.
6. Update stable project asset aliases and role descriptions.
7. Record the decision and keep rejected candidates for traceability.
8. Validate every input path and canonical alias before committing.

Do not point default production aliases at candidates. Do not overwrite an old version when regenerating.

## Cross-project reuse

Reuse the structure, specification, and prompt methods. When a character asset is needed in another self-contained project, copy an accepted canonical asset and record its provenance rather than creating a fragile cross-project relative path. A redesign in the new project becomes a new local candidate; it must not rewrite the source project's history.
