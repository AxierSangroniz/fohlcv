from __future__ import annotations

import pandas as pd
import yfinance as yf


def fetch_tohlcv_yahoo(
    ticker: str,
    interval: str = "1h",
    start: str | None = None,
    end: str | None = None,
    period: str | None = None,
    auto_adjust: bool = False,
    prepost: bool = False,
    timeout: int = 30,
) -> pd.DataFrame:
    """
    Download OHLCV from Yahoo Finance via yfinance.

    Output schema: time, open, high, low, close, volume (UTC-aware).
    Notes:
      - Use either (start/end) OR (period). If both, start/end wins.
      - interval examples: 1m,2m,5m,15m,30m,60m,90m,1h,1d,1wk,1mo
      - period examples: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
    """
    ticker = ticker.strip()
    if not ticker:
        raise ValueError("ticker vacío")

    use_start_end = (start is not None) or (end is not None)
    if use_start_end:
        df = yf.download(
            tickers=ticker,
            interval=interval,
            start=start,
            end=end,
            auto_adjust=auto_adjust,
            prepost=prepost,
            progress=False,
            timeout=timeout,
            threads=True,
        )
    else:
        if period is None:
            # por defecto, algo razonable para 1h
            period = "60d"
        df = yf.download(
            tickers=ticker,
            interval=interval,
            period=period,
            auto_adjust=auto_adjust,
            prepost=prepost,
            progress=False,
            timeout=timeout,
            threads=True,
        )

    if df is None or df.empty:
        raise RuntimeError(f"Yahoo no devolvió datos para {ticker} (interval={interval})")

    # yfinance devuelve columnas con mayúsculas
    # index: DatetimeIndex (a veces tz-naive)
    df = df.copy()

    # Si viene MultiIndex (p.ej. varios tickers) nos quedamos con el ticker
    if isinstance(df.columns, pd.MultiIndex):
        # columnas: (PriceField, Ticker)
        # Nos quedamos con el ticker pedido si existe
        if ticker in df.columns.get_level_values(-1):
            df = df.xs(ticker, axis=1, level=-1)
        else:
            # fallback: primer ticker disponible
            df = df.xs(df.columns.get_level_values(-1)[0], axis=1, level=-1)

    # Normaliza a UTC
    if getattr(df.index, "tz", None) is None:
        # yfinance a veces trae index tz-naive; asumimos UTC
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )

    # Construye salida TOHLCV
    out = pd.DataFrame(
        {
            "time": df.index,
            "open": df.get("open"),
            "high": df.get("high"),
            "low": df.get("low"),
            "close": df.get("close"),
            "volume": df.get("volume"),
        }
    )

    # Asegura dtypes
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce")

    # Orden y reset
    out = out.sort_values("time").reset_index(drop=True)

    return out
