import asyncio
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import flet as ft
from PIL import Image, UnidentifiedImageError

from image_processing import (
    ART_PALETTES,
    DEFAULT_ART_STYLE,
    DITHER_BAYER,
    DITHER_FLOYD,
    DITHER_NONE,
    IMAGE_EXTS,
    PALETTE_MODE_ADAPTIVE,
    PALETTE_MODE_PRESET,
    PALETTE_MODE_TRANSFER,
    ImageEntry,
    fit_palette,
    find_images,
)

DEFAULT_PIXEL_SIZE = 3
DEFAULT_N_COLORS = 16
PLAY_INTERVAL_SECONDS = 1.05
SIDEBAR_WIDTH = 300
SIDEBAR_PADDING = 12

PALETTE_MODE_LABELS = {
    PALETTE_MODE_PRESET: "Preset",
    PALETTE_MODE_ADAPTIVE: "Adaptive (learned from image)",
    PALETTE_MODE_TRANSFER: "Transfer (from another image)",
}
PALETTE_MODE_BY_LABEL = {label: key for key, label in PALETTE_MODE_LABELS.items()}

DITHER_LABELS = {
    DITHER_NONE: "None",
    DITHER_FLOYD: "Floyd-Steinberg",
    DITHER_BAYER: "Bayer (ordered)",
}
DITHER_BY_LABEL = {label: key for key, label in DITHER_LABELS.items()}


