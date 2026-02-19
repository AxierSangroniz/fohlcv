from __future__ import annotations
import pandas as pd


REQUIRED_COLS = ["time", "open", "high", "low", "close", "volume"]


def validate_tohlcv(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas: {missing}")

    if df.empty:
        raise ValueError("DataFrame vacío")

    if df["time"].isna().any():
        raise ValueError("Hay NaNs en time")

    # Duplicados en time
    dup = df["time"].duplicated().sum()
    if dup:
        raise ValueError(f"Hay {dup} timestamps duplicados")

    # Orden temporal
    if not df["time"].is_monotonic_increasing:
        raise ValueError("time no está ordenado ascendente")

    # OHLC básicos
    for c in ["open", "high", "low", "close"]:
        if df[c].isna().all():
            raise ValueError(f"Columna {c} viene toda NaN")

    # Volumen puede ser 0 o NaN en algunos activos, no forzamos demasiado
