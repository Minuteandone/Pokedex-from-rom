from __future__ import annotations

import csv
import io
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image

ROM_POINTER_BASE = 0x08000000
NUM_SPECIES = 412  # Pokémon Emerald's internal species count
SPECIES_NAME_LENGTH = 11

# These defaults target Pokémon Emerald (US, BPEE) and can be overridden.
DEFAULT_SPECIES_NAME_TABLE = 0x3185C8
DEFAULT_FRONT_SPRITE_TABLE = 0x3C1CAC
DEFAULT_PALETTE_TABLE = 0x3C21CC

TERMINATOR = 0xFF

CHARMAP = {
    0x00: " ",
    0xA1: "0",
    0xA2: "1",
    0xA3: "2",
    0xA4: "3",
    0xA5: "4",
    0xA6: "5",
    0xA7: "6",
    0xA8: "7",
    0xA9: "8",
    0xAA: "9",
    0xAB: "!",
    0xAC: "?",
    0xAD: ".",
    0xAE: "-",
    0xB0: "…",
    0xB1: "“",
    0xB2: "”",
    0xB3: "‘",
    0xB4: "’",
    0xB5: "♂",
    0xB6: "♀",
    0xB7: "$",
    0xB8: ",",
    0xB9: "×",
    0xBA: "/",
    0xBB: "A",
    0xBC: "B",
    0xBD: "C",
    0xBE: "D",
    0xBF: "E",
    0xC0: "F",
    0xC1: "G",
    0xC2: "H",
    0xC3: "I",
    0xC4: "J",
    0xC5: "K",
    0xC6: "L",
    0xC7: "M",
    0xC8: "N",
    0xC9: "O",
    0xCA: "P",
    0xCB: "Q",
    0xCC: "R",
    0xCD: "S",
    0xCE: "T",
    0xCF: "U",
    0xD0: "V",
    0xD1: "W",
    0xD2: "X",
    0xD3: "Y",
    0xD4: "Z",
    0xD5: "a",
    0xD6: "b",
    0xD7: "c",
    0xD8: "d",
    0xD9: "e",
    0xDA: "f",
    0xDB: "g",
    0xDC: "h",
    0xDD: "i",
    0xDE: "j",
    0xDF: "k",
    0xE0: "l",
    0xE1: "m",
    0xE2: "n",
    0xE3: "o",
    0xE4: "p",
    0xE5: "q",
    0xE6: "r",
    0xE7: "s",
    0xE8: "t",
    0xE9: "u",
    0xEA: "v",
    0xEB: "w",
    0xEC: "x",
    0xED: "y",
    0xEE: "z",
}


@dataclass
class SpeciesRecord:
    index: int
    name: str


def gba_ptr_to_offset(ptr: int) -> int:
    if ptr < ROM_POINTER_BASE:
        raise ValueError(f"Bad GBA pointer: {ptr:#x}")
    return ptr - ROM_POINTER_BASE


def decode_poke_string(raw: bytes) -> str:
    chars: list[str] = []
    for b in raw:
        if b == TERMINATOR:
            break
        chars.append(CHARMAP.get(b, "?"))
    return "".join(chars).strip() or "UNKNOWN"


def lz77_decompress(blob: bytes, offset: int) -> bytes:
    if blob[offset] != 0x10:
        raise ValueError(f"Expected LZ77 header at {offset:#x}, got {blob[offset]:#x}")

    out_len = blob[offset + 1] | (blob[offset + 2] << 8) | (blob[offset + 3] << 16)
    pos = offset + 4
    out = bytearray()

    while len(out) < out_len:
        flags = blob[pos]
        pos += 1
        for bit in range(8):
            if len(out) >= out_len:
                break
            if flags & (0x80 >> bit):
                b1 = blob[pos]
                b2 = blob[pos + 1]
                pos += 2
                length = (b1 >> 4) + 3
                disp = ((b1 & 0x0F) << 8) | b2
                src = len(out) - (disp + 1)
                if src < 0:
                    raise ValueError("Invalid LZ77 back-reference")
                for _ in range(length):
                    out.append(out[src])
                    src += 1
            else:
                out.append(blob[pos])
                pos += 1

    return bytes(out)


