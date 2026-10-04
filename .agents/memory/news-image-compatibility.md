---
name: News image compatibility
description: Apply upload restrictions to new publications without rewriting historical news.
---

New publication limits must not erase or retroactively invalidate legitimate historical news images. Keep display-time source checks separate from upload/content validation.

**Why:** The user explicitly requires published older data to remain safely visible and legitimate custom images not to be indiscriminately deleted.

**How to apply:** Keep historical records unchanged. Escape every custom image attribute and restrict its source to image-safe schemes. Legacy formats can stay in the inert image context even when new uploads allow only selected raster formats; never move them to inline SVG, object, iframe, or raw HTML contexts.