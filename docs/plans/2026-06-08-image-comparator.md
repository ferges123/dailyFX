# Image Comparator Toggle Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Implement a simplified Before/After toggle button comparison feature in the History details panel and Lightbox modal.

**Architecture:** We will introduce a boolean state `showOriginal` in both components. The original and generated images will be overlaid inside a relative container. The original image will fade in and out via CSS transitions controlled by the state.

**Tech Stack:** React 19, TypeScript, Tailwind CSS

---

### Task 1: Update HistoryDetailPanel

**Files:**
- Modify: `frontend/src/pages/History/HistoryDetailPanel.tsx`
- Test: `frontend/src/__tests__/History.test.tsx`

**Step 1: Write the failing test**
Run the existing tests in `frontend/src/__tests__/History.test.tsx` to verify baseline behavior.
`cd frontend && npm test`

**Step 2: Run test to verify it fails**
Run baseline test suite. Expected: PASS (baseline is green).

**Step 3: Write minimal implementation**
1. Import `useState` and `useEffect` if not already present.
2. Inside `HistoryDetailPanel`, add state:
   ```typescript
   const [showOriginal, setShowOriginal] = useState(false);
   ```
3. Add a `useEffect` to reset `showOriginal` to `false` when `entry` changes:
   ```typescript
   useEffect(() => {
     setShowOriginal(false);
   }, [entry]);
   ```
4. Extract `sourceAssetId` inside `HistoryDetailPanel`:
   ```typescript
   const sourceAssetId = (() => {
     if (!entry?.source_asset_ids) return null;
     try {
       const ids = JSON.parse(entry.source_asset_ids);
       return Array.isArray(ids) && ids.length > 0 ? ids[0] : null;
     } catch {
       return null;
     }
   })();
   ```
