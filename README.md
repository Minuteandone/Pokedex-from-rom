# Pokedex-from-rom

A small web tool that lets you upload a **Pokémon Emerald (US)** ROM and download an extracted Pokédex package with:

- `names.csv` (species index + species name)
- `sprites/*.png` (front sprites)

## Quick start

### macOS / Linux (bash)

```bash
./setup.sh
source .venv/bin/activate
python app.py
```

### Windows (PowerShell)

```powershell
.\setup.ps1
.\.venv\Scripts\Activate.ps1
python app.py
```

The setup scripts create a virtual environment and install all dependencies automatically.

Then open <http://127.0.0.1:5000>, upload your `.gba`, and download the generated ZIP.

## Notes

- Current ROM support is intentionally narrow: Pokémon Emerald US only (`BPEE`).
- The extractor decodes names from the ROM charmap and front sprites from LZ77-compressed graphics + palettes.
- If you want to support additional regions/revisions later, the extractor constants in `extractor.py` can be made profile-driven.
