#!/usr/bin/env python3
"""一次性 built≠wired 接线审计 (2026-09-05, 恢复期 backlog P0 #1).

对应:
  - discussions/2026-09-05-CogMirror迁移适用性分析-与built-unwired接线审计.md §二
  - README §下一步 P0「全量 built≠wired 接线审计」

扫描 ecos/ 包内所有 class method / module function, 按三层分类:
  Tier A 死代码候选: 全仓 (ecos+web+scripts+examples+tests) 无任何引用
  Tier B 产品路径未接线: 仅 tests/ (或 examples/) 引用, ecos/ + web/ 产品路径零调用
  Tier C 公开 API: 名字出现在任一模块 __all__ 导出 → 仓库内无 caller 属合法
                   (ecos 是 pip 包 + Plugin SDK, 公开 API 本就不该有仓内 caller)

附加扫描: self.X = ClassName() 实例化后, self.X.<attr> 是否在本模块被再次引用
(抓 BjorkSpacingEffect 型 "实例化未调用")。

已知局限 (结果需人工复核, 本脚本是审计初筛不是结论):
  - 方法名匹配为名字级 (同名跨类共享, 如 update/compute), 同名方法会互相"救活"
  - 子类 override 不算调用; getattr(obj, "name") 字符串引用不算
  - 语义级接线 (引擎存在但未注入, 如 Evidence/Event Engine 未进答题流) 不在
    本扫描范围, 属人工审计范畴 (已知实例 ③ 即此类)
  - Flask route / plugin on_event 等框架分发入口已按装饰器豁免, 但豁免可能过宽

用法: python scripts/wiring_audit.py [--json OUT.json]
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_log = logging.getLogger("wiring_audit")

REPO = Path(__file__).resolve().parent.parent

# 被审计对象 (定义所在): ecos/ 包
DEF_ROOTS = [REPO / "ecos"]
# 引用语料: 产品路径 (ecos + web) + 测试/示例/脚本
PRODUCT_ROOTS = [REPO / "ecos", REPO / "web"]
AUX_ROOTS = [REPO / "tests", REPO / "examples", REPO / "scripts"]
# prototypes/ 为归档原型, 不计入语料 (引用它不算接线)

# 框架分发装饰器 (函数由框架调用, 仓内无 caller 属正常)
FRAMEWORK_DECORATOR_PATTERNS = ("route", "app.route", "get", "post", "put",
                                "patch", "delete", "command", "event_handler",
                                "subscriber", "register")


@dataclass
class DefSite:
    qualname: str          # module:Class.method / module:function
    name: str              # 裸名
    file: str              # repo 相对路径
    is_method: bool
    is_private: bool       # _前缀 (非 dunder)
    is_dunder: bool
    is_exported: bool      # 名字出现在任一模块 __all__
    is_framework_entry: bool  # 框架装饰器豁免
    line: int


@dataclass
class Report:
    tier_a: list = field(default_factory=list)   # 死代码候选
    tier_b: list = field(default_factory=list)   # 产品路径未接线
    tier_c_unref: list = field(default_factory=list)  # 公开 API 且仓内零引用 (合法, 登记)
    orphan_attrs: list = field(default_factory=list)  # self.X=ClassName() 后 self.X. 未再引用


def _py_files(roots: list[Path]) -> list[Path]:
    out = []
    for root in roots:
        if not root.exists():
            continue
        out.extend(sorted(root.rglob("*.py")))
    return out


def _module_path(p: Path) -> str:
    return str(p.relative_to(REPO)).replace("/", ".").removesuffix(".py")


def _iter_all_names(tree: ast.Module) -> set[str]:
    """收集模块 __all__ 导出的裸名 (Tier C 判定源)."""
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    for elt in node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else []:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            names.add(elt.value)
    return names


def _has_framework_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        # @app.route(...) → Attribute; @something → Name; @app.route → Attribute
        parts = []
        d = dec.func if isinstance(dec, ast.Call) else dec
        while isinstance(d, ast.Attribute):
            parts.append(d.attr)
            d = d.value
        if isinstance(d, ast.Name):
            parts.append(d.id)
        joined = ".".join(reversed(parts))
        if any(p in FRAMEWORK_DECORATOR_PATTERNS for p in parts) or any(
            joined.endswith(pat) for pat in FRAMEWORK_DECORATOR_PATTERNS
        ):
            return True
    return False


def collect_defs() -> tuple[list[DefSite], set[str]]:
    """收集 ecos/ 内所有函数/方法定义 + 全仓 __all__ 导出名集合."""
    exported: set[str] = set()
    defs: list[DefSite] = []

    files = _py_files(DEF_ROOTS)
    parsed: dict[Path, ast.Module] = {}
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            _log.warning("解析失败 %s: %s (跳过)", f, exc)
            continue
        parsed[f] = tree
        exported |= _iter_all_names(tree)

    for f, tree in parsed.items():
        mod = _module_path(f)

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.class_stack: list[str] = []

            def _add(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                if node.name.startswith("__") and node.name.endswith("__"):
                    dunder, private = True, False
                elif node.name.startswith("_"):
                    dunder, private = False, True
                else:
                    dunder, private = False, False
                cls = self.class_stack[-1] if self.class_stack else None
                qualname = f"{mod}:{'.'.join(self.class_stack)}.{node.name}" if cls else f"{mod}:{node.name}"
                defs.append(DefSite(
                    qualname=qualname, name=node.name,
                    file=str(f.relative_to(REPO)), line=node.lineno,
                    is_method=cls is not None, is_private=private, is_dunder=dunder,
                    is_exported=node.name in exported,
                    is_framework_entry=_has_framework_decorator(node),
                ))

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node) -> None:
                self._add(node)
                # 嵌套函数不单独审计 (闭包内定义必被本函数引用)
                self.class_stack.append(f"<fn:{node.name}>")
                self.generic_visit(node)
                self.class_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

        Visitor().visit(tree)

    return defs, exported


def collect_refs() -> dict[str, dict[str, set[str]]]:
    """收集引用语料: name -> {'product': {files}, 'aux': {files}, 'defsite': {files}}."""
    refs: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"product": set(), "aux": set()})

    def scan(files: list[Path], bucket: str) -> None:
        for f in files:
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                _log.warning("解析失败 %s: %s (跳过)", f, exc)
                continue
            rel = str(f.relative_to(REPO))
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    refs[node.id][bucket].add(rel)
                elif isinstance(node, ast.Attribute):
                    refs[node.attr][bucket].add(rel)

    scan(_py_files(PRODUCT_ROOTS), "product")
    scan(_py_files(AUX_ROOTS), "aux")
    return refs


def scan_orphan_instance_attrs() -> list[dict]:
    """抓 self.X = ClassName() 后, 本模块内 self.X.<attr> 再无引用 (BjorkSpacingEffect 型).

    只看类构造/工厂调用 (排除 int()/float()/list() 等内建标量初始化)。
    注意: 只查本模块, 属性被外部文件访问 (engine.X.foo) 不在此列 → 报告时需跨文件复核。
    """
    BUILTIN_FACTORIES = {
        "int", "float", "bool", "str", "list", "dict", "set", "tuple",
        "max", "min", "len", "abs", "sum", "round", "sorted", "frozenset",
        "np", "numpy",
    }
    findings = []
    for f in _py_files(DEF_ROOTS):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            _log.warning("解析失败 %s: %s (跳过)", f, exc)
            continue
        rel = str(f.relative_to(REPO))
        # 第一遍: 找 self.X = SomeClass() 赋值 (类名大写开头或 get_* 工厂, 排除内建)
        assigned: dict[str, tuple[int, str]] = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Attribute)
                    and isinstance(node.targets[0].value, ast.Name)
                    and node.targets[0].value.id == "self"
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)):
                func_name = node.value.func.id
                if func_name in BUILTIN_FACTORIES:
                    continue
                if not (func_name[0].isupper() or func_name.startswith("get_")):
                    continue
                attr = node.targets[0].attr
                assigned.setdefault(attr, (node.lineno, func_name))
        if not assigned:
            continue
        # 第二遍: 统计本模块内 self.X 的全部出现 (含构造器注入 l1=self.X / 方法调用 self.X.foo)
        # 出现次数 == 作为赋值目标次数 → 每次出现都是赋值 → 孤儿
        occurrences: dict[str, int] = defaultdict(int)
        assign_targets: dict[str, int] = defaultdict(int)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id == "self"):
                occurrences[node.attr] += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                            and target.value.id == "self"):
                        assign_targets[target.attr] += 1
        for attr, (line, cls) in assigned.items():
            if occurrences.get(attr, 0) <= assign_targets.get(attr, 0):
                findings.append({
                    "file": rel, "line": line, "attr": f"self.{attr}",
                    "class": cls, "note": f"实例化 self.{attr} = {cls}() 后, 本模块无任何再引用 (含构造器注入)",
                })
    return findings


def classify(defs: list[DefSite], refs: dict[str, dict[str, set[str]]]) -> Report:
    rep = Report()
    for d in defs:
        if d.is_dunder or d.is_framework_entry:
            continue
        r = refs.get(d.name, {"product": set(), "aux": set()})
        # 定义文件本身的引用不算 (定义处 Name 不产生, 但同文件可能既有定义又有真调用;
        # 名字级初筛保留同文件引用, 人工复核时区分)
        product_refs = r["product"]
        aux_refs = r["aux"]
        has_product = bool(product_refs)
        has_aux = bool(aux_refs)

        entry = {
            "qualname": d.qualname, "file": d.file, "line": d.line,
            "is_method": d.is_method, "is_private": d.is_private,
            "product_refs": sorted(product_refs), "aux_refs": sorted(aux_refs)[:5],
        }
        if not has_product and not has_aux:
            if d.is_exported:
                rep.tier_c_unref.append(entry)
            else:
                rep.tier_a.append(entry)
        elif not has_product and has_aux:
            # 仅 tests/examples 引用: 无论是否 __all__ 导出, 语义都是"产品路径未接线"
            # (导出只解释合法性, 不改变接线事实)
            entry["is_exported"] = d.is_exported
            rep.tier_b.append(entry)
        # has_product → wired, 不登记
    return rep


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="结果 JSON 输出路径")
    args = parser.parse_args()

    _log.info("收集 ecos/ 定义 ...")
    defs, exported = collect_defs()
    _log.info("  %d 个函数/方法定义, %d 个 __all__ 导出名", len(defs), len(exported))

    _log.info("收集全仓引用语料 (product: ecos+web / aux: tests+examples+scripts) ...")
    refs = collect_refs()

    _log.info("分类 ...")
    rep = classify(defs, refs)

    _log.info("附加扫描: 实例化未调用 (self.X = Cls() 后 self.X. 无访问) ...")
    rep.orphan_attrs = scan_orphan_instance_attrs()

    _log.info("=" * 70)
    _log.info("Tier A 死代码候选 (全仓零引用, 非导出): %d", len(rep.tier_a))
    for e in rep.tier_a:
        _log.info("  A  %s:%d", e["file"], e["line"])
    _log.info("Tier B 产品路径未接线 (仅 tests/examples 引用): %d", len(rep.tier_b))
    for e in rep.tier_b:
        _log.info("  B  %s:%d  (aux: %s)", e["file"], e["line"], ",".join(e["aux_refs"][:3]))
    _log.info("Tier C 公开 API 且仓内零引用 (合法, 登记): %d", len(rep.tier_c_unref))
    _log.info("孤儿实例属性 (实例化未调用): %d", len(rep.orphan_attrs))
    for e in rep.orphan_attrs:
        _log.info("  O  %s:%d  %s", e["file"], e["line"], e["note"])
    _log.info("=" * 70)
    _log.info("注意: Tier A/B 为名字级初筛, 需人工复核 (同名跨类互救 / 子类 override 不算调用)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tier_a": rep.tier_a, "tier_b": rep.tier_b, "tier_c_unref": rep.tier_c_unref,
            "orphan_attrs": rep.orphan_attrs,
        }
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _log.info("JSON 结果: %s", args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
