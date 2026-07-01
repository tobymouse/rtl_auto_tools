# RTL 自动 Instance & Connect 工具调研报告

> 调研日期：2026-06-26  
> 调研范围：Verilog / SystemVerilog 模块自动例化、端口自动连线、格式化兼容性

---

## 一、背景与问题定义

在 Verilog / SystemVerilog RTL 开发中，SoC 顶层集成是��复性最高、最容易出错的环节。典型痛点包括：

| 痛点 | 影响 |
|------|------|
| 手动编写 `module` 实例化代码 | 端口遗漏、位宽写错、方向搞反 |
| 模块间信号连接 | 成百上千根 `wire` 声明和端口映射，极其繁琐 |
| 子模块接口变更 | 需要手动更新所有上层例化代码 |
| 多个同类模块例化 | 重复劳动，且命名规则不统一 |
| 格式化工具冲突 | auto-instance 生成代码再被 formatter 改动，反复覆盖 |

---

## 二、现有方案全景图

```
┌────────────────────────────────────────────────────────────────────┐
│                    RTL Auto Instance & Connect 工具生态             │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│  编辑器集成   │  独立脚本/CLI │  语言服务器   │  包管理/构建系统      │
├──────────────┼──────────────┼──────────────┼───────────────────────┤
│ verilog-mode │ AutoWire     │ Verible LSP  │ FuseSoC              │
│  (Emacs)     │  (Python)    │  (C++/LSP)   │ Bender               │
│ SV-Tools     │ vlogai       │ sv-lsp       │                       │
│  (VSCode)    │  (Python)    │  (Rust/LSP)  │                       │
│ automatic-   │ svinst       │ svls         │                       │
│  verilog(Vim)│  (Python)    │  (Rust)      │                       │
│ TerosHDL     │              │              │                       │
│ Digital-IDE  │              │              │                       │
└──────────────┴──────────────┴──────────────┴───────────────────────┘
```

---

## 三、重点方案详细分析

### 3.1 Verilog-mode（Emacs）⭐⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **来源** | GNU Emacs 内置 / [veripool/verilog-mode](https://github.com/veripool/verilog-mode) |
| **语言** | Emacs Lisp |
| **定位** | Emacs 编辑器内的 Verilog 开发模式，AUTO 机制是核心 |
| **社区** | 非常成熟，GNU Emacs 内置，30+ 年历史，Veripool 维护 |

#### AUTO 机制核心能力

| AUTO 标记 | 功能 | 关键场景 |
|-----------|------|---------|
| `/*AUTOINST*/` | 自动生成子模块端口例化 | 模块例化核心功能 |
| `/*AUTOWIRE*/` | 自动声明模块间互连 wire | 子模块互连 |
| `/*AUTOARG*/` | 自动生成模块端口参数列表 | 模块声明 |
| `/*AUTO_TEMPLATE*/` | 批量例化的命名模板（支持正则、Lisp表达式） | 多实例/总线切片 |
| `/*AUTOINSTPARAM*/` | 自动填充 parameter 列表 | 参数化模块 |
| `/*AUTOINPUT*/` | 自动声明顶层输入端口 | Top 层集成 |
| `/*AUTOOUTPUT*/` | 自动声明顶层输出端口 | Top 层集成 |
| `/*AUTOREG*/` / `/*AUTOWIRE*/` | 自动 reg/wire 声明 | 信号声明 |
| `/*AUTORESET*/` | 自动复位赋值 | always 块 |

#### 工作原理
1. 在代码中插入 `/*AUTO...*/` 注释标记
2. `C-c C-a` 一键展开所有标记为实际代码
3. `C-c C-k` 可回退到标记状态
4. 支持命令行批量处理：`emacs --batch -l verilog-mode.el file.v -f verilog-auto -f save-buffer`

#### 模板系统（`AUTO_TEMPLATE`）亮点
```verilog
// 正则提取 + Lisp 计算
/* InstModule AUTO_TEMPLATE (
    .a(in[@"(+ (* 8 @) 7)":@"(* 8 @)"]),    // @=0→in[7:0], @=1→in[15:8]...
    .ptl_bus(PTL_BUSNEW[]),                   // []→自动展开为实际位宽
    );*/
```

