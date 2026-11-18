"""Command-line interface and batch processing loop."""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

from .extractors import extract_recipe, parse_plain_text_recipe
from .storage import index_existing_sources, process_url, save_recipe


def load_urls(args: argparse.Namespace) -> List[str]:
    urls: List[str] = []
    if args.file:
        if args.file == "-":
            lines = sys.stdin.read().splitlines()
        else:
            lines = Path(args.file).read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if re.match(r"^https?://", line, re.I):
                urls.append(line)
    urls.extend(args.urls)
    seen = set()
    unique: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert recipe URLs into Obsidian-ready Markdown files."
    )
    parser.add_argument("urls", nargs="*", help="One or more recipe URLs.")
    parser.add_argument(
        "-f",
        "--file",
        help="Path to a text file with one URL per line (use '-' for stdin).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="./recipes",
        help="Destination folder for Markdown files (default: ./recipes).",
    )
    parser.add_argument(
        "--images-dir",
        default="",
        help="Optional subfolder inside output-dir for downloaded images (default: same folder as Markdown).",
    )
    parser.add_argument(
        "--no-download-images",
        action="store_true",
        help="Keep remote image URLs instead of downloading images locally.",
    )
    parser.add_argument(
        "--checkboxes",
        action="store_true",
        help="Render ingredients as Obsidian checkboxes (- [ ]) instead of bullets (-).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing Markdown files with the same slug.",
    )
    parser.add_argument(
        "-e",
        "--error-file",
        default="errors.txt",
        help="Path to write failed URLs (default: errors.txt).",
    )
    parser.add_argument(
        "--from-html",
        help="Convert a locally saved HTML file (e.g. from a paywalled page) instead of fetching.",
    )
    parser.add_argument(
        "--from-text",
        help="Convert a plain-text file (copied recipe text) into Markdown.",
    )
    parser.add_argument(
        "--paste",
        action="store_true",
        help="Read copied recipe text from stdin (press Ctrl+D when done).",
    )
    parser.add_argument(
        "--url",
        default="",
        help="Source URL metadata when using --from-html, --from-text, or --paste.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional title override when using --from-text or --paste.",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir).expanduser().resolve()

    if args.from_html:
        raw_html = Path(args.from_html).expanduser().read_text(
            encoding="utf-8", errors="replace"
        )
        recipe = extract_recipe(args.url or args.from_html, raw_html)
        save_recipe(
            recipe=recipe,
            out_dir=out_dir,
            images_subdir=args.images_dir,
            download_images=not args.no_download_images,
            use_checkboxes=args.checkboxes,
            overwrite=args.overwrite,
        )
        return 0

    if args.from_text or args.paste:
        if args.paste:
            print("Paste recipe text below, then press Ctrl+D:")
            raw_text = sys.stdin.read()
        else:
            raw_text = Path(args.from_text).expanduser().read_text(
                encoding="utf-8", errors="replace"
            )
        recipe = parse_plain_text_recipe(
            raw_text, source_url=args.url, title_override=args.title
        )
        save_recipe(
            recipe=recipe,
            out_dir=out_dir,
            images_subdir=args.images_dir,
            download_images=False,
            use_checkboxes=args.checkboxes,
            overwrite=args.overwrite,
        )
        return 0

    urls = load_urls(args)
    if not urls:
        parser.print_help()
        return 1

    existing_sources = index_existing_sources(out_dir)
    succeeded = 0
    skipped = 0
    failed_urls: List[Tuple[str, str]] = []
    for url in urls:
        if not args.overwrite and url in existing_sources:
            print(f"Skipping (already exists): {url} -> {existing_sources[url].name}")
            skipped += 1
            continue
        try:
            md_path = process_url(
                url=url,
                out_dir=out_dir,
                images_subdir=args.images_dir,
                download_images=not args.no_download_images,
                use_checkboxes=args.checkboxes,
                overwrite=args.overwrite,
            )
            existing_sources[url] = md_path
            succeeded += 1
        except Exception as exc:
            failed_urls.append((url, str(exc)))
            print(f"  [error] Failed {url}: {exc}", file=sys.stderr)

    if failed_urls:
        error_path = Path(args.error_file).expanduser().resolve()
        error_path.parent.mkdir(parents=True, exist_ok=True)
        error_lines = [f"# {reason}\n{url}\n" for url, reason in failed_urls]
        error_path.write_text("\n".join(error_lines), encoding="utf-8")
        print(
            f"\nDone: {succeeded} succeeded, {skipped} skipped, {len(failed_urls)} failed. "
            f"Failed URLs saved to {error_path}",
            file=sys.stderr,
        )
        return 1

    print(f"\nDone: {succeeded} succeeded, {skipped} skipped, 0 failed.")
    return 0
