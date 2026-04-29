"""Deriv WebSocket trade executor.

Places and closes Deriv *multiplier* contracts for forex instruments via the
Deriv WebSocket API.

Multiplier contracts behave like leveraged CFDs:
- **MULTUP**  → long  (equivalent to BUY)
- **MULTDOWN** → short (equivalent to SELL)

The *stake* (contract cost) is derived from :attr:`OrderSpec.amount` × price,
which equals the ``max_spend`` computed by :class:`~trading_bot.risk.manager.RiskManager`.

Stop-loss and take-profit are forwarded as Deriv ``limit_order`` parameters
so that they are enforced server-side even when the bot is offline.

References
----------
https://developers.deriv.com/docs/multipliers
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from trading_bot.execution.executor import BaseExecutor, Trade
from trading_bot.risk.manager import OrderSpec

logger = logging.getLogger(__name__)

# Deriv WebSocket endpoint
_WS_URL = "wss://ws.binaryws.com/websockets/v3"


def _to_deriv_symbol(symbol: str) -> str:
    """Convert 'EUR/USD' → 'frxEURUSD'."""
    return "frx" + symbol.replace("/", "")


class DerivExecutor(BaseExecutor):
    """Executes multiplier contracts on the Deriv WebSocket API.

    Parameters
    ----------
    app_id:
        Deriv application ID.
    token:
        Deriv OAuth token (required for live trading).
    multiplier:
        Contract leverage, e.g. ``10``, ``20``, ``50``.
    currency:
        Account currency, e.g. ``"USD"``.
    """

    def __init__(
        self,
        app_id: str = "1089",
        token: str = "",
        multiplier: int = 10,
        currency: str = "USD",
    ):
        self._app_id = app_id
        self._token = token
        self._multiplier = multiplier
        self._currency = currency
        self._ws_url = f"{_WS_URL}?app_id={app_id}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_recv(self, payload: dict) -> dict:
        from websockets.sync.client import connect  # lazy import

        with connect(self._ws_url) as ws:
            # Always authorise before any trading action
            ws.send(json.dumps({"authorize": self._token, "req_id": 0}))
            auth_resp = json.loads(ws.recv())
            if "error" in auth_resp:
                raise RuntimeError(
                    f"Deriv auth failed: {auth_resp['error']['message']}"
                )
            ws.send(json.dumps(payload))
            return json.loads(ws.recv())

    # ------------------------------------------------------------------
    # BaseExecutor implementation
    # ------------------------------------------------------------------

    def execute(self, spec: OrderSpec) -> Trade:
        """Buy a Deriv multiplier contract for *spec*.

        The stake is ``spec.amount × spec.price`` (the USD value to risk).
        """
        contract_type = "MULTUP" if spec.side == "buy" else "MULTDOWN"
        stake = round(spec.amount * spec.price, 2)
        deriv_symbol = _to_deriv_symbol(spec.symbol)

        # Convert absolute SL/TP prices to pip-based distances for Deriv
        sl_distance = round(abs(spec.price - spec.stop_loss), 5)
        tp_distance = round(abs(spec.take_profit - spec.price), 5)

        payload = {
            "buy": "1",
            "price": stake,
            "parameters": {
                "amount": stake,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": self._currency,
                "multiplier": self._multiplier,
                "symbol": deriv_symbol,
                "limit_order": {
                    "stop_loss": sl_distance,
                    "take_profit": tp_distance,
                },
            },
            "req_id": 1,
        }

        logger.info(
            "[DERIV] Placing %s on %s | stake=%.2f | SL=%.5f | TP=%.5f",
            contract_type,
            spec.symbol,
            stake,
            sl_distance,
            tp_distance,
        )

        response = self._send_recv(payload)

        if "error" in response:
            raise RuntimeError(
                f"Deriv buy failed: {response['error']['message']}"
            )

        buy_resp = response.get("buy", {})
        contract_id = str(buy_resp.get("contract_id", "UNKNOWN"))
        buy_price = float(buy_resp.get("buy_price", stake))

        trade = Trade(
            trade_id=contract_id,
            symbol=spec.symbol,
            side=spec.side,
            amount=spec.amount,
            price=buy_price,
            stop_loss=spec.stop_loss,
            take_profit=spec.take_profit,
        )
        logger.info(
            "[DERIV] Contract opened: %s @ %.5f", contract_id, buy_price
        )
        return trade

    def close_trade(self, trade: Trade, current_price: float) -> Trade:
        """Sell (close) the Deriv contract identified by *trade.trade_id*."""
        payload = {"sell": trade.trade_id, "price": 0, "req_id": 2}

        logger.info("[DERIV] Closing contract %s at market", trade.trade_id)
        response = self._send_recv(payload)

        if "error" in response:
            raise RuntimeError(
                f"Deriv sell failed: {response['error']['message']}"
            )

        sell_resp = response.get("sell", {})
        sold_for = float(sell_resp.get("sold_for", current_price))

        if trade.side == "buy":
            pnl = (current_price - trade.price) * trade.amount
        else:
            pnl = (trade.price - current_price) * trade.amount

        trade.closed_at = datetime.now(timezone.utc)
        trade.pnl = pnl
        logger.info(
            "[DERIV] Contract %s closed | sold_for=%.5f | PnL=%.4f",
            trade.trade_id,
            sold_for,
            pnl,
        )
        return trade
