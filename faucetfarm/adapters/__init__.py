from .base import Adapter
from .firefaucet import FireFaucetAdapter
from .coinpayu import CoinpayuAdapter
from .freebitco import FreeBitcoAdapter
from .cointiply import CointiplyAdapter

REGISTRY = {
    "firefaucet": FireFaucetAdapter,
    "coinpayu": CoinpayuAdapter,
    "freebitco": FreeBitcoAdapter,
    "cointiply": CointiplyAdapter,
}


def get_adapter(name: str) -> type[Adapter]:
    if name not in REGISTRY:
        raise KeyError(f"unknown adapter: {name}")
    return REGISTRY[name]
