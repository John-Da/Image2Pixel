# Image2Pixel Studio

A small desktop GUI for converting regular images into **pixel-art style images**.
Built with **Flet**, **Pillow**, and **NumPy**, Image2Pixel Studio implements the pixelation pipeline from scratch:

**Downsample → Palette Reduction → Dithering → Nearest-Neighbor Upscale**

The goal is to provide a simple, visual way to experiment with different pixel-art styles, palettes, dithering techniques, and image-processing settings without relying on a dedicated pixel-art conversion library.

## Features

* 🖼️ Load individual images or entire folders
* 📁 Browse images through a folder-based file tree
* 🎨 Multiple palette modes
* 🕹️ Preset retro palettes
* 🌈 Adaptive image-based palettes
* 🖌️ Palette transfer between images
* ✨ Floyd-Steinberg and Bayer dithering
* 🔲 Edge-aware downsampling
* 🎚️ Adjustable pixel size and color count
* 👀 Original / pixelated comparison view
* ▶️ Navigate and play through loaded images
* 💾 Export individual images or batches as PNG
* 📂 Preserve folder structure when exporting folders
* 🪟 Native desktop file and folder dialogs
* 🧊 Preserve transparency / alpha channels

---

## How It Works

Image2Pixel Studio follows a simple image-processing pipeline:

```text
Original Image
      │
      ▼
┌─────────────────────┐
│   Downsampling      │
│                     │
│ Edge-aware /        │
│ Bilinear            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Palette Reduction   │
│                     │
│ Preset / Adaptive / │
│ Transfer            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│     Dithering       │
│                     │
│ None / Floyd-       │
│ Steinberg / Bayer   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Nearest-Neighbor    │
│ Upscaling           │
└──────────┬──────────┘
           │
           ▼
      Pixel Art
```

The processing is implemented using **Pillow and NumPy**, without relying on an external pixel-art conversion library.

---

## Outputs

|                                                             Original                                                            |                                                                  Pixelated                                                                 |
| :-----------------------------------------------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------------------: |
| <img alt="Original Ali image" height="300" src="https://github.com/John-Da/Image2Pixel/blob/main/examples/screenshots/ali.jpg"> | <img alt="Pixelated Ali image" height="300" src="https://github.com/John-Da/Image2Pixel/blob/main/examples/screenshots/ali_pixelated.png"> |
|        <img alt="Original car image" src="https://github.com/John-Da/Image2Pixel/blob/main/examples/screenshots/car.jpg">       |        <img alt="Pixelated car image" src="https://github.com/John-Da/Image2Pixel/blob/main/examples/screenshots/car_pixelated.png">       |

---

## Installation

Clone the repository and install the dependencies:

```bash
git clone https://github.com/John-Da/Image2Pixel.git
cd Image2Pixel

pip install -r requirements.txt
```

Then start the application:

```bash
python main.py
```

### Linux

On Linux desktops, native file dialogs require `zenity`:

```bash
sudo apt-get install zenity
```

---

## Project Structure

```text
Image2Pixel/
│
├── main.py
├── image_processing.py
├── requirements.txt
├── README.md
│
└── examples/
    └── screenshots/
        ├── ali.jpg
        ├── ali_pixelated.png
        ├── car.jpg
        ├── car_pixelated.png
        ├── ui1.png
        └── ui2.png
```

### `main.py`

Contains the Flet desktop interface and application state, including:

* File and folder selection
* Image navigation
* Preview controls
* Processing controls
* Export controls
* Palette configuration
* UI state management

### `image_processing.py`

Contains the image-processing pipeline, including:

* Image loading
* Downsampling
* Edge-aware reduction
* Palette generation
* Color quantization
* Dithering
* Nearest-neighbor upscaling
* Alpha-channel handling

---

# Interface

The application is divided into two main areas.

## Left Sidebar

The sidebar contains the image management and processing controls.

### File Tree

The top section contains an expandable file tree grouped by source folder.

You can:

* Browse loaded images
* Select individual images
* Select entire folders
* Preview an image by clicking it
* Check images/folders for export
* Remove images or folders from the application

Removing an item only removes it from the application. **The original files are not deleted from disk.**

The file tree also has its own card background to visually separate it from the processing controls.

### Processing Controls

The lower section contains:

* **Images** — add individual image files
* **Folder** — add an entire folder
* **Palette Mode**
* **Art Style / palette controls**
* **Color count**
* **Edge-aware downsampling**
* **Dithering**
* **Pixel size**
* **Show original**
* **Reset**
* **Process Images**

