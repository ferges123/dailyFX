# DailyFX — Kompleksowy Audyt Aplikacji

**Data:** 2026-06-18
**Zakres:** Backend (FastAPI), Frontend (React/Vite), Infrastruktura (Docker, CI/CD)

---

## Podsumowanie Krytyczności

| Krytyczność | Backend | Frontend | Infra | Razem |
|-------------|---------|----------|-------|-------|
| **CRITICAL** | 0 | 0 | 1 | **1** |
| **HIGH** | 3 | 2 | 4 | **9** |
| **MEDIUM** | 13 | 11 | 14 | **38** |
| **LOW** | 12 | 16 | 8 | **36** |

---

## 1. CRITICAL — Natychmiastowe działanie

### `.env` z domyślnymi kluczami w produkcji

**Plik:** `.env:9-10`

Live `.env` zawiera domyślny placeholder `APP_SECRET_KEY=change-me-generate-a-long-random-secret` oraz słaby token `APP_ACCESS_TOKEN=token`. Jeżeli instancja jest dostępna z zewnątrz, API jest niechronione.

**Akcja:** Natychmiast wygeneruj nowe klucze (`openssl rand -hex 32`).

---

## 2. HIGH — Wymagają szybkiego działania

| # | Znalezisko | Lokalizacja |
|---|-----------|-------------|
| 1 | **Brak izolacji sieci Docker** — oba kontenery współdzielą domyślną sieć Compose | `docker-compose.yml` |
| 2 | **Token Telegram logowany w fragmentach** — `_poll_bot_updates` loguje 6 ostatnich znaków tokenu botu | `workers/telegram_bot.py:40,54,74,94` |
| 3 | **Race condition w `_running_task_ids`** — set modyfikowany z wielu tasków bez locka; wpisy nieusuwane przy błędzie | `workers/scheduler.py:21,398-399` |
| 4 | **Klucz API wysyłany bez wymuszenia TLS** — ImmichClient nie wymusza weryfikacji TLS, klucz API może iść po HTTP | `immich/client.py:40-49` |
| 5 | **AbortController w `request()` nieudostępniony** — callerzy nie mogą anulować żądań, porzucone requesty zużywają bandwidth | `frontend/src/api/base.ts:55-56` |
| 6 | **Mutowalny `onUnauthorizedCallback` na poziomie modułu** — race condition przy re-mount `AuthProvider` | `frontend/src/api/base.ts:29-31` |
| 7 | **Migracja 0020/0021 nieodwracalna** — downgrade skutkuje utratą danych (usunięte kolumny, preset-y) | `migrations/versions/0020_*.py`, `0021_*.py` |
| 8 | **`pip-audit` ignoruje błędy** (`\|\| true`) — podatne dependencje przechodzą CI | `.github/workflows/ci.yml:36` |
| 9 | **Brak CORS_ORIGINS w `.env`** — domyślne origins mogą blokować frontend lub zezwalać na niechciane źródła | `backend/app/config.py:66-74` |

---

## 3. MEDIUM — Warte poprawienia

### Backend (13)

| # | Znalezisko | Lokalizacja |
|---|-----------|-------------|
| 1 | **SSRF na URL-ach Immich/local_ai** — brak walidacji czy IP nie jest w sieciach prywatnych | `immich/client.py`, `services/local_ai.py:12-18` |
| 2 | **`follow_redirects=True`** na żądaniach Immich — potencjalne przekierowanie z API key | `immich/client.py:87,124,141,174` |
| 3 | **Brak rate limiting na destrukcyjnych endpointach** (`DELETE /api/generation/history/cache`, import AI effects) | `routes_generation.py:523,562` |
| 4 | **Auth może być całkowicie wyłączony** — bez `APP_ACCESS_TOKEN` wszystkie endpointy publiczne | `security.py:20-21` |
| 5 | **`defaultdict(Lock)` w `ai_budget.py`** — nieograniczony growth kluczy | `services/generation/ai_budget.py:16` |
| 6 | **Błąd w tle bez rollback sesji** w `_run_queued_task_in_background` | `workers/scheduler.py:206-243` |
| 7 | **Brak timeout na generation tasks** — zawieszony request AI blokuje slot w nieskończoność | `workers/scheduler.py:399,203-247` |
| 8 | **Pełne logowanie pliku debug** — `read_text()` bez limitu rozmiaru | `routes_debug.py:26` |
| 9 | **CORS: `allow_methods=["*"]`, `allow_headers=["*"]`** — maksymalnie permisywne | `main.py:81-87` |
| 10 | **Exception messages w HTTP responses** — ujawniają ścieżki wewnętrzne | `routes_generation.py:397`, `routes_studio.py:213` |
| 11 | **Brak paginacji na listach** — preset-y, AI effects, schedules zwracają nieograniczone zbiory | `routes_presets.py`, `routes_ai_effects.py`, `routes_schedules.py` |
| 12 | **`GET /api/health` ujawnia status auth** nieuwierzytelnionym callerom | `routes_health.py:25` |
| 13 | **`/api/debug/log` ujawnia pełne logi** — mogą zawierać tokeny, wewnętrzne błędy | `routes_debug.py:10-28` |

