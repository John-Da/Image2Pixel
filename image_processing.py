from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageOps

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"}

# ---------------------------------------------------------------------------
# Palette modes
# ---------------------------------------------------------------------------
PALETTE_MODE_PRESET = "preset"
PALETTE_MODE_ADAPTIVE = (
    "adaptive"
)
PALETTE_MODE_TRANSFER = (
    "transfer"
)

DITHER_NONE = "none"
DITHER_FLOYD = "floyd"  # Floyd-Steinberg, via Pillow
DITHER_BAYER = "bayer"  # 4x4 ordered dithering, hand-rolled

ART_PALETTES: dict[str, tuple[tuple[int, int, int], ...]] = {
    "Retro": (
        (20, 12, 28),
        (68, 36, 52),
        (48, 52, 109),
        (78, 74, 78),
        (133, 76, 48),
        (52, 101, 36),
        (208, 70, 72),
        (117, 113, 97),
        (89, 125, 206),
        (210, 125, 44),
        (133, 149, 161),
        (109, 170, 44),
        (210, 170, 153),
        (109, 194, 202),
        (218, 212, 94),
        (222, 238, 214),
    ),
    "Y2K": (
        (15, 12, 40),
        (45, 26, 91),
        (91, 44, 147),
        (177, 48, 190),
        (245, 77, 190),
        (255, 142, 210),
        (41, 196, 220),
        (78, 238, 237),
        (146, 247, 238),
        (231, 236, 255),
        (126, 142, 194),
        (65, 78, 122),
    ),
    "Game Boy": (
        (15, 56, 15),
        (48, 98, 48),
        (139, 172, 15),
        (155, 188, 15),
    ),
    "Arcade": (
        (0, 0, 0),
        (29, 43, 83),
        (126, 37, 83),
        (0, 135, 81),
        (171, 82, 54),
        (95, 87, 79),
        (194, 195, 199),
        (255, 241, 232),
        (255, 0, 77),
        (255, 163, 0),
        (255, 236, 39),
        (0, 228, 54),
        (41, 173, 255),
        (131, 118, 156),
        (255, 119, 168),
        (255, 204, 170),
    ),
    "Vaporwave": (
        (22, 12, 51),
        (48, 24, 92),
        (93, 35, 129),
        (157, 45, 141),
        (225, 75, 156),
        (255, 131, 175),
        (255, 191, 202),
        (74, 67, 156),
        (81, 120, 199),
        (77, 190, 211),
        (157, 237, 222),
        (242, 233, 228),
    ),
}
DEFAULT_ART_STYLE = "Retro"

_BAYER_4X4 = (
    np.array(
        [
            [0, 8, 2, 10],
            [12, 4, 14, 6],
            [3, 11, 1, 9],
            [15, 7, 13, 5],
        ],
        dtype=np.float32,
    )
    / 16.0
)


@lru_cache(maxsize=len(ART_PALETTES))
def _preset_palette_image(style: str) -> Image.Image:
    try:
        colors = ART_PALETTES[style]
    except KeyError as error:
        raise ValueError(f"Unknown art style: {style}") from error
    
    palette_image = Image.new("P", (len(colors), 1))
    palette_image.putdata(list(range(len(colors))))
    palette = [channel for color in colors for channel in color]
    palette.extend([0] * (768 - len(palette)))
    palette_image.putpalette(palette)
    return palette_image


# ---------------------------------------------------------------------------
# Adaptive / learned palettes  (Pyxelate: fit() learns a palette from the image)
# ---------------------------------------------------------------------------
def fit_palette(image: Image.Image, n_colors: int = 16) -> Image.Image:
    n_colors = max(2, min(256, n_colors))
    rgb = image.convert("RGB")
    return rgb.quantize(colors=n_colors, method=Image.Quantize.MAXCOVERAGE)