---

## Right Panel

The right side is used for image preview and playback.

### Preview

The current image is displayed in the center.

When **Show Original** is enabled, the interface switches to a two-pane comparison:

```text
┌──────────────────┬──────────────────┐
│     Original     │    Pixelated     │
│                  │                  │
│                  │                  │
└──────────────────┴──────────────────┘
```

Even before an image has been processed, the two-pane layout remains visible. In that case, the original image is displayed on both sides until processing is performed.

### Navigation

The bottom-left controls provide:

* Previous
* Play / Pause
* Next

The top-right displays the current position:

```text
3 / 12
```

### Export

The bottom-right contains:

**Save PNG(s)**

This can export either the currently displayed image or selected images/folders.

---

# Loading Images

## Images

The **Images** button opens a native multi-select file dialog.

Multiple image files can be selected at once.

The picker is filtered to supported image formats.

## Folder

The **Folder** button allows an entire folder to be loaded.

Images inside the selected folder and its nested directories are discovered and loaded as a sequence.

For example:

```text
MyImages/
├── characters/
│   ├── hero.png
│   └── enemy.png
│
├── environments/
│   ├── forest.jpg
│   └── desert.jpg
│
└── menu.png
```

The application displays the folder structure in the file tree and allows the entire folder or an individual subfolder to be removed from the application.

---

# Processing

After loading images, configure the desired processing settings and click:

**Process Images**

The selected settings are applied to every loaded image.

Processing is intentionally explicit.

Changing a setting does **not** immediately re-process the images.

For example, moving the pixel-size slider does not cause the preview to suddenly revert to the original image. Instead, the current processed result remains visible until **Process Images** is clicked again.

This makes it easier to experiment with settings without constantly reprocessing the entire image set.

---

# Palette Modes

The palette dropdown controls how colors are selected during processing.

## Preset

Uses one of five predefined palettes:

* **Retro**
* **Y2K**
* **Game Boy**
* **Arcade**
* **Vaporwave**

These palettes provide consistent, stylized color schemes that can be useful for experimenting with different pixel-art aesthetics.

---

## Adaptive

Adaptive mode generates a palette specifically for the image being processed.

The application uses Pillow's `MAXCOVERAGE` color quantization to identify a small set of representative colors from the source image.

The **Colors** slider controls the number of colors in the resulting palette.

For example:

```text
Original Image
      │
      ▼
Analyze colors
      │
      ▼
Generate palette
      │
      ▼
Map pixels to palette
```

This is useful when you want the pixelated result to retain the overall color characteristics of the original image.

---

## Transfer

Transfer mode allows the palette from one image to be applied to another.

First, select an image in the tree and choose:

**Use current image as palette source**

The application fits a palette to that image.

You can then switch other images to **Transfer** mode and process them.

Instead of generating an independent palette for each image, those images are quantized against the palette extracted from the selected source image.

This can be useful for creating a more consistent visual style across multiple images.

```text
Palette Source
      │
      ▼
Extract Palette
      │
      ├──────────────┐
      ▼              ▼
 Image A          Image B
      │              │
      └──────┬───────┘
             ▼
       Shared Palette
```

---

# Dithering

Dithering controls how colors that are not directly available in the selected palette are represented.

## None

No dithering is applied.

Pixels are mapped directly to the nearest palette color.

This is the fastest option and generally produces a clean, flat, **8-bit-style** appearance.

## Floyd-Steinberg

Uses Pillow's built-in **Floyd-Steinberg error-diffusion dithering**.

Instead of simply replacing a color, the quantization error is distributed to neighboring pixels.

This can produce smoother-looking gradients when working with a limited palette.

## Bayer

Uses a hand-implemented **4×4 ordered dithering matrix**.

Pixels are adjusted using a repeating threshold pattern before being mapped to the nearest palette color.

Compared with Floyd-Steinberg, Bayer dithering is cheaper and produces a more regular, patterned appearance that can work particularly well for retro-style graphics.

Dithering is supported across all three palette modes:

```text
Preset
Adaptive    ──► Dithering
Transfer
```

---

# Edge-Aware Downsampling

The **Edge-aware downsampling** option controls how the original image is reduced before palette mapping.

It is enabled by default.

## Enabled

A Sobel gradient-magnitude map is calculated for each image tile.

When a tile contains a strong edge, the algorithm attempts to preserve the color of the edge pixel instead of simply averaging the entire tile.