#### 优势
- ✅ 功能最全面：instance + connect + wire + reg + arg 全覆盖
- ✅ 模板系统强大：正则 + Lisp 表达式，处理复杂命名规则
- ✅ 批量模式：可通过 CLI 集成到 CI/CD 流程
- ✅ 注释标记法：`/*AUTO*/` 是合法的 Verilog 注释，不影响 EDA 工具
- ✅ 成熟稳定：30+ 年历史，社区庞大

#### 劣势
- ❌ 强绑定 Emacs：非 Emacs 用户门槛高
- ❌ 解析基于正则，非完整语法树：复杂宏/条件编译可能出错
- ❌ 不支持 SystemVerilog interface 的 modport 自动连接（有限支持）
- ❌ Emacs Lisp 维护成本高，扩展性有限

#### 与 Formatter 兼容性
- ⚠️ **存在冲突**：AUTO 展开后代码若被 Verible/SV-Tools 等重新格式化，可能与 verilog-mode 的缩进风格不一致
- ⚠️ `AUTOSENSE` / `AUTORESET` 等行内标记展开后，formatter 可能破坏标记与内容的关联
- ✅ **推荐流程**：`AUTO 标记 → 展开 → formatter`（不可逆），或使用 `.vp→.v` 双文件策略

---

### 3.2 SV-Tools（VSCode）⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **来源** | [JayceVane/SV-Tools](https://github.com/JayceVane/SV-Tools) |
| **语言** | Rust (napi-rs) + VSCode Extension |
| **定位** | VSCode 一体化 Verilog/SV 开发工具 |
| **License** | Apache 2.0 |

#### 核心能力

| 功能 | 说明 |
|------|------|
| **Module Instantiation** | `Ctrl+Shift+C`：解析模块定义 → 生成例化代码 → 复制到剪贴板 |
| **Testbench Generation** | `Ctrl+Shift+T`：自动生成完整 testbench（含 clk/rst） |
| **Code Formatter** | 完整的 Verilog/SV 格式化引擎（端口对齐、信号对齐、always 缩进等） |
| **Code Alignment** | `Ctrl+Shift+X`：选中代码块智能对齐 |
| **Code Duplication** | `Ctrl+F12`：使用占位符批量生成编号代码 |
| **CLI 工具** | `svtools file.sv` 命令行格式化（独立于 VSCode） |

#### Instantiation 实现方式
- 解析当前文件的 `module ... (...)` 语法
- 自动识别 input/output/inout 端口
- 自动识别 clk/rst 信号（可配置关键词列表）
- input → reg 声明，output → wire 声明
- 可配置前缀（默认 `u_`）、端口声明开关、对齐风格

#### 优势
- ✅ **一体化**：instance + format + align + tb gen 在一个工具内
- ✅ **Rust 原生引擎**：速度快、零外部依赖（v3.0+）
- ✅ **自带 Formatter**：instance 生成的代码与 formatter 输出天然兼容
- ✅ CLI 支持：可集成到 CI/CD
- ✅ 活跃维护：2026 年持续更新

#### 劣势
- ❌ Instance 功能较基础：仅解析当前文件，不支持跨文件模块查找
- ❌ 无自动连线（auto-connect）：只生成 instance 模板，不生成 wire 和 connect
- ❌ 无模板系统：多实例命名规则需手动修改
- ❌ 解析深度有限：不支持完整的 SystemVerilog 语法树

---

### 3.3 AutoWire（独立 Python 工具）⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **来源** | [czz-zzc/autowire](https://github.com/czz-zzc/autowire) |
| **语言** | Python + PyVerilog |
| **定位** | SoC 集成场景的自动连线工具（顶层生成） |

#### 核心能力
- **YAML 配置文件驱动**：声明 rtl_path、instances、connections、bundle_con
- **协议信号批量匹配**：通过 `bundle.yaml` 定义 AXI/APB/AHB 等协议信号集
- **通配符连线**：`u_dma_core.axim_*` → `dma_axi4m_*` 批量映射
- **连线优先级**：协议连线 > 手动连线 > 同名自动匹配
- **位宽检查**：自动检测位宽不匹配并报错
- **参数传递**：支持 instance 级别 parameter 覆盖