def _palette_rgb_colors(palette_img: Image.Image) -> np.ndarray:
    """Extract the actual (used) RGB colors out of a P-mode palette image."""
    pal = palette_img.getpalette()
    if not pal:
        arr = np.asarray(palette_img.convert("RGB")).reshape(-1, 3)
        return np.unique(arr, axis=0).astype(np.float32)

    colors = np.array(pal, dtype=np.float32).reshape(-1, 3)
    used_indices = np.unique(np.asarray(palette_img))
    used_indices = used_indices[used_indices < len(colors)]
    if used_indices.size == 0:
        return colors
    return colors[used_indices]


# ---------------------------------------------------------------------------
# Edge-aware downsampling
# ---------------------------------------------------------------------------
def _sobel_magnitude(gray: np.ndarray) -> np.ndarray:
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    ky = kx.T
    padded = np.pad(gray, 1, mode="edge")
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    for dy in range(3):
        for dx in range(3):
            kxv, kyv = kx[dy, dx], ky[dy, dx]
            if kxv == 0 and kyv == 0:
                continue
            shifted = padded[dy : dy + gray.shape[0], dx : dx + gray.shape[1]]
            if kxv:
                gx += kxv * shifted
            if kyv:
                gy += kyv * shifted
    return np.sqrt(gx * gx + gy * gy)


