# RTL Auto Instance & Connect — 技术规格书 (Spec)

> 版本：v1.0  
> 日期：2026-06-26  
> 状态：**待用户确认**  
> 方案：A'（verilog-mode + Python 标记临时加删）

---

## 1. 概述

### 1.1 工具名称

`rtl-auto` — RTL 自动 Instance & Connect 工具

### 1.2 核心机制

```
干净 .v 文件（无标记）
  → Python 括号匹配定位 instance 块，临时插入 /*AUTOINST*/
  → emacs --batch 调用 verilog-mode 展开
  → Python 删除所有 /*AUTO...*/ 标记
  → Verible 格式化
  → 最终 .v 文件（无标记）
```

### 1.3 两阶段交付

| 阶段 | 功能 | 命令 |
|------|------|------|
| **P1** | 增量 instance：只更新 instance 块的端口连接 | `rtl-auto inst` |
| **P2** | 全流程：instance + wire 声明 + 端口声明 + connect | `rtl-auto full` |

---

## 2. TOML 配置文件规格

### 2.1 完整示例

```toml
# rtl-auto 项目配置文件

[project]
name = "demo_soc"

# ---------------------------------------------------------------------------
# 顶层模块
# ---------------------------------------------------------------------------
[top]
module   = "soc_top"           # 顶层模块名
file     = "top/soc_top.v"     # 顶层文件路径（相对于配置文件）
output   = "top/soc_top.v"     # 输出文件（可与 file 相同，原地更新）

# ---------------------------------------------------------------------------
# 子模块列表
# ---------------------------------------------------------------------------
# 模块序号 = 列表索引（0-based）: 第1个=00, 第2个=01, ...
# 实例名 = u{模块序号:02d}_{子模块名}_{实例序号}
#
# 例：第1个子模块 sub_module，第1次例化 → u00_sub_module_0
#     第2个子模块 axi_slave，第1次例化  → u01_axi_slave_0
#     第2个子模块 axi_slave，第2次例化  → u01_axi_slave_1
# ---------------------------------------------------------------------------

[[submodules]]
module = "sub_module"          # 子模块名（Verilog module 名）
file   = "rtl/sub_module.v"    # 子模块源文件路径
update = true                  # 增量更新开关：true=本次执行时更新该模块的 instance
count  = 1                     # 例化次数（默认1），>1 时生成多个实例

[[submodules]]
module = "axi_slave"
file   = "rtl/axi_slave.v"
update = true
count  = 2                     # 例化2次：u01_axi_slave_0, u01_axi_slave_1

# params 按实例配置（可选）
# 不写 = 所有实例用子模块默认参数
# 和 wires 统一：inst 支持正则，rules 用数组格式 [["PARAM", val], ...]
[[params]]
insts = ["u01_axi_slave_0"]         # 支持正则：["~u01_axi_slave_.*"]
rules = [["DATA_W", 32], ["ADDR_W", 64]]

[[params]]
insts = ["u01_axi_slave_1"]
rules = [["DATA_W", 64], ["ADDR_W", 128]]

# ---------------------------------------------------------------------------
# 连线规则 (wires) — P2 阶段
# ---------------------------------------------------------------------------
# 核心思路：所有连线本质都是同一件事——
#   "某个实例的某个端口，接到什么信号上"
#
# scope 三种：
#   scope = "general"  全局默认设置（auto_match 开关）
#   scope = "inst"     按实例匹配端口，rules 用简洁数组格式
#   scope = "auto"     同名自动匹配（默认行为，general 里开关控制）
#
# rules 格式：[["端口名", "信号名模板"], ...]
#   - 信号名为常量（如 "1'b0"）→ 自动识别为 tie
#   - 信号名为空 ""             → 自动识别为 nc（悬空）
#   - 信号名为信号名/模板       → connect
# ---------------------------------------------------------------------------

# --- scope = "general"：全局默认设置（可选，有默认值） ---
[[wires]]
scope         = "general"
auto_match    = true         # 开启同名自动匹配（默认 true）

# --- scope = "inst"：按实例匹配端口 ---
# insts 支持正则（~ 前缀），放1个=精确，放多个=批量，用正则=模糊匹配

# 示例1: 多实例批量映射
[[wires]]
scope = "inst"
insts = ["u01_axi_slave_0", "u01_axi_slave_1"]
rules = [
    ["awaddr",  "m_axi_awaddr_{inst_idx}"],      # inst_idx=0→m_axi_awaddr_0
    ["awvalid", "m_axi_awvalid_{inst_idx}"],
    ["awready", "m_axi_awready_{inst_idx}"],
]

# 示例2: 单实例精确（替代旧 scope=port）
[[wires]]
scope = "inst"
insts = ["u00_sub_module_0"]
rules = [
    ["error", "1'b0"],           # 常量 → 自动 tie
    ["valid_in", ""],            # 空 → 自动 nc
    ["data_out", "ext_data"],    # 信号名 → connect
]

# 示例3: signal 模板里直接写后缀（不需要 postfix 字段）
[[wires]]
scope = "inst"
insts = ["u01_axi_slave_0"]
rules = [
    ["wdata", "m_axi_wdata_w"],       # 后缀 _w 直接写在信号名里
    ["~(aw|w|b).*", "m_axi_{port}_w"], # 正则批量加后缀
]

# 示例4: 正则匹配端口 + 正则匹配实例
[[wires]]
scope = "inst"
insts = ["~u01_axi_slave_.*"]   # 匹配 u01_axi_slave_0, u01_axi_slave_1
rules = [
    ["~aw.*", "m_axi_{port}_{inst_idx}"],
]

# --- 连线优先级（从高到低） ---
# 1. scope=inst (精确/批量匹配，后面的覆盖前面的)
# 2. scope=auto (同名自动匹配，受 general.auto_match 控制)
# 3. 未匹配的提升为顶层端口

# ---------------------------------------------------------------------------
# 全局配置（可选）
# ---------------------------------------------------------------------------
[options]
verible        = "verible-verilog-format"   # Verible 可执行文件路径
verible_flags  = "--inplace"                 # Verible 额外参数
emacs          = "emacs"                     # emacs 可执行文件路径
auto_format    = true                        # 展开后自动调用 Verible 格式化
```

