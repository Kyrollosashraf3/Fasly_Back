from pathlib import Path

# Production output of `npm run build` in front_fasly (vite.config outDir).
# Served under /ui by the StaticFiles mount registered in :mod:`app.app`.
REACT_DIR = Path(__file__).resolve().parent.parent / "static_react"