def edge_aware_downsample(rgb_img: Image.Image, pixel_size: int) -> Image.Image:
    if pixel_size <= 1:
        return rgb_img.copy()

    arr = np.asarray(rgb_img, dtype=np.float32)
    h, w, _ = arr.shape
    new_h = max(1, h // pixel_size)
    new_w = max(1, w // pixel_size)
    crop_h, crop_w = new_h * pixel_size, new_w * pixel_size
    if crop_h == 0 or crop_w == 0:
        return rgb_img.resize(
            (new_w or 1, new_h or 1), resample=Image.Resampling.BILINEAR
        )

    cropped = arr[:crop_h, :crop_w]
    gray = cropped.mean(axis=2)
    edges = _sobel_magnitude(gray)

    tiles = cropped.reshape(new_h, pixel_size, new_w, pixel_size, 3)
    tiles = tiles.transpose(0, 2, 1, 3, 4).reshape(
        new_h, new_w, pixel_size * pixel_size, 3
    )
    tile_edges = edges.reshape(new_h, pixel_size, new_w, pixel_size)
    tile_edges = tile_edges.transpose(0, 2, 1, 3).reshape(
        new_h, new_w, pixel_size * pixel_size
    )

    avg_color = tiles.mean(axis=2)
    max_edge = tile_edges.max(axis=2)
    mean_edge = tile_edges.mean(axis=2)
    strong = max_edge > (mean_edge * 1.8 + 1e-3)

    argmax_idx = tile_edges.argmax(axis=2)
    idx_h, idx_w = np.meshgrid(np.arange(new_h), np.arange(new_w), indexing="ij")
    edge_color = tiles[idx_h, idx_w, argmax_idx]

    result = np.where(strong[..., None], edge_color, avg_color)
    result = np.clip(result, 0, 255).astype(np.uint8)
    return Image.fromarray(result, mode="RGB")


# ---------------------------------------------------------------------------
# Dithering
# ---------------------------------------------------------------------------
def _bayer_dither_quantize(
    rgb_arr: np.ndarray, palette_colors: np.ndarray
) -> np.ndarray:
    """Ordered (Bayer) dithering: jitter pixels by a repeating threshold
    matrix *before* nearest-palette matching, then map every pixel to its
    nearest palette color. Cheap and fast, unlike error-diffusion methods.
    """
    h, w, _ = rgb_arr.shape
    tiles_y = h // 4 + 1
    tiles_x = w // 4 + 1
    bayer = np.tile(_BAYER_4X4, (tiles_y, tiles_x))[:h, :w]
    amplitude = 24.0
    noise = (bayer - 0.5) * amplitude
    noisy = np.clip(rgb_arr + noise[..., None], 0, 255)

    flat = noisy.reshape(-1, 3)
    dists = ((flat[:, None, :] - palette_colors[None, :, :]) ** 2).sum(axis=2)
    idx = dists.argmin(axis=1)
    out = palette_colors[idx].reshape(h, w, 3)
    return out.astype(np.uint8)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def pixelate_image(
    img: Image.Image,
    pixel_size: int,
    palette_mode: str = PALETTE_MODE_PRESET,
    art_style: str = DEFAULT_ART_STYLE,
    n_colors: int = 16,
    transfer_palette: Optional[Image.Image] = None,
    dither_mode: str = DITHER_NONE,
    edge_aware: bool = True,
) -> Image.Image:
    
    if pixel_size < 1:
        raise ValueError("Pixel size must be at least 1")

    has_transparency = "A" in img.getbands() or "transparency" in img.info
    rgba = img.convert("RGBA") if has_transparency else None
    rgb = rgba.convert("RGB") if rgba is not None else img.convert("RGB")

    width, height = rgb.size

    if edge_aware and pixel_size > 1:
        small = edge_aware_downsample(rgb, pixel_size)
    else:
        small_size = (max(1, width // pixel_size), max(1, height // pixel_size))
        small = rgb.resize(small_size, resample=Image.Resampling.BILINEAR)
    small_size = small.size

    if palette_mode == PALETTE_MODE_ADAPTIVE:
        palette_img = fit_palette(small, n_colors)
    elif palette_mode == PALETTE_MODE_TRANSFER:
        if transfer_palette is None:
            raise ValueError("Transfer mode requires a fitted source palette")
        palette_img = transfer_palette
    else:
        palette_img = _preset_palette_image(art_style)

    if dither_mode == DITHER_BAYER:
        palette_colors = _palette_rgb_colors(palette_img)
        small_arr = np.asarray(small.convert("RGB"), dtype=np.float32)
        quantized_arr = _bayer_dither_quantize(small_arr, palette_colors)
        quantized = Image.fromarray(quantized_arr, mode="RGB")
    else:
        pil_dither = (
            Image.Dither.FLOYDSTEINBERG
            if dither_mode == DITHER_FLOYD
            else Image.Dither.NONE
        )
        quantized = small.quantize(palette=palette_img, dither=pil_dither).convert(
            "RGB"
        )

    pixelated = quantized.resize((width, height), resample=Image.Resampling.NEAREST)

    if rgba is None:
        return pixelated

    alpha = rgba.getchannel("A")
    alpha = alpha.resize(small_size, resample=Image.Resampling.BILINEAR)
    alpha = alpha.resize((width, height), resample=Image.Resampling.NEAREST)
    pixelated.putalpha(alpha)
    return pixelated


def find_images(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in IMAGE_EXTS else []
    if path.is_dir():
        return sorted(
            image
            for image in path.rglob("*")
            if image.is_file() and image.suffix.lower() in IMAGE_EXTS
        )
    return []


@dataclass
class ImageEntry:
    path: Path
    original: Optional[Image.Image] = None
    pixelated: Optional[Image.Image] = None
    error: Optional[str] = None
    image_bytes: Optional[bytes] = None
    source_root: Optional[Path] = None
    folder_import: bool = False

    def load(self) -> None:
        if self.original is None:
            source = BytesIO(self.image_bytes) if self.image_bytes else self.path
            with Image.open(source) as image:
                image.seek(0)
                oriented = ImageOps.exif_transpose(image)
                self.original = oriented.copy()

    def process(
        self,
        pixel_size: int,
        palette_mode: str = PALETTE_MODE_PRESET,
        art_style: str = DEFAULT_ART_STYLE,
        n_colors: int = 16,
        transfer_palette: Optional[Image.Image] = None,
        dither_mode: str = DITHER_NONE,
        edge_aware: bool = True,
    ) -> None:
        self.load()
        if self.original is None:
            raise OSError(f"Could not load image: {self.path}")
        self.pixelated = pixelate_image(
            self.original,
            pixel_size,
            palette_mode=palette_mode,
            art_style=art_style,
            n_colors=n_colors,
            transfer_palette=transfer_palette,
            dither_mode=dither_mode,
            edge_aware=edge_aware,
        )
        self.error = None
