"""Polymarket CLOB API — limit order placement.
Only executed when edge is detected (|swarm_p - market_p| > threshold).
Limit orders only. Polygon USDC wallet auth.
"""
from __future__ import annotations
from ..config import settings
from ..schemas import BetReceipt


def place_limit_order(
    market_id: str,
    side: str,         # "BUY" or "SELL"
    size: float,       # USDC amount
    price: float,      # limit price 0–1
) -> BetReceipt:
    """Place a limit order on the CLOB. Returns a BetReceipt."""
    # TODO: initialise py-clob-client with wallet credentials
    # from py_clob_client.client import ClobClient
    # from py_clob_client.clob_types import OrderArgs, OrderType
    #
    # client = ClobClient(
    #     host="https://clob.polymarket.com",
    #     chain_id=settings.polymarket_chain_id,
    #     private_key=settings.polymarket_private_key,
    # )
    # order = client.create_order(OrderArgs(
    #     token_id=market_id,
    #     price=price,
    #     size=size,
    #     side=side,
    # ))
    # resp = client.post_order(order, OrderType.GTC)
    # return BetReceipt(
    #     order_id=resp["orderID"],
    #     market_id=market_id,
    #     side=side,
    #     size=size,
    #     price=price,
    #     status=resp["status"],
    # )
    raise NotImplementedError("Wire py-clob-client credentials to enable bet placement.")
