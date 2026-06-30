"""
rtl-auto / src / formatter.py — Verible 格式化封装
"""
import subprocess, shutil


def format_file(verilog_file: str, verible: str = "verible-verilog-format",
                extra_flags: list = None) -> bool:
    """用 Verible 格式化文件，返回 True=成功"""
    if not shutil.which(verible):
        return False

    cmd = [verible, "--inplace", verilog_file]
    if extra_flags:
        cmd.extend(extra_flags)

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return result.returncode == 0


def verify_format(verilog_file: str, verible: str = "verible-verilog-format") -> bool:
    """验证格式化是否收敛（exit 0 = 无需更改）"""
    if not shutil.which(verible):
        return False

    result = subprocess.run(
        [verible, "--verify", verilog_file],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
    )
    return result.returncode == 0
