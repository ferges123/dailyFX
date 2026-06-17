# Studio Missing Effects Integration Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Integrate, list, and group all missing/new premium AI effects in the Studio and Effect Presets pages, displaying them sorted by category.

**Architecture:** Extend backend schema responses with `display_group`, update frontend static configurations/fallbacks, and group the Studio select dropdown options using HTML `<optgroup>`.

**Tech Stack:** FastAPI, React (TypeScript), Tailwind/CSS, SQLite/SQLAlchemy.

---

### Task 1: Backend API updates for display_group
Include the `display_group` metadata in module listings to enable category-based grouping on the client side.

**Files:**
- Modify: `backend/app/schemas/generation.py:88-95`
- Modify: `backend/app/services/generation/modules/__init__.py:29-53`
- Modify: `backend/app/services/generation/ai_effects_builder.py:7-19`
- Modify: `backend/app/api/routes_studio.py:264-283`
- Modify: `backend/app/api/routes_generation.py:217-232`
- Test: `backend/tests/test_studio_routes.py`

**Step 1: Write failing test**
In `backend/tests/test_studio_routes.py`, update `test_studio_modules_include_ai_and_exclude_multisource` to assert that returned items contain `display_group`.
```python
def test_studio_modules_include_ai_and_exclude_multisource(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/studio/modules")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    # Every module response should now contain a display_group key (either a string or None)
    for item in data:
        assert "display_group" in item
```

**Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_studio_routes.py::test_studio_modules_include_ai_and_exclude_multisource -v`
Expected: FAIL with KeyError/ValidationError because `display_group` is not yet defined on the schema.

**Step 3: Write minimal implementation**
1. Add `display_group: str | None = None` to `GenerationModuleResponse` in `backend/app/schemas/generation.py`:
```python
class GenerationModuleResponse(BaseModel):
    name: str
    label: str
    description: str
    display_group: str | None = None
    default_weight: int = 1
    default_config: dict = Field(default_factory=dict)
    config_schema: list[GenerationModuleConfigField] = Field(default_factory=list)
```

2. Assign `self.display_group = row.display_group` in `AIEffectModule.__init__` in `backend/app/services/generation/ai_effects_builder.py`:
```python
class AIEffectModule(AIStyleBaseModule):
    def __init__(self, row: AIEffectModel):
        self.name = row.id
        self.label = row.title
        self.description = row.description or row.title
        self.display_group = row.display_group
```

3. In `backend/app/services/generation/modules/__init__.py`, define `LOCAL_MODULE_GROUPS` map:
```python
LOCAL_MODULE_GROUPS = {
    "apple_weather": "Portrait",
    "instaweather": "Portrait",
    "museum_archive": "Poster",
    "bokeh_blur": "Portrait",
    "vintage_film": "Photography",
    "huji": "Photography",
    "collage": "Poster",
    "instafilter": "Photography",
    "filmstrip": "Photography",
    "popart": "Artistic",
    "duotone": "Artistic",
    "halftone": "Artistic",
    "glitch": "Artistic",
    "light_leak": "Photography",
    "neon_bloom": "Artistic",
    "cyanotype": "Photography",
    "polaroid": "Photography",
    "prism_split": "Photography",
    "paper_cutout": "Artistic",
    "pencil_sketch": "Artistic",
    "cartoon": "Illustration",
    "hdr": "Photography",
    "aerochrome": "Photography",
}
```

4. Populate `display_group` in both endpoints (`list_studio_modules` in `routes_studio.py` and `list_generation_modules` in `routes_generation.py`):
```python
# In routes_studio.py
display_group=getattr(module, "display_group", None) or LOCAL_MODULE_GROUPS.get(module.name),

# In routes_generation.py
display_group=getattr(item, "display_group", None) or LOCAL_MODULE_GROUPS.get(item.name),
```

**Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_studio_routes.py::test_studio_modules_include_ai_and_exclude_multisource -v`
Expected: PASS

**Step 5: Commit**
```bash
git add backend/app/schemas/generation.py backend/app/services/generation/ai_effects_builder.py backend/app/services/generation/modules/__init__.py backend/app/api/routes_studio.py backend/app/api/routes_generation.py backend/tests/test_studio_routes.py
git commit -m "backend: add display_group to studio and generation module APIs"
```

---