> **注意**：上面的 TOML 示例省略了 `[[templates]]` 段，详见 2.3 节。

### 2.2 字段说明

#### `[project]`

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| name | string | ✅ | 项目名，用于日志和生成文件头注释 |

#### `[top]`

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| module | string | ✅ | 顶层 Verilog module 名 |
| file | string | ✅ | 顶层文件路径（相对配置文件） |
| output | string | ❌ | 输出路径，默认与 file 相同（原地更新） |

#### `[[submodules]]`（数组，可多条）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| module | string | ✅ | — | 子模块 Verilog module 名 |
| file | string | ✅ | — | 子模块源文件路径 |
| update | bool | ❌ | false | 增量更新开关 |
| count | int | ❌ | 1 | 例化次数 |
| inst_name | string | ❌ | 自动生成 | 手动指定实例名（覆盖自动规则） |

#### `[[params]]`（参数配置，可选，独立数组）

风格和 `[[wires]]` 统一，用 `insts` + `rules` 数组格式：

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| insts | string[] | ✅ | 实例名，支持正则（`~` 前缀） |
| rules | array[] | ✅ | `[["PARAM", val], ...]` 格式 |

> 不写 `[[params]]` = 所有实例用子模块默认参数。

**示例**：

```toml
# 两个实例不同参数
[[params]]
insts = ["u01_axi_slave_0"]
rules = [["DATA_W", 32], ["ADDR_W", 64]]

[[params]]
insts = ["u01_axi_slave_1"]
rules = [["DATA_W", 64], ["ADDR_W", 128]]

# 正则批量：所有 axi_slave 实例统一参数
[[params]]
insts = ["~u01_axi_slave_.*"]
rules = [["DATA_W", 32], ["ADDR_W", 64]]
```

#### `[[wires]]`（连线规则数组，P2 阶段）

所有连线统一用 `[[wires]]` 描述，通过 `scope` 区分类型：

**scope = "general"**（全局默认设置，可选，最多一条）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| scope | string | — | 固定 `"general"` |
| auto_match | bool | `true` | 是否开启同名自动匹配 |

**scope = "inst"**（按实例匹配端口）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| scope | string | ✅ | — | 固定 `"inst"` |
| insts | string[] | ✅ | — | 应用到哪些实例，支持正则（`~` 前缀） |
| rules | array[] | ✅ | — | 端口映射规则，数组格式 |

**rules 格式**：`[["端口名", "信号名"], ...]`

