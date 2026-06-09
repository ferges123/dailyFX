# Design Doc: InstaWeather Safe Area Layout

## 1. Overview
The InstaWeather module is being redesigned from a single localized card to a full-screen, photography-style "Safe Area" watermark overlay. Content is distributed along the margins of the photo while dynamically avoiding overlapping any detected faces.

## 2. Layout Structure
All UI elements are kept within a **7% safe area margin** from the canvas edges.
- **Top-Left (Day & Date):**
  - Line 1: Day of the week in uppercase English (e.g. `SATURDAY`).
  - Line 2: Date below (e.g. `MAY 18, 2024`).
- **Left-Middle (Main Weather Detail):**
  - Main weather icon (colored/themed).
  - Below it: Large temperature (e.g. `22°C` or `72°F`).
  - Below temp: Thin horizontal divider line (spanning 30% of canvas width).
  - Below divider: "FEELS LIKE" label and value, and a Cloudiness category label and value (e.g. `CLOUDINESS` / `LOW`).
- **Top-Right (Sunrise & Sunset):**
  - Row 1: Sunrise icon + time.
  - Row 2: Sunset icon + time.
  - Divider: Subtle dotted line between the rows.
- **Bottom-Left (Location):**
  - Pin icon.
  - City name in uppercase bold (e.g. `ZAKOPANE`).
  - Country/region below (e.g. `POLAND`).
- **Bottom-Right (Metrics):**
  - Row 1: Humidity icon + value (e.g. `HUMIDITY 48%`).
  - Row 2: Wind icon + value (e.g. `WIND 11 km/h NE`).

## 3. Data Fetching & Fallbacks
Open-Meteo integration is extended to fetch the following:
- Hourly variables: `apparent_temperature`, `cloud_cover`, `relative_humidity_2m`, `wind_speed_10m`, `wind_direction_10m`.
- Daily variables: `sunrise`, `sunset`.
- Cloud cover to text mapping:
  - 0-20%: `LOW`
  - 21-60%: `MEDIUM`
  - 61-100%: `HIGH`
- Cardinal wind directions calculated from degrees.
- Fallback weather simulation extended to mock reasonable values for these parameters when GPS/internet are offline.

## 4. Typography & Readability
- Font: `Inter-Regular.ttf` for all text.
- Main Temperature: Drawn very large.
- City Name: Bolded via "fake bold" drawing (drawing with minor pixel offsets: `(x,y)`, `(x+1,y)`, `(x,y+1)`, `(x+1,y+1)`).
- Readability Shadow: A dark drop shadow drawn behind all white text in semi-transparent black `(0, 0, 0, 140)` offset diagonally by `int(1.5 * scale)`.

## 5. Collision Avoidance (Face Protection)
For each block, we compute an estimated bounding box based on the canvas size. If any face bounding box intersects:
- **Corner blocks:** Shift inwards (horizontally or vertically) by up to 15% of the canvas size.
- **Left-Middle block:** Shift vertically. If still colliding, swap to the right-middle edge.
- **Fallback:** Hide the block if collision cannot be resolved.

## 6. Vector Icon Specification
We draw minimal vector shapes using `PIL.ImageDraw`:
- **Main Weather:**
  - Sun: Yellow circle with 8 radial lines.
  - Cloud: Overlapping white/gray circles/arcs.
  - Rain: Cloud with diagonal blue lines.
  - Snow: Cloud with white dots.
  - Thunderstorm: Cloud with yellow lightning bolt.
- **Sunrise/Sunset:** Horizon line with a half-circle and rays (or arrows pointing up/down).
- **Pin:** Teardrop with hollow center.
- **Humidity:** Drop shape.
- **Wind:** Two wavy horizontal lines.