### Task 2: Frontend Types and UI Groups ordering
Update the API typescript models and the central sorting order map with new categories.

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/pages/AIEffects/AIEffectCard.tsx`

**Step 1: Write code updates**
1. Add `display_group: string | null;` to `GenerationModuleInfo` in `frontend/src/api/types.ts`.
2. Add new categories (`Artistic`, `Photography`, `Seasonal`) to `AI_EFFECT_GROUP_ORDER` in `frontend/src/pages/AIEffects/AIEffectCard.tsx`:
```typescript
const AI_EFFECT_GROUP_ORDER = [
  'Portrait',
  'Illustration',
  'Artistic',
  'Poster',
  '3D / Toy',
  'Pop Culture',
  'Cinematic',
  'Sci-Fi',
  'Horror',
  'Historical',
  'Photography',
  'Seasonal',
  'Ungrouped',
];
```

**Step 2: Verify type check passes**
Run: `cd frontend && npm run build`
Expected: Succeeds without TypeScript compilation errors.

**Step 3: Commit**
```bash
git add frontend/src/api/types.ts frontend/src/pages/AIEffects/AIEffectCard.tsx
git commit -m "frontend: add display_group type and register new AI categories"
```

---

### Task 3: Frontend static fallbacks and defaults
Expand the list of fallback modules and default settings to cover all 58 backend-defined AI effects.

**Files:**
- Modify: `frontend/src/pages/automation.types.ts`
- Modify: `frontend/src/pages/automation.utils.ts`

**Step 1: Write code updates**
1. Replace AI fallback entries in `fallbackModules` in `frontend/src/pages/automation.types.ts` with the complete list of 58 AI effects.
2. Replace AI entries in `createDefaultModificationGroups` in `frontend/src/pages/automation.utils.ts` to include all AI effects initialized to `enabled: false, weight: 1, config: {}`.

**Step 2: Run unit tests**
Run: `cd frontend && npm test`
Expected: All tests pass.

**Step 3: Commit**
```bash
git add frontend/src/pages/automation.types.ts frontend/src/pages/automation.utils.ts
git commit -m "frontend: extend fallbacks and default configs for premium AI effects"
```

---

### Task 4: Group select options in Studio UI
Revamp the Studio effect selector dropdown into grouped sections.

**Files:**
- Modify: `frontend/src/pages/StudioPage.tsx`
- Test: `frontend/src/__tests__/Studio.test.tsx`

**Step 1: Write failing test**
In `frontend/src/__tests__/Studio.test.tsx`, assert that select dropdown options are wrapped inside `optgroup` elements.
```typescript
  it('renders dropdown options grouped by display category', async () => {
    renderStudio();
    const dropdown = await screen.findByRole('combobox');
    expect(dropdown.querySelector('optgroup[label="Portrait"]')).toBeInTheDocument();
  });
```

**Step 2: Run test to verify it fails**
Run: `cd frontend && npm test Studio.test`
Expected: FAIL with "optgroup[label="Portrait"] not found".

**Step 3: Implement minimal code**
In `frontend/src/pages/StudioPage.tsx`, sort and group the modules list by their sorted `display_group`:
```typescript
  // Sort and group modules
  const groupedModules = useMemo(() => {
    const map = new Map<string, GenerationModuleInfo[]>();
    for (const mod of modules) {
      const g = mod.display_group || 'Ungrouped';
      const list = map.get(g) || [];
      list.push(mod);
      map.set(g, list);
    }
    return Array.from(map.entries()).sort(([a], [b]) => {
      const aOrder = getAIEffectGroupOrder(a);
      const bOrder = getAIEffectGroupOrder(b);
      if (aOrder !== bOrder) return aOrder - bOrder;
      return a.localeCompare(b);
    });
  }, [modules]);
```
Wait, import `getAIEffectGroupOrder` from `./AIEffects/AIEffectCard` in `StudioPage.tsx`.

Then update the select input rendering in `StudioPage.tsx`:
```typescript
            <select
              value={activeEffectId}
              onChange={(event) => {
                setSelectedEffect(event.target.value);
                setPreview(null);
              }}
              className="app-input"
            >
              {groupedModules.map(([groupName, items]) => (
                <optgroup key={groupName} label={groupName}>
                  {items.map((module) => (
                    <option key={module.name} value={module.name}>
                      {module.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
```

**Step 4: Run test to verify it passes**
Run: `cd frontend && npm test Studio.test`
Expected: PASS

**Step 5: Commit**
```bash
git add frontend/src/pages/StudioPage.tsx frontend/src/__tests__/Studio.test.tsx
git commit -m "frontend: group studio dropdown effects by display group category"
```
