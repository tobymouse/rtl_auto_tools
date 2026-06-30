"""
rtl-auto / src / config.py — TOML 配置解析
内置轻量 TOML 解析器，零依赖。
"""
import re, os
from pathlib import Path


# ---------------------------------------------------------------------------
# 轻量 TOML 解析器（仅支持本工具使用的 TOML 子集）
# 支持: [section], [[array]], key="str", key=123, key=true/false,
#       inline array [...], inline table { ... }
# ---------------------------------------------------------------------------

def _parse_toml(text: str) -> dict:
    """解析 TOML 文本为嵌套 dict"""
    result = {}
    current = result
    current_path = []

    for line in text.split('\n'):
        line = line.strip()
        # 空行 / 注释
        if not line or line.startswith('#'):
            continue

        # 数组表 [[xxx]]
        m = re.match(r'^\[\[(.+)\]\]$', line)
        if m:
            path = m.group(1).split('.')
            current = result
            for key in path:
                if key not in current:
                    current[key] = []
                if not isinstance(current[key], list):
                    raise ValueError("冲突: " + key + " 不是数组")
                current[key].append({})
                current = current[key][-1]
            current_path = path + ['__last__']
            continue

        # 普通表 [xxx]
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            path = m.group(1).split('.')
            current = result
            for key in path:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current_path = path
            continue

        # 键值对 key = value（含 inline table）
        m = re.match(r'^(\w[\w.]*)\s*=\s*(.*)', line)
        if m:
            key = m.group(1)
            val_str = m.group(2).strip()
            current[_toml_key(key)] = _parse_toml_value(val_str)
            continue

    return result


def _parse_toml_value(s: str):
    """解析 TOML 值"""
    s = s.strip()
    # 去掉行尾注释
    s = re.sub(r'\s+#.*$', '', s)

    # 字符串
    if s.startswith('"'):
        return s.strip('"')

    # 布尔
    if s == 'true':
        return True
    if s == 'false':
        return False

    # 整数
    m = re.match(r'^-?\d+$', s)
    if m:
        return int(s)

    # inline 数组 [...]
    if s.startswith('['):
        return _parse_inline_array(s)

    # inline 表 { ... }
    if s.startswith('{'):
        return _parse_inline_table(s)

    return s


def _parse_inline_array(s: str) -> list:
    """解析 [1, 2, "a"] 格式"""
    items = []
    depth = 0
    buf = ''
    for ch in s:
        if ch in '[{' :
            depth += 1
            if depth > 1:
                buf += ch
        elif ch in ']}':
            depth -= 1
            if depth > 0:
                buf += ch
            elif depth == 0:
                if buf.strip():
                    items.append(_parse_toml_value(buf.strip()))
                buf = ''
        elif ch == ',' and depth == 1:
            if buf.strip():
                items.append(_parse_toml_value(buf.strip()))
            buf = ''
        elif depth >= 1:
            buf += ch
    return items


def _parse_inline_table(s: str) -> dict:
    """解析 { key = val, key = val } 格式"""
    d = {}
    inner = s.strip()[1:-1].strip()
    if not inner:
        return d
    for pair in re.split(r',\s*(?=[\w.]+)', inner):
        if '=' in pair:
            k, v = pair.split('=', 1)
            d[_toml_key(k.strip())] = _parse_toml_value(v.strip())
    return d


def _toml_key(s: str) -> str:
    """规范化 TOML key 名称"""
    return s.strip().strip('"').strip("'")


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict:
    """加载并校验 TOML 配置文件"""
    path = Path(path)
    project_dir = path.parent.resolve()

    with open(path, "rb") as f:
        raw = f.read().decode("utf-8")
    cfg = _parse_toml(raw)

    # 校验
    if "project" not in cfg:
        raise ValueError("Missing [project] section")
    if "top" not in cfg:
        raise ValueError("Missing [top] section")
    if "submodules" not in cfg or not cfg["submodules"]:
        raise ValueError("Missing [[submodules]] (at least one required)")

    top = cfg["top"]
    top["file"] = _resolve(top["file"], project_dir)
    top.setdefault("output", top["file"])

    for sm in cfg["submodules"]:
        sm["file"] = _resolve(sm["file"], project_dir)
        sm.setdefault("update", False)
        sm.setdefault("count", 1)

    # 构建实例列表
    instances = _build_instances(cfg["submodules"])
    cfg["_instances"] = instances

    cfg.setdefault("_project_dir", project_dir)
    return cfg


def get_instances(cfg: dict) -> list:
    """获取所有实例列表 [{name, module, file, params}, ...]"""
    return cfg.get("_instances", [])


def get_instances_to_update(cfg: dict) -> list:
    """获取需要更新的实例列表（update=true 的 submodules 生成的实例）"""
    return [inst for inst in get_instances(cfg) if inst.get("update")]


def apply_params(cfg: dict) -> None:
    """读取 [[params]] 段，将参数值写入对应实例的 params 字段"""
    raw_params = cfg.get("params", [])
    instances = get_instances(cfg)

    for param_entry in raw_params:
        insts = param_entry.get("insts", [])
        rules = param_entry.get("rules", [])
        matched = match_instances(instances, insts)
        for inst in matched:
            for name, val in rules:
                inst["params"][name] = val


def match_instances(insts: list, patterns: list) -> list:
    """根据 insts 列表（支持 ~ 正则）匹配实例"""
    matched = []
    for pat in patterns:
        is_regex = pat.startswith("~")
        pattern = re.compile(pat[1:] if is_regex else '^' + re.escape(pat) + '$')
        for inst in insts:
            if pattern.match(inst["name"]):
                if inst not in matched:
                    matched.append(inst)
    return matched


def _resolve(path: str, project_dir: Path) -> str:
    """将相对路径转为绝对路径"""
    p = Path(path)
    return str(p if p.is_absolute() else project_dir / p)


def _build_instances(submodules: list) -> list:
    """根据 submodules 构建实例名列表"""
    instances = []
    for idx, sm in enumerate(submodules):
        module = sm["module"]
        count = sm.get("count", 1)
        for i in range(count):
            if "inst_name" in sm:
                name = sm["inst_name"]
            else:
                name = 'u{:02d}_{}_{}'.format(idx, module, i)
            instances.append({
                "name": name,
                "module": module,
                "file": sm["file"],
                "update": sm.get("update", False),
                "params": {},  # 后续由 params 段填充
            })
    return instances
