#!/usr/bin/env python
"""Generate MkDocs API reference pages from source docstrings via AST."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "provara"
DOCS_ROOT = REPO_ROOT / "docs" / "api-reference"

MODULE_FILES = [
    "__init__.py",
    "cli.py",
    "scitt.py",
    "timestamp.py",
    "privacy.py",
    "sync_v0.py",
    "wallet.py",
]


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts: list[str] = []
    args = node.args
    all_args = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(all_args) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(all_args, defaults):
        piece = arg.arg
        if arg.annotation is not None:
            piece += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            piece += f" = {ast.unparse(default)}"
        parts.append(piece)
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        piece = arg.arg
        if arg.annotation is not None:
            piece += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            piece += f" = {ast.unparse(default)}"
        parts.append(piece)
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")
    sig = ", ".join(parts)
    ret = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
    return f"({sig}){ret}"


def _iter_public_functions(nodes: Iterable[ast.stmt]) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            yield node


def _iter_public_classes(nodes: Iterable[ast.stmt]) -> Iterable[ast.ClassDef]:
    for node in nodes:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            yield node


def _module_page(file_name: str) -> str:
    path = SRC_ROOT / file_name
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_name = "provara" if file_name == "__init__.py" else file_name.replace(".py", "")

    lines = [f"# `{module_name}`", "", ast.get_docstring(tree) or "No module docstring provided.", ""]

    functions = list(_iter_public_functions(tree.body))
    if functions:
        lines.extend(["## Functions", ""])
        for func in functions:
            doc = ast.get_docstring(func) or "No docstring provided."
            lines.extend([f"### `{func.name}{_format_signature(func)}`", "", doc, ""])

    classes = list(_iter_public_classes(tree.body))
    if classes:
        lines.extend(["## Classes", ""])
        for cls in classes:
            lines.extend([f"### `{cls.name}`", "", ast.get_docstring(cls) or "No class docstring provided.", ""])
            for node in cls.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                    doc = ast.get_docstring(node) or "No docstring provided."
                    lines.extend([f"#### `{cls.name}.{node.name}{_format_signature(node)}`", "", doc, ""])

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    modules_dir = DOCS_ROOT / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)

    index_lines = [
        "# API Reference",
        "",
        "These pages are auto-generated from Python module docstrings.",
        "",
    ]

    for file_name in MODULE_FILES:
        slug = "provara" if file_name == "__init__.py" else file_name.replace(".py", "")
        out = modules_dir / f"{slug}.md"
        out.write_text(_module_page(file_name), encoding="utf-8")
        index_lines.append(f"- [{slug}](modules/{slug}.md)")

    DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    (DOCS_ROOT / "index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
