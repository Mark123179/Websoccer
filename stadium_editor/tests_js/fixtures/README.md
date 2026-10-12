# Unity ground renderer regression

Run `npm run test:stadium-ground` from the workspace root. The normal
`npm test` wildcard also includes this check.

Requires the existing `playwright-core` dependency and Chromium at
`/repl/tools/bin/chromium`, or an executable supplied via `CHROMIUM_PATH`.
Missing Chromium or WebGL is a failure, not a skipped/passing check.

The test starts its own temporary HTTP server and runs the **unmodified**
`mountUnityStadium` loader and Three.js WebGL renderer under SwiftShader.
It creates a small geometry buffer and two tiny SVG textures in memory;
no real arena assets, external services, authentication or database are used.
The HTML harness renders the fixture on a 256×128 canvas; assertions read
pixels from a render target rather than relying on screenshot timing.

Checks:

- Fully transparent carrier texels leave the grass unchanged.
- Texels below `alphaTest` leave the grass unchanged.
- Half-transparent and solid white markings remain visible, at distinct
  brightness levels.
- Transparent materials disable depth writes; an isolated, controlled-order
  depth probe verifies the actual GPU depth behavior.
- All eight world-UV coefficients produce independently specified values,
  including nonzero, varying Y coordinates. Rendered color quadrants also
  confirm the projection reaches the shader instead of mirrored source UVs.
- Without optional fields, materials stay opaque, depth-writing and
  alpha-test-free, with original UVs and the original visible carrier.

The probe temporarily forces the marker into the opaque render queue solely
to isolate depth writing from Three.js transparent-object sorting, restoring
it afterwards. The main transparency checks use the normal renderer settings.
Comparisons are same-scene pixel comparisons and wide color/brightness
bounds, not machine-specific full-image golden baselines.
