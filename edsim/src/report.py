"""
report.py -- output plumbing and PROVENANCE.

Every result this project publishes must be traceable back to the exact command
that produced it.  Each runner script opens an :class:`Artifact` context, which

  * creates results/{tables,figures,raw}/ if needed,
  * stamps every table it writes with a header comment naming the script, the
    command line, the seeds and the replication count,
  * writes a machine-readable ``results/raw/<script>.manifest.json``,
  * appends a human-readable entry to ``results/PROVENANCE.md``.

So for any figure or CSV in results/, ``results/PROVENANCE.md`` says which
script made it, when, with which arguments, and how much simulation it cost.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
TABLES = os.path.join(RESULTS, "tables")
FIGURES = os.path.join(RESULTS, "figures")
RAW = os.path.join(RESULTS, "raw")
PROVENANCE = os.path.join(RESULTS, "PROVENANCE.md")


def ensure_dirs() -> None:
    for d in (RESULTS, TABLES, FIGURES, RAW):
        os.makedirs(d, exist_ok=True)


def _jsonable(o: Any):
    if is_dataclass(o) and not isinstance(o, type):
        return {k: _jsonable(v) for k, v in asdict(o).items()}
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


class Artifact:
    """Context manager owning one script's outputs.

    Usage::

        with Artifact("run_01_validate_paper", args_namespace) as art:
            art.note("n_reps", 100)
            art.table("wp1_policy_comparison", rows, headers)
            art.figure(fig, "wp1_waiting_boxplot")
    """

    def __init__(self, script: str, args: Optional[object] = None,
                 description: str = ""):
        ensure_dirs()
        self.script = script
        self.description = description
        self.args = vars(args) if args is not None and hasattr(args, "__dict__") else {}
        self.t0 = time.time()
        self.outputs: List[Dict[str, str]] = []
        self.notes: Dict[str, Any] = {}
        self.tables: Dict[str, Any] = {}

    # -- context ------------------------------------------------------------
    def __enter__(self) -> "Artifact":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.elapsed = time.time() - self.t0
        self._write_manifest()
        self._append_provenance(failed=exc is not None)
        return False

    # -- recording ----------------------------------------------------------
    def note(self, key: str, value: Any) -> None:
        self.notes[key] = _jsonable(value)

    def header_lines(self) -> List[str]:
        return [
            f"# produced by: scripts/{self.script}.py",
            f"# command    : python scripts/{self.script}.py "
            + " ".join(sys.argv[1:]),
            f"# timestamp  : {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"# args       : {json.dumps(self.args, default=str)}",
        ]

    # -- outputs ------------------------------------------------------------
    def table(self, name: str, rows: Sequence[Sequence[Any]],
              headers: Sequence[str], caption: str = "") -> str:
        """Write a CSV (with a provenance header) and a Markdown twin."""
        csv_path = os.path.join(TABLES, f"{name}.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as fh:
            for line in self.header_lines():
                fh.write(line + "\n")
            if caption:
                fh.write(f"# caption    : {caption}\n")
            fh.write(",".join(f'"{h}"' for h in headers) + "\n")
            for r in rows:
                fh.write(",".join(_csv_cell(c) for c in r) + "\n")

        md_path = os.path.join(TABLES, f"{name}.md")
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(f"### {caption or name}\n\n")
            fh.write("| " + " | ".join(str(h) for h in headers) + " |\n")
            fh.write("|" + "|".join(["---"] * len(headers)) + "|\n")
            for r in rows:
                fh.write("| " + " | ".join("" if c is None else str(c) for c in r) + " |\n")
            fh.write(f"\n<sub>{' &middot; '.join(l.lstrip('# ') for l in self.header_lines())}</sub>\n")

        self.outputs.append({"kind": "table", "name": name, "path": _rel(csv_path),
                             "caption": caption})
        self.tables[name] = {"headers": list(headers),
                             "rows": [[_jsonable(c) for c in r] for r in rows]}
        return csv_path

    def figure(self, fig, name: str, caption: str = "") -> str:
        from .plotting import save
        png = save(fig, name)
        self.outputs.append({"kind": "figure", "name": name, "path": _rel(png),
                             "caption": caption})
        return png

    def raw(self, name: str, obj: Any) -> str:
        path = os.path.join(RAW, f"{name}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(_jsonable(obj), fh, indent=1)
        self.outputs.append({"kind": "raw", "name": name, "path": _rel(path),
                             "caption": ""})
        return path

    def dataframe(self, name: str, df) -> str:
        """Persist a pandas DataFrame of per-replication results."""
        path = os.path.join(RAW, f"{name}.csv")
        df.to_csv(path, index=False)
        self.outputs.append({"kind": "raw", "name": name, "path": _rel(path),
                             "caption": ""})
        return path

    # -- manifests ----------------------------------------------------------
    def _write_manifest(self) -> None:
        man = {
            "script": self.script,
            "description": self.description,
            "command": "python scripts/%s.py %s" % (self.script, " ".join(sys.argv[1:])),
            "args": _jsonable(self.args),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_seconds": round(getattr(self, "elapsed", 0.0), 2),
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "numpy": _ver("numpy"), "scipy": _ver("scipy"),
                "matplotlib": _ver("matplotlib"), "pandas": _ver("pandas"),
            },
            "notes": self.notes,
            "outputs": self.outputs,
            "tables": self.tables,
        }
        with open(os.path.join(RAW, f"{self.script}.manifest.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(man, fh, indent=1)

    def _append_provenance(self, failed: bool) -> None:
        first = not os.path.exists(PROVENANCE)
        with open(PROVENANCE, "a", encoding="utf-8") as fh:
            if first:
                fh.write("# Provenance log\n\n"
                         "Every entry below records one execution of one runner "
                         "script: the exact command, when it ran, how long it "
                         "took, the key settings, and every file it wrote.\n"
                         "Newest entries are appended at the bottom.\n")
            fh.write(f"\n---\n\n## `{self.script}`"
                     f"{'  **(FAILED)**' if failed else ''}\n\n")
            if self.description:
                fh.write(f"{self.description}\n\n")
            fh.write(f"- **command**: `python scripts/{self.script}.py "
                     f"{' '.join(sys.argv[1:])}`\n")
            fh.write(f"- **run at**: {time.strftime('%Y-%m-%d %H:%M:%S')}  "
                     f"(**{getattr(self, 'elapsed', 0.0):.1f} s**)\n")
            if self.notes:
                fh.write("- **settings / key numbers**:\n")
                for k, v in self.notes.items():
                    fh.write(f"    - `{k}` = {v}\n")
            if self.outputs:
                fh.write("- **outputs**:\n")
                for o in self.outputs:
                    cap = f" -- {o['caption']}" if o.get("caption") else ""
                    fh.write(f"    - `{o['path']}`{cap}\n")


def _rel(p: str) -> str:
    return os.path.relpath(p, ROOT).replace("\\", "/")


def _csv_cell(c: Any) -> str:
    if c is None:
        return ""
    s = str(c)
    if any(ch in s for ch in ',"\n'):
        return '"' + s.replace('"', '""') + '"'
    return s


def _ver(mod: str) -> str:
    try:
        return __import__(mod).__version__
    except Exception:
        return "n/a"
