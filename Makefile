# =============================================================================
# rtl-auto — RTL Auto Instance & Connect Tool
# =============================================================================
# 
# 依赖:
#   - emacs-nox (verilog-mode 内置)
#   - python3
#   - verible-verilog-format (可选，推荐)
#
# 用法:
#   make inst     —  P1: 增量 instance + wire + params（入 place）
#   make full     —  P2: 全流程生成（输出到独立文件）
#   make check    —       CI gate
#   make test     —       P1 + P2 自测
#   make clean    —       清理
# =============================================================================

PYTHON := python3
VERIBLE := verible-verilog-format
TOOL    := $(PYTHON) bin/rtl-auto

# =============================================================================
# P1: 增量 instance — 更新 TOML 中 update=true 的模块
#     原地修改 test/top/soc_top.v
# =============================================================================
.PHONY: inst
inst:
	$(TOOL) inst -c demo.toml

# =============================================================================
# P2: 全流程生成 — 从零生成完整顶层模块
#     输出到 test/top/soc_top_p2.v（和 P1 隔离）
# =============================================================================
.PHONY: full
full:
	$(TOOL) full -c demo_full.toml

# =============================================================================
# CI gate
# =============================================================================
.PHONY: check
check:
	$(TOOL) check -c demo.toml

# =============================================================================
# 显示配置
# =============================================================================
.PHONY: config
config:
	$(TOOL) config -c demo.toml

# =============================================================================
# P1 自测：恢复原文件 → 增量 instance → Verible 验证
# =============================================================================
.PHONY: test-p1
test-p1: restore
	$(TOOL) inst -c demo.toml
	$(VERIBLE) --verify test/top/soc_top.v
	@echo "[OK] P1 test passed"

# =============================================================================
# P2 自测：全流程生成 → 打印总结 → Verible 验证
# =============================================================================
.PHONY: test-p2
test-p2:
	$(TOOL) full -c demo_full.toml
	$(VERIBLE) --verify test/top/soc_top_p2.v
	@echo "[OK] P2 test passed"

# =============================================================================
# 完整自测
# =============================================================================
.PHONY: test
test: test-p1 test-p2
	@echo "[OK] All tests passed"

# =============================================================================
# 恢复测试文件为原始状态
# =============================================================================
.PHONY: restore
restore:
	cp test/top/soc_top.orig test/top/soc_top.v

# =============================================================================
# 清理
# =============================================================================
.PHONY: clean
clean:
	rm -f test/top/soc_top.v.tmp
	rm -f test/top/soc_top_auto.v
	rm -rf __pycache__ src/__pycache__

# =============================================================================
# 帮助
# =============================================================================
.PHONY: help
help:
	@echo "rtl-auto — RTL Auto Instance & Connect Tool"
	@echo ""
	@echo "P1:"
	@echo "  make inst     增量更新 instance + wire + params"
	@echo "P2:"
	@echo "  make full     从零生成完整顶层模块"
	@echo "验证:"
	@echo "  make check    CI gate"
	@echo "  make test-p1  P1 自测"
	@echo "  make test-p2  P2 自测"
	@echo "  make test     完整自测"
	@echo "工具:"
	@echo "  make restore  恢复原文件"
	@echo "  make config   查看配置"
	@echo "  make clean    清理"
