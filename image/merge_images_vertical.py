#!/usr/bin/env python3
"""
将两张图片竖向拼接：上图 + 下图。
默认读取当前工作目录下的 1.jpg（上）与 2.jpg（下），输出 merged_vertical.jpg。
依赖: pip install Pillow
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def merge_vertical(
    top_path: str | Path,
    bottom_path: str | Path,
    output_path: str | Path,
    *,
    bg: tuple[int, int, int] = (255, 255, 255),
) -> None:
    top = Image.open(top_path).convert("RGBA")
    bottom = Image.open(bottom_path).convert("RGBA")

    width = max(top.width, bottom.width)
    height = top.height + bottom.height

    canvas = Image.new("RGBA", (width, height), (*bg, 255))

    x_top = (width - top.width) // 2
    x_bot = (width - bottom.width) // 2
    canvas.paste(top, (x_top, 0), top)
    canvas.paste(bottom, (x_bot, top.height), bottom)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if out.suffix.lower() in {".jpg", ".jpeg", ".bmp"}:
        canvas = canvas.convert("RGB")
    canvas.save(out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="两张图片竖向拼接（上 + 下）。不传参数时默认拼接当前目录 1.jpg（上）与 2.jpg（下）。"
    )
    parser.add_argument(
        "top",
        nargs="?",
        default="1.jpg",
        help="上方图片路径（默认 1.jpg）",
    )
    parser.add_argument(
        "bottom",
        nargs="?",
        default="2.jpg",
        help="下方图片路径（默认 2.jpg）",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="merged_vertical.jpg",
        help="输出路径（默认 merged_vertical.jpg）",
    )
    parser.add_argument(
        "--bg",
        nargs=3,
        type=int,
        metavar=("R", "G", "B"),
        default=[255, 255, 255],
        help="宽度不一致时的填充背景 RGB，默认 255 255 255",
    )
    args = parser.parse_args()

    merge_vertical(
        args.top,
        args.bottom,
        args.output,
        bg=(args.bg[0], args.bg[1], args.bg[2]),
    )
    print(f"已保存: {args.output}")


if __name__ == "__main__":
    main()
