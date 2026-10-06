# Pixel Studio

A small desktop GUI (built with Flet) that turns regular images into
pixel-art style images. Inspired by the approach in
[sedthh/pyxelate](https://github.com/sedthh/pyxelate) — downscale, reduce
the color palette, upscale with nearest-neighbour — but re-implemented from
scratch using only Pillow and numpy, so there's no numba/scikit-learn/
scikit-image build step to fight with.

## Run it

```bash
pip install -r requirements.txt
python main.py
```

(On Linux desktops you also need `zenity` installed for the native file
dialogs: `sudo apt-get install zenity`.)

## Project structure

- `main.py` contains the Flet interface and app state.
- `image_processing.py` handles image discovery, loading, and pixelation
  (downsampling, palettes, dithering).

## Layout

- **Left sidebar**
  - Top: expandable file tree grouped by source folder; click an image to
    preview it, check images/folders to choose exports, or use the delete
    icon beside a file/folder to remove it from the app without deleting
    source files. The tree has a separate card background from the controls.
  - Bottom: equal-width Images and Folder buttons, palette-mode controls
    (see below), edge-aware checkbox, dithering selector, pixel-size
    slider, "show original" checkbox, and Reset / Process Images buttons
- **Right panel**
  - Top-right: `n / total` frame counter
  - Middle: the pixelated preview (and the original, side-by-side, when
    the checkbox is on — this stays a two-pane view even for an image
    that hasn't been processed yet, it just shows the raw original on
    both sides until you process it)
  - Bottom-left: prev / play-pause / next controls; bottom-right: Save PNG(s)

## Loading images

- **Images** opens a multi-select file dialog filtered to image
  files in the native desktop app. You can select one or several images.
- **Folder** lets you pick a whole folder — images in it and nested folders
  are loaded as a sequence you can page or play through. The tree shows the
  selected folder and its nested directories, so a whole folder or a
  subfolder can be removed from the app at once.
- Choose your palette mode and settings, then select **Process Images** to
  apply them to every loaded image. **Reset** restores processing settings
  to their defaults and returns previews to the originals, but keeps all
  uploaded files and folders loaded in the tree.
  Check one or more images or folders in the tree, then select **Save PNG(s)**
  and choose a save location in the native Save dialog. With no checked
  items, Save PNG(s) exports the currently previewed image to the selected
  filename. Folder exports preserve the source folder and nested directory
  structure and write separate `*_pixelated.png` files beside that save
  location.

## Palette modes

The palette-mode dropdown switches which controls show beneath it:

- **Preset** — one of five curated, fixed swatches: Retro, Y2K, Game Boy,
  Arcade, Vaporwave.
- **Adaptive** — the palette is learned from the image being processed
  (Pillow's `MAXCOVERAGE` color quantization finds a small set of colors
  that best represent that specific image). Use the "Colors" slider to
  set how many.
- **Transfer** — the palette is learned from a *different* image and
  applied here, like a simple style transfer. Select the source image in
  the tree, click "Use current image as palette source," then switch other
  images to Transfer mode and process them — they'll be quantized against
  the fitted source palette instead of their own colors.

## Dithering

- **None** — flat color mapping, no dithering (fastest, most "8-bit"
  look).
- **Floyd-Steinberg** — Pillow's built-in error-diffusion dithering.
- **Bayer** — a hand-rolled 4x4 ordered dither: pixels are jittered by a
  repeating threshold pattern before nearest-palette matching. Cheaper
  than Floyd-Steinberg and gives a more uniform, retro dot-pattern look.

Dithering works the same way across all three palette modes.

## Downsampling

The "Edge-aware downsampling" checkbox (on by default) controls how the
image is shrunk before palette mapping:

- **On** — a Sobel gradient-magnitude map is computed per tile, and tiles
  with a clear, strong edge keep that edge pixel's color instead of being
  blurred into a flat average. This preserves silhouettes and hard edges
  better than a plain resize, similar in spirit to Pyxelate's
  gradient-based tile reduction (though implemented independently, without
  scikit-image).
- **Off** — falls back to a plain bilinear resize.

## Settings vs. processing

Changing pixel size, palette mode, art style, color count, dithering, or
edge-aware settings does **not** immediately re-pixelate or clear what's
currently shown — the preview keeps displaying the last processed result
(and Save PNG(s) stays usable) until you explicitly click **Process
Images** again. This avoids the preview flashing back to the raw original
every time you nudge a slider.

## Notes / things you may want to tune

- The app runs as a native Flet desktop app and opens native file and
  folder pickers. Selected images are read from the picker-provided bytes;
  folder images are read from their local file paths.
- Transparent images keep their alpha channel when pixelated and saved.