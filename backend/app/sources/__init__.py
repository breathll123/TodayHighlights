from app.sources.base import SourceAdapter
from app.sources.xueqiu import XueqiuAdapter
from app.sources.eastmoney import EastmoneyAdapter
from app.sources.tonghuashun import TonghuashunAdapter
from app.sources.dongqiudi import DongqiudiAdapter

ADAPTER_REGISTRY: dict[str, type] = {
    "xueqiu": XueqiuAdapter,
    "eastmoney": EastmoneyAdapter,
    "tonghuashun": TonghuashunAdapter,
    "dongqiudi": DongqiudiAdapter,
}


def get_adapter(site: str):
    adapter_cls = ADAPTER_REGISTRY.get(site)
    if adapter_cls is None:
        raise ValueError(f"Unknown source site: {site}")
    return adapter_cls()
