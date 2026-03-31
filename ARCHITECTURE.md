# Top Video Generator — Architecture Decision Record

## Estado: Post-Phase 2 (vibes branch, 2026-03-05)

## Visión General

Pipeline automatizado: fetch YouTube trending → score/rank → generate video → publish (YT/IG/TikTok) + Spotify playlist update.

Arquitectura objetivo: **Hexagonal (Ports & Adapters)** con capas explícitas.

## Capas Actuales

```
src/
├── domain/           ✅ Phase 2 — Entities + Ports (Protocols)
├── application/      ✅ Phase 2 — Use Cases (FetchTrending, PublishVideo)
├── adapters/         ✅ Phase 2 — VideoPublisher × 3, YouTubeSource
├── infrastructure/   ⚠️  Phase 2 parcial — solo publisher_registry.py
│                              Phase 3 TARGET: youtube/, storage/, video/
├── web/              ✅ FastAPI + HTMX + Jinja2
├── config/           ✅ Phase 2 — Pydantic v2 Settings
│
│ ── LEGACY (pendiente migración Phase 3) ──
├── yt_client.py      🔴 55KB God File → infrastructure/youtube/
├── db_client.py      🔴 18KB God File → infrastructure/storage/ + domain/
├── video_processing.py 🔴 22KB God File → infrastructure/video/
├── instagram_client.py → infrastructure/social/
├── spotify_client.py   → infrastructure/social/
└── tiktok_client.py    → infrastructure/social/
```

## Dependencias entre Capas (Dependency Rule)

```
web → application → domain ← adapters ← infrastructure
                    ↑
              (solo Protocols)
```

**Regla:** Las flechas apuntan hacia el dominio. Nunca al revés.

## ADR-001: TinyDB + TinyFlux (storage actual)

- **Decisión:** Mantener para Phase 3. Sin SQLAlchemy aún.
- **Razón:** El volumen de datos no justifica el overhead.
- **Revisitar:** Si se añade multi-region o histórico > 1 año.

## ADR-002: Scoring en Domain Service (Phase 3)

- `VideoPointTools.generate_top_list_compared` **pertenece al dominio**, no a la infraestructura.
- Mover a `domain/services/scoring_service.py`.

## ADR-003: Commit messages

- Formato: `type(scope): description` — Conventional Commits.
- **No** mensajes genéricos como `"vibes"`.

## Problemas críticos en `db_client.py` para arreglar

### BUG 1: Mutable default argument
```python
# ❌ ACTUAL (evaluado en import-time)
def calculate_datetime_for_range(timeseries_range, day: PastDate = date.today()):
    ...

# ✅ TARGET
def datetime_range_start(days_back: int, reference: date | None = None) -> datetime:
    ref = reference or date.today()  # Evaluado en llamada
```

### BUG 2: Pydantic v1 deprecado
```python
# ❌ ACTUAL (Pydantic v1)
Video.parse_obj(results[0])   # → .model_validate()
video.dict()                   # → .model_dump()

# ✅ TARGET: Pydantic v2 API
VideoRecord.model_validate(results[0])
video.model_dump()
```

### BUG 3: Copy-paste en auth TikTok
```python
# ❌ ACTUAL – add_or_update_spotify_auth llama get_tiktok_auth!!!
def add_or_update_spotify_auth(self, spotify_auth):
    if self.get_tiktok_auth(spotify_auth.client_id):  # ← 🔴 ERROR
        return self.update_spotify_auth(spotify_auth)
```

---

## 🗂️ Estructura Target Phase 3

```
src/
├── domain/
│   ├── models.py              ✅ (CanonicalVideo, PublishingResult, Platform)
│   ├── ports.py               ✅ (VideoDataSource, VideoPublisher)
│   ├── exceptions.py          🆕 DomainError, FetchError, PublishError, ScoringError
│   └── services/
│       └── scoring_service.py 🆕 VideoPointTools migrado aquí
│
├── application/
│   ├── fetch_trending_use_case.py  ✅
│   ├── publish_video_use_case.py   ✅
│   └── score_videos_use_case.py    🆕
│
├── infrastructure/
│   ├── youtube/
│   │   ├── __init__.py
│   │   ├── api_client.py      🔀 yt_client.py (API calls)
│   │   ├── auth_manager.py    🔀 yt_client.py (OAuth flow)
│   │   └── video_uploader.py  🔀 yt_client.py (upload logic)
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── video_repository.py       🔀 db_client.py (TinyDB part)
│   │   ├── timeseries_repository.py  🔀 db_client.py (TinyFlux part)
│   │   └── auth_repository.py        🔀 db_client.py (auth tables)
│   ├── video/
│   │   ├── __init__.py
│   │   ├── compositor.py      🔀 video_processing.py (ffmpeg/moviepy)
│   │   ├── renderer.py        🔀 video_processing.py (text/overlay render)
│   │   └── thumbnail.py       🔀 video_processing.py (Pillow/SVG)
│   └── social/
│       ├── instagram_client.py  🔀 src/instagram_client.py
│       ├── spotify_client.py    🔀 src/spotify_client.py
│       └── tiktok_client.py     🔀 src/tiktok_client.py
```

---

## 📋 Orden de Ejecución Phase 3

| # | Tarea | Riesgo | Dependencias |
|---|---|---|---|
| 1 | `domain/exceptions.py` | 🟢 Bajo | Ninguna |
| 2 | `domain/services/scoring_service.py` | 🟢 Bajo | exceptions.py |
| 3 | Tests de scoring (TDD primero) | 🟢 Bajo | scoring_service |
| 4 | `infrastructure/storage/video_repository.py` | 🟡 Medio | Ninguna |
| 5 | `infrastructure/storage/timeseries_repository.py` | 🟡 Medio | scoring_service |
| 6 | Fix bugs `db_client.py` (`.dict()`→`.model_dump()`, copy-paste bug) | 🟡 Medio | Nada |
| 7 | Split `yt_client.py` → `infrastructure/youtube/` | 🔴 Alto | repository listo |
| 8 | Split `video_processing.py` → `infrastructure/video/` | 🔴 Alto | Independiente |
| 9 | Eliminar `db_client.py` legacy | 🔴 Alto | 4 + 5 completados |
| 10 | `application/score_videos_use_case.py` | 🟢 Bajo | scoring_service |

**Regla de oro para Phase 3**: pasos 1–6 son seguros de hacer en paralelo. Los pasos 7–9 deben ir en ese orden estricto porque `yt_client.py` tiene dependencias cruzadas con `db_client.py` y con los adapters.

---

## Checksums y Validación

Cada paso debe validarse:
- ✅ No hay imports circulares (`python -c "import src"`)
- ✅ Linting: `ruff check src/`
- ✅ Type checking: `ty` (pyright)
- ✅ Tests pasan: `pytest tests/unit/domain/`
