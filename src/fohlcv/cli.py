# src/fohlcv/cli.py
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from dateutil.parser import isoparse
from rich.console import Console
from rich.table import Table

from .yahoo import fetch_tohlcv_yahoo
from .validate import validate_tohlcv
from .io import build_outpath_fixed, save_df
from .utils import is_blank

console = Console()

ASSET_TYPE_EXAMPLES = {
    "stock": ["AAPL", "MSFT", "TSLA"],
    "etf": ["SPY", "QQQ", "IWM"],

    "index": [
        # 🇺🇸 USA
        "^GSPC",      # S&P 500
        "^IXIC",      # Nasdaq Composite
        "^DJI",       # Dow Jones Industrial Average
        "^RUT",       # Russell 2000
        "^VIX",       # Volatility Index

        # 🇪🇺 EUROPA
        "^STOXX50E",  # Euro Stoxx 50
        "^FTSE",      # FTSE 100 (UK)
        "^GDAXI",     # DAX (Alemania)
        "^FCHI",      # CAC 40 (Francia)
        "^IBEX",      # IBEX 35 (España)
        "^SSMI",      # SMI (Suiza)

        # 🇨🇳 CHINA
        "000001.SS",  # Shanghai Composite
        "399001.SZ",  # Shenzhen Component
        "000300.SS",  # CSI 300
        "^HSI",       # Hang Seng (Hong Kong)
        "^HSCE",      # Hang Seng China Enterprises
    ],

    "crypto": ["BTC-USD", "ETH-USD", "SOL-USD"],
    "fx": ["EURUSD=X", "GBPUSD=X", "USDJPY=X"],
    "commodity": ["GC=F", "CL=F", "SI=F"],
    "rate": [
        "^TNX",  # US 10Y
        "^IRX",  # US 13W
        "^TYX",  # US 30Y
    ],
}


DEFAULT_INTERVAL = "1h"


def _ask(prompt: str, default: str | None = None) -> str:
    if default is None:
        return console.input(f"[bold]{prompt}[/bold]: ").strip()
    s = console.input(f"[bold]{prompt}[/bold] [dim](default: {default})[/dim]: ").strip()
    return s if s else default


def _ask_choice(prompt: str, choices: list[str], default: str) -> str:
    choices_str = "/".join(choices)
    while True:
        s = _ask(f"{prompt} ({choices_str})", default).strip().lower()
        if s in choices:
            return s
        console.print(f"[red]Opción inválida[/red]. Elige una de: {choices_str}")


def _parse_date_yyyy_mm_dd(s: str) -> datetime:
    d = isoparse(s).date()
    return datetime(d.year, d.month, d.day)


def _fix_same_day_range(start: str | None, end: str | None) -> tuple[str | None, str | None, str | None]:
    """
    Si start == end, Yahoo trata end como EXCLUSIVO.
    Ajustamos end=end+1día para tener barras del día start.
    """
    if not start or not end:
        return start, end, None
    try:
        ds = _parse_date_yyyy_mm_dd(start)
        de = _parse_date_yyyy_mm_dd(end)
    except Exception:
        return start, end, None

    if ds == de:
        new_end = (de + timedelta(days=1)).strftime("%Y-%m-%d")
        warn = (
            f"Rango de 1 solo día detectado (start=end={end}). "
            f"En Yahoo 'end' es exclusivo → ajusto end a {new_end}."
        )
        return start, new_end, warn

    return start, end, None


