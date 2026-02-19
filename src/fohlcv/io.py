# src/fohlcv/io.py
from __future__ import annotations

import re
from pathlib import Path
import pandas as pd

# ✅ BASE PATH FIJO
FIXED_DATA_ROOT = Path(
    r"C:\Users\axier\Desktop\CARPETA PROGRAMACION\quant_trading_system\data"
)


def _sanitize_token(s: str) -> str:
    """
    Convierte cualquier string a formato seguro para Windows:
    - Sustituye caracteres no alfanuméricos por '_'
    - Colapsa múltiples '_'
    - Elimina '_' inicial/final
    """
    s = str(s).strip()
    s = re.sub(r"[^A-Za-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "NA"


def build_outpath_fixed(
    ticker: str,
    interval: str,
    start_tag: str,
    end_tag: str,
    ext: str = ".parquet",
    data_root: Path = FIXED_DATA_ROOT,
) -> Path:
    """
    Construye EXACTAMENTE:

    <data_root>/<TICKER_SANITIZADO>/tohlcv/<INTERVAL_SANITIZADO>/<START_SANITIZADO>_<END_SANITIZADO>.parquet

    Ej:
      ...\data\BTC_USD\tohlcv\1h\2025_01_01_2026_01_01.parquet
    """
    safe_ticker = _sanitize_token(ticker)
    safe_interval = _sanitize_token(interval)
    safe_start = _sanitize_token(start_tag)
    safe_end = _sanitize_token(end_tag)

    folder = data_root / safe_ticker / "tohlcv" / safe_interval
    folder.mkdir(parents=True, exist_ok=True)

    filename = f"{safe_start}_{safe_end}{ext}"
    return folder / filename


def save_df(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() == ".parquet":
        df.to_parquet(path, index=False)
    elif path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
    else:
        raise ValueError(f"Extensión no soportada: {path.suffix}")