#### 架构
```
YAML 配置 → ConfigManager → PyVerilog Parser → ConnectionManager → CodeGenerator → 顶层 .v 文件
```

#### 优势
- ✅ **协议感知**：bundle 机制适合总线型 SoC 集成
- ✅ **通配符批量匹配**：大幅减少配置量
- ✅ YAML 驱动：配置即文档，可版本管理
- ✅ 模块化设计：代码结构清晰，可扩展

#### 劣势
- ❌ 依赖 PyVerilog（需 iverilog）
- ❌ 生成的是完整顶层模块，非增量修改
- ❌ 配置文件格式自定义，学习成本
- ❌ 与 Formatter 无直接集成：生成的代码需单独格式化

---

### 3.4 vlogai（Python 库 + Vim 插件）⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **来源** | [taoyl/vlogai](https://github.com/taoyl/vlogai) |
| **语言** | Python + PyVerilog |
| **定位** | Python 库，配合 Vim 插件使用 |

#### 核心能力
- 跨文件模块查找（file list、incdir）
- 支持 SystemVerilog interface bundle
- 支持 parameter 和 macro
- 支持 instance 增量更新（检测 parameter/macro 变化）
- Vim 插件：`vim-vlogautoinst`

#### 优势
- ✅ 跨文件查找能力强
- ✅ 支持 interface bundle
- ✅ 可嵌入 Python 脚本工作流
- ✅ 增量更新机制

#### 劣势
- ❌ 2021 年后停止维护（31 commits）
- ❌ 依赖 PyVerilog（需要 iverilog）
- ❌ 无自动连线功能（仅 instance 生成）
- ❌ 无 formatter 集成

---

### 3.5 Verible（Google/CHIPS Alliance）⭐⭐⭐⭐

