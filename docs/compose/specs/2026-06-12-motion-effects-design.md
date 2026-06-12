# [S1] Problem

DailyFX generuje wyłącznie statyczne obrazy PNG. Użytkownicy chcą efektów dynamicznych (animacji) dla social media, prezentacji i personalizacji. Brak możliwości tworzenia GIF/WebP motion effects.

## [S2] Solution Overview

Nowa kategoria modułów `motion_*` generujących animowane GIF i WebP. Wykorzystuje istniejącą architekturę modułów z rozszerzeniem `GenerationResult` o format wyjściowy. Nowa zależność: `imageio` do zapisu animacji.

## [S3] Persistence & History

Rozszerzenie `GenerationHistoryModel` o `output_format` (png/gif/webp). Zmiana nazwy pliku wynikowego na `{task_id}.{format}`. Thumbnail generowany z pierwszej klatki jako PNG.

## [S4] Frontend

Automatyczna detekcja formatu w `SecureImage`. Dodanie play/pause w lightboxie. Badge "Motion" w historii.

## [S5] Testing & Error Handling

Testy jednostkowe dla każdego modułu motion. Fallback do PNG gdy imageio niedostępne. Timeout 30s. Limit rozmiaru 10MB.

---

# Motion Effects Design Spec

## [S1] Problem

DailyFX generuje wyłącznie statyczne obrazy PNG. Użytkownicy chcą efektów dynamicznych (animacji) dla social media, prezentacji i personalizacji. Brak możliwości tworzenia GIF/WebP motion effects.

## [S2] Solution Overview

Nowa kategoria modułów `motion_*` generujących animowane GIF i WebP. Wykorzystuje istniejącą architekturę modułów z rozszerzeniem `GenerationResult` o format wyjściowy.

### Architektura

```
backend/app/services/generation/modules/
  motion_parallax.py      ← Parallax 3D (2.5D depth)
  motion_cinemagraph.py   ← Cinemagraph (static bg + moving element)
  motion_zoom_pan.py      ← Zoom + Pan (Ken Burns)
  motion_pulse.py         ← Time-based (brightness/saturation/hue modulation)
  common.py               ← frames_to_animation() helper
```

### Zmiany w istniejących plikach

| Plik | Zmiana |
|------|--------|
| `base.py` | Dodanie `output_format: str = "png"` i `frame_count: int \| None = None` do `GenerationResult` |
| `pyproject.toml` | Dodanie `imageio>=2.35.0` do zależności |
| `persistence.py` | Zmiana nazwy pliku na `{task_id}.{format}`, obsługa `output_format` |
| `generation_history.py` | Dodanie kolumny `output_format` (nullable, default "png") |
| `history.py` | Przekazywanie `output_format` do `upsert_history_entry` |
| `output.py` | Ustawianie `Content-Type` na podstawie formatu w endpointach obrazu |

### Nowe zależności

```toml
# pyproject.toml
dependencies = [
    ...
    "imageio>=2.35.0",
]
```

## [S3] Szczegóły Efektów

### motion_parallax — Efekt 2.5D (Parallax)

Symulacja ruchu kamery na statycznym zdjęciu przez przesuwanie warstw z różną prędkością.

**Konfiguracja:**
- `depth` (int, 1-10, default 5) — intensywność efektu głębi
- `speed` (float, 0.5-2.0, default 1.0) — prędkość animacji
- `direction` (select: left/right/up/down, default "left") — kierunek ruchu

**Implementacja:**
1. OpenCV GrabCut do segmentacji foreground/background
2. Pillow do tworzenia klatek z przesuniętymi warstwami
3. Interpolacja liniowa między klatkami

**Wyjście:** 12 klatek @ 12fps = 1s pętla GIF/WebP

### motion_cinemagraph — Cinemagraph

Statyczne tło z ruchomym maskowanym obszarem (woda, chmury, światło).

**Konfiguracja:**
- `mask_region` (select: center/face/custom, default "center") — region ruchu
- `motion_type` (select: water/clouds/glow, default "glow") — typ animacji
- `speed` (float, 0.5-2.0, default 1.0)

**Implementacja:**
1. Prostokątna/kołowa maska na zaznaczonym obszarze
2. Efekt falowania (sinusoidalna deformacja) na maskowanym obszarze
3. Reszta obrazu statyczna

