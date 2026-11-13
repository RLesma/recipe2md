# recipe2md
Own your own recipes! This is a script that extracts a recipe from a website and creates a nice markdown file to see with Obsidian.

## Features

- **Zero external dependencies**: Uses only Python 3's standard library (`python3` on macOS works out of the box).
- **Obsidian-ready YAML frontmatter**: `title`, `source`, `author`, `date`, `servings`, `prep_time`/`cook_time`/`total_time`, and `tags`.
- **Clean sections**:
  - Header metadata & blockquote summary
  - Hero / preview image (if a recipe has a video, only the preview image is downloaded)
  - **Contexto**: Introductory story/notes from the article
  - **Ingredientes**: Preserves sub-sections (e.g. *Emplatado*, *Para la salsa*)
  - **Preparación**: Numbered step-by-step instructions
- **Local images for reliable PDF printing**: Downloads images directly into your `--output-dir` alongside the Markdown file and links them with relative Markdown (`![Title](slug.jpg)`), so Obsidian Reading View and **Export to PDF** work offline.

## Usage

From a file of URLs:

```bash
python3 recipe_to_md.py -f urls.txt -o ~/path/to/ObsidianVault/Recetas
```

Or pass URLs directly:

```bash
python3 recipe_to_md.py -o ~/path/to/ObsidianVault/Recetas \
  https://elpais.com/gastronomia/recetas/2021/09/30/receta/1633022593_843329.html
```

### Options

- `-f, --file`: Text file with one URL per line (`#` comments supported), or `-` for stdin.
- `-o, --output-dir`: Destination folder for `.md` files and images (default: `./recipes`).
- `--images-dir`: Optional subfolder for downloaded images inside `--output-dir` (default: same folder as Markdown).
- `--no-download-images`: Keep remote image URLs instead of downloading them locally.
- `--checkboxes`: Use `- [ ]` checkboxes for ingredients instead of `-` bullets.
- `--overwrite`: Overwrite existing `.md` files with the same filename.

## Tips for Printing to PDF in Obsidian

1. Open the recipe note in **Reading View** (`Cmd + E` on macOS).
2. Use `Cmd + P` or **More options (`...`) → Export to PDF...**
3. Standard Markdown links `![...](slug.jpg)` ensure images appear cleanly in the exported PDF.