| 维度 | 详情 |
|------|------|
| **来源** | [chipsalliance/verible](https://github.com/chipsalliance/verible) |
| **语言** | C++ |
| **定位** | SystemVerilog 开发者工具套件（IEEE 1800-2017） |

#### 核心能力
| 工具 | 功能 |
|------|------|
| `verible-verilog-format` | 语法感知的代码格式化 |
| `verible-verilog-lint` | 风格检查（可配置规则集） |
| `verible-verilog-ls` | LSP 语言服务器 |
| `verible-verilog-syntax` | 语法树导出（JSON） |
| `verible-verilog-project` | 项目级工具 |

#### 关键特性
- ✅ **完整的 SystemVerilog 2017 解析器**（非正则，真正的 CST）
- ✅ LSP 支持所有兼容编辑器
- ✅ GitHub Actions 集成
- ✅ 增量格式化（只改修改过的行）
- ✅ CHIPS Alliance 维护，社区活跃（4000+ commits）
- ❌ **无 auto instantiation / auto connect 功能**
- ❌ 主要是格式化 + lint，不是 instance 生成工具

#### 与其他工具的关系
- Verible 是 **Formatter**，应与 Instance 生成工具**配合使用**而非替代
- 推荐流程：instance 工具生成代码 → Verible 格式化 → 交付

---

### 3.6 其他值得关注的工具

| 工具 | 类型 | 亮点 | 局限 |
|------|------|------|------|
| **svinst** | Python 解析器 | 纯解析：提取 module 定义和 instance 关系 | 只解析不生成，需自己写生成逻辑 |
| **tree-sitter-verilog** | 解析器库 | 完整 SystemVerilog 2017 语法树，可用于 Neovim/Helix | 仅解析器，不是 instance 工具 |
| **sv-lsp** | Rust LSP | 双引擎（tree-sitter 实时 + slang 全量），类型推断 | 尚无 instance 生成功能 |
| **svls** | Rust LSP | 轻量级 SystemVerilog 语言服务器 | 主要用于补全/diagnostics |
| **automatic-verilog** | Vim 插件 | Vimscript 实现，支持跨文件例化、always 块生成 | 基于正则，功能有限 |
| **TerosHDL** | VSCode 插件 | 一体化 IDE（编辑器 + 仿真 + 波形） | 较重，配置复杂 |
| **Digital-IDE** | VSCode 插件 | 国内开发者维护，含 LSP + formatter | 文档较少 |
| **FuseSoC** | 包管理/构建 | IP 核管理 + 依赖解析 + 构建脚本生成 | 面向项目构建，非 instance 生成 |
| **Bender** | 依赖管理 | Rust 实现，ETH PULP 平台开发 | 面向 IP 依赖，非 instance 生成 |
| **Verilog-Perl** | Perl 工具集 | vhier 可导出模块层级树 | Perl 生态老旧 |

---

## 四、技术路线对比

### 4.1 解析技术对比

| 解析方式 | 代表工具 | 优点 | 缺点 |
|----------|---------|------|------|
| **正则匹配** | verilog-mode, automatic-verilog | 快、无依赖 | 复杂语法（宏、generate）易出错 |
| **PyVerilog** | AutoWire, vlogai | 较完整语法支持 | 依赖 iverilog，安装重，解析有 bug |
| **tree-sitter** | sv-lsp, tree-sitter-verilog | 增量解析、容错好、IDE 友好 | 需要编写查询逻辑 |
| **slang** | sv-lsp (后端) | 完整 IEEE 2017，类型推断 | C++ 绑定，较重 |
| **Verible (自研)** | Verible | 完整 CST，格式化感知 | C++，无 instance 功能 |
| **手写解析器** | SV-Tools (Rust) | 轻量、针对性优化 | 语法覆盖不完整 |

### 4.2 连线能力对比

| 工具 | 仅 Instance | Instance + Wire | Auto Connect | 协议感知 | 模板系统 |
|------|:-----------:|:---------------:|:------------:|:--------:|:--------:|
| **verilog-mode** | ✅ | ✅ AUTOWIRE | ✅ 同名自动 | ❌ | ✅ AUTO_TEMPLATE |
| **SV-Tools** | ✅ | ✅ 局部 | ❌ | ❌ | ❌ |
| **AutoWire** | ✅ | ✅ | ✅ 通配符 | ✅ bundle.yaml | ❌ |
| **vlogai** | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## 五、Formatter 兼容性分析

### 5.1 主流 Formatter 对比

| Formatter | 语言 | 特点 | 实例化端口对齐 |
|-----------|------|------|:-------------:|
| **Verible** | C++ | IEEE 2017 语法感知，Google 风格 | ✅ |
| **SV-Tools** | Rust | 自有风格（源自 Sublime Text 插件） | ✅ |
| **istyle-verilog-formatter** | C++ | 开源，类似 astyle 风格 | ⚠️ 基础 |
| **verilog-format** | Python | 简单、轻量 | ❌ |

### 5.2 Instance 工具 + Formatter 兼容策略

```
推荐工作流（分层处理）：

  [源文件 .vp/.svp]          ← 保留 AUTO 标记
       │
       ▼
  [Instance 工具展开]        ← verilog-mode / AutoWire / SV-Tools
       │
       ▼
  [Formatter 格式化]         ← Verible / SV-Tools formatter
       │
       ▼
  [输出文件 .v/.sv]          ← 交付 EDA 工具
```

**关键原则**：
1. **Instance 生成和 Formatting 分步执行**，不要混在同一轮
2. **源文件保留标记**，生成文件用于工具链
3. **Formatter 选择**：若用 SV-Tools 做 instance，建议用 SV-Tools 自带的 formatter（内部一致性好）
4. **CI/CD 集成**：脚本串行调用 instance 工具 → formatter → lint

---

## 六、技术选型建议

### 按使用场景推荐

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| **个人开发 / Emacs 用户** | verilog-mode | 功能最全面，AUTO_TEMPLATE 强大 |
| **VSCode 用户 / 轻量需求** | SV-Tools | 一体化，自带 formatter |
| **SoC 顶层集成 / 协议总线** | AutoWire | bundle 协议匹配，YAML 驱动 |
| **团队协作 / CI 流程** | verilog-mode (batch) + Verible | 脚本化，可批量，LSP 支持 |
| **全新自研工具** | tree-sitter-verilog + Rust/Python | 现代解析器，可定制 |

### 自研工具的技术栈建议

如果你要做自己的 RTL auto instance & connect 工具，推荐技术路线：

```
┌────────────────────────────────────────────┐
│              推荐技术栈                      │
├────────────────────────────────────────────┤
│ 解析器：tree-sitter-verilog (完整 SV 语法)  │
│ 语言：  Rust（性能 + WASM 跨平台）           │
│         或 Python（快速原型 + PyO3 桥接）     │
│ 集成：  LSP Server（编辑器无关）             │
│         CLI 工具（CI/CD 集成）               │
│ 格式化：生成符合 Verible 风格的代码            │
│         或内置 formatter（学 SV-Tools）       │
│ 配置：  TOML/YAML 配置文件                   │
│         支持 inline 注释指令（学 verilog-mode）│
└────────────────────────────────────────────┘
```

#### 核心功能优先级建议

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 模块定义解析 | 跨文件 module 查找 |
| P0 | 基础 Instance 生成 | 端口例化代码生成 |
| P1 | 同名信号 Auto Connect | 自动匹配同名端口 |
| P1 | Wire/Reg 自动声明 | 根据方向自动声明 |
| P2 | 协议 Bundle 匹配 | 类似 AutoWire 的 bundle.yaml |
| P2 | 模板系统 | 多实例命名规则 |
| P2 | Parameter 传递 | 参数化模块支持 |
| P3 | Interface/modport 支持 | SV 特性 |
| P3 | Generate 块处理 | 复杂 SoC 场景 |
| P3 | Formatter 兼容输出 | 生成代码直接通过 Verible 检查 |

---

## 七、关键参考资料

| 资源 | 链接 |
|------|------|
| verilog-mode 官方 | https://www.veripool.org/verilog-mode/ |
| verilog-mode GitHub | https://github.com/veripool/verilog-mode |
| AutoWire GitHub | https://github.com/czz-zzc/autowire |
| SV-Tools GitHub | https://github.com/JayceVane/SV-Tools |
| vlogai GitHub | https://github.com/taoyl/vlogai |
| Verible GitHub | https://github.com/chipsalliance/verible |
| tree-sitter-verilog | https://github.com/tree-sitter/tree-sitter-verilog |
| sv-lsp GitHub | https://github.com/nktkt/sv-lsp |
| svinst GitHub | https://github.com/sgherbst/svinst |
| PyVerilog | https://github.com/PyHDI/Pyverilog |
| 知乎讨论：自动化连线工具 | https://www.zhihu.com/question/611007074 |
| verilog-mode 使用指南 | https://www.wenhui.space/docs/02-emacs/verilog_mode_useguide/ |

---

## 八、纯脚本方案验证 ✅

> **结论：verilog-mode batch + Verible 的纯脚本方案完全可行，已验证通过。**

### 8.1 环境依赖

```bash
# 只需要 emacs-nox（无 GUI），verilog-mode 已内置
sudo apt install emacs-nox

# Verible formatter（静态链接二进制，无依赖）
# 从 GitHub Releases 下载即可
```

### 8.2 已验证的完整流程

#### 源文件（保留 AUTO 标记）— `top_wrapper.vp`

```verilog
module top_wrapper (/*AUTOARG*/);
/*AUTOINPUT*/
/*AUTOOUTPUT*/
/*AUTOWIRE*/

sub_module u_sub (
    /*AUTOINST*/
);

endmodule
// Local Variables:
// verilog-library-directories:(".")
// End:
```

#### Step 1: verilog-mode AUTO 展开

```bash
cp top_wrapper.vp top_wrapper.v
emacs --batch --no-site-file top_wrapper.v -f verilog-batch-auto
```

#### Step 2: Verible 格式化

```bash
verible-verilog-format --inplace top_wrapper.v
```

#### Step 3 (可选): 验证格式化收敛

```bash
verible-verilog-format --verify top_wrapper.v  # exit 0 = 无需再格式化
```

### 8.3 CI/CD 集成命令

```makefile
# Makefile 示例
AUTO_SOURCES := $(wildcard *.vp)
GEN_SOURCES  := $(AUTO_SOURCES:.vp=.v)

%.v: %.vp
	cp $< $@
	emacs --batch --no-site-file $@ -f verilog-batch-auto
	verible-verilog-format --inplace $@

# 检查 AUTO 是否过期（CI gate）
check-auto:
	emacs --batch --no-site-file $(wildcard *.v) -f verilog-batch-diff-auto

# 完整流程
all: $(GEN_SOURCES)
```

### 8.4 验证结果总结

| 测试场景 | 结果 |
|----------|:----:|
| 基础 module instance + AUTOINST | ✅ |
| AUTOARG 自动端口列表 | ✅ |
| AUTOINPUT/AUTOOUTPUT 自动方向声明 | ✅ |
| `define 宏 + include 文件 | ✅ |
| parameter 参数化模块 | ✅ |
| Verible 格式化收敛性 (`--verify`) | ✅ |
| CI diff 检测 (`verilog-batch-diff-auto`) | ✅ |
| emacs --batch 无 GUI 运行 | ✅ |

### 8.5 方案的局限性

| 局限 | 影响 | 缓解方式 |
|------|------|---------|
| 需要 emacs-nox (~150MB) | CI 镜像增大 | 可接受，大多数 CI 已有 emacs |
| AUTO 展开 + 格式化后的文件**不可逆** | 不能再回退到 AUTO 标记 | 保留 `.vp` 源文件，`.v` 为生成文件 |
| 不支持 SystemVerilog interface/modport | 复杂 SV 项目受限 | 需自研或等 verilog-mode 更新 |
| 复杂 `ifdef 条件编译可能出错 | 多配置项目 | 用 `verilog-read-defines` 显式指定 |
| AUTO_TEMPLATE 正则较难调试 | 多实例命名 | 先在 Emacs GUI 调好再放入脚本 |

---

## 九、纯脚本双方案完整对比 ✅

> 两套方案均已实际跑通，并验证与 Verible 完全兼容。

### 9.1 环境依赖对比

| 依赖 | 方案 A: verilog-mode batch | 方案 B: AutoWire |
|------|---------------------------|-------------------|
| **运行时** | emacs-nox (~150MB 安装) | Python 3 + pip |
| **解析引擎** | Emacs Lisp 正则 (内置) | PyVerilog (pip) + iverilog |
| **额外安装** | 0 (verilog-mode 随 emacs 自带) | `pip install pyverilog pyyaml` + `apt install iverilog` |
| **安装复杂度** | ⭐ 极简 | ⭐⭐ 中等 |
| **总磁盘占用** | ~150MB | ~50MB (Python + iverilog) |

> ⚠️ **verilog-mode 必须装 emacs**：verilog-mode.el 深度依赖 Emacs 运行时（buffer、font-lock、regexp 引擎、文件访问 API），不存在独立的 elisp 解释器能跑它。好消息是只需要 `emacs-nox`（无 GUI），一个 apt 命令搞定。

### 9.2 功能对比

| 功能维度 | 方案 A: verilog-mode | 方案 B: AutoWire |
|----------|:--------------------:|:----------------:|
| **模块解析** | 跨文件正则匹配 | PyVerilog AST 解析 |
| **Instance 生成** | ✅ `AUTOINST` | ✅ YAML 配置驱动 |
| **自动连线** | ✅ `AUTOWIRE` 同名匹配 | ✅ 三级优先级（协议>手动>同名） |
| **协议 Bundle** | ❌ | ✅ `bundle.yaml` (AXI/APB/AHB) |
| **通配符匹配** | ❌ | ✅ `u_xxx.axim_*` |
| **模板系统** | ✅ `AUTO_TEMPLATE` (正则+Lisp) | ❌ |
| **端口列表** | ✅ `AUTOARG` | ✅ 自动生成 |
| **输入输出声明** | ✅ `AUTOINPUT/AUTOOUTPUT` | ✅ 自动生成 |
| **Parameter 传递** | ✅ `AUTOINSTPARAM` | ✅ YAML 配置 |
| **多实例命名** | ✅ 正则提取+Lisp 计算 | ❌ 需手动配置 |
| **位宽检查** | ⚠️ 基础 | ✅ 自动检测+报错 |
| **常量连接** | ⚠️ 手动 | ✅ YAML 配置 `16'habcd` |
| **SystemVerilog** | ⚠️ 有限 (无 interface) | ⚠️ 有限 (依赖 PyVerilog) |
| **增量更新** | ✅ diff-auto 检测 | ❌ 每次全量生成 |
| **源文件格式** | 注释标记 `/*AUTO*/` | YAML 配置文件 |

### 9.3 工作流对比

#### 方案 A: verilog-mode batch 流程

```
源文件 .vp  (保留 /*AUTOINST*/ /*AUTOWIRE*/ 等注释标记)
    │
    ├── cp top.vp top.v
    ├── emacs --batch top.v -f verilog-batch-auto   # AUTO 展开
    ├── verible-verilog-format --inplace top.v       # 格式化
    │
    ▼
输出 top.v  (交付)
```

**特点**：源文件即 Verilog 代码，AUTO 标记是合法注释，可直接在编辑器中查看。

#### 方案 B: AutoWire 流程

```
YAML 配置  (声明 rtl_path, instances, connections, bundle_con)
    │
    ├── python autowire.py -i project.yaml -o ./output -d
    ├── verible-verilog-format --inplace ./output/top.v
    │
    ▼
输出 top.v  (交付)
```

**特点**：配置与代码分离，适合 SoC 顶层集成。YAML 即文档。

### 9.4 与 Verible 兼容性验证

| 验证项 | 方案 A | 方案 B |
|--------|:------:|:------:|
| Verible 格式化成功 | ✅ | ✅ |
| 格式化后收敛 (`--verify` exit 0) | ✅ | ✅ |
| 端口声明对齐 | ✅ | ✅ |
| wire 声明对齐 | ✅ | ✅ |
| instance 端口对齐 | ✅ | ✅ |
| 参数对齐 | ✅ | ✅ |
| 格式化改动范围 | 缩进+对齐 (小) | 缩进+对齐+间距 (小) |

> **结论**：两种方案生成的代码经过 Verible 格式化后**完全收敛**，不会出现反复改动。

### 9.5 方案选择决策树

```
需要模板系统（多实例命名规则）？
├── YES → 方案 A: verilog-mode
└── NO  → 需要协议 bundle（AXI/APB 批量匹配）？
          ├── YES → 方案 B: AutoWire
          └── NO  → 哪种配置风格更适合你？
                    ├── 注释标记嵌入代码 → 方案 A
                    └── YAML 外部配置       → 方案 B
```

### 9.6 CI/CD 集成模板

#### 方案 A Makefile

```makefile
EMACS   := emacs --batch --no-site-file
VERIBLE := verible-verilog-format
VP_SRCS := $(wildcard *.vp)
V_SRCS  := $(VP_SRCS:.vp=.v)

%.v: %.vp
	cp $< $@
	$(EMACS) $@ -f verilog-batch-auto
	$(VERIBLE) --inplace $@

all: $(V_SRCS)

check:
	$(EMACS) $(V_SRCS) -f verilog-batch-diff-auto
	$(VERIBLE) --verify $(V_SRCS)

clean:
	rm -f $(V_SRCS)
```

#### 方案 B Makefile

```makefile
AUTOWIRE := python3 autowire.py
VERIBLE  := verible-verilog-format
CONFIGS  := $(wildcard *.yaml)

all:
	$(AUTOWIRE) -i project.yaml -o ./output -d
	$(VERIBLE) --inplace ./output/*.v

check:
	$(VERIBLE) --verify ./output/*.v
```

---

## 十、总结

1. **emacs 必须装**（方案 A）——verilog-mode.el 是 Emacs Lisp，不存在独立运行时。但只需 `emacs-nox`（无 GUI），一个 apt 命令，CI 友好。

2. **方案 A (verilog-mode batch + Verible)** 适合：需要模板系统、注释标记风格、轻量安装、跨文件自动查找。

3. **方案 B (AutoWire + Verible)** 适合：SoC 顶层集成、协议总线批量连线、配置即文档、不依赖 Emacs 生态。

4. 两套方案与 Verible **完全兼容**，均通过格式化收敛验证。

5. 如果两个都不够用（如 SystemVerilog interface/modport），再考虑基于 tree-sitter-verilog 自研。