### Frontend (11)

| # | Znalezisko | Lokalizacja |
|---|-----------|-------------|
| 1 | **Zero `React.memo()`** — niepotrzebne re-rendering list | ogólne |
| 2 | **SecureImage: brak batchingu/anulowania** — każde thumbnail = osobny auth request | `SecureImage.tsx:28` |
| 3 | **SecureImage: `isMounted` zamiast AbortController** — porzucone requesty zużywają bandwidth | `SecureImage.tsx:16` |
| 4 | **SSE stream: torn down przy zmianie filtra** — brief disconnection window | `useHistoryStreamSync.ts:25-55` |
| 5 | **Push notification `url` bez walidacji origin** w service worker | `sw.js:25` |
| 6 | **`base: '/'` hardcoded** w vite.config.ts — brak konfiguracji env | `vite.config.ts:6` |
| 7 | **Race condition: szybkie przełączanie providerów** w ScheduleForm | `ScheduleForm.tsx:75-84,94-103` |
| 8 | **Brak testów: API layer, hooks, SSE, SecureImage** — 0% coverage tych obszarów | ogólne |
| 9 | **`useFocusTrap` nie obsługuje async content** — auto-focus przed załadowaniem DOM | `useFocusTrap.ts:17` |
| 10 | **Caller-provided headers mogą nadpisać Content-Type/Authorization** | `base.ts:54-82` |
| 11 | **Duplicated timeout/abort pattern** w `generation.ts` poza `request()` | `generation.ts:43-65` |

### Infra (14)

| # | Znalezisko | Lokalizacja |
|---|-----------|-------------|
| 1 | **Brak `read_only: true`** na kontenerach Docker | `docker-compose.yml` |
| 2 | **Brak `cap_drop: ALL`** na kontenerach | `docker-compose.yml` |
| 3 | **Trivy skan nie blokuje publikacji** (`exit-code: '0'`) | `.github/workflows/docker-publish.yml:78,109` |
| 4 | **Action versions niepinned** (SHA) — podatność na supply-chain | `ci.yml`, `docker-publish.yml` |
| 5 | **`workflow_dispatch` version niezwalidowana** — potencjalnie zły image tag | `docker-publish.yml:48-49` |
| 6 | **Brak security headers** (X-Content-Type-Options, HSTS, Referrer-Policy) | `frontend/nginx.conf:7` |
| 7 | **No HTTPS enforcement** — TLS musi być obsłużony przez reverse proxy (niedokumentowane) | `frontend/nginx.conf:2` |
| 8 | **SECURITY.md bez kontaktu/email/PGP** i bez polityki czasu odpowiedzi | `SECURITY.md` |
| 9 | **`.codex/` i `.agents/` nie w .gitignore** | `.gitignore` |
| 10 | **Brak pre-migration backup** — `alembic upgrade head` bez backupu | `app/migrations/env.py` |
| 11 | **Migracja 0028: downgrade traci dodatkowe associations** | `versions/0028_*.py:55-69` |
| 12 | **Brak `server_default` zgodności** — `server_default="0"` String dla Boolean | `versions/0019_*.py:65` |
| 13 | **Brak frontend targets w Makefile** | `Makefile` |
| 14 | **Inkonsystentne wersje actions** — `@v5` vs `@v6` | `ci.yml` vs `docker-publish.yml` |

---

## 4. LOW

### Backend (12)

