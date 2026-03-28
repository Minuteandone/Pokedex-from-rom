from __future__ import annotations

import io
from datetime import UTC, datetime

from flask import Flask, flash, redirect, render_template, request, send_file, url_for

from extractor import build_zip_bytes

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.secret_key = "pokedex-rom-tool"


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/extract")
def extract():
    rom = request.files.get("rom")
    if not rom or rom.filename == "":
        flash("Please upload a Pokémon Emerald ROM file (.gba).", "error")
        return redirect(url_for("index"))

    try:
        zip_bytes = build_zip_bytes(rom.read())
    except Exception as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"emerald_pokedex_{stamp}.zip"
    return send_file(
        io.BytesIO(zip_bytes),
        as_attachment=True,
        download_name=filename,
        mimetype="application/zip",
    )


if __name__ == "__main__":
    app.run(debug=True)