| 端口名写法 | 含义 |
|-----------|------|
| `"awaddr"` | 精确匹配端口名 |
| `"~aw.*"` | 正则匹配（`~` 前缀表示正则） |

**insts 格式**：`["实例名", ...]`，同样支持 `~` 正则

| insts 写法 | 匹配 |
|-----------|------|
| `"u01_axi_slave_0"` | 精确匹配 |
| `"~u01_axi_slave_.*"` | 正则匹配 u01_axi_slave_0, u01_axi_slave_1 |

| 信号名写法 | 自动识别为 | 示例 |
|-----------|-----------|------|
| 常量表达式 | tie（接常量） | `"1'b0"`, `"16'habcd"` |
| 空字符串 | nc（悬空） | `""` |
| 信号名/模板 | connect（接信号） | `"m_axi_awaddr_{inst_idx}"` |

**示例**：

```toml
# general: 全局默认
[[wires]]
scope      = "general"
auto_match = true

# inst: 多实例批量
[[wires]]
scope = "inst"
insts = ["u01_axi_slave_0", "u01_axi_slave_1"]
rules = [
    ["awaddr",  "m_axi_awaddr_{inst_idx}"],
    ["awvalid", "m_axi_awvalid_{inst_idx}"],
    ["~w.*",    "m_axi_{port}_{inst_idx}"],   # 正则
]

# inst: 单实例精确（tie/nc/connect）
[[wires]]
scope = "inst"
insts = ["u00_sub_module_0"]
rules = [
    ["error",    "1'b0"],      # tie
    ["valid_in", ""],           # nc
    ["data_out", "ext_data"],   # connect
]

# inst: 后缀直接写在 signal 模板里
[[wires]]
scope = "inst"
insts = ["u01_axi_slave_0"]
rules = [
    ["wdata", "m_axi_wdata_w"],          # 后缀 _w 直接写
    ["~(aw|w|b).*", "m_axi_{port}_w"],   # 正则批量加后缀
]
```

**连线优先级**（从高到低）：

```
1. scope=inst (精确/批量匹配，后面的 wires 段覆盖前面的)
2. scope=auto (同名自动匹配，受 general.auto_match 控制)
3. 未匹配的提升为顶层端口
```

**wire 名生成**：

| 场景 | wire 名来源 |
|------|-------------|
| scope=inst, connect | signal 模板替换后的值（后缀直接写在模板里） |
| scope=inst, tie/nc | 不需要 wire |
| scope=auto | 端口名（自动同名匹配，无需模板） |

**可用模板变量**：

| 变量 | 含义 | 示例值 |
|------|------|--------|
| `{port}` | 端口名 | `awready` |
| `{inst_idx}` | 实例在 insts 列表中的序号 | `0`, `1` |
| `{inst_name}` | 当前实例名 | `u01_axi_slave_0` |
| `{src_inst}` | 源实例名（output 端） | `u00_sub_module_0` |
| `{dst_inst}` | 目标实例名（input 端） | `u01_axi_slave_0` |
| `{src_module}` | 源模块名 | `sub_module` |
| `{dst_module}` | 目标模块名 | `axi_slave` |

#### `[options]`

| 字段 | 默认值 | 说明 |
|------|--------|------|
| verible | `"verible-verilog-format"` | Verible 可执行文件 |
| verible_flags | `"--inplace"` | Verible 参数 |
| emacs | `"emacs"` | emacs 可执行文件 |
| auto_format | `true` | 展开后自动格式化 |

---

## 3. 例化名生成规则

### 3.1 自动生成

```
u{模块序号:02d}_{子模块名}_{实例序号}
```

| 子模块在 TOML 中的位置 | 模块名 | 实例序号 | 生成的实例名 |
|:--:|------|:--:|------|
| 第1个 (index=0) | sub_module | 0 | `u00_sub_module_0` |
| 第1个 (index=0) | sub_module | 1 | `u00_sub_module_1` |
| 第2个 (index=1) | axi_slave | 0 | `u01_axi_slave_0` |
| 第2个 (index=1) | axi_slave | 1 | `u01_axi_slave_1` |
| 第3个 (index=2) | dma_core | 0 | `u02_dma_core_0` |

### 3.2 手动覆盖

在 TOML 中设置 `inst_name` 可覆盖自动规则：

```toml
[[submodules]]
module = "sub_module"
file   = "rtl/sub_module.v"
inst_name = "u_my_custom_name"   # 覆盖自动生成的名字
```

---

