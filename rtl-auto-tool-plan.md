# RTL Auto Instance & Connect — 方案比较

> 版本：v0.2（技术验证后更新）  
> 日期：2026-06-26  
> 状态：**待用户确认**

---

## 一、需求理解

| 维度 | 内容 |
|------|------|
| **目标用户** | 团队级（5人+），需要配置体系、CI 集成、错误处理 |
| **配置文件** | TOML，定义 hierarchy + 连线规则 + template + 增量控制 |
| **例化名规则** | 自动生成：`u{模块序号}_{子模块名}_{实例序号}`，如 `u0_sub_module_0` |
| **代码标记** | **生成的代码里不要 verilog-mode 标记**（`/*AUTOINST*/` 等） |
| **增量控制** | TOML 里显式指定哪些模块/实例需要更新 |
| **格式化** | Verible |
| **两阶段** | 先做增量 instance，再做全流程（instance + connect + wire） |

---

## 二、两个关键问题的技术验证结果

### 问题 1：tree-sitter-verilog 能否实现和 verilog-mode 一样的效果？

**结论：部分能，部分不能。**

| 能力 | tree-sitter-verilog | verilog-mode |
|------|:-------------------:|:------------:|
| **解析模块端口**（input/output/位宽/名称） | ✅ 已验证 | ✅ |
| **解析参数 parameter** | ✅ | ✅ |
| **自动展开 instance 端口连接** | ❌ 需自己写生成逻辑 | ✅ AUTOINST |
| **自动生成 wire 声明** | ❌ 需自己写 | ✅ AUTOWIRE |
| **自动生成顶层端口声明** | ❌ 需自己写 | ✅ AUTOINPUT/AUTOOUTPUT |
| **解析已有 instance 块** | ❌ 验证失败（解析混乱） | ⚠️ 有限 |

> **关键差异**：tree-sitter 只是一个**解析器**（告诉你语法树长什么样），verilog-mode 是**解析+生成器**（解析后还能自动生成代码）。如果用 tree-sitter，instance 展开、wire 声明、端口声明都得自己写 Python 生成逻辑。

### 问题 2：verilog-mode 标记可以"用的时候再加，用完删除"吗？

**结论：可以，已完整验证。**

验证流程（3 步）：

```
Step 1: Python 括号匹配定位 instance 块 → 替换为 /*AUTOINST*/
Step 2: emacs --batch → verilog-batch-auto 展开（自动填充端口连接）
Step 3: Python 删除 /*AUTOINST*/ 标记 → 干净的 Verilog 代码
```

**验证结果**：

```
输入（无标记）:
sub_module u_sub (
    .clk(clk), .rst_n(rst_n), ...
);

Step 1 加标记:
sub_module u_sub (
    /*AUTOINST*/
);

Step 2 verilog-mode 展开:
sub_module u_sub (
    /*AUTOINST*/
    // Outputs
    .data_out(data_out[7:0]),
    .valid_out(valid_out),
    // Inputs
    .clk(clk), .rst_n(rst_n), ...
);

Step 3 删标记（最终输出，无标记）:
sub_module u_sub (
    // Outputs
    .data_out(data_out[7:0]),
    .valid_out(valid_out),
    // Inputs
    .clk(clk), .rst_n(rst_n), ...
);
```

> ✅ 单文件 .v 方案完全可行，不需要 .vp 双文件。

---

## 三、更新后的方案对比

基于验证结果，方案更新为三个：

### 方案 A'：verilog-mode + Python 控制（标记临时加删，单文件）⭐推荐

```
干净 .v 文件                 Python 加标记               verilog-mode 展开           Python 删标记            Verible 格式化
┌──────────────┐           ┌──────────────┐           ┌──────────────┐           ┌──────────────┐        ┌──────────────┐
│ sub_module   │   Python  │ sub_module   │   emacs   │ sub_module   │   Python  │ sub_module   │  保留   │ sub_module   │
│  u_sub (     │  括号匹配  │  u_sub (     │  --batch  │  u_sub (     │  删除标记  │  u_sub (     │  ────→  │  u_sub (     │
│   .clk(clk)  │  ──────→  │   /*AUTOINST*/│  ──────→ │   /*AUTOINST*/│  ──────→  │   .clk(clk)  │  格式化  │   .clk(clk)  │
│  );          │           │  );          │           │   .clk(clk)  │           │  );          │        │  );          │
└──────────────┘           └──────────────┘           │  );          │           └──────────────┘        └──────────────┘
                                                      └──────────────┘
```

**增量控制**：TOML 指定 `update = true` → Python 只对这些模块做加标记→展开→删标记

| 维度 | 评价 |
|------|------|
| **标记问题** | ✅ 最终 .v 无标记（标记只在内存中临时存在） |
| **解析能力** | ✅ 利用 verilog-mode 成熟解析（30年打磨） |
| **生成能力** | ✅ instance + wire + 端口声明都能自动生成 |
| **增量精度** | ✅ Python 括号匹配精确定位 instance 块 |
| **例化名规则** | ✅ Python 生成实例名，verilog-mode 只管端口连接 |
| **依赖** | emacs-nox + python3 |
| **复杂度** | ⭐⭐ 中等（Python 做定位+清理，verilog-mode 做展开） |
| **全流程能力** | ✅ AUTOINST + AUTOWIRE + AUTOINPUT/AUTOOUTPUT 都能用同样方式 |
| **风险** | 低，核心技术点均已验证通过 |

