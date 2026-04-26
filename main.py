#!/usr/bin/env python3
"""CLI entry point for the intelligent trading bot."""

import argparse
import logging
import sys

from trading_bot.bot import TradingBot


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
    parser.add_argument("--interval", type=int, default=3600, help="Loop interval in seconds (run mode)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    bot = TradingBot()

    if args.mode == "run":
        bot.run_forever(interval_seconds=args.interval)
    elif args.mode == "step":
        signal = bot.step()
        print(f"Signal: {signal.signal.value} | Price: {signal.price:.4f} | Reason: {signal.reason}")
    elif args.mode == "summary":
        summary = bot.summary()
        for key, value in summary.items():
            print(f"  {key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