## 4. P1：增量 Instance 规格

### 4.1 功能定义

只更新 TOML 中 `update = true` 的子模块的 instance 块端口连接。其他 instance 块和顶层端口声明不动。

### 4.2 工作流程

```
1. 读取 TOML 配置
2. 解析顶层 .v 文件
3. 对每个 update=true 的子模块：
   a. 读取子模块 .v 文件
   b. 用 Python 括号匹配在顶层 .v 中定位 instance 块
      定位规则：正则匹配 "<module_name>\s+<inst_name>\s*\("
   c. 将 instance 块的端口连接区域替换为 /*AUTOINST*/
   d. 调用 emacs --batch verilog-batch-auto 展开
   e. 删除 /*AUTOINST*/ 及其他 AUTO 标记
4. 调用 Verible 格式化
5. 写回输出文件
```

### 4.3 Instance 块定位规则

**正则匹配**：`{module_name}\s+{inst_name}\s*\(`

示例：定位 `sub_module u00_sub_module_0 (`

```verilog
// 顶层 .v 文件中的 instance 块
sub_module u00_sub_module_0 (     ← 正则匹配到这里
    .clk        (clk),
    .rst_n      (rst_n),
    ...
);                                 ← 括号匹配找到结束位置
```

**括号匹配**：从 `(` 开始，深度计数，直到 `depth == 0` 的 `)`，后面的 `;` 为块结束。

### 4.4 标记临时加删

```
原始 instance 块:
    sub_module u00_sub_module_0 (
        .clk(clk), .rst_n(rst_n), ...
    );

加标记后:
    sub_module u00_sub_module_0 (
        /*AUTOINST*/
    );

verilog-mode 展开后:
    sub_module u00_sub_module_0 (
        /*AUTOINST*/
        // Outputs
        .data_out(data_out[7:0]),
        // Inputs
        .clk(clk), .rst_n(rst_n), ...
    );

删标记后（最终输出）:
    sub_module u00_sub_module_0 (
        // Outputs
        .data_out(data_out[7:0]),
        // Inputs
        .clk(clk), .rst_n(rst_n), ...
    );
```

### 4.5 多实例处理

当 `count > 1` 时：

```toml
[[submodules]]
module = "axi_slave"
file   = "rtl/axi_slave.v"
count  = 2
update = true
```

生成的顶层代码：

```verilog
axi_slave u01_axi_slave_0 (
    // ... 端口连接
);

axi_slave u01_axi_slave_1 (
    // ... 端口连接
);
```

每个实例独立定位、独立展开。

### 4.6 参数传递

当 `params` 存在时，instance 块包含 `#(...)` 参数覆盖：

```verilog
axi_slave #(
    .DATA_W(32),
    .ADDR_W(64)
) u01_axi_slave_0 (
    /*AUTOINST*/
);
```

---

## 5. P2：全流程方案规格

### 5.1 功能定义

从 TOML 配置生成完整的顶层模块：instance + wire 声明 + 端口声明 + connect。

### 5.2 工作流程

```
1. 读取 TOML 配置
2. 解析所有子模块 .v 文件，提取端口列表
3. 生成顶层 .v 文件骨架：
   a. module 声明 + 端口列表
   b. wire 声明区
   c. instance 块（带 /*AUTOINST*/ 标记）
4. 调用 emacs --batch verilog-batch-auto 全量展开
5. 应用 [[wires]] 连线规则（按优先级：inst > auto > 提升顶层）
6. 删除所有 AUTO 标记
7. 调用 Verible 格式化
8. 写回输出文件
```

### 5.3 连线规则（统一模型）

所有连线用 `[[wires]]` 描述，通过 `scope` 区分类型：

| 优先级 | scope | 匹配范围 | wire 名来源 |
|:------:|-------|----------|-------------|
| 1 | `inst` | 精确/批量匹配端口（rules 数组） | signal 模板替换 |
| 2 | `auto` | 同名自动匹配（受 general.auto_match 控制） | 端口名 |
| 3 | — | 未匹配的提升为顶层端口 | 不需要 wire |

### 5.4 rules 自动识别

rules 中第二个元素（信号名）自动识别动作：

| 信号名写法 | 自动识别为 | 生成代码 |
|-----------|-----------|---------|
| `"1'b0"`, `"16'habcd"` | tie | `.port(1'b0)` |
| `""` | nc | `.port()` |
| `"m_axi_awaddr_0"` | connect | `.port(m_axi_awaddr_0)` + 声明 wire |
| scope=auto | 端口名 | → `clk` |

