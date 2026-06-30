"""
rtl-auto / src / backends / verilog_mode.py — emacs verilog-mode 后端

调用 emacs --batch 执行 verilog-auto 展开。
不依赖文件内嵌 Local Variables，直接通过 elisp 设置路径。
"""
import subprocess, os
from .base import Backend


class VerilogModeBackend(Backend):

    name = "verilog-mode"

    def expand(self, verilog_file: str, library_dirs: list) -> str:
        file_abs = os.path.abspath(verilog_file)
        file_dir = os.path.dirname(file_abs)
        file_name = os.path.basename(verilog_file)

        dirs_str = "(" + " ".join('"' + d + '"' for d in library_dirs) + ")"
        elisp = _ELISP_EXPAND % (dirs_str, file_name)

        result = subprocess.run(
            ["emacs", "--batch", "--no-site-file", "--eval", elisp],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
            cwd=file_dir,
        )
        return result.stderr

    def check(self, verilog_file: str, library_dirs: list) -> bool:
        file_abs = os.path.abspath(verilog_file)
        file_dir = os.path.dirname(file_abs)
        file_name = os.path.basename(verilog_file)

        dirs_str = "(" + " ".join('"' + d + '"' for d in library_dirs) + ")"
        elisp = _ELISP_CHECK % (dirs_str, file_name)

        result = subprocess.run(
            ["emacs", "--batch", "--no-site-file", "--eval", elisp],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
            cwd=file_dir,
        )
        return "%%Warning" in result.stderr or "Difference" in result.stderr


_ELISP_EXPAND = r"""
(progn
  (require 'verilog-mode)
  (setq make-backup-files nil)
  (setq enable-local-variables t)
  (setq enable-local-eval t)
  (setq verilog-library-directories '%s)
  (setq verilog-library-extensions '(".v" ".vh" ".sv"))
  (find-file "%s")
  (verilog-mode)
  (hack-local-variables)
  (verilog-auto)
  (save-buffer)
  (kill-buffer))
"""

_ELISP_CHECK = r"""
(progn
  (require 'verilog-mode)
  (setq make-backup-files nil)
  (setq enable-local-variables t)
  (setq enable-local-eval t)
  (setq verilog-library-directories '%s)
  (setq verilog-library-extensions '(".v" ".vh" ".sv"))
  (find-file "%s")
  (verilog-mode)
  (hack-local-variables)
  (verilog-diff-auto)
  (kill-buffer))
"""
