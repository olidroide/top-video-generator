---
name: video-processing-migration
description: "Video processing migration (C1 split): guidelines for decomposing src/video_processing.py into src/infrastructure/video/. Triggers on: video_processing, VideoAssetManager, VideoRenderer, ThumbnailGenerator, VideoCompositor, moviepy, CompositeVideoClip, PIL Image."
compatibility: "Python 3.12+, moviepy 1.0+, Pillow 10+, segno (QR codes). Integration tests require @pytest.mark.slow. Media pipeline not testable in bare CI without Docker."
---

# Video Processing Migration (C1 Split)

## Context

`src/video_processing.py` (22KB, 900 lines) is being split into `src/infrastructure/video/` as part of Phase 4 hexagonal architecture refactoring.

**Critical**: DO NOT add new code to `src/video_processing.py`. All new video logic goes into the target modules in `infrastructure/video/`.

---

## Target Structure

```
src/infrastructure/video/
├── asset_manager.py          # VideoAssetManager — file paths, render to disk, cleanup
├── renderer.py               # VideoRenderer — text overlays, TextClip, template rendering
├── thumbnail.py              # ThumbnailGenerator — 2x2 grid composite (Pillow)
└── compositor.py             # VideoCompositor — final assembly, crossfade, encode
```

---

## Migration Order (MANDATORY — do not skip or reorder)

1. **asset_manager.py FIRST** (lowest coupling, no moviepy imports)
   - Methods: `_get_asset_path()`, `_render_font_to_disk()`, `cleanup_temp_assets()`
   - No dependencies on other video classes

2. **renderer.py** (depends on asset_manager)
   - Methods: `render_text_clip()`, `apply_transitions()`, etc.
   - Depends on: `VideoAssetManager`

3. **thumbnail.py** (depends on asset_manager)
   - Methods: `generate_thumbnail_grid()` (2x2 Pillow composite)
   - Depends on: `VideoAssetManager`

4. **compositor.py LAST** (orchestrates all above)
   - Methods: `assemble_final_clip()`, `crossfade_videos()`, `encode_mp4()`
   - Depends on: VideoAssetManager, VideoRenderer, ThumbnailGenerator

---

## Pre-Migration: Write Characterization Tests

**Before moving ANY class**, write a test that documents current behavior:

```python
# tests/integration/video/test_video_processing_current.py
import pytest
from pathlib import Path
from src.video_processing import VideoProcessing

@pytest.mark.slow
class TestVideoProcessingCharacterization:
    """Characterization tests — document behavior before refactor.
    These tests MUST pass before migration and PASS after each migration step.
    """

    def test_asset_manager_get_asset_path(self, tmp_path: Path) -> None:
        """Document current VideoProcessing.asset_manager.get_asset_path behavior."""
        vp = VideoProcessing()
        path = vp._get_asset_path("fonts/Roboto-Bold.ttf")
        # This test captures the CURRENT behavior
        assert path.exists() or path.parent.exists()

    def test_renderer_render_text_clip(self, tmp_path: Path) -> None:
        """Document current VideoProcessing.render_text_clip behavior."""
        from moviepy.editor import CompositeVideoClip
        vp = VideoProcessing()
        clip = vp.render_text_clip(text="Hello", duration=5.0, fontsize=40)
        assert isinstance(clip, CompositeVideoClip)
        assert clip.duration == 5.0

    def test_thumbnail_generator_grid(self, tmp_path: Path) -> None:
        """Document current VideoProcessing.generate_thumbnail_grid behavior."""
        from PIL import Image
        vp = VideoProcessing()
        images = [Image.new("RGB", (320, 180)) for _ in range(4)]
        grid = vp.generate_thumbnail_grid(images)
        assert isinstance(grid, Image.Image)
        assert grid.size == (640, 360)  # 2x2 grid of 320x180

    def test_compositor_assemble_final(self, tmp_path: Path) -> None:
        """Document current VideoProcessing.assemble_final_clip behavior."""
        from moviepy.editor import VideoFileClip
        vp = VideoProcessing()
        # Create minimal test clip (this is expensive, mark @pytest.mark.slow)
        result = vp.assemble_final_clip(video_list=[], ...)
        assert isinstance(result, VideoFileClip) or isinstance(result, bytes)
```

**Run test suite before migration**:
```bash
uv run pytest tests/integration/video/test_video_processing_current.py -m slow -v
```

---

## Per-Class Migration Pattern

### Step 1: Extract the Class

```python
# src/infrastructure/video/asset_manager.py
from pathlib import Path
from typing import Optional

class VideoAssetManager:
    """Manages file paths, font rendering, and cleanup for video production."""

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path("src/resources")

    def get_asset_path(self, asset_name: str) -> Path:
        """Return path to asset (fonts, images, etc.)"""
        return self.base_path / asset_name

    def render_font_to_disk(self, font_name: str) -> Path:
        """Render or fetch font, return local path."""
        ...

    def cleanup_temp_assets(self) -> None:
        """Remove temporary files from video generation."""
        ...
```