### 5.5 Wire 声明

- scope=auto 的内部信号 → `wire [width] {端口名};`
- scope=inst 的信号 → `wire [width] {signal 模板替换结果};`
- scope=inst, tie → 不需要 wire（直接接常量）
- scope=inst, nc → 不需要 wire（悬空）
- TOML tie 的端口不需要额外 wire（直接接常量）
- TOML nc 的端口不需要 wire（悬空）

### 5.6 顶层端口声明

- 子模块的 input，未被任何规则匹配 → 提升为顶层 `input`
- 子模块的 output，未被任何规则匹配 → 提升为顶层 `output`
- TOML 中可通过 `top_ports` 额外添加顶层端口

---

## 6. 命令行接口

### 6.1 命令

```bash
# P1: 增量 instance
rtl-auto inst -c project.toml

# P1: 指定单个文件（不用 TOML）
rtl-auto inst -f top/soc_top.v --module sub_module --instance u00_sub_module_0

# P2: 全流程
rtl-auto full -c project.toml

# 检查（CI gate）：验证 instance 是否需要更新
rtl-auto check -c project.toml

# 显示配置
rtl-auto config -c project.toml
```

### 6.2 参数

| 参数 | 说明 |
|------|------|
| `-c, --config FILE` | TOML 配置文件路径 |
| `-f, --file FILE` | 直接指定 .v 文件（不需 TOML） |
| `--module NAME` | 子模块名（配合 -f 使用） |
| `--instance NAME` | 实例名（配合 -f 使用） |
| `--no-format` | 跳过 Verible 格式化 |
| `--dry-run` | 只输出到 stdout，不写文件 |
| `-v, --verbose` | 详细日志 |
| `-h, --help` | 帮助 |

---

## 7. 文件结构

```
rtl-auto/
├── bin/
│   └── rtl-auto              # 主入口脚本（Python）
├── src/
│   ├── config.py             # TOML 配置解析（通用）
│   ├── parser.py             # Verilog 文本操作：定位、标记注入/删除（通用）
│   ├── formatter.py          # Verible 格式化封装（通用）
│   ├── expander.py           # 后端调度层（薄层）
│   ├── generator.py          # 代码生成（P2: wire/端口/instance + wires 规则）
│   └── backends/             # AUTO 展开后端（可替换）
│       ├── base.py           # Backend 抽象接口
│       └── verilog_mode.py   # emacs verilog-mode 实现
├── config/
│   └── demo.toml             # 示例配置
├── test/
│   ├── rtl/                  # 测试用子模块
│   ├── top/                  # 测试用顶层
│   └── expected/             # 期望输出
├── Makefile                  # 集成示例
└── README.md
```

### 7.1 架构原则：配置与实现分离

```
                      TOML 配置（通用，不变）
                             │
               ┌─────────────┼─────────────┐
               │             │             │
            config.py    parser.py    formatter.py
          (通用 TOML)   (通用文本)   (通用 Verible)
               │             │
               └──────┬──────┘
                      │
                 bin/rtl-auto
               (流程编排，通用)
                      │
               expander.py  ← 薄调度层
                      │
         ┌────────────┴────────────┐
         │                         │
   backends/                 backends/
   verilog_mode.py           tree_sitter.py  (未来)
   avaiwire.py               纯 Python
         │                         │
    backends/base.py         backends/base.py
      (Backend 接口)          (同一接口)
```

- **配置层**（通用）：`config.py`, `parser.py`, `formatter.py` — TOML schema、文本操作、格式化，和后端无关
- **实现层**（可替换）：`backends/` 目录下的具体后端，通过 `Backend` 接口接入
- **调度层**（薄层）：`expander.py` 根据配置选择后端，只做转发

### 7.2 Backend 接口

```python
class Backend(ABC):
    name: str              # 后端名称

    def expand(self, verilog_file: str, library_dirs: list) -> str:
        """展开 AUTO 标记，原地修改文件，返回 stderr"""

    def check(self, verilog_file: str, library_dirs: list) -> bool:
        """检查是否需要展开，返回 True=需要更新"""
```

### 7.3 当前实现：verilog-mode

