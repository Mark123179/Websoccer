"""Deterministic, separated material layers from one explicitly generated AI scan.

No database, asset registry or productive material is touched.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

OUT = Path("generated-artifacts/grass-study")
PATTERNS = ["Längsstreifen", "Querstreifen", "Schachbrett", "Dezente Rauten"]
TONES = ["Frisches Mittelgrün", "Sattes Dunkelgrün", "Helleres Grün", "Leicht olivgrün"]
WEAR = ["Frisch gepflegt", "Leicht bespielt", "Deutlich beansprucht"]
TARGETS = np.array([[66, 119, 46], [42, 85, 43], [88, 139, 57], [104, 119, 49]], dtype="float32")
PRESETS = {
    "A1": (0, 0, 0), "A2": (1, 0, 0), "A3": (2, 0, 0), "A4": (3, 0, 0),
    "B1": (0, 1, 0), "B2": (0, 2, 0), "B3": (0, 3, 0),
    "C1": (0, 0, 1), "C2": (0, 0, 2),
    "D1": (1, 1, 1), "D2": (2, 2, 0), "D3": (3, 3, 2),
}


def periodic(channel):
    """Periodic-plus-smooth decomposition removes scan-edge discontinuities."""
    h, w = channel.shape
    v = np.zeros_like(channel)
    v[0] = channel[-1] - channel[0]
    v[-1] = -v[0]
    edge = channel[:, -1] - channel[:, 0]
    v[:, 0] += edge
    v[:, -1] -= edge
    denominator = 2 * np.cos(2 * np.pi * np.arange(h)[:, None] / h)
    denominator = denominator + 2 * np.cos(2 * np.pi * np.arange(w)[None, :] / w) - 4
    denominator[0, 0] = 1
    smooth = np.fft.fft2(v) / denominator
    smooth[0, 0] = 0
    return channel - np.fft.ifft2(smooth).real


def main():
    for directory in ["layers", "textures", "top", "renders"]:
        (OUT / directory).mkdir(parents=True, exist_ok=True)
    source_path = OUT / "grass-ai-base.png"
    source = np.asarray(Image.open(source_path).convert("RGB"), dtype=np.float32) / 255
    # Remove generated broad illumination, retain the actual generated grass detail.
    light = gaussian_filter(source, (35, 35, 0), mode="reflect")
    detail = np.clip(source / np.maximum(light, .04), .60, 1.50)
    detail = np.stack([periodic(detail[:, :, c]) for c in range(3)], axis=-1)
    detail /= detail.mean(axis=(0, 1))
    detail = detail.astype("float32")
    tile = (np.clip(detail * np.array([66, 119, 46]), 0, 255)).astype("uint8")
    Image.fromarray(tile).save(OUT / "layers/ai-detail-seamless.png")
    width, height = 3150, 2040
    x = (np.arange(width, dtype=np.float32) + .5)[None, :] / 30 - 52.5
    y = (np.arange(height, dtype=np.float32) + .5)[:, None] / 30 - 34
    xx, yy = np.broadcast_arrays(x, y)
    noise = np.random.default_rng(261026).normal(size=(height, width)).astype("float32")
    broad = gaussian_filter(noise, 35)
    broad /= max(float(broad.std()), 1e-6)
    grain = np.clip(.92 + noise * .08, .5, 1.25)
    def sample(a, b):
        coords = [((b / 8) % 1) * (detail.shape[0] - 1),
                  ((a / 8) % 1) * (detail.shape[1] - 1)]
        return np.stack([map_coordinates(detail[:, :, c], coords, order=1, mode="wrap")
                         for c in range(3)], axis=-1)
    forward = sample(xx, yy)
    reverse = sample(-xx, -yy)
    secondary = sample(yy * .421 + 1.23, -xx * .421 + 2.14)
    def wave(value):
        return np.tanh(4.5 * np.sin(np.pi * value))
    patterns = [
        np.broadcast_to(wave((y + 34) / 8.5), (height, width)),
        np.broadcast_to(wave((x + 52.5) / 7.5), (height, width)),
        wave((x + 52.5) / 7.5) * wave((y + 34) / 8.5),
        wave((x + y) / (7.5 * 1.4142)) * wave((x - y) / (7.5 * 1.4142)),
    ]
    def gauss(cx, cy, sx, sy):
        return np.exp(-.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))
    goal = gauss(-49.3, 0, 2.7, 4.3) + gauss(49.3, 0, 2.7, 4.3)
    boxes = gauss(-43, 0, 5, 9) + gauss(43, 0, 5, 9)
    center = gauss(0, 0, 7, 7)
    lanes = sum(np.exp(-.5 * ((y - cy) / 1.5) ** 2) for cy in [-12, 0, 12])
    lanes = lanes * np.exp(-.5 * (x / 35) ** 6) * .1
    matte = np.clip((goal * .9 + boxes * .20 + center * .35 + lanes) *
                    np.clip(.90 + broad * .15, .25, 1.3), 0, 1)
    # Bare-earth contact only in goalmouths; no random brown spill across the field.
    clumps = gaussian_filter(noise, 6)
    clumps /= max(float(clumps.std()), 1e-6)
    earth = np.clip(goal * np.clip(.95 + .32 * clumps, .15, 1.45) - .10, 0, .95)
    masks = np.stack([matte, earth, np.broadcast_to(lanes, matte.shape)], axis=-1)
    Image.fromarray((masks * 255).astype("uint8")).save(OUT / "layers/wear-field-rgb.png")
    variants = []
    for id_, (pattern, tone, wear) in PRESETS.items():
        p = patterns[pattern]
        Image.fromarray(((p * .5 + .5) * 255).astype("uint8")).save(
            OUT / f"layers/mow-{pattern + 1}.png")
        mix = ((1 - p) * .5)[:, :, None]
        grass = (.6 * (forward * (1 - mix) + reverse * mix) + .4 * secondary)
        grass *= (1 + .012 * broad[:, :, None])
        amplitude = [.075, .075, .065, .042][pattern]
        compression = matte * [0, .40, .85][wear]
        field = grass * TARGETS[tone] * (1 + amplitude * p *
                                          (1 - .8 * compression))[:, :, None]
        faded = field * [1.46, 1.04, .67]
        field = field * (1 - compression[:, :, None]) + faded * compression[:, :, None]
        bare = earth * [0, 0, .90][wear]
        field = field * (1 - bare[:, :, None]) + (
            np.array([119, 105, 67]) * grass) * bare[:, :, None]
        image = Image.fromarray(np.clip(field, 0, 255).astype("uint8"))
        image.save(OUT / f"textures/{id_}.webp", quality=94, method=5)
        image.resize((1260, 816), Image.Resampling.LANCZOS).save(OUT / f"top/{id_}.png")
        variants.append(dict(id=id_, pattern=pattern + 1, tone=tone + 1, wear=wear + 1,
            patternLabel=PATTERNS[pattern], toneLabel=TONES[tone], wearLabel=WEAR[wear],
            group=("Mähmuster" if id_.startswith("A") else "Grüntöne" if id_.startswith("B")
                   else "Abnutzung" if id_.startswith("C") else "Kombinationen"),
            albedoMean=np.asarray(image).mean(axis=(0, 1)).round(2).tolist(),
            texture=f"textures/{id_}.webp"))
        print(id_, "generated", flush=True)
    manifest = dict(schema="blueprint.grass-material-study", version=1,
        generatedBaseSha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        pitchMetres=[105, 68], pixelsPerMetre=30, textureSize=[width, height],
        uv="u=(52.5-worldX)/105, v=(worldZ+34)/68; image top is +34m",
        colourSpace="sRGB albedo; renderer decodes to linear before lighting; wear mask is data",
        productionChanged=False, variants=variants,
        layers=dict(detail="layers/ai-detail-seamless.png", mow="layers/mow-{1..4}.png",
                    wear="layers/wear-field-rgb.png", wearChannels="R=compressed grass; G=goalmouth earth; B=running lanes"),
        recipe=dict(mowContrast=[.075, .075, .065, .042], toneRgb=TARGETS.tolist(),
                    wearMatte=[0, .40, .85], wearEarth=[0, 0, .90], seed=261026))
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
