# Optional feature knowledge index

Feature modules contain reusable prompt-writing knowledge for a requested visual attribute. They are not default character traits.

## Routing rule

Load a module only when:

- the user explicitly asks for that appearance, or
- a supplied authoritative reference clearly contains it and the user wants it preserved.

Never activate a module merely because it exists or worked for a previous character.

## Available modules

| User intent or observed target | Read |
|---|---|
| 粉嫩、白里透红、冷白透粉、瓷白但有自然血色 | [skin/porcelain-rosy.md](skin/porcelain-rosy.md) |

## Adding a module

Add a module only after a technique is supported by actual use or a clear recurring need. Each module must contain:

1. Trigger phrases and visual target
2. When not to use it
3. Configurable variables
4. Positive prompt logic
5. Likely failure modes and targeted exclusions
6. QA criteria
7. Interaction rules with the base character specification

Keep character identity, hairstyle, clothing, body type, pose, and background out of a feature module unless the module specifically governs that category. Do not add speculative catalogs or empty placeholders.