| 维度 | 详情 |
|------|------|
| **类名** | `VerilogModeBackend` |
| **依赖** | emacs-nox（verilog-mode 内置） |
| **原理** | 注入 `/*AUTOINST*/` + `/*AUTOWIRE*/` 标记 → emacs batch 展开 → 删除标记 |
| **优势** | verilog-mode 30 年打磨，成熟稳定 |
| **局限** | 需要 emacs (~150MB)，展开依赖正则而非完整语法树 |

### 7.4 未来候选后端

#### 方案 A：AutoWire（YAML 驱动）

| 维度 | 详情 |
|------|------|
| **依赖** | Python + PyVerilog + iverilog |
| **优势** | 协议 bundle 批量匹配（AXI/APB/AHB），YAML 配置即文档 |
| **替换工作** | 实现 `AutoWireBackend(Backend)`，调用 `autowire.py` |
| **风险** | PyVerilog 依赖 iverilog，安装较重 |

#### 方案 B：tree-sitter + 纯 Python

| 维度 | 详情 |
|------|------|
| **依赖** | Python + tree-sitter-verilog（pip 安装） |
| **优势** | 完整 SV 2017 CST 解析，无 iverilog/emacs 依赖，包体积小 |
| **替换工作** | 实现 `TreeSitterBackend(Backend)`，自写 instance 展开 + wire 生成逻辑 |
| **风险** | 需要自己实现生成逻辑（端口连接、wire 声明、顶层端口），开发量大 |

#### 方案 C：AutoWire + tree-sitter 混合

| 维度 | 详情 |
|------|------|
| **依赖** | Python + tree-sitter-verilog + PyVerilog（仅解析） |
| **优势** | tree-sitter 解析端口定义（轻量），AutoWire 做连线匹配（成熟） |
| **替换工作** | 实现 `HybridBackend(Backend)`，整合两端 |

### 7.5 换后端步骤

```python
# 1. 新建 backends/xxx.py，实现 Backend 接口
from .base import Backend

class XxxBackend(Backend):
    name = "xxx"
    def expand(self, verilog_file, library_dirs): ...
    def check(self, verilog_file, library_dirs): ...

# 2. 在 expander.py 注册
backends = {
    "verilog-mode": VerilogModeBackend(),
    "xxx":          XxxBackend(),         # 新增
}

# 3. (可选) TOML 配置支持
# [options]
# backend = "xxx"

# config.py, parser.py, formatter.py 完全不用改
```

---

## 8. 验收标准

### P1 验收

| # | 测试场景 | 预期结果 |
|---|---------|---------|
| 1 | 单模块 instance 更新 | instance 块端口连接正确展开，无 AUTO 标记残留 |
| 2 | 多模块 instance 更新 | update=true 的模块更新，update=false 的不动 |
| 3 | count>1 多实例 | 生成多个 instance，实例名序号正确 |
| 4 | params 按实例配置 | 不同实例包含不同 `#(.PARAM(val))` |
| 5 | Verible 格式化 | 输出通过 `verible-verilog-format --verify` |
| 6 | 增量不变检测 | 子模块未改时，输出文件内容不变 |

### P2 验收

| # | 测试场景 | 预期结果 |
|---|---------|---------|
| 1 | 全量生成 | 顶层 module + 端口 + wire + instance 完整 |
| 2 | auto 同名连接 | 两个 instance 的同名端口自动连 wire |
| 3 | rules tie 自动识别 | `["error", "1'b0"]` → 端口接常量 |
| 4 | rules nc 自动识别 | `["port", ""]` → 端口悬空 `()` |
| 5 | rules connect | `["port", "signal"]` → 连接到指定信号 |
| 6 | inst 多实例批量 | `insts` 多个实例，`{inst_idx}` 按序号替换 |
| 7 | insts 正则 | `["~u01_axi_.*"]` 匹配所有符合条件的实例 |
| 8 | rules 正则 | `"~aw.*"` 匹配所有 aw 开头端口 |
| 8 | signal 模板后缀 | `"m_axi_{port}_w"` 生成带后缀的 wire 名 |
| 9 | 优先级 | inst > auto > 提升顶层 |
| 10 | Verible 格式化 | 输出通过 `--verify` |

---

## 9. 依赖

| 依赖 | 版本 | 用途 | 能否离线 |
|------|------|------|---------|
| emacs-nox | ≥ 27 | verilog-mode batch 展开（系统包） | ✅ |
| python3 | ≥ 3.5 | 主程序（内置 TOML 解析器，零 pip 依赖） | ✅ |
| verible-verilog-format | latest | 格式化（可选，静态二进制） | ✅ 预下载 |

