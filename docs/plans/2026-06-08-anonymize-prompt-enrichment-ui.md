# Anonymize Prompt Enrichment UI Context Hint Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Ensure the raw `context_hint` stored in the history's `prompt_enrichment_context` is anonymized to avoid showing real people's names in the UI under "Prompt enrichment".

**Architecture:**
1. In `AIStyleBaseModule.run`, after creating the `anonymized_enrichment` block, overwrite `context_hint` and `people_prompt_hint` in the non-anonymized `enrichment_context` with the anonymized values.
2. This ensures that the structured `people_names` list still holds the original names for structured UI reference, but the raw prompt text block is fully anonymized.

**Tech Stack:** Python 3.13, FastAPI

---

### Task 1: Update ai_style_base.py Prompt Enrichment Storage

**Files:**
- Modify: `backend/app/services/generation/modules/ai_style_base.py`

**Step 1: Write the implementation**
Open `backend/app/services/generation/modules/ai_style_base.py` and modify the prompt enrichment assembly block:
```python
                anonymized_enrichment = self._build_prompt_context_hint(
                    album_name=album_name,
                    people_context=people_context,
                    exif_info=exif_info,
                    anonymize=True,
                )
                if anonymized_enrichment:
                    enrichment_context_hint = anonymized_enrichment["context_hint"]
                    debug_log(
                        "AI prompt enrichment context assembled (anonymized)",
                        album_name=anonymized_enrichment["album_name"],
                        people_names=anonymized_enrichment["people_names"],
                        exif_summary=anonymized_enrichment["exif_summary"],
                        context_hint=enrichment_context_hint,
                    )
                    # Update enrichment_context with anonymized hints so that history database
                    # and UI correctly display the anonymized prompt hints sent to the AI.
                    if enrichment_context:
                        enrichment_context["context_hint"] = anonymized_enrichment["context_hint"]
                        enrichment_context["people_prompt_hint"] = anonymized_enrichment["people_prompt_hint"]
```

---

### Task 2: Update Tests and Verify

**Files:**
- Modify: `backend/tests/test_generation_modules.py`

**Step 1: Add assertions to test_generate_ai_image_with_prompt_enrichment**
Add the following assertions at the end of the test case to ensure the stored context hint does not leak original names:
```python
    assert "Alice" not in result.config["prompt_enrichment_context"]["context_hint"]
    assert "person 1" in result.config["prompt_enrichment_context"]["context_hint"]
```

**Step 2: Run pytest to verify**
Run the backend test suite.

**Step 3: Commit all changes**
Commit changes to git.

---
