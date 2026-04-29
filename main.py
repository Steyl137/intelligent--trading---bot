#!/usr/bin/env python3
"""CLI entry point for the intelligent trading bot."""

import argparse
import logging
import sys

from trading_bot.bot import TradingBot
from trading_bot.multi_bot import MultiBotOrchestrator


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Intelligent Trading Bot")
    parser.add_argument(
        "--mode",
        choices=["run", "step", "summary"],
        default="step",
        help="run: continuous loop | step: single iteration | summary: print portfolio",
    )
    parser.add_argument(
        "--symbols",
        help="Comma-separated list of symbols to trade, e.g. 'EUR/USD,GBP/USD'. "
             "Overrides SYMBOLS env var.",
    )
    parser.add_argument("--interval", type=int, default=3600, help="Loop interval in seconds (run mode)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    # Determine symbol list (CLI flag overrides env/config)
    from config.settings import Config

    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = Config.SYMBOLS or [Config.SYMBOL]

    multi = len(symbols) > 1

    if multi:
        orchestrator = MultiBotOrchestrator(symbols=symbols, config=Config)
        if args.mode == "run":
            orchestrator.run_forever(interval_seconds=args.interval)
        elif args.mode == "step":
            results = orchestrator.step()
            for sym, signal in results.items():
                print(f"[{sym}] {signal.signal.value} @ {signal.price:.5f} – {signal.reason}")
        elif args.mode == "summary":
            summary = orchestrator.summary()
            for key, value in summary.items():
                print(f"  {key}: {value}")
    else:
        bot = TradingBot(config=Config, symbol=symbols[0])
        if args.mode == "run":
            bot.run_forever(interval_seconds=args.interval)
        elif args.mode == "step":
            signal = bot.step()
            print(f"Signal: {signal.signal.value} | Price: {signal.price:.5f} | Reason: {signal.reason}")
        elif args.mode == "summary":
            summary = bot.summary()
            for key, value in summary.items():
                print(f"  {key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

