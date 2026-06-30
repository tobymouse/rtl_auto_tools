"""
rtl-auto / src / backends / base.py — 后端抽象接口

配置是通用的，实现通过后端接口隔离。
换实现只需实现此接口，config/parser/formatter 不变。
"""

from abc import ABC, abstractmethod


class Backend(ABC):
    """AUTO 展开后端抽象"""

    @abstractmethod
    def expand(self, verilog_file: str, library_dirs: list) -> str:
        """
        展开文件中的 AUTO 标记，原地修改文件。
        library_dirs: verilog-library-directories 列表
        返回: stderr 输出（空=成功）
        """
        ...

    @abstractmethod
    def check(self, verilog_file: str, library_dirs: list) -> bool:
        """
        检查文件是否需要展开。
        返回: True=需要更新
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """后端名称"""
        ...
