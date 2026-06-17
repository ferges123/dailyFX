# Design: Add and Organize Missing AI Effects in the Studio

## Overview
Currently, the application backend has 58 AI effects defined in its seed files. However, the frontend is missing references to the newly added premium effects in the static fallback lists and default modification settings. Additionally, the Studio dropdown displays all effects in a flat, unorganized list without grouping by category, and the categories `Artistic`, `Photography`, and `Seasonal` are missing from the frontend group ordering.

This design introduces a cohesive `display_group` integration from the backend to the frontend, updates all fallback lists, adds the missing categories to the UI ordering, and organizes the Studio page dropdown into searchable/readable grouped options.

## Architecture & Data Flow

```mermaid
graph TD
    DB[(Database: ai_effects)] -->|loads rows| Registry[GenerationModuleRegistry]
    Registry -->|returns modules with display_group| StudioAPI[/api/studio/modules]
    Registry -->|returns modules with display_group| GenAPI[/api/generation/modules]
    StudioAPI -->|fetched by react-query| StudioPage[StudioPage.tsx]
    GenAPI -->|fetched by react-query| PresetsPage[EffectPresetsPage.tsx]
    
    StudioPage -->|groups using getAIEffectGroupOrder| Dropdown[grouped select dropdown using optgroup]
```

## Detailed Changes

### 1. Backend Changes
- **Pydantic Schema**: Add `display_group: str | None = None` to `GenerationModuleResponse` in `backend/app/schemas/generation.py`.
- **API Endpoints**: Include `display_group` in both `list_studio_modules` (`routes_studio.py`) and `list_generation_modules` (`routes_generation.py`).
- **AI Effect Module Class**: Pass `row.display_group` to the `AIEffectModule` instance in `backend/app/services/generation/ai_effects_builder.py`.
- **Local Python Modules Group Mapping**: Introduce a helper dictionary mapping local Python modules to logical display groups in `backend/app/services/generation/modules/__init__.py` to provide a display group for all 22+ local filters.

### 2. Frontend Changes
- **API Types**: Update `GenerationModuleInfo` in `frontend/src/api/types.ts` to include `display_group: string | null`.
- **Group Ordering**: Update `AI_EFFECT_GROUP_ORDER` in `frontend/src/pages/AIEffects/AIEffectCard.tsx` to include `Artistic`, `Photography`, and `Seasonal`.
- **Static Fallbacks & Default States**:
  - Update `fallbackModules` in `frontend/src/pages/automation.types.ts` to include all 58 backend AI effects with their correct details.
  - Update `createDefaultModificationGroups` in `frontend/src/pages/automation.utils.ts` to declare default state definitions for all new AI effects.
- **Studio Page Grouping**:
  - Group the `modules` array by `display_group` in `StudioPage.tsx`.
  - Order the groups according to the sorting utility `getAIEffectGroupOrder`.
  - Render options inside HTML `<optgroup>` tags labeled with each group name.

## Verification Plan
1. Run backend pytest tests (`make backend-test`) to verify the schema updates and studio routes behave correctly.
2. Run frontend type check and build (`cd frontend && npm run build`) to ensure TypeScript compilation passes.
3. Run frontend tests (`cd frontend && npm test`) to confirm no unit tests are broken.
