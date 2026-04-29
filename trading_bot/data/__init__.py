from trading_bot.data.fetcher import DataFetcher
from trading_bot.data.deriv_fetcher import DerivFetcher
from trading_bot.data.mt5_fetcher import MT5Fetcher


def get_fetcher(source: str, **kwargs):
    """Factory – return the right fetcher for *source*.

    Parameters
    ----------
    source:
        ``"ccxt"``, ``"deriv"``, or ``"mt5"``.
    kwargs:
        Forwarded to the fetcher constructor.
    """
    if source == "ccxt":
        return DataFetcher(
            exchange_id=kwargs.get("exchange_id", "binance"),
            api_key=kwargs.get("api_key", ""),
            api_secret=kwargs.get("api_secret", ""),
        )
    if source == "deriv":
        return DerivFetcher(
            app_id=kwargs.get("app_id", "1089"),
            token=kwargs.get("token", ""),
        )
    if source == "mt5":
        return MT5Fetcher(
            login=kwargs.get("login", 0),
            password=kwargs.get("password", ""),
            server=kwargs.get("server", ""),
        )
    raise ValueError(f"Unknown data source '{source}'. Choose: ccxt | deriv | mt5")


__all__ = ["DataFetcher", "DerivFetcher", "MT5Fetcher", "get_fetcher"]
