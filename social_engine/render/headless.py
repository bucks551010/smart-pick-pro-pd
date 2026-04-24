"""Headless rendering: HTML → high-res PNG via Playwright Chromium."""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Iterable

from playwright.async_api import async_playwright

from config import OUTPUT_DIR, OUTPUT_SIZES


async def _render_one(html: str, width: int, height: int, out_path: Path) -> Path:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=2,           # 2x for retina-grade PNGs
        )
        page = await context.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.screenshot(
            path=str(out_path),
            full_page=False,
            type="png",
            omit_background=False,
        )
        await browser.close()
    return out_path


async def _render_bytes(html: str, width: int, height: int) -> bytes:
    """Render HTML to PNG bytes without writing to disk."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=2,
        )
        page = await context.new_page()
        await page.set_content(html, wait_until="networkidle")
        data = await page.screenshot(full_page=False, type="png", omit_background=False)
        await browser.close()
    return data


def render_png_bytes(html: str, width: int = 1080, height: int = 1080) -> bytes:
    """Sync wrapper — render HTML to raw PNG bytes (no disk write)."""
    return asyncio.run(_render_bytes(html, width, height))


async def render_to_images_async(
    html: str,
    *,
    sizes: Iterable[str] = ("square", "landscape", "portrait"),
    name_prefix: str = "asset",
) -> dict[str, Path]:
    """Render the same HTML across multiple aspect ratios concurrently."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    tasks: dict[str, asyncio.Task[Path]] = {}
    for size_key in sizes:
        if size_key not in OUTPUT_SIZES:
            continue
        w, h = OUTPUT_SIZES[size_key]
        out = OUTPUT_DIR / f"{name_prefix}_{size_key}_{w}x{h}.png"
        tasks[size_key] = asyncio.create_task(_render_one(html, w, h, out))
    return {k: await t for k, t in tasks.items()}


def render_to_images(
    html: str,
    *,
    sizes: Iterable[str] = ("square", "landscape", "portrait"),
    name_prefix: str = "asset",
) -> dict[str, Path]:
    """Sync wrapper for Streamlit / scheduler use."""
    return asyncio.run(
        render_to_images_async(html, sizes=sizes, name_prefix=name_prefix)
    )