def decode_4bpp_sprite(sprite_data: bytes, palette_15bit: bytes, width: int = 64, height: int = 64) -> Image.Image:
    palette_colors: list[tuple[int, int, int, int]] = []
    for i in range(16):
        color = struct.unpack_from("<H", palette_15bit, i * 2)[0]
        r = (color & 0x1F) << 3
        g = ((color >> 5) & 0x1F) << 3
        b = ((color >> 10) & 0x1F) << 3
        a = 0 if i == 0 else 255
        palette_colors.append((r, g, b, a))

    image = Image.new("RGBA", (width, height))
    px = image.load()

    tiles_x = width // 8
    tiles_y = height // 8
    tile_count = tiles_x * tiles_y

    expected_len = tile_count * 32
    if len(sprite_data) < expected_len:
        raise ValueError(f"Sprite too small: got {len(sprite_data)} bytes, need {expected_len}")

    tile_offset = 0
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            tile = sprite_data[tile_offset : tile_offset + 32]
            tile_offset += 32
            for y in range(8):
                for x in range(8):
                    byte = tile[(y * 8 + x) // 2]
                    color_idx = byte & 0x0F if x % 2 == 0 else (byte >> 4) & 0x0F
                    px[tx * 8 + x, ty * 8 + y] = palette_colors[color_idx]

    return image


def read_species_names(rom: bytes, table_offset: int = DEFAULT_SPECIES_NAME_TABLE) -> list[SpeciesRecord]:
    names: list[SpeciesRecord] = []
    for i in range(NUM_SPECIES):
        start = table_offset + i * SPECIES_NAME_LENGTH
        end = start + SPECIES_NAME_LENGTH
        names.append(SpeciesRecord(index=i, name=decode_poke_string(rom[start:end])))
    return names


def extract_sprites(
    rom: bytes,
    output_dir: Path,
    names: Iterable[SpeciesRecord],
    front_table_offset: int = DEFAULT_FRONT_SPRITE_TABLE,
    palette_table_offset: int = DEFAULT_PALETTE_TABLE,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for species in names:
        front_entry = front_table_offset + species.index * 8
        pal_entry = palette_table_offset + species.index * 8

        sprite_ptr = struct.unpack_from("<I", rom, front_entry)[0]
        pal_ptr = struct.unpack_from("<I", rom, pal_entry)[0]
        if sprite_ptr == 0 or pal_ptr == 0:
            continue

        sprite_offset = gba_ptr_to_offset(sprite_ptr)
        pal_offset = gba_ptr_to_offset(pal_ptr)

        sprite_data = lz77_decompress(rom, sprite_offset)
        palette_data = lz77_decompress(rom, pal_offset)

        image = decode_4bpp_sprite(sprite_data, palette_data)
        safe_name = species.name.replace("/", "_")
        image.save(output_dir / f"{species.index:03d}_{safe_name}.png")


def write_names_csv(names: Iterable[SpeciesRecord], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "name"])
        for item in names:
            writer.writerow([item.index, item.name])


def validate_emerald_header(rom: bytes) -> None:
    code = rom[0xAC:0xB0].decode("ascii", errors="ignore")
    if code != "BPEE":
        raise ValueError(
            f"Unsupported ROM game code {code!r}. This extractor currently targets Pokémon Emerald (US), code 'BPEE'."
        )


def build_zip_bytes(rom_bytes: bytes) -> bytes:
    validate_emerald_header(rom_bytes)

    names = read_species_names(rom_bytes)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        csv_rows = io.StringIO()
        writer = csv.writer(csv_rows)
        writer.writerow(["index", "name"])
        for item in names:
            writer.writerow([item.index, item.name])
        zf.writestr("names.csv", csv_rows.getvalue())

        for species in names:
            front_entry = DEFAULT_FRONT_SPRITE_TABLE + species.index * 8
            pal_entry = DEFAULT_PALETTE_TABLE + species.index * 8

            sprite_ptr = struct.unpack_from("<I", rom_bytes, front_entry)[0]
            pal_ptr = struct.unpack_from("<I", rom_bytes, pal_entry)[0]
            if sprite_ptr == 0 or pal_ptr == 0:
                continue

            sprite_offset = gba_ptr_to_offset(sprite_ptr)
            pal_offset = gba_ptr_to_offset(pal_ptr)
            sprite_data = lz77_decompress(rom_bytes, sprite_offset)
            palette_data = lz77_decompress(rom_bytes, pal_offset)
            image = decode_4bpp_sprite(sprite_data, palette_data)

            png = io.BytesIO()
            image.save(png, format="PNG")
            safe_name = species.name.replace("/", "_")
            zf.writestr(f"sprites/{species.index:03d}_{safe_name}.png", png.getvalue())

    return buffer.getvalue()