| # | Znalezisko | Lokalizacja |
|---|-----------|-------------|
| 1 | Missing index na `generation_history.status` | `models/generation_history.py:15` |
| 2 | Missing index na `generation_tasks.status` | `models/generation_task.py:13` |
| 3 | Missing index na `generation_history.schedule_id` | `models/generation_history.py:39` |
| 4 | Brak `ON DELETE` FK constraints na schedule → preset | `models/schedule.py:29-30` |
| 5 | `ai_effects.id` jako String(255) PK — wolniejszy lookup | `models/ai_effect.py:14` |
| 6 | `debug_logger.py` hardcodes `/data/logs` | `utils/debug_logger.py:30,68-69` |
| 7 | SHA-1 do checksum immich assets | `immich/client.py:53-54` |
| 8 | Telegram bot: nieefektywne pollowanie co 15s | `workers/telegram_bot.py:26` |
| 9 | Brak graceful shutdown dla background tasks | `workers/scheduler.py:482-497` |
| 10 | `APP_SECRET_KEY` placeholder ostrzegany ale nie blokowany | `preflight.py:58-62` |
| 11 | `app_host` default `0.0.0.0` — powinno być udokumentowane | `config.py:13` |
| 12 | Notification preset test wysyła prawdziwe powiadomienia (bez dry-run) | `services/notifications/preset_tests.py:22` |

### Frontend (16)

| # | Znalezisko | Lokalizacja |
|---|-----------|-------------|
| 1 | Token w localStorage (akceptowalne dla self-hosted) | `api/base.ts:10` |
| 2 | Brak `engines` w package.json | `package.json` |
| 3 | Dev server binduje `0.0.0.0` | `package.json:7` |
| 4 | Brak CSP meta tag | `index.html` |
| 5 | `SecureImage` prop spreading — fragile src override | `SecureImage.tsx:73` |
| 6 | `immich.ts` niezwalidowany assetId w URL path | `immich.ts:8-9` |
| 7 | `sessionStorage` z server data | `Schedules.tsx:235` |
| 8 | `FilterPanels.tsx` nowy array na cada render | `FilterPanels.tsx:14-15` |
| 9 | `AIEffectCard` dropdown bez outside-click handler | `AIEffectCard.tsx:132` |
| 10 | Mobile nav bez `aria-label` | `App.tsx:340-364` |
| 11 | Brak testów: modals, form submits, AIEffects CRUD | ogólne |
| 12 | `SecureImage` globalnie mockowany w testach | `test-setup.ts:5-7` |
| 13 | `generationStream.ts` brak testów | ogólne |
| 14 | `useHistorySelection` dependency na nową referencję | `useHistorySelection.ts:19-38` |
| 15 | `ScheduleForm` brak AbortController | `ScheduleForm.tsx:75-84` |
| 16 | Brak `React.memo` kandydatów dla małych komponentów | ogólne |

### Infra (8)

| # | Znalezisko | Lokalizacja |
|---|-----------|-------------|
| 1 | Backend Dockerfile brak multi-stage build | `backend/Dockerfile` |
| 2 | `chmod -R o+rX /app` zbyt szeroki | `backend/Dockerfile:16` |
| 3 | Frontend build stage jako root | `frontend/Dockerfile:1-8` |
| 4 | Brak `stop_grace_period` | `docker-compose.yml` |
| 5 | Brak `docker-compose` targets w Makefile | `Makefile` |
| 6 | Brak `clean` / `db-migrate` targets | `Makefile` |
| 7 | Brak branch protection / CODEOWNERS | repo-level |
| 8 | Brak SAST (bandit, trufflehog) w CI | `ci.yml` |

---

## 5. Pozytywne wzorce

| Kategoria | Co działa dobrze |
|-----------|-----------------|
| **XSS** | Zero `dangerouslySetInnerHTML`, `eval()`, `document.write()` — cały rendering przez React auto-escaping |
| **TypeScript** | `"strict": true`, discriminated unions w type definitions |
| **Błędy** | Route-level error boundaries, lazy loading, loading states |
| **Accessibilitas** | `aria-label`, `aria-expanded`, `role="status"`, `useFocusTrap` w modalach |
| **Szyfrowanie** | Fernet do kluczy API, HMAC-signed review tokens, `secrets.compare_digest` |
| **Docker** | Non-root containers, SHA256-pinned images, resource limits, health checks |
| **Baza danych** | SQLAlchemy ORM (brak raw SQL), WAL mode, proper UTC handling, pool sizing |
| **Pamięć** | Blob URL cleanup, useEffect cleanup, `isMounted` guards |
| **Immutability** | Frozen dataclasses dla Immich models |
| **Path traversal** | `_safe_path()` walidacja w Studio |

---

## 6. Plany naprawcze (kolejność priorytetów)

### Zrobione
- [x] Zabezpieczono `backend/app/static/review.html` przed XSS w dynamicznych danych EXIF/timeline/linków przez zastąpienie interpolowanego `innerHTML` bezpiecznym DOM API oraz dodanie testu regresyjnego.
- [x] Usunięto logowanie fragmentów tokenu Telegram bot.
- [x] Zmieniono/rotowano `APP_SECRET_KEY`.