### 方案 B：tree-sitter-verilog + 纯 Python 生成

```
子模块 .v             tree-sitter 解析           Python 生成             输出 .v
┌──────────────┐    ┌──────────────┐         ┌──────────────┐       ┌──────────────┐
│ module sub(  │    │ ports: [     │         │ sub_module   │       │ sub_module   │
│   input clk  │ →  │  {dir: in,   │  →      │  u0_sub_0 (  │  →    │  u0_sub_0 (  │
│   output o   │    │   name: clk, │         │   .clk(clk)  │       │   .clk(clk)  │
│ );           │    │   width: 1}, │         │  );          │       │  );          │
└──────────────┘    │  ...]        │         └──────────────┘       └──────────────┘
                    └──────────────┘
```

**增量控制**：TOML 指定 `update = true` → 只重新解析这些子模块 → Python 生成新 instance → 替换 .v 中的旧 instance 块

| 维度 | 评价 |
|------|------|
| **标记问题** | ✅ 完全无标记 |
| **解析能力** | ✅ 端口提取已验证可用 |
| **生成能力** | ❌ instance 展开、wire 声明、端口声明都得自己写 |
| **增量精度** | ✅ Python 控制替换 |
| **例化名规则** | ✅ 完全可控 |
| **依赖** | python3 + tree-sitter-verilog（pip 安装） |
| **复杂度** | ⭐⭐⭐ 高（需要自己写所有生成逻辑） |
| **全流程能力** | ⚠️ 需要自己实现 wire 声明和端口声明生成 |
| **风险** | 高，Verilog 语法边界情况多（generate、typedef、interface 等） |

### 方案 C：混合（verilog-mode 解析端口 + Python 生成代码）

| 维度 | 评价 |
|------|------|
| **标记问题** | ✅ 完全无标记 |
| **解析能力** | ✅ verilog-mode 解析 |
| **生成能力** | ⚠️ Python 生成，但需自己写 |
| **依赖** | emacs-nox + python3 |
| **复杂度** | ⭐⭐⭐ 高（两套技术栈，elisp 提取 API 不稳定） |
| **风险** | 高，elisp 提取端口的 API 不稳定 |

---

## 四、综合对比

| 维度 | 方案 A' (vm+Python标记加删) | 方案 B (tree-sitter+Python) | 方案 C (混合) |
|------|:-------------------------:|:--------------------------:|:-------------:|
| **无标记** | ✅ 标记临时存在 | ✅✅ 完全无标记 | ✅✅ 完全无标记 |
| **解析准确性** | ✅ verilog-mode | ✅ tree-sitter (端口) | ✅ verilog-mode |
| **生成能力** | ✅ verilog-mode 自�� | ❌ 自己写 | ⚠️ 自己写 |
| **例化名自动生成** | ✅ Python | ✅ Python | ✅ Python |
| **增量精度** | ✅ 括号匹配 | ✅ Python 控制 | ✅ Python 控制 |
| **全流程(instance+connect+wire)** | ✅ AUTO 机制天然支持 | ⚠️ 需大量自研 | ⚠️ 需部分自研 |
| **安装复杂度** | ⭐ emacs+python | ⭐ python only | ⭐⭐ emacs+python |
| **维护成本** | ⭐⭐ 低 | ⭐⭐⭐ 高 | ⭐⭐⭐ 高 |
| **技术验证** | ✅ 全部验证通过 | ⚠️ 端口提取可用，生成需自研 | ❌ elisp API 未验证 |

---

## 五、推荐

### 推荐方案 A'：verilog-mode + Python 控制（标记临时加删）

**理由**：

1. **技术风险最低**：所有关键环节均已验证通过
2. **生成能力最强**：verilog-mode 的 AUTOINST/AUTOWIRE/AUTOINPUT/AUTOOUTPUT 天然支持全流程，不需要自己写生成逻辑
3. **标记问题已解决**：标记只在内存中临时存在，最终 .v 文件完全无标记
4. **增量可控**：TOML 配置 + Python 括号匹配 = 精确的增量更新
5. **维护成本低**：核心展开逻辑由 verilog-mode 负责（30年打磨），Python 只做定位和清理

**与方案 B 的关键差异**：
- 方案 B 需要自己写 instance 展开、wire 声明、端口声明的生成逻辑——这是 verilog-mode 已经做好的事情
- 方案 A' 用 Python 做"加标记→展开→删标记"，相当于让 verilog-mode 在"无标记"的代码上工作

---

## 六、待确认问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | **你同意方案 A' 吗？**（verilog-mode + Python 标记临时加删，单文件，无标记残留） | 决定后续 Spec 方向 |
| 2 | **例化名规则 `u{模块序号}_{子模块名}_{实例序号}`** 中，"模块序号"是 TOML 中 submodules 列表的索引（0-based）吗？ | 影响命名规则 |
| 3 | **增量更新时，如何定位 .v 中要替换的 instance 块？** 推荐：用 `// @inst: u0_sub_module_0` 注释标记定位（不是 verilog-mode 标记，是工具自己的定位注释），还是用模块名+实例名正则匹配？ | 影响增量实现 |
| 4 | **全流程方案的"connect"** 是同名信号自动连？还是 TOML 里定义连线规则（如 tie/nc/map）？还是两者都要？ | 影响 P2 设计 |