---

## 10. 不在本次范围内

| 功能 | 原因 |
|------|------|
| SystemVerilog interface/modport | verilog-mode 支持有限，后续版�� |
| 多级嵌套 hierarchy | 当前只支持单层 Top-Down |
| GUI 界面 | 团队级 CLI 工具 |

---

## 11. 端到端示例

### 11.1 输入文件

#### 子模块 `rtl/sub_module.v`

```verilog
module sub_module (
    input           clk,
    input           rst_n,
    input   [7:0]   data_in,
    input           valid_in,
    output  [7:0]   data_out,
    output          valid_out,
    output          error
);
    assign data_out  = data_in;
    assign valid_out = valid_in;
    assign error     = 1'b0;
endmodule
```

#### 子模块 `rtl/axi_slave.v`

```verilog
module axi_slave #(
    parameter DATA_W = 16,
    parameter ADDR_W = 32
) (
    input                       clk,
    input                       rst_n,
    input   [ADDR_W-1:0]        awaddr,
    input                       awvalid,
    output                      awready,
    input   [DATA_W-1:0]        wdata,
    output                      wready,
    output  [1:0]               bresp,
    output                      bvalid,
    input                       bready
);
    assign awready = awvalid;
    assign wready  = wvalid;
    assign bresp   = 2'b00;
    assign bvalid  = bready;
endmodule
```

#### 配置文件 `project.toml`

```toml
[project]
name = "demo_soc"

[top]
module = "soc_top"
file   = "top/soc_top.v"

# 子模块0: sub_module, 例化1次
[[submodules]]
module = "sub_module"
file   = "rtl/sub_module.v"
update = true
count  = 1

# 子模块1: axi_slave, 例化2次, 按实例配不同参数
[[submodules]]
module = "axi_slave"
file   = "rtl/axi_slave.v"
update = true
count  = 2

[[params]]
insts = ["u01_axi_slave_0"]
rules = [["DATA_W", 32], ["ADDR_W", 64]]

[[params]]
insts = ["u01_axi_slave_1"]
rules = [["DATA_W", 64], ["ADDR_W", 128]]

# --- 连线规则 (统一用 [[wires]]) ---

# general: 全局默认，开启同名自动匹配
[[wires]]
scope      = "general"
auto_match = true

# inst: 单实例精确（tie/nc）
[[wires]]
scope = "inst"
insts = ["u00_sub_module_0"]
rules = [
    ["error", "1'b0"],               # tie
]

[[wires]]
scope = "inst"
insts = ["u01_axi_slave_0"]
rules = [
    ["bready", ""],                  # nc
]

# inst: 多实例批量映射
[[wires]]
scope = "inst"
insts = ["u01_axi_slave_0", "u01_axi_slave_1"]
rules = [
    ["awaddr",  "m_axi_awaddr_{inst_idx}"],
    ["awvalid", "m_axi_awvalid_{inst_idx}"],
    ["awready", "m_axi_awready_{inst_idx}"],
]

# auto: 同名自动匹配（clk/rst_n），不用写规则，general.auto_match=true 自动处理

[options]
auto_format = true
```

### 11.2 P1 输出：增量 Instance

执行 `rtl-auto inst -c project.toml` 后，`top/soc_top.v` 中的 instance 块被更新：

```verilog
module soc_top (
    input           clk,
    input           rst_n,
    input   [7:0]   data_in,
    // ... 其他端口（P1 不动顶层端口声明）
);

// Instance: u00_sub_module_0 (sub_module)
sub_module u00_sub_module_0 (
    .clk        (clk),
    .rst_n      (rst_n),
    .data_in    (data_in),
    .valid_in   (valid_in),
    .data_out   (data_out),
    .valid_out  (valid_out),
    .error      (error)           // 已展开，无 /*AUTOINST*/ 标记
);

// Instance: u01_axi_slave_0 (axi_slave, DATA_W=32, ADDR_W=64)
axi_slave #(
    .DATA_W(32),
    .ADDR_W(64)
) u01_axi_slave_0 (
    .clk        (clk),
    .rst_n      (rst_n),
    .awaddr     (awaddr),
    .awvalid    (awvalid),
    .awready    (awready),
    .wdata      (wdata),
    .wready     (wready),
    .bresp      (bresp),
    .bvalid     (bvalid),
    .bready     (bready)
);

// Instance: u01_axi_slave_1 (axi_slave, DATA_W=64, ADDR_W=128)
axi_slave #(
    .DATA_W(64),
    .ADDR_W(128)
) u01_axi_slave_1 (
    .clk        (clk),
    .rst_n      (rst_n),
    .awaddr     (awaddr),
    .awvalid    (awvalid),
    .awready    (awready),
    .wdata      (wdata),
    .wready     (wready),
    .bresp      (bresp),
    .bvalid     (bvalid),
    .bready     (bready)
);

endmodule
```

