# Review Page Image Comparator Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Implement the Before/After comparison toggle button and original image overlay on the standalone review page `backend/app/static/review.html`.

**Architecture:** 
1. Introduce a CSS-based opacity overlay `#img-original` inside the main image wrapper `#img-wrap`, and `#lb-img-original` inside the lightbox canvas.
2. Add toggle buttons `#btn-toggle-original` and `#lb-toggle-original` to switch between generated and original images.
3. Fetch the original source asset authenticated with the user's access token if available using a blob URL via `URL.createObjectURL(blob)` and revoke it appropriately.

**Tech Stack:** HTML5, CSS3, Vanilla Javascript

---

### Task 1: Update review.html Styles and Elements

**Files:**
- Modify: `backend/app/static/review.html`

**Step 1: Write styles for toggles and overlays**
Open `backend/app/static/review.html` and add styling for `#btn-toggle-original`, `#lb-toggle-original`, `#img-original`, and `#lb-img-original` in the `<style>` tag.

**Step 2: Add HTML elements for toggles and overlays**
1. Add the `#btn-toggle-original` button next to the `#source-link` inside `#source-row`.
2. Add the `#img-original` image element inside `#img-wrap`.
3. Add the `#lb-img-original` image and `#lb-toggle-original` button inside the lightbox canvas `.lb-canvas`.

---

### Task 2: Add JS Logic for Image Comparison

**Files:**
- Modify: `backend/app/static/review.html`

**Step 1: Declare global variables**
Add `showOriginalMain`, `showOriginalLightbox`, and `originalImageBlobUrl` to the script variables.

**Step 2: Implement loadOriginalImage(sourceAssetId)**
Add the `loadOriginalImage` function to fetch the original thumbnail using authenticated headers, convert it to a Blob object URL, set the sources of `#img-original` and `#lb-img-original`, and make the toggle buttons visible.

**Step 3: Hook loadOriginalImage into load()**
If a source asset ID is found during the `load()` fetch flow, invoke `loadOriginalImage(sourceAssetId)`.

**Step 4: Bind event listeners**
1. Hook a click listener on `#btn-toggle-original` to toggle `showOriginalMain`, show/hide the original overlay, and update button text/classes.
2. Hook a click listener on `#lb-toggle-original` to toggle `showOriginalLightbox`, show/hide the original overlay in the lightbox, and update button text/classes.
3. Reset `showOriginalLightbox` state to `false` and update the UI accordingly whenever the lightbox is opened.

---

### Task 3: Add Regression Test for Review Page

**Files:**
- Modify: `backend/tests/test_generation_routes.py`

**Step 1: Write test case**
Add `test_get_review_page` at the end of the file. It will call `get_review_page` and verify the file exists and contains the newly added element IDs (`#btn-toggle-original`, `#img-original`, `#lb-img-original`, `#lb-toggle-original`).

**Step 2: Run backend tests to verify**
Run `pytest` to make sure all tests pass.

**Step 3: Commit all changes**
Commit files:
- `backend/app/static/review.html`
- `backend/tests/test_generation_routes.py`

---
