# Top Video Generator — Architecture Decision Record

## Estado: Phase 2 completada; estabilización y refactor incremental en curso (2026-03-31)

## Visión General

Pipeline automatizado: fetch de YouTube trending → score/rank → generación de vídeo → publicación en YT/IG/TikTok + actualización de Spotify.

La arquitectura activa es **hexagonal (Ports & Adapters)** y el grueso de la migración fuera de los antiguos god files ya está completado.

## Capas Actuales

```
src/
├── domain/           ✅ modelos canónicos, puertos y servicios de dominio
├── application/      ✅ casos de uso y orquestación
├── adapters/         ✅ adaptadores de publicación y fuente YouTube
├── infrastructure/   ✅ youtube/, storage/, video/, social/, publisher_registry.py
├── entrypoints/      ✅ fetch_data.py, publish_video.py, publish_vertical.py, api_server.py, workers/
├── web/              ⚠️ FastAPI SSR funcional, pero con demasiado wiring concentrado en main.py
├── config/           ✅ settings con Pydantic v2
└── shared/           ✅ utilidades transversales como logging
```

Los antiguos módulos `db_client.py`, `yt_client.py` y `video_processing.py` ya no forman parte del árbol principal. No deben reintroducirse ni como archivos nuevos ni como import paths “temporales”.

## Dependencias entre Capas

```
web / entrypoints → application → domain ← adapters ← infrastructure
                                   ↑
                              (solo puertos)
```

**Regla:** las dependencias apuntan hacia el dominio. Los handlers web y los entrypoints deben limitarse a validar entrada, resolver dependencias y delegar en casos de uso.

## ADR-001: TinyDB + TinyFlux

- **Decisión:** mantener TinyDB + TinyFlux en la fase actual.
- **Razón:** el volumen y la topología de despliegue siguen siendo de instancia única.
- **Revisitar:** cuando se necesite concurrencia real, backups operativos más sólidos o histórico de mayor escala.

## ADR-002: Scoring en Domain Service

- El scoring pertenece al dominio y ya vive en `src/domain/services/scoring_service.py`.
- **Trabajo pendiente:** eliminar duplicación de ranking en `src/application/fetch_top_videos_use_case.py` y `src/entrypoints/fetch_data.py` para que el servicio de dominio sea la única fuente de verdad.

## ADR-003: Commit Messages

- Formato: `type(scope): description`.
- Evitar mensajes genéricos o context-free.

## Deuda Actual Prioritaria

1. **Web main demasiado denso**: `src/web/main.py` sigue concentrando callbacks OAuth, setup, health, metrics y parte del wiring.
2. **Duplicación de scoring**: el dominio ya tiene la lógica canónica, pero todavía no toda la aplicación la reutiliza.
3. **Despliegue monolítico**: el contenedor sigue multiplexando fetch, publish y web por `STEP`.
4. **Observabilidad local al proceso**: `/metrics` no persiste ni exporta métricas centralizadas.
5. **Convenciones de paths y runners**: cualquier cambio en entrypoints, assets o Docker debe cubrirse con smoke tests para evitar deriva entre código y documentación.

## Estructura Vigente Relevante

```
src/
├── domain/
│   ├── models.py
│   ├── ports.py
│   ├── exceptions.py
│   └── services/
│       └── scoring_service.py
├── application/
│   ├── authorize_use_case.py
│   ├── fetch_top_videos_use_case.py
│   ├── fetch_trending_use_case.py
│   └── publish_video_use_case.py
├── infrastructure/
│   ├── social/
│   ├── storage/
│   ├── video/
│   │   ├── asset_manager.py
│   │   ├── compositor.py
│   │   ├── renderer.py
│   │   └── thumbnail_generator.py
│   └── youtube/
│       ├── api_client.py
│       ├── auth_manager.py
│       ├── client.py
│       ├── downloader.py
│       ├── schemas.py
│       └── uploader.py
├── entrypoints/
│   ├── api_server.py
│   ├── fetch_data.py
│   ├── publish_vertical.py
│   ├── publish_video.py
│   └── workers/
└── web/
    ├── dependencies.py
    └── main.py
```

## Validación Mínima

Cualquier cambio arquitectural relevante debe validar:
- ✅ Import limpio de la aplicación (`python -c "import src"`)
- ✅ Linting (`ruff check src/ tests/`)
- ✅ Type checking (`ty check src/`)
- ✅ Tests relevantes del área tocada
