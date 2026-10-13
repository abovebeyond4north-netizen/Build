"""Single source of truth for the offered Base USDC prices."""
from decimal import Decimal

PRICES = {'GET /chain/status': '$0.001',
          'GET /token/metadata/:address': '$0.003',
          'GET /token/context/:address': '$0.009'}


def atomic_price(route: str) -> int:
    price = PRICES[route]
    atomic = Decimal(price.removeprefix('$')) * Decimal(1_000_000)
    if atomic <= 0 or atomic != atomic.to_integral_value():
        raise ValueError('price cannot be represented in Base USDC atomic units')
    return int(atomic)