### Faza 1: Krytyczne / Bezpieczeństwo natychmiastowe
- [x] Rotuj `APP_SECRET_KEY` w `.env`
- [ ] Rotuj `APP_ACCESS_TOKEN` w `.env`
- [ ] Dodaj Docker network isolation (frontend network + backend network)
- [ ] Enforce Trivy scans blocking (`exit-code: '1'`)
- [ ] Pin GitHub Actions do SHA (nie tagów)
- [ ] Dodaj timeout na background generation tasks (`workers/scheduler.py`)

### Faza 2: Bezpieczeństwo (HIGH)
- [ ] Dodaj SSRF protection na Immich/local_ai URLs (waliduj IP nie jest w sieciach prywatnych)
- [ ] Dodaj rate limiting na destrukcyjnych endpointach (cache delete, import)
- [x] Usuń logowanie fragmentów Telegram bot token
- [ ] Napraw race condition w `_running_task_ids` (lock lub asyncio primitive)
- [ ] Rollback sesji w `_run_queued_task_in_background` na exception
- [ ] Wymuszaj `APP_ACCESS_TOKEN` w production (lub głośne warning)

### Faza 3: Infrastruktura (MEDIUM)
- [ ] Dodaj `read_only: true` na kontenerach Docker
- [ ] Dodaj `cap_drop: ALL` na kontenerach
- [ ] Dodaj security headers w nginx (X-Content-Type-Options, HSTS, Referrer-Policy)
- [ ] Dodaj pre-migration backup przed `alembic upgrade head`
- [ ] Dodaj walidację `workflow_dispatch` version
- [ ] Dodaj `.codex/` i `.agents/` do .gitignore
- [ ] Uzupełnij SECURITY.md o kontakt i politykę czasu odpowiedzi
- [ ] Dodaj frontend targets do Makefile

### Faza 4: Frontend (MEDIUM)
- [ ] Dodaj `React.memo()` do list components (SecureImage, FilterRow, ScheduleCard, HistoryEntry)
- [ ] Implementuj AbortController w `SecureImage` zamiast `isMounted`
- [ ] Optymalizuj SSE stream — nie torn down przy zmianie filtra
- [ ] Waliduj push notification URL w service worker
- [ ] Dodaj `base` jako env variable w vite.config.ts
- [ ] Dodaj testy: API layer, hooks, SSE streaming, SecureImage

### Faza 5: Backend (MEDIUM)
- [x] Zabezpiecz `review.html` przed XSS w danych dynamicznych renderowanych poza Reactem
- [ ] Enforce `follow_redirects=False` lub waliduj redirect targets
- [ ] Dodaj paginację na listach (presets, AI effects, schedules)
- [ ] Zmień `allow_methods`/`allow_headers` na konkretne wartości
- [ ] Dodaj debug log size limit
- [ ] Ukrywaj exception details w HTTP responses
- [ ] Dodaj timeout na generation tasks
- [ ] Dodaj `defaultdict(Lock)` eviction policy

### Faza 6: Baza danych (LOW)
- [ ] Dodaj indeksy: `generation_history.status`, `generation_tasks.status`, `generation_history.schedule_id`
- [ ] Dodaj `ON DELETE CASCADE/SET NULL` na schedule → preset FK
- [ ] Rozważ zmianę `ai_effects.id` na integer PK

### Faza 7: Cleanup (LOW)
- [x] Dodaj missing .gitignore entries (`.vscode/`, `.idea/`, `.DS_Store`, `Thumbs.db`)
- [x] Dodaj `engines` do package.json
- [x] Dodaj CSP meta tag
- [x] Dodaj `aria-label` do mobile nav
- [x] Dodaj outside-click handler do AIEffectCard dropdown
- [x] Dodaj testy: modals, form submits, AIEffects CRUD
- [x] Dodaj SAST (bandit) do CI

---

## Metryki testowe

### Backend
- **Razem endpointów:** ~60
- **Z rate limitingiem:** 12 (~20%)
- **Z auth required:** ~55 (~92%)
- **SQL injection:** 0 (SQLAlchemy ORM)
- **Path traversal:** 0 (walidacja `_safe_path`)

### Frontend
- **Razem komponentów:** 10 shared + 13 pages
- **Z testami:** 49 testów
- **Brak testów:** API layer, hooks, SSE, SecureImage
- **XSS:** 0 (brak `dangerouslySetInnerHTML`)
- **React.memo:** 0 użyc