### Step 2: Add Shim Re-export to `src/video_processing.py`

```python
# src/video_processing.py
import warnings
from src.infrastructure.video.asset_manager import VideoAssetManager as _VideoAssetManager


# DEPRECATED — use src.infrastructure.video.asset_manager directly
class VideoAssetManager(_VideoAssetManager):
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "VideoAssetManager moved to src.infrastructure.video.asset_manager — "
            "update imports",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
```

### Step 3: Write Integration Test for Migrated Class

```python
# tests/integration/video/test_asset_manager.py
from pathlib import Path
from src.infrastructure.video.asset_manager import VideoAssetManager

def test_asset_manager_after_migration(tmp_path: Path) -> None:
    """Test VideoAssetManager after extraction."""
    mgr = VideoAssetManager(base_path=tmp_path)
    path = mgr.get_asset_path("test.ttf")
    assert path.parent == tmp_path
```

### Step 4: Commit

```bash
git add src/infrastructure/video/asset_manager.py tests/integration/video/test_asset_manager.py src/video_processing.py
git commit -m "refactor(video): extract VideoAssetManager to infrastructure/video/

- Move asset path logic to VideoAssetManager class
- Add deprecation shim in video_processing.py for backward compat
- Write integration test (tests/integration/video/test_asset_manager.py)
- Verify characterization tests still pass"
```

### Step 5: Verify Characterization Tests Pass

```bash
uv run pytest tests/integration/video/test_video_processing_current.py -v -m slow
```

---

## Anti-Patterns During Migration

❌ **Do NOT**:
- Refactor *multiple* classes in one commit (one class per commit)
- Remove shims from `src/video_processing.py` until all 4 classes migrated + tests passing
- Touch `src/video_processing.py` logic during migration (only add shims, never edit existing)
- Write new video code in `src/video_processing.py` while migration is in progress

✅ **DO**:
- Keep characterization tests running throughout
- Commit after each class migration with passing tests
- Use `git log --oneline` to track migration progress (should see 4 commits: asset_manager, renderer, thumbnail, compositor)
- Run full test suite after each commit: `uv run pytest tests/ -m "not slow" && uv run pytest tests/integration/video/ -m slow`

---

## Final Cleanup (After All 4 Classes Migrated)

Once all classes migrated and all tests passing:

1. Remove shims from `src/video_processing.py`:
   ```bash
   git rm src/video_processing.py
   ```

2. Validate no broken imports:
   ```bash
   uv run ruff check src/ --select F401  # No unused imports
   python -c "from src.infrastructure.video import *; print('✅ imports OK')"
   ```

3. Final commit:
   ```bash
   git commit -m "chore(video): remove video_processing.py — migration complete

   - All video logic now in infrastructure/video/
   - Shims removed
   - Integration tests verify all behavior preserved"
   ```

---

## Reference: Expected Method Breakdown

From `video_processing.py` (11 methods across 900 lines):

| Class | Methods | Dependencies |
|-------|---------|--------------|
| **VideoAssetManager** | `_get_asset_path()`, `_render_font_to_disk()`, `cleanup_temp_assets()` | None (stdlib + pathlib) |
| **VideoRenderer** | `render_text_clip()`, `apply_transitions()` | VideoAssetManager, moviepy |
| **ThumbnailGenerator** | `generate_thumbnail_grid()` | VideoAssetManager, PIL |
| **VideoCompositor** | `assemble_final_clip()`, `crossfade_videos()`, `encode_mp4()`, final orchestration | All above, moviepy, ffmpeg |

---

## moviepy File Handle Safety

moviepy 1.x does not always close ffmpeg handles automatically. Use context managers wherever the migrated code opens clips:

```python
# Correct — handle closed on exit
with VideoFileClip(file_path) as clip:
    result = clip.subclip(0, 10)

# Avoid — handle may leak if an exception is raised
clip = VideoFileClip(file_path)
result = clip.subclip(0, 10)
```

In `cleanup_temp_assets()` call `clip.close()` explicitly if a context manager cannot be used.

---

## Testing Strategy

- **Characterization tests** (before): *Document* current behavior
- **Unit tests** (during): Mock moviepy/PIL for fast testing
- **Integration tests** (after): Real moviepy/PIL, mark `@pytest.mark.slow`
- **No `@pytest.mark.skip`**: If migration breaks test, FIX the migration, don't skip

---

## See Also

- `.github/copilot-instructions.md` — Phase 4 architecture overview
- `src/infrastructure/video/__init__.py` — Phase documentation
- `tests/integration/video/` — Integration test patterns
- `hexagonal-architecture-video-publish` skill — General adapter patterns