def pil_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@dataclass
class AppState:
    entries: list[ImageEntry] = field(default_factory=list)
    index: int = 0
    playing: bool = False
    pixel_size: int = DEFAULT_PIXEL_SIZE
    show_original: bool = False
    edge_aware: bool = True
    dither_mode: str = DITHER_NONE

    # palette
    palette_mode: str = PALETTE_MODE_PRESET
    art_style: str = DEFAULT_ART_STYLE
    n_colors: int = DEFAULT_N_COLORS
    transfer_palette: Optional[Image.Image] = None
    transfer_source_name: Optional[str] = None

    @property
    def current(self) -> Optional[ImageEntry]:
        if 0 <= self.index < len(self.entries):
            return self.entries[self.index]
        return None


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
async def main(page: ft.Page):
    page.title = "Image2Pixel Studio"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1200
    page.window.height = 800
    page.window.min_width = 900
    page.window.min_height = 600
    page.padding = 0
    page.bgcolor = ft.Colors.BLACK
    page.update()
    await page.window.center()
    page.update()

    state = AppState()
    collapsed_folders: set[tuple[Optional[Path], tuple[str, ...]]] = set()
    selected_for_save: set[int] = set()

    file_list_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=2)
    status_text = ft.Text("No images loaded", size=12, color=ft.Colors.GREY_400)

    status_container = ft.Container(
        content=ft.Column(
            controls=[status_text],
            scroll=ft.ScrollMode.AUTO,
        ),
        height=48,
    )

    frame_count_text = ft.Text("0 / 0", size=13, weight=ft.FontWeight.BOLD)

    pixelated_image = ft.Image(
        src="", fit=ft.BoxFit.CONTAIN, expand=True, border_radius=ft.BorderRadius.all(6)
    )
    original_image = ft.Image(
        src="", fit=ft.BoxFit.CONTAIN, expand=True, border_radius=ft.BorderRadius.all(6)
    )
    pixelated_label = ft.Text("Pixelated", size=12, color=ft.Colors.GREY_400)
    pixelated_col = ft.Column(
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            pixelated_label,
            pixelated_image,
        ],
    )
    original_col = ft.Column(
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        visible=False,
        controls=[
            ft.Text("Original", size=12, color=ft.Colors.GREY_400),
            original_image,
        ],
    )
    preview_row = ft.Row(
        expand=True,
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[pixelated_col, original_col],
    )

    placeholder_text = ft.Text(
        "No images loaded",
        size=16,
        weight=ft.FontWeight.BOLD,
        text_align=ft.TextAlign.CENTER,
        color=ft.Colors.GREY_300,
    )
    placeholder_container = ft.Container(
        content=placeholder_text,
        alignment=ft.Alignment.CENTER,
        padding=20,
        expand=True,
        visible=True,
    )
    preview_stack = ft.Stack(expand=True, controls=[preview_row, placeholder_container])

    # ---------------- palette mode controls ----------------
    palette_mode_dropdown = ft.Dropdown(
        label="Palette mode",
        value=PALETTE_MODE_LABELS[state.palette_mode],
        width=SIDEBAR_WIDTH - 2 * SIDEBAR_PADDING,
        options=[
            ft.dropdown.Option(key=label, text=label)
            for label in PALETTE_MODE_LABELS.values()
        ],
        on_select=lambda e: on_palette_mode_change(e),
    )
    art_style_dropdown = ft.Dropdown(
        label="Art style",
        value=state.art_style,
        width=SIDEBAR_WIDTH - 2 * SIDEBAR_PADDING,
        options=[ft.dropdown.Option(key=style, text=style) for style in ART_PALETTES],
        on_select=lambda e: on_art_style_change(e),
    )
    n_colors_label = ft.Text(f"Colors: {state.n_colors}", size=12)
    n_colors_slider = ft.Slider(
        min=2, max=64, divisions=62, value=state.n_colors, label="{value}"
    )
    transfer_status_text = ft.Text(
        "No palette source set yet.", size=12, color=ft.Colors.GREY_400
    )
    fit_source_button = ft.OutlinedButton(
        content="Use current image as palette source",
        icon=ft.Icons.COLORIZE,
        on_click=lambda e: on_fit_source(e),
    )
    palette_controls_col = ft.Column(spacing=20, controls=[])

    dither_dropdown = ft.Dropdown(
        label="Dithering",
        value=DITHER_LABELS[state.dither_mode],
        width=SIDEBAR_WIDTH - 2 * SIDEBAR_PADDING,
        options=[
            ft.dropdown.Option(key=label, text=label)
            for label in DITHER_LABELS.values()
        ],
        on_select=lambda e: on_dither_change(e),
    )
    edge_aware_checkbox = ft.Checkbox(
        label="Edge-aware downsampling",
        value=state.edge_aware,
        on_change=lambda e: on_edge_aware_change(e),
    )

    pixel_size_label = ft.Text(f"Pixel size: {state.pixel_size}", size=12)
    pixel_size_slider = ft.Slider(
        min=2, max=32, divisions=30, value=state.pixel_size, label="{value}"
    )
    pixel_size_col = ft.Column(
        spacing=10,
        controls=[
            pixel_size_label,
            pixel_size_slider,
        ],
    )

    play_pause_button = None

    def rebuild_palette_controls():
        controls = [palette_mode_dropdown]
        if state.palette_mode == PALETTE_MODE_PRESET:
            controls.append(art_style_dropdown)
        elif state.palette_mode == PALETTE_MODE_ADAPTIVE:
            controls.extend([n_colors_label, n_colors_slider])
        else:  # transfer
            controls.extend([fit_source_button, transfer_status_text])
        palette_controls_col.controls = controls

    def refresh_file_list():
        file_list_col.controls.clear()
        roots: dict[Optional[Path], dict] = {}
        for index, entry in enumerate(state.entries):
            root = entry.source_root
            root_node = roots.setdefault(root, {"folders": {}, "images": []})
            relative_path = (
                entry.path.relative_to(root)
                if root is not None
                else Path(entry.path.name)
            )
            node = root_node
            for folder_name in relative_path.parts[:-1]:
                node = node["folders"].setdefault(
                    folder_name, {"folders": {}, "images": []}
                )
            node["images"].append((index, entry))

        def folder_row(
            label: str,
            root: Optional[Path],
            folder_parts: tuple[str, ...],
            depth: int,
            image_count: int,
            node: dict,
        ):
            folder_key = (root, folder_parts)
            collapsed = folder_key in collapsed_folders
            entries = list(node_entries(node))
            selected_count = sum(id(entry) in selected_for_save for entry in entries)

            def on_folder_selection_change(e):
                select_all = e.control.value is True
                for entry in entries:
                    if select_all:
                        selected_for_save.add(id(entry))
                    else:
                        selected_for_save.discard(id(entry))
                refresh_all()

            def toggle_folder(e):
                if folder_key in collapsed_folders:
                    collapsed_folders.remove(folder_key)
                else:
                    collapsed_folders.add(folder_key)
                refresh_file_list()
                page.update()

            return ft.Row(
                spacing=2,
                controls=[
                    ft.IconButton(
                        icon=(
                            ft.Icons.CHEVRON_RIGHT
                            if collapsed
                            else ft.Icons.EXPAND_MORE
                        ),
                        icon_size=18,
                        tooltip="Expand folder" if collapsed else "Collapse folder",
                        on_click=toggle_folder,
                    ),
                    ft.Checkbox(
                        value=bool(entries) and selected_count == len(entries),
                        on_change=on_folder_selection_change,
                        tooltip="Select folder images for saving",
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.FOLDER, size=16),
                                ft.Text(
                                    label,
                                    size=12,
                                    expand=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                ),
                                ft.Text(
                                    str(image_count),
                                    size=11,
                                    color=ft.Colors.GREY_400,
                                ),
                            ],
                            spacing=6,
                        ),
                        padding=ft.Padding.symmetric(vertical=4, horizontal=4),
                        border_radius=6,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=18,
                        tooltip=f"Remove {label} and its images from the list",
                        on_click=lambda e: delete_folder(root, folder_parts),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        def append_tree_nodes(
            node: dict,
            root: Optional[Path],
            folder_parts: tuple[str, ...],
            depth: int,
        ):
            for folder_name in sorted(node["folders"], key=str.casefold):
                child_parts = folder_parts + (folder_name,)
                child = node["folders"][folder_name]
                count = count_images(child)
                folder_control = folder_row(
                    folder_name, root, child_parts, depth, count, child
                )
                folder_control.controls[0].padding = ft.Padding.only(left=depth * 14)
                file_list_col.controls.append(folder_control)
                if (root, child_parts) not in collapsed_folders:
                    append_tree_nodes(child, root, child_parts, depth + 1)

            for index, entry in node["images"]:
                selected = index == state.index
                file_list_col.controls.append(
                    ft.Row(
                        spacing=2,
                        controls=[
                            ft.Checkbox(
                                value=id(entry) in selected_for_save,
                                on_change=lambda e, image_entry=entry: toggle_entry_selection(
                                    image_entry, e.control.value
                                ),
                                tooltip="Select image for saving",
                            ),
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.IMAGE, size=16),
                                        ft.Text(
                                            entry.path.name,
                                            size=12,
                                            expand=True,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            max_lines=1,
                                        ),
                                    ],
                                    spacing=6,
                                ),
                                padding=ft.Padding.only(
                                    left=depth * 14 + 8,
                                    top=6,
                                    bottom=6,
                                    right=8,
                                ),
                                border_radius=6,
                                bgcolor=ft.Colors.BLUE_700 if selected else None,
                                ink=True,
                                expand=True,
                                on_click=lambda e, idx=index: select_frame(idx),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=18,
                                tooltip=f"Remove {entry.path.name} from the list",
                                on_click=lambda e, idx=index: delete_image(idx),
                            ),
                        ],
                    )
                )

        def count_images(node: dict) -> int:
            return len(node["images"]) + sum(
                count_images(child) for child in node["folders"].values()
            )

        def node_entries(node: dict):
            for _, entry in node["images"]:
                yield entry
            for child in node["folders"].values():
                yield from node_entries(child)

        for root in sorted(roots, key=lambda path: str(path).casefold()):
            root_node = roots[root]
            label = root.name if root is not None else "Selected images"
            root_key = (root, ())
            collapsed = root_key in collapsed_folders
            root_control = folder_row(
                label, root, (), 0, count_images(root_node), root_node
            )
            root_control.controls[0].icon = (
                ft.Icons.CHEVRON_RIGHT if collapsed else ft.Icons.EXPAND_MORE
            )
            file_list_col.controls.append(root_control)
            if not collapsed:
                append_tree_nodes(root_node, root, (), 1)

    def current_palette_kwargs() -> dict:
        return dict(
            palette_mode=state.palette_mode,
            art_style=state.art_style,
            n_colors=state.n_colors,
            transfer_palette=state.transfer_palette,
            dither_mode=state.dither_mode,
            edge_aware=state.edge_aware,
        )

    def process_entry(entry: ImageEntry) -> bool:
        try:
            entry.process(state.pixel_size, **current_palette_kwargs())
        except (
            OSError,
            ValueError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
        ) as error:
            entry.error = str(error)
            return False
        return True

    def refresh_preview():
        entry = state.current
        total = len(state.entries)
        frame_count_text.value = f"{state.index + 1} / {total}" if total else "0 / 0"

        if entry is None:
            pixelated_image.src = ""
            original_image.src = ""
            pixelated_image.visible = False
            original_image.visible = False
            pixelated_label.value = "Pixelated"
            placeholder_text.value = (
                "No images loaded\nUpload images or add a folder to get started"
            )
            placeholder_container.visible = True
        else:
            try:
                entry.load()
            except (
                OSError,
                ValueError,
                UnidentifiedImageError,
                Image.DecompressionBombError,
            ) as error:
                entry.error = str(error)
                pixelated_image.src = ""
                original_image.src = ""
                pixelated_image.visible = False
                original_image.visible = False
                placeholder_text.value = (
                    f"Couldn't open {entry.path.name}\n{entry.error}".strip()
                )
                placeholder_container.visible = True
            else:
                has_pixelated = entry.pixelated is not None
                pixelated_label.value = (
                    "Pixelated" if has_pixelated else "Original (not processed yet)"
                )
                pixelated_image.src = pil_to_bytes(
                    entry.pixelated if has_pixelated else entry.original
                )
                pixelated_image.visible = True
                placeholder_container.visible = False

                # "Show original" always splits into two panes — even for an
                # image that hasn't been processed yet — so the layout never
                # collapses back to a single centered image while it's checked.
                if state.show_original:
                    original_image.src = pil_to_bytes(entry.original)
                    original_image.visible = True
                else:
                    original_image.src = ""
                    original_image.visible = False

        original_col.visible = (
            state.show_original
            and entry is not None
            and not placeholder_container.visible
        )
        if entry is None:
            status_text.value = "No images loaded"
        elif entry.error:
            status_text.value = f"Could not open {entry.path.name}: {entry.error}"
        else:
            status_text.value = entry.path.name

    def refresh_all():
        rebuild_palette_controls()
        refresh_file_list()
        refresh_preview()
        process_button.disabled = not state.entries
        if not state.entries and state.playing:
            state.playing = False
            if play_pause_button is not None:
                play_pause_button.selected = False
        entries_to_save = get_entries_to_save()
        save_button.disabled = not entries_to_save or any(
            entry.pixelated is None for entry in entries_to_save
        )
        page.update()

    def get_entries_to_save() -> list[ImageEntry]:
        selected = [entry for entry in state.entries if id(entry) in selected_for_save]
        if selected:
            return selected
        return [state.current] if state.current is not None else []

    def toggle_entry_selection(entry: ImageEntry, selected: bool):
        if selected:
            selected_for_save.add(id(entry))
        else:
            selected_for_save.discard(id(entry))
        refresh_all()

    def process_images(e=None):
        if not state.entries:
            status_text.value = "Choose images or a folder before processing"
            page.update()
            return
        if (
            state.palette_mode == PALETTE_MODE_TRANSFER
            and state.transfer_palette is None
        ):
            status_text.value = (
                "Transfer mode needs a palette source — "
                "pick an image and click 'Use current image as palette source'"
            )
            page.update()
            return

        processed = 0
        failed = []
        for entry in state.entries:
            if process_entry(entry):
                processed += 1
            else:
                failed.append(entry.path.name)

        refresh_all()
        if failed:
            status_text.value = (
                f"Processed {processed}/{len(state.entries)}; couldn't open: "
                + ", ".join(failed[:3])
            )
            if len(failed) > 3:
                status_text.value += f" and {len(failed) - 3} more"
        else:
            mode_label = PALETTE_MODE_LABELS[state.palette_mode]
            status_text.value = f"Processed {processed} image(s) — {mode_label}"
        page.update()

    def select_frame(idx: int):
        state.index = idx
        refresh_all()

    def delete_image(idx: int):
        if not 0 <= idx < len(state.entries):
            return
        remove_entries(lambda entry: entry is state.entries[idx])

    def delete_folder(root: Optional[Path], folder_parts: tuple[str, ...]):
        if root is None:
            remove_entries(lambda entry: entry.source_root is None)
            return

        folder_path = root.joinpath(*folder_parts)

        def belongs_to_folder(entry: ImageEntry) -> bool:
            if entry.source_root != root:
                return False
            try:
                entry.path.relative_to(folder_path)
            except ValueError:
                return False
            return True

        remove_entries(belongs_to_folder)
        collapsed_folders.difference_update(
            {
                key
                for key in collapsed_folders
                if key[0] == root and key[1][: len(folder_parts)] == folder_parts
            }
        )

    def remove_entries(should_remove):
        current = state.current
        old_index = state.index
        removed = [entry for entry in state.entries if should_remove(entry)]
        removed_ids = {id(entry) for entry in removed}
        state.entries = [
            entry for entry in state.entries if id(entry) not in removed_ids
        ]
        selected_for_save.difference_update(removed_ids)
        if not state.entries:
            state.index = 0
        elif current is not None and id(current) not in removed_ids:
            state.index = next(
                index for index, entry in enumerate(state.entries) if entry is current
            )
        else:
            state.index = min(old_index, len(state.entries) - 1)
        refresh_all()

    def go_prev(e):
        if not state.entries:
            return
        state.index = (state.index - 1) % len(state.entries)
        refresh_all()

    def go_next(e):
        if not state.entries:
            return
        state.index = (state.index + 1) % len(state.entries)
        refresh_all()

    async def play_loop():
        while state.playing:
            waited = 0.0
            while waited < PLAY_INTERVAL_SECONDS and state.playing:
                await asyncio.sleep(0.1)
                waited += 0.1
            if not state.playing or not state.entries:
                break
            state.index = (state.index + 1) % len(state.entries)
            refresh_all()

    def toggle_play_pause(e):
        if not state.entries:
            return
        state.playing = not state.playing
        e.control.selected = state.playing
        page.update()
        if state.playing:
            page.run_task(play_loop)

    def on_show_original_change(e):
        state.show_original = e.control.value
        refresh_preview()
        page.update()

    # Note: none of the handlers below touch entry.pixelated. Changing a
    # setting only changes what the *next* click of "Process Images" will
    # produce — the currently displayed pixelated result (if any) keeps
    # showing until the user actually reprocesses.
    def on_pixel_size_change_end(e):
        state.pixel_size = int(e.control.value)
        pixel_size_label.value = f"Pixel size: {state.pixel_size}"
        if state.entries:
            status_text.value = "Settings changed. Press Process Images to update."
        page.update()

    def on_art_style_change(e):
        state.art_style = e.control.value
        if state.entries:
            status_text.value = "Art style changed. Press Process Images to update."
        page.update()

    def on_palette_mode_change(e):
        state.palette_mode = PALETTE_MODE_BY_LABEL[e.control.value]
        rebuild_palette_controls()
        if state.entries:
            status_text.value = "Palette mode changed. Press Process Images to update."
        page.update()

    def on_dither_change(e):
        state.dither_mode = DITHER_BY_LABEL[e.control.value]
        if state.entries:
            status_text.value = "Dithering changed. Press Process Images to update."
        page.update()

    def on_edge_aware_change(e):
        state.edge_aware = e.control.value
        if state.entries:
            status_text.value = "Downsampling changed. Press Process Images to update."
        page.update()

    def on_n_colors_change_end(e):
        state.n_colors = int(e.control.value)
        n_colors_label.value = f"Colors: {state.n_colors}"
        if state.entries:
            status_text.value = "Color count changed. Press Process Images to update."
        page.update()

    def reset_settings(e=None):
        state.pixel_size = DEFAULT_PIXEL_SIZE
        state.show_original = False
        state.edge_aware = True
        state.dither_mode = DITHER_NONE
        state.palette_mode = PALETTE_MODE_PRESET
        state.art_style = DEFAULT_ART_STYLE
        state.n_colors = DEFAULT_N_COLORS
        state.transfer_palette = None
        state.transfer_source_name = None

        for entry in state.entries:
            entry.pixelated = None
        state.playing = False
        if play_pause_button is not None:
            play_pause_button.selected = False

        pixel_size_label.value = f"Pixel size: {state.pixel_size}"
        pixel_size_slider.value = state.pixel_size
        edge_aware_checkbox.value = state.edge_aware
        dither_dropdown.value = DITHER_LABELS[state.dither_mode]
        palette_mode_dropdown.value = PALETTE_MODE_LABELS[state.palette_mode]
        art_style_dropdown.value = state.art_style
        n_colors_label.value = f"Colors: {state.n_colors}"
        n_colors_slider.value = state.n_colors
        show_original_checkbox.value = state.show_original
        transfer_status_text.value = "No palette source set yet."
        transfer_status_text.color = ft.Colors.GREY_400
        rebuild_palette_controls()
        refresh_all()
        status_text.value = (
            "Reset settings and preview; uploaded files are still loaded"
            if state.entries
            else "Settings reset to defaults"
        )
        page.update()

    def on_fit_source(e):
        entry = state.current
        if entry is None:
            status_text.value = "Select an image first to use it as a palette source"
            page.update()
            return
        try:
            entry.load()
            state.transfer_palette = fit_palette(entry.original, state.n_colors)
            state.transfer_source_name = entry.path.name
        except (OSError, ValueError, UnidentifiedImageError) as error:
            status_text.value = f"Could not fit palette from {entry.path.name}: {error}"
            page.update()
            return
        transfer_status_text.value = f"Palette source: {entry.path.name}"
        transfer_status_text.color = ft.Colors.GREEN_400
        status_text.value = f"Fitted palette from {entry.path.name}. Now process other images to transfer it."
        page.update()

    def add_paths(paths: list[Path]):
        existing = {entry.path.resolve() for entry in state.entries}
        added_paths = []
        try:
            discovered = [
                (img_path, path if path.is_dir() else img_path.parent, path.is_dir())
                for path in paths
                for img_path in find_images(path)
            ]
        except OSError as error:
            status_text.value = f"Could not read selected folder: {error}"
            page.update()
            return

        for img_path, source_root, folder_import in discovered:
            try:
                resolved = img_path.resolve()
            except OSError:
                resolved = img_path
            if resolved not in existing:
                state.entries.append(
                    ImageEntry(
                        path=img_path,
                        source_root=source_root,
                        folder_import=folder_import,
                    )
                )
                existing.add(resolved)
                added_paths.append(img_path)
        if added_paths:
            state.index = len(state.entries) - len(added_paths)
            refresh_all()
        else:
            status_text.value = "No new supported images found"
            page.update()

    def add_selected_files(files: list[ft.FilePickerFile]):
        existing = {entry.path.resolve() for entry in state.entries}
        added = []
        skipped = []
        for selected_file in files:
            path = (
                Path(selected_file.path)
                if selected_file.path
                else Path(selected_file.name)
            )
            if path.suffix.lower() not in IMAGE_EXTS:
                continue
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved in existing:
                continue
            if not selected_file.bytes and not path.is_file():
                skipped.append(selected_file.name)
                continue
            state.entries.append(
                ImageEntry(
                    path=path,
                    image_bytes=selected_file.bytes,
                    source_root=path.parent if selected_file.path else None,
                )
            )
            existing.add(resolved)
            added.append(path)

        if added:
            state.index = len(state.entries) - len(added)
            refresh_all()
            if skipped:
                status_text.value = (
                    f"Couldn't read {len(skipped)} selected file(s): "
                    + ", ".join(skipped[:3])
                )
                if len(skipped) > 3:
                    status_text.value += f" and {len(skipped) - 3} more"
                page.update()
        elif skipped:
            status_text.value = "Couldn't read selected file(s): " + ", ".join(
                skipped[:3]
            )
            if len(skipped) > 3:
                status_text.value += f" and {len(skipped) - 3} more"
            page.update()
        else:
            status_text.value = "No new supported images found in the selection"
            page.update()

    async def handle_input_picker(e):
        files = await ft.FilePicker().pick_files(
            dialog_title="Choose images",
            allow_multiple=True,
            file_type=ft.FilePickerFileType.IMAGE,
            with_data=True,
        )
        if files:
            add_selected_files(files)
        else:
            status_text.value = "Selection canceled"
            page.update()

    async def handle_folder_picker(e):
        selected_path = await ft.FilePicker().get_directory_path(
            dialog_title="Choose a folder of images"
        )
        if selected_path:
            add_paths([Path(selected_path)])
        else:
            status_text.value = "Selection canceled"
            page.update()

    async def handle_save(e):
        entries = get_entries_to_save()
        if not entries:
            return
        unprocessed = [entry.path.name for entry in entries if entry.pixelated is None]
        if unprocessed:
            status_text.value = "Process selected images before saving: " + ", ".join(
                unprocessed[:3]
            )
            if len(unprocessed) > 3:
                status_text.value += f" and {len(unprocessed) - 3} more"
            page.update()
            return

        suggested_name = (
            f"{entries[0].path.stem}_pixelated.png"
            if len(entries) == 1
            else "PixelForge export.png"
        )
        save_path = await ft.FilePicker().save_file(
            dialog_title="Save PNG(s)",
            file_name=suggested_name,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["png"],
        )
        if not save_path:
            return

        save_path = Path(save_path)
        if save_path.suffix.lower() != ".png":
            save_path = save_path.with_suffix(".png")
        destination_root = save_path.parent
        try:
            for index, entry in enumerate(entries):
                if entry.pixelated is None:
                    continue
                if entry.folder_import and entry.source_root is not None:
                    relative_path = entry.path.relative_to(entry.source_root)
                    output_path = (
                        destination_root
                        / entry.source_root.name
                        / relative_path.parent
                        / f"{relative_path.stem}_pixelated.png"
                    )
                elif len(entries) == 1 or index == 0:
                    output_path = save_path
                else:
                    output_path = destination_root / f"{entry.path.stem}_pixelated.png"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                entry.pixelated.save(output_path, format="PNG")
        except OSError as error:
            status_text.value = f"Could not save images: {error}"
        else:
            selected_for_save.difference_update(id(entry) for entry in entries)
            refresh_file_list()
            status_text.value = f"Saved {len(entries)} image(s) to {destination_root}"
        page.update()

    # ---------------- layout: left sidebar ----------------
    tight_button_style = ft.ButtonStyle(
        padding=ft.Padding.symmetric(horizontal=4, vertical=10),
    )
    upload_button = ft.OutlinedButton(
        content="Upload",
        icon=ft.Icons.CLOUD_UPLOAD_OUTLINED,
        on_click=handle_input_picker,
        expand=1,
        style=tight_button_style,
    )
    folder_button = ft.OutlinedButton(
        content="Folder",
        icon=ft.Icons.FOLDER_OPEN,
        on_click=handle_folder_picker,
        expand=1,
        style=tight_button_style,
        tooltip="Choose a folder of images",
    )

    show_original_checkbox = ft.Checkbox(
        label="Show original (side-by-side)",
        value=state.show_original,
        on_change=on_show_original_change,
    )
    process_button = ft.Button(
        content=ft.Text("Process", no_wrap=True, size=13),
        icon=ft.Icons.AUTO_FIX_HIGH,
        on_click=process_images,
        disabled=True,
        expand=1,
    )
    reset_button = ft.OutlinedButton(
        content=ft.Text("Reset", no_wrap=True, size=13),
        icon=ft.Icons.RESTART_ALT,
        on_click=reset_settings,
        expand=1,
        tooltip="Reset processing settings to defaults",
    )
    save_button = ft.Button(
        content="Save PNG(s)",
        icon=ft.Icons.SAVE,
        on_click=handle_save,
        disabled=True,
        tooltip="Save the selected image(s), or the current image if none are selected",
    )
    controls_section = ft.Column(
        spacing=20,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Row(
                spacing=8,
                controls=[upload_button, folder_button],
            ),
            palette_controls_col,
            edge_aware_checkbox,
            dither_dropdown,
            pixel_size_col,
            show_original_checkbox,
            ft.Row(
                spacing=8,
                controls=[reset_button, process_button],
            ),
            ft.Divider(),
            # status_text,
            status_container,
        ],
    )
    pixel_size_slider.on_change_end = on_pixel_size_change_end
    n_colors_slider.on_change_end = on_n_colors_change_end

    left_panel = ft.Container(
        width=SIDEBAR_WIDTH,
        bgcolor=ft.Colors.GREY_900,
        padding=SIDEBAR_PADDING,
        content=ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=[
                ft.Text("Images", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=file_list_col,
                    # expand=True,
                    height=260,
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=8,
                    padding=6,
                    width=SIDEBAR_WIDTH - SIDEBAR_PADDING,
                ),
                ft.Divider(height=1, color=ft.Colors.GREY_700),
                controls_section,
            ],
        ),
    )

    # ---------------- layout: right preview panel ----------------
    top_row = ft.Row(
        controls=[
            ft.Text("Preview", size=18, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            frame_count_text,
        ]
    )

    play_pause_button = ft.IconButton(
        icon=ft.Icons.PLAY_ARROW,
        selected_icon=ft.Icons.PAUSE,
        selected=False,
        on_click=toggle_play_pause,
        icon_size=24,
    )
    bottom_controls = ft.Row(
        alignment=ft.MainAxisAlignment.START,
        spacing=8,
        controls=[
            ft.IconButton(icon=ft.Icons.SKIP_PREVIOUS, on_click=go_prev, icon_size=24),
            play_pause_button,
            ft.IconButton(icon=ft.Icons.SKIP_NEXT, on_click=go_next, icon_size=24),
        ],
    )
    preview_footer = ft.Row(
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            bottom_controls,
            ft.Container(expand=True),
            save_button,
        ],
    )

    right_panel = ft.Container(
        expand=True,
        padding=16,
        content=ft.Column(
            expand=True,
            controls=[
                top_row,
                ft.Container(
                    content=preview_stack,
                    expand=True,
                    bgcolor=ft.Colors.GREY_800,
                    border_radius=10,
                    padding=10,
                ),
                preview_footer,
            ],
        ),
    )

    page.add(
        ft.Row(
            expand=True,
            spacing=0,
            controls=[left_panel, ft.VerticalDivider(width=1), right_panel],
        )
    )

    rebuild_palette_controls()
    page.update()
    refresh_all()


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.FLET_APP)
