"""
Video processing infrastructure layer (Phase 4 C1 - In Progress).

This package will eventually split responsibilities from src/video_processing.py:

PLANNED MODULES:
1. video_renderer.py       - Text overlays, TextClip generation, template rendering
2. video_compositor.py     - Clip composition, transitions, video assembly
3. thumbnail_generator.py  - Thumbnail grid creation (2x2 composite)
4. asset_manager.py        - File management, rendering to disk, cleanup

MIGRATION STRATEGY:
Phase 1: Extract VideoAssetManager (lowest coupling) ← START HERE
Phase 2: Extract VideoRenderer (text overlay logic)
Phase 3: Extract ThumbnailGenerator (uses asset_manager)
Phase 4: Extract VideoCompositor (orchestrates all above)
Final:   VideoProcessing → thin facade or deprecate

STATUS: Placeholder created for Phase 4 continuation.
"""

__all__ = []  # Modules to be added as extraction proceeds
