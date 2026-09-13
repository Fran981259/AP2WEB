"""Read-only structural inventory; prints JSON, never imports application code.

Usage: python scripts/audit_structure.py
AST branch counts are a complexity proxy, not formal McCabe complexity.
Duplicate bodies and missing inbound imports are review candidates, not proof
that code can be deleted (entrypoints, decorators and dynamic imports exist).
"""
from __future__ import annotations

import ast
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache",
           ".pytest_cache", ".ruff_cache", "dist"}
TEXT = {".py", ".js", ".jsx", ".css", ".md", ".txt", ".toml", ".ini",
        ".yml", ".yaml", ".sh"}


def inventory(root: Path = ROOT) -> dict:
    files = []
    duplicates = defaultdict(list)
    bodies = defaultdict(list)
    functions = []
    imports = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(p in EXCLUDE for p in rel.parts) or not path.is_file() or path.is_symlink():
            continue
        row = {"path": rel.as_posix(), "bytes": path.stat().st_size}
        if path.suffix in TEXT:
            content = path.read_bytes()
            row["sha256"] = hashlib.sha256(content).hexdigest()
            row["lines"] = len(content.splitlines())
            if content.strip():
                duplicates[row["sha256"]].append(row["path"])
            if path.suffix == ".py":
                tree = ast.parse(content, filename=str(rel))
                imports[row["path"]] = sorted({
                    ("." * n.level + (n.module or "")) if isinstance(n, ast.ImportFrom)
                    else a.name
                    for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                    for a in (n.names if isinstance(n, ast.Import) else [None])
                })
                for n in ast.walk(tree):
                    if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    body = list(n.body)
                    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                        body = body[1:]
                    location = f"{rel}:{n.lineno}:{n.name}"
                    span = n.end_lineno - n.lineno + 1
                    if span >= 8:
                        fingerprint = ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)
                        bodies[hashlib.sha256(fingerprint.encode()).hexdigest()].append(location)
                    branches = sum(isinstance(x, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                                                   ast.IfExp, ast.comprehension)) for x in ast.walk(n))
                    functions.append({"location": location, "lines": span, "branch_proxy": branches})
        files.append(row)
    return {
        "excluded_directory_names": sorted(EXCLUDE),
        "file_count": len(files),
        "files": files,
        "python_imports": imports,
        "largest_functions": sorted(functions, key=lambda x: x["lines"], reverse=True)[:25],
        "exact_duplicate_files": [v for v in duplicates.values() if len(v) > 1],
        "duplicate_python_bodies": [v for v in bodies.values() if len(v) > 1],
    }


if __name__ == "__main__":
    print(json.dumps(inventory(), ensure_ascii=False, indent=2))