5. Modify the "Source photo" block (around line 184) to render the button next to the link:
   ```tsx
   {sourceAssetImmichUrl && (
     <div className="flex items-center gap-1.5 text-[9.5px] text-stone-500 font-medium pt-0.5">
       <span>Source photo:</span>
       <a
         href={sourceAssetImmichUrl}
         target="_blank"
         rel="noreferrer"
         className="inline-flex items-center gap-1 rounded-lg border border-emerald-200/60 bg-emerald-50 px-2 py-0.5 text-[9.5px] font-semibold text-emerald-800 transition hover:bg-emerald-100"
       >
         <ExternalLink size={10} />
         View original in Immich
       </a>
       {sourceAssetId && (
         <button
           type="button"
           onClick={() => setShowOriginal(!showOriginal)}
           className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 text-[9.5px] font-semibold transition cursor-pointer ${
             showOriginal
               ? 'border-emerald-600 bg-emerald-800 text-white hover:bg-emerald-900'
               : 'border-emerald-250 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
           }`}
         >
           {showOriginal ? 'Show Effect' : 'Show Original'}
         </button>
       )}
     </div>
   )}
   ```
6. Update the image display container (around line 261) to overlay both images:
   ```tsx
   {entry.image_url ? (
     <div className="relative group max-w-full overflow-hidden rounded-xl md:rounded-2xl border border-stone-200 bg-stone-100 shadow-[0_12px_26px_rgba(36,29,16,0.06)]">
       {/* Base: Generated image */}
       <SecureImage
         src={`${entry.image_url}?thumbnail=true`}
         alt={entry.title}
         className="w-full max-h-[220px] md:max-h-[320px] cursor-zoom-in object-contain mx-auto transition-transform duration-500 ease-out group-hover:scale-[1.015]"
         onClick={() => onOpenLightbox(entry.image_url ?? '')}
       />
       {/* Overlay: Original image */}
       {sourceAssetId && (
         <div
           className={`absolute inset-0 bg-stone-100 transition-opacity duration-200 pointer-events-none ${
             showOriginal ? 'opacity-100' : 'opacity-0'
           }`}
         >
           <SecureImage
             src={`/api/immich/assets/${sourceAssetId}/thumbnail?size=preview`}
             alt="Original"
             className="w-full h-full object-contain mx-auto"
           />
         </div>
       )}
       {/* Centered Zoom Icon Overlay */}
       <div className="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center pointer-events-none">
         <div className="bg-white/20 backdrop-blur-md border border-white/30 text-white p-2 rounded-full shadow-lg">
           <ZoomIn size={14} />
         </div>
       </div>
       {/* Floating Download Button */}
       <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
         <a
           href={entry.image_url}
           download
           className="pointer-events-auto flex items-center justify-center rounded-xl border border-white/10 bg-stone-900/80 p-1.5 text-white shadow-md transition hover:bg-stone-950 active:scale-95"
           title="Download image"
           onClick={(e) => e.stopPropagation()}
         >
           <Download size={13} />
         </a>
       </div>
     </div>
   ) : ...
   ```

**Step 4: Run test to verify it passes**
Run: `cd frontend && npm test` and `npm run build`
Expected: Passes.

**Step 5: Commit**
```bash
git add frontend/src/pages/History/HistoryDetailPanel.tsx
git commit -m "feat: add Before/After image toggle comparison to HistoryDetailPanel"
```

---

### Task 2: Update LightboxModal

**Files:**
- Modify: `frontend/src/pages/History/LightboxModal.tsx`

**Step 1: Write the failing test**
Run `cd frontend && npm run build` to verify PWA is building successfully before changes.

**Step 2: Run test to verify it fails**
Run build. Expected: PASS (baseline is green).

**Step 3: Write minimal implementation**
1. Open `frontend/src/pages/History/LightboxModal.tsx`.
2. Add `useState` import.
3. Inside `LightboxModal`, add state:
   ```typescript
   const [showOriginal, setShowOriginal] = useState(false);
   ```
4. Reset this state to `false` when the modal opens or `imageUrl` changes:
   ```typescript
   useEffect(() => {
     setShowOriginal(false);
   }, [imageUrl, isOpen]);
   ```
5. Extract `sourceAssetId` and `originalImageUrl`:
   ```typescript
   const sourceAssetId = (() => {
     if (!entry?.source_asset_ids) return null;
     try {
       const ids = JSON.parse(entry.source_asset_ids);
       return Array.isArray(ids) && ids.length > 0 ? ids[0] : null;
     } catch {
       return null;
     }
   })();
   const originalImageUrl = sourceAssetId ? `/api/immich/assets/${sourceAssetId}/thumbnail?size=preview` : null;
   ```
6. Update the canvas viewport section (around line 164) to overlay the images:
   ```tsx
   {/* Photo Canvas */}
   <div className="relative flex max-h-[52vh] flex-1 items-center justify-center bg-stone-950 p-2 md:max-h-[85vh]">
     <SecureImage
       src={imageUrl}
       alt="Preview"
       className="max-h-full max-w-full rounded-lg object-contain"
     />
     {originalImageUrl && (
       <div
         className={`absolute inset-0 flex items-center justify-center bg-stone-950 transition-opacity duration-200 ${
           showOriginal ? 'opacity-100' : 'opacity-0'
         }`}
       >
         <SecureImage
           src={originalImageUrl}
           alt="Original Preview"
           className="max-h-full max-w-full rounded-lg object-contain"
         />
       </div>
     )}
     {originalImageUrl && (
       <button
         type="button"
         onClick={() => setShowOriginal(!showOriginal)}
         className={`absolute bottom-4 right-4 z-30 inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold shadow-lg backdrop-blur-md transition active:scale-95 cursor-pointer ${
           showOriginal
             ? 'border-emerald-600 bg-emerald-800 text-white hover:bg-emerald-900'
             : 'border-white/10 bg-stone-900/80 text-white hover:bg-stone-950'
         }`}
       >
         <Layers size={13} />
         {showOriginal ? 'Show Effect' : 'Show Original'}
       </button>
     )}
   </div>
   ```

**Step 4: Run test to verify it passes**
Run: `cd frontend && npm run build` and `npm test`
Expected: Build and tests pass successfully.

**Step 5: Commit**
```bash
git add frontend/src/pages/History/LightboxModal.tsx
git commit -m "feat: add Before/After image toggle comparison to LightboxModal"
```