This helps preserve:

* Silhouettes
* Object boundaries
* High-contrast edges
* Small structural details

Conceptually:

```text
Normal Downsampling

████████████
████████████
████████████
      ↓
   Average
      ↓
   Blurred


Edge-Aware

███████░░░░░
███████░░░░░
███████░░░░░
      ↓
 Detect Edge
      ↓
 Preserve Boundary
```

The approach is similar in spirit to gradient-based tile reduction used by tools such as Pyxelate, but the implementation here is independent and does not use `scikit-image`.

## Disabled

The application falls back to a standard **bilinear resize** before palette mapping.

This produces a simpler and faster processing path.

---

# Pixel Size

The pixel-size control determines how aggressively the source image is reduced before being enlarged again.

The basic idea is:

```text
Original
   │
   ▼
Small Image
   │
   ▼
Palette Reduction
   │
   ▼
Nearest-Neighbor
   │
   ▼
Pixel Art
```

A smaller intermediate image produces larger, more noticeable pixels.

A larger intermediate image preserves more detail.

---

# Reset vs. Processing

The **Reset** button restores the processing settings to their default values and returns the previews to the original images.

It does **not** remove loaded images or folders.

For example:

```text
Loaded Images
     │
     ├── Image A
     ├── Image B
     └── Image C
          │
          ▼
        Reset
          │
          ▼
Images remain loaded
Processing settings reset
Preview returns to originals
```

This is intentionally different from removing images from the project.

---

# Exporting

Select one or more images or folders in the file tree and click:

**Save PNG(s)**

A native Save dialog is then used to select the destination.

### No Selection

If nothing is checked, the currently previewed image is exported to the selected filename.

### Selected Images

Checked images are exported as individual PNG files.

### Selected Folders

When a folder is selected, the application exports its images while preserving the source folder and nested directory structure.

Output files use the following naming convention:

```text
original.png
      ↓
original_pixelated.png
```

For example:

```text
MyImages/
├── characters/
│   ├── hero.png
│   └── enemy.png
│
└── environments/
    └── forest.jpg
```

can become:

```text
Export/
└── MyImages/
    ├── characters/
    │   ├── hero_pixelated.png
    │   └── enemy_pixelated.png
    │
    └── environments/
        └── forest_pixelated.png
```

---

# Transparency

Transparent images are supported.

The alpha channel is preserved during processing and when the resulting image is exported as PNG.

This allows images containing transparent backgrounds, sprites, icons, and other assets to be pixelated without losing their transparency.

---

# Native Desktop Application

Image2Pixel Studio runs as a native Flet desktop application rather than as a browser-based web application.

File selection uses the platform's native dialogs where supported.

Images selected through the file picker are read from the picker-provided data, while images discovered inside folders are read directly from their local file paths.

---

# App Preview

### Main Interface

<img alt="Image2Pixel Studio interface" src="https://github.com/John-Da/Image2Pixel/blob/main/examples/screenshots/ui1.png">

### Processing / Preview

<img alt="Image2Pixel Studio preview" src="https://github.com/John-Da/Image2Pixel/blob/main/examples/screenshots/ui2.png">

---

# Tech Stack

| Technology          | Purpose                                               |
| ------------------- | ----------------------------------------------------- |
| **Python**          | Application and processing logic                      |
| **Flet**            | Desktop GUI                                           |
| **Pillow**          | Image loading, resizing, quantization, and PNG export |
| **NumPy**           | Numerical image processing and pixel operations       |
| **Sobel Operator**  | Edge detection for edge-aware downsampling            |
| **Floyd-Steinberg** | Error-diffusion dithering                             |
| **Bayer Matrix**    | Ordered dithering                                     |

---

# Design Goals

Image2Pixel Studio was built around a few simple goals:

1. **Keep the interface simple**
   Image processing should be controlled visually rather than through command-line arguments.

2. **Keep the processing understandable**
   The core pixelation pipeline is intentionally built from relatively simple image-processing operations.

3. **Experiment with pixel-art techniques**
   Palette selection, dithering, downsampling, and pixel size can be changed independently.

4. **Support batch workflows**
   Images and entire directory structures can be processed and exported together.

5. **Avoid unnecessary dependencies**
   The core image-processing implementation relies primarily on Pillow and NumPy.

---

# License

See the repository's [license file](https://github.com/John-Da/Image2Pixel/blob/main/LICENSE) for the current licensing terms.