> P1 只更新 instance 块的端口连接，顶层端口声明和 wire 声明不动。

### 11.3 P2 输出：全流程

执行 `rtl-auto full -c project.toml` 后，生成完整顶层模块：

```verilog
module soc_top (
    // 提升的顶层端口（未被连线规则匹配的子模块端口）
    input           clk,
    input           rst_n,
    input   [7:0]   data_in,
    input           valid_in,
    output  [7:0]   data_out,
    output          valid_out,
    // axi_slave 端口（未被 template 匹配的提升为顶层）
    input   [63:0]  wdata,          // DATA_W=32 → 但提升后用子模块位宽
    output          wready,
    output  [1:0]   bresp,
    output          bvalid,
    // template 生成的端口（多实例按序号区分）
    input   [63:0]  m_axi_awaddr_0, // 实例0
    input           m_axi_awvalid_0,
    output          m_axi_awready_0,
    input   [63:0]  m_axi_awaddr_1, // 实例1
    input           m_axi_awvalid_1,
    output          m_axi_awready_1
);

    // wire 声明（同名自动匹配）
    wire  clk;
    wire  rst_n;

    // Instance: u00_sub_module_0 (sub_module)
    sub_module u00_sub_module_0 (
        .clk        (clk),            // 同名自动匹配
        .rst_n      (rst_n),
        .data_in    (data_in),          // 提升顶层，不需要 wire
        .valid_in   (valid_in),
        .data_out   (data_out),
        .valid_out  (valid_out),
        .error      (1'b0)              // tie 规则
    );

    // Instance: u01_axi_slave_0 (axi_slave)
    axi_slave #(
        .DATA_W(32),
        .ADDR_W(64)
    ) u01_axi_slave_0 (
        .clk        (clk),
        .rst_n      (rst_n),
        .awaddr     (m_axi_awaddr_0),   // template 映射，inst_idx=0
        .awvalid    (m_axi_awvalid_0),
        .awready    (m_axi_awready_0),
        .wdata      (wdata),
        .wready     (wready),
        .bresp      (bresp),
        .bvalid     (bvalid),
        .bready     ()                  // nc 规则：悬空
    );

    // Instance: u01_axi_slave_1 (axi_slave)
    axi_slave #(
        .DATA_W(32),
        .ADDR_W(64)
    ) u01_axi_slave_1 (
        .clk        (clk),
        .rst_n      (rst_n),
        .awaddr     (m_axi_awaddr_1),   // template 映射，inst_idx=1
        .awvalid    (m_axi_awvalid_1),
        .awready    (m_axi_awready_1),
        .wdata      (wdata),
        .wready     (wready),
        .bresp      (bresp),
        .bvalid     (bvalid),
        .bready     (bready)
    );

endmodule
```

### 11.4 关键规则说明

| 规则 | 示例中的体现 |
|------|-------------|
| **例化名** | `u00_sub_module_0`（模块序号00 + 模块名 + 实例0） |
| **多实例** | `u01_axi_slave_0`、`u01_axi_slave_1`（count=2） |
| **params** | 实例0 `#(.DATA_W(32),.ADDR_W(64))`，实例1 `#(.DATA_W(64),.ADDR_W(128))`，按实例独立配置 |
| **tie** | `u00_sub_module_0.error → 1'b0` |
| **nc** | `u01_axi_slave_0.bready → ()` |
| **template** | `awaddr → m_axi_awaddr_{inst_idx}`（insts 列表中实例0→`m_axi_awaddr_0`） |
| **同名匹配** | `clk`/`rst_n` 两实例同名，自动连 `clk`/`rst_n`（wire 名 = 端口名） |
| **提升顶层** | `data_in`/`data_out` 未被规则匹配 → 提升为顶层端口 |
| **无标记** | 输出代码中无 `/*AUTOINST*/` 等任何 verilog-mode 标记 |