def _wizard() -> dict:
    console.print("\n[bold cyan]WIZARD — FOHLCV (Yahoo Finance)[/bold cyan]")
    console.print("[dim]Descarga TOHLCV: time, open, high, low, close, volume[/dim]\n")

    asset_type = _ask_choice(
        "Tipo de activo",
        choices=["stock", "etf", "index", "crypto", "fx", "commodity", "rate", "other"],
        default="stock",
    )

    examples = ASSET_TYPE_EXAMPLES.get(asset_type, [])
    if examples:
        console.print(f"[dim]Ejemplos ({asset_type}): {', '.join(examples)}[/dim]")

    ticker = _ask("Nombre del activo (ticker Yahoo)", examples[0] if examples else "")
    interval = _ask("Intervalo (ej: 1m,5m,15m,1h,1d,1wk,1mo)", DEFAULT_INTERVAL)

    console.print("\n[bold]Periodo[/bold]")
    console.print("[dim]Nota: Yahoo trata 'end' como exclusivo. Para un único día usa end = día siguiente.[/dim]")
    start = _ask("Inicio (YYYY-MM-DD) [vacío = usar period]", "")
    end = _ask("Fin (YYYY-MM-DD) [vacío = usar period]", "")

    period = None
    if not start and not end:
        period = _ask("Periodo Yahoo (ej: 5d, 30d, 60d, 1y, max)", "60d")

    fmt = _ask_choice("Formato de salida", ["parquet", "csv"], "parquet")
    autosave = _ask_choice("¿Guardar a disco?", ["y", "n"], "y") == "y"

    return {
        "ticker": ticker,
        "interval": interval,
        "start": start or None,
        "end": end or None,
        "period": period,
        "format": fmt,
        "no_save": not autosave,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fohlcv",
        description="Descarga TOHLCV desde Yahoo Finance (yfinance) y guarda a disco.",
    )

    p.add_argument("--wizard", action="store_true", help="Modo interactivo wizard")

    p.add_argument("--ticker", default=None, help="Ticker Yahoo (ej: AAPL, BTC-USD, ^GSPC, EURUSD=X)")
    p.add_argument("--interval", default=DEFAULT_INTERVAL, help="Intervalo (default: 1h)")
    p.add_argument("--start", default=None, help="Inicio (YYYY-MM-DD) opcional")
    p.add_argument("--end", default=None, help="Fin (YYYY-MM-DD) opcional")
    p.add_argument("--period", default=None, help="Periodo Yahoo (ej: 60d, 1y, max). Se ignora si hay start/end")

    p.add_argument("--auto-adjust", action="store_true", help="Ajustar precios por splits/dividendos (auto_adjust)")
    p.add_argument("--prepost", action="store_true", help="Incluir pre/after-market si aplica")

    # si lo pasas, respeta esa ruta (override total)
    p.add_argument("--out", default=None, help="Ruta salida exacta (si no, autogenera)")
    p.add_argument("--format", choices=["parquet", "csv"], default="parquet", help="Formato salida")
    p.add_argument("--no-save", action="store_true", help="No guardar, solo mostrar resumen")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    use_wizard = args.wizard or is_blank(args.ticker)

    if use_wizard:
        w = _wizard()
        ticker = w["ticker"]
        interval = w["interval"]
        start = w["start"]
        end = w["end"]
        period = w["period"]
        fmt = w["format"]
        no_save = w["no_save"]
    else:
        ticker = args.ticker
        interval = args.interval
        start = None if is_blank(args.start) else args.start
        end = None if is_blank(args.end) else args.end

        use_start_end = (start is not None) or (end is not None)
        period = None if use_start_end else (None if is_blank(args.period) else args.period)

        fmt = args.format
        no_save = args.no_save

    # Ajuste start=end (end exclusivo en Yahoo)
    start, end, warn = _fix_same_day_range(start, end)
    if warn:
        console.print(f"[yellow]{warn}[/yellow]")

    # Descarga + validación
    try:
        df = fetch_tohlcv_yahoo(
            ticker=ticker,
            interval=interval,
            start=start,
            end=end,
            period=period,
            auto_adjust=args.auto_adjust,
            prepost=args.prepost,
        )
        validate_tohlcv(df)
    except Exception as e:
        console.print(f"\n[red]ERROR:[/red] {e}\n")
        console.print("[bold]Sugerencias rápidas (Yahoo/yfinance):[/bold]")
        if start and end:
            console.print(" - Si querías un único día, usa end = día siguiente (Yahoo trata end como exclusivo).")
        console.print(" - Prueba interval=1d (muchos tickers no ofrecen intradía).")
        console.print(" - Prueba period=30d o 60d (sin start/end).")
        console.print(" - En commodities/futuros, Yahoo puede limitar intradía en ciertos periodos.\n")
        return 2

    # Resumen
    t = Table(title="TOHLCV descargado")
    t.add_column("ticker")
    t.add_column("interval")
    t.add_column("rows", justify="right")
    t.add_column("from")
    t.add_column("to")
    t.add_row(
        ticker,
        interval,
        f"{len(df):,}",
        str(df["time"].iloc[0]),
        str(df["time"].iloc[-1]),
    )
    console.print(t)

    if not no_save:
        # ✅ para el nombre final: <start>_<end>.parquet
        # - si el usuario dio start/end → usamos esos valores
        # - si no → usamos el rango real descargado (por fechas)
        if start and end:
            start_tag = start
            end_tag = end
        else:
            t0 = df["time"].iloc[0]
            t1 = df["time"].iloc[-1]
            start_tag = str(t0.date())
            end_tag = str(t1.date())

        ext = ".parquet" if fmt == "parquet" else ".csv"

        if args.out:
            outpath = Path(args.out).resolve()
        else:
            outpath = build_outpath_fixed(
                ticker=ticker,
                interval=interval,
                start_tag=start_tag,
                end_tag=end_tag,
                ext=ext,
            )

        save_df(df, outpath)
        console.print(f"[green]Saved →[/green] {outpath}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())



## python -m src.fohlcv.cli
