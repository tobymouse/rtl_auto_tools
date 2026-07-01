"""
rtl-auto / src / parser.py — Verilog 实例块定位
"""
import re
from typing import Optional


class InstanceBlock:
    """定位和替换 .v 文件中的实例块"""

    def __init__(self, text: str):
        self.text = text

    def locate(self, module_name: str, inst_name: str) -> Optional[dict]:
        """
        定位实例块，返回 {start, end, body_start, body_end, text}
        start~end 是整个实例块（含 module 名到 );）
        body_start~body_end 是端口连接区域（括号内内容）
        """
        # 先找到 module_name 的出现位置
        module_escaped = re.escape(module_name)
        inst_escaped = re.escape(inst_name)
        
        # 逐行扫描找到 module_name
        idx = 0
        while idx < len(self.text):
            # 找下一个 module_name
            m = re.search(module_escaped, self.text[idx:])
            if not m:
                return None
            
            start = idx + m.start()
            rest = self.text[start:]
            
            # 跳过注释和注释行
            if rest.startswith('//') or rest.startswith('/*'):
                idx = start + 1
                continue
            
            # 找到 module_name 后，跳过可能的 #(...) 参数块
            pos = start + len(module_name)
            # 跳过空白
            while pos < len(self.text) and self.text[pos] in ' \t\n\r':
                pos += 1
            
            # 如果遇到 #，跳过 #(...) 参数块（处理嵌套括号）
            has_params = False
            if pos < len(self.text) and self.text[pos] == '#':
                has_params = True
                end_of_params = self._skip_paren_block(self.text, pos)
                if end_of_params is None:
                    idx = start + 1
                    continue
                pos = end_of_params + 1  # 跳过 )
            
            # 跳过空白
            while pos < len(self.text) and self.text[pos] in ' \t\n\r':
                pos += 1
            
            # 检查是否有 inst_name
            inst_match = re.match(inst_escaped + r'\s*\(', self.text[pos:])
            if not inst_match:
                idx = start + 1
                continue
            
            # 找到 (，开始括号匹配
            paren_start = pos + inst_match.end() - 1  # 指向 (
            body_end = self._skip_paren_block(self.text, paren_start)
            if body_end is None:
                idx = start + 1
                continue
            
            paren_end = body_end  # 指向 )
            
            # 找到 );
            semi = self.text.find(';', paren_end)
            if semi == -1:
                idx = start + 1
                continue
            
            return {
                "start": start,
                "end": semi + 1,
                "body_start": paren_start + 1,
                "body_end": paren_end,
                "has_params": has_params,
                "text": self.text[start:semi + 1],
            }

    @staticmethod
    def _skip_paren_block(text: str, pos: int) -> Optional[int]:
        """
        从 pos（指向 ( 或 #）开始，跳过括号块，返回 ) 的位置
        处理嵌套括号和注释
        """
        if text[pos] == '#':
            pos += 1  # 跳过 #
            # 跳过空白
            while pos < len(text) and text[pos] in ' \t\n\r':
                pos += 1
        
        if pos >= len(text) or text[pos] != '(':
            return None
        
        depth = 0
        i = pos
        while i < len(text):
            ch = text[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    return i
            elif ch == '/' and i + 1 < len(text):
                if text[i + 1] == '/':
                    nl = text.find('\n', i)
                    i = nl if nl != -1 else len(text) - 1
                elif text[i + 1] == '*':
                    end = text.find('*/', i + 2)
                    i = end + 1 if end != -1 else len(text) - 1
            i += 1
        return None

    def replace_with_autoinst(self, block: dict) -> str:
        """将实例块括号内内容替换为 /*AUTOINST*/"""
        indent = self._get_indent(self.text[block["start"]:block["body_start"]])
        return (
            self.text[:block["body_start"]]
            + '\n' + indent + '/*AUTOINST*/\n' + indent
            + self.text[block["body_end"]:]
        )

    def replace_params(self, block: dict, params: list, indent: str = "    ") -> str:
        """
        更新实例块的 #(params) 部分
        params 格式: [["PARAM", val], ...]
        如果 block 没有 params 区域则插入新的
        """
        if not params:
            return self.text

        # 找到实例名的位置
        module = block.get("module", "")
        inst = block.get("inst", "")

        # 从 block start 到 body_start 之间找 #(
        prefix = self.text[block["start"]:block["body_start"]]
        hash_idx = prefix.find("#(")

        if hash_idx >= 0:
            # 现有 params，替换内容
            hash_start = block["start"] + hash_idx
            end_of_params = self._skip_paren_block(self.text, hash_start)
            if end_of_params is None:
                return self.text

            # 生成新的 params 文本
            param_str = self._build_params(params, indent)
            return (
                self.text[:hash_start]
                + param_str
                + self.text[end_of_params + 1:]
            )
        else:
            # 没有 params，在 module_name 和 inst_name 之间插入
            inst_start = self.text.find(inst, block["start"])
            if inst_start < 0:
                return self.text
            param_str = self._build_params(params, indent)
            # 插入 #(...) + 换行在 inst_name 之前
            before_inst = self.text[block["start"]:inst_start]
            # 找到最后一行 module_name 的位置
            insertion = inst_start
            return (
                self.text[:insertion]
                + param_str + '\n' + indent
                + self.text[insertion:]
            )

    @staticmethod
    def _build_params(params: list, indent: str) -> str:
        """构建 #(param1, param2, ...) 文本"""
        lines = ["#("]
        for i, (name, val) in enumerate(params):
            comma = "," if i < len(params) - 1 else ""
            lines.append(indent + '.' + name + '(' + str(val) + ')' + comma)
        lines.append(")")
        return "\n".join(lines)

    def inject_autowire(self) -> str:
        """在 module 端口声明后注入 /*AUTOWIRE*/"""
        # 找 module ... ( ... ); 块中的 );
        module_match = re.search(
            r'module\s+\w+\s*\([^)]*\)\s*;', self.text, re.DOTALL
        )
        if not module_match:
            return self.text
        
        pos = module_match.end()
        inject = "\n  /*AUTOWIRE*/\n"
        return self.text[:pos] + inject + self.text[pos:]

    def replace_body(self, block: dict, new_body: str) -> str:
        """替换实例块括号内的内容"""
        return (
            self.text[:block["body_start"]]
            + new_body
            + self.text[block["body_end"]:]
        )

    @staticmethod
    def _get_indent(text_before_paren: str) -> str:
        """从 ( 之前的行提取缩进"""
        lines = text_before_paren.split('\n')
        last = lines[-1] if lines else ""
        indent = re.match(r'^(\s*)', last[::-1]).group(1)
        return indent

    @staticmethod
    def remove_auto_markers(text: str) -> str:
        """只删除 /*AUTO...*/ 标记和 Local Variables 块
        保留 // Beginning/End of automatics 作为生成区域标志
        """
        text = re.sub(r'^\s*/\*AUTO[A-Z_]*\*/\s*\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'/\*AUTO[A-Z_]*\*/', '', text)
        # 删除 Local Variables 块
        text = re.sub(
            r'\n\s*//\s*Local Variables:[\s\S]*?//\s*End:\s*\n?',
            '', text
        )
        return text

    @staticmethod
    def extract_ports(text: str, block: dict) -> list:
        """
        从已展开的 instance 块中提取端口连接列表。
        返回: [{name, signal, is_input}, ...]
        """
        body = text[block["body_start"]:block["body_end"]]
        ports = []
        current_input = False

        for line in body.split('\n'):
            line = line.strip()
            # 跟踪方向注释
            if '// Inputs' in line:
                current_input = True
                continue
            if '// Outputs' in line or '// Inouts' in line:
                current_input = False
                continue

            # 匹配 .port(signal)
            m = re.match(r'\.(\w+)\s*\(\s*([^)]*)\s*\)', line)
            if m:
                ports.append({
                    "name": m.group(1),
                    "signal": m.group(2).strip() or "",
                    "is_input": current_input,
                })

        return ports
