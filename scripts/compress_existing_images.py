from __future__ import annotations

import argparse
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener


register_heif_opener()


@dataclass
class Conversion:
    asset_id: int
    old_relative_path: str
    new_relative_path: str
    source_path: Path
    temp_path: Path
    final_path: Path
    old_size: int
    new_size: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert existing labnotez uploads to resized JPEG files."
    )
    parser.add_argument("--database", default="data/labnotes.db")
    parser.add_argument("--upload-dir", default="data/uploads")
    parser.add_argument("--max-dimension", type=int, default=1920)
    parser.add_argument("--quality", type=int, default=75)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write converted files, update the database, and remove replaced originals.",
    )
    return parser.parse_args()


def as_jpeg_path(relative_path: str, upload_dir: Path) -> tuple[str, Path]:
    path = Path(relative_path)
    candidate = path.with_suffix(".jpg")
    final_path = upload_dir / candidate
    if candidate.as_posix() == relative_path or not final_path.exists():
        return candidate.as_posix(), final_path

    unique_candidate = path.with_name(f"{path.stem}-{uuid4().hex}.jpg")
    return unique_candidate.as_posix(), upload_dir / unique_candidate


def save_resized_jpeg(source_path: Path, temp_path: Path, max_dimension: int, quality: int) -> None:
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        if image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        ):
            image = image.convert("RGBA")
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")

        image.save(
            temp_path,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
        )


def build_conversions(args: argparse.Namespace) -> list[Conversion]:
    upload_dir = Path(args.upload_dir).resolve()
    connection = sqlite3.connect(args.database)
    connection.row_factory = sqlite3.Row
    rows = connection.execute("SELECT id, file_path FROM assets ORDER BY id").fetchall()
    connection.close()

    conversions: list[Conversion] = []
    for row in rows:
        source_path = upload_dir / row["file_path"]
        if not source_path.exists():
            print(f"missing: asset {row['id']} {row['file_path']}")
            continue

        new_relative_path, final_path = as_jpeg_path(row["file_path"], upload_dir)
        temp_path = final_path.with_name(f".{final_path.name}.tmp-{uuid4().hex}")
        save_resized_jpeg(source_path, temp_path, args.max_dimension, args.quality)

        conversions.append(
            Conversion(
                asset_id=row["id"],
                old_relative_path=row["file_path"],
                new_relative_path=new_relative_path,
                source_path=source_path,
                temp_path=temp_path,
                final_path=final_path,
                old_size=source_path.stat().st_size,
                new_size=temp_path.stat().st_size,
            )
        )

    return conversions


def apply_conversions(database: Path, conversions: list[Conversion]) -> None:
    connection = sqlite3.connect(database)
    try:
        with connection:
            for conversion in conversions:
                conversion.final_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(conversion.temp_path, conversion.final_path)
                connection.execute(
                    "UPDATE assets SET file_path = ? WHERE id = ?",
                    (conversion.new_relative_path, conversion.asset_id),
                )

        for conversion in conversions:
            if conversion.source_path != conversion.final_path and conversion.source_path.exists():
                conversion.source_path.unlink()
    finally:
        connection.close()


def cleanup_temp_files(conversions: list[Conversion]) -> None:
    for conversion in conversions:
        if conversion.temp_path.exists():
            conversion.temp_path.unlink()


def main() -> None:
    args = parse_args()
    database = Path(args.database).resolve()
    conversions = build_conversions(args)

    old_total = sum(conversion.old_size for conversion in conversions)
    new_total = sum(conversion.new_size for conversion in conversions)
    print(f"assets converted: {len(conversions)}")
    print(f"old bytes: {old_total}")
    print(f"new bytes: {new_total}")
    print(f"saved bytes: {old_total - new_total}")

    if not args.apply:
        cleanup_temp_files(conversions)
        print("dry run only; pass --apply to write changes")
        return

    apply_conversions(database, conversions)
    print("applied")


if __name__ == "__main__":
    main()
