"""
rtl-auto / src / expander.py — 后端调度

根据配置（或默认）选择 AUTO 展开后端。
换实现只需修改 _get_backend() 中的逻辑，config/parser/formatter 不变。
"""
from .backends.base import Backend
from .backends.verilog_mode import VerilogModeBackend


def get_backend(name: str = None) -> Backend:
    """根据名称获取后端实例"""
    backends = {
        "verilog-mode": VerilogModeBackend(),
    }
    name = name or "verilog-mode"
    if name not in backends:
        raise ValueError("Unknown backend: {}. Available: {}".format(name, list(backends.keys())))
    return backends[name]


def expand_auto(verilog_file: str, library_dirs: list = None,
                backend: Backend = None) -> str:
    """展开 AUTO 标记"""
    be = backend or get_backend()
    return be.expand(verilog_file, library_dirs or [])


def needs_expansion(verilog_file: str, library_dirs: list = None,
                    backend: Backend = None) -> bool:
    """检查是否需要展开"""
    be = backend or get_backend()
    return be.check(verilog_file, library_dirs or [])