**Wyjście:** 24 klatki @ 12fps = 2s pętla

### motion_zoom_pan — Zoom + Pan

Animowane kadrowanie ze skalowaniem (Ken Burns effect).

**Konfiguracja:**
- `style` (select: zoom-in/zoom-out/ken-burns/pan-left/pan-right, default "ken-burns")
- `duration` (float, 1-3, default 2) — czas trwania w sekundach
- `intensity` (float, 0.1-0.5, default 0.2) — intensywność ruchu

**Implementacja:**
1. Pillow `Image.transform` z interpolacją bicubic
2. Liniowa interpolacja parametrów transformacji między klatkami

**Wyjście:** 24-36 klatek @ 12fps

### motion_pulse — Efekty Time-Based

Pulsowanie parametrów obrazu (jasność, nasycenie, barwa, glitch).

**Konfiguracja:**
- `effect` (select: brightness/saturation/hue/glitch, default "brightness")
- `speed` (float, 0.5-2.0, default 1.0)
- `intensity` (float, 0.3-1.0, default 0.6)

**Implementacja:**
1. Sinusoidalna modulacja parametrów Pillow (ImageEnhance)
2. Dla glitch: losowe RGB offset co N klatek

**Wyjście:** 24 klatki @ 12fps = 2s pętla

### Helper: frames_to_animation

Wspólna funkcja w `common.py`:

```python
def frames_to_animation(
    frames: list[Image.Image],
    fps: int = 12,
    format: str = "gif",
    loop: int = 0,
) -> bytes:
    """Compress PIL frames to animated GIF or WebP using imageio."""
```

## [S4] Frontend — Zmiany

### SecureImage.tsx

Rozszerzenie o automatyczną detekcję formatu:

```tsx
// Dodanie autoPlay prop
interface SecureImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
  autoPlay?: boolean;
}

// Dla GIF/WebP: img automatycznie odtwarza animację
// Brak zmian w renderowaniu — <img> obsługuje animowane obrazy natywnie
```

### LightboxModal.tsx

Dodanie kontroli play/pause dla animacji:

```tsx
// Gdy output_format === 'gif' || 'webp':
// Przycisk Play/Pause toggle
// Reset animacji przez usunięcie i ponowne dodanie src
```

### HistoryPage.tsx

Badge "Motion" dla animowanych wyników:

```tsx
// Mały tag obok tytułu gdy entry.output_format !== 'png'
// Styl: emerald badge z ikoną play
```

### API Client

Rozszerzenie `GenerationHistoryEntry`:

```typescript
export type GenerationHistoryEntry = {
  // ... istniejące pola
  output_format: 'png' | 'gif' | 'webp';
};
```

## [S5] Testy i Obsługa Błędów

### Backend Tests

| Test | Opis |
|------|------|
| `test_motion_parallax.py` | Generowanie klatek, rozmiar, format GIF/WebP, timeout |
| `test_motion_cinemagraph.py` | Maska, ruch, pętla, rozmiar |
| `test_motion_zoom_pan.py` | Style zoom, interpolacja, rozmiar |
| `test_motion_pulse.py` | Modulacja sinusoidalna, rozmiar |
| `test_motion_common.py` | `frames_to_animation` — GIF/WebP, kompresja |
| `test_generation_routes.py` | Endpointy z `output_format` |

### Error Handling

| Scenariusz | Zachowanie |
|------------|-----------|
| imageio nie zainstalowane | Fallback do PNG + log warning |
| Generacja klatek > 30s | Timeout → PNG fallback |
| Rozmiar GIF/WebP > 10MB | Redukcja klatek/rozdzielczości |
| Nieprawidłowy format | ValueError w module |

### Limit Size

Dla GIF/WebP: automatyczna redukcja gdy rozmiar > 10MB:
1. Redukcja klatek (24 → 12)
2. Redukcja rozdzielczości (1600 → 800)
3. Redukcja quality (WebP: 90 → 70)

---

# Coverage

| Spec Section | Plan Coverage |
|--------------|---------------|
| [S1] Problem | Context only |
| [S2] Solution Overview | Tasks T1-T4 |
| [S3] Persistence & History | Tasks T5-T7 |
| [S4] Frontend | Tasks T8-T10 |
| [S5] Testing & Errors | Tasks T11-T13 |
