#!/usr/bin/env python3
"""Validate the YAML and Mermaid in this repository.

Parses every YAML document (skipping Helm templates, which are Go templates
rather than YAML), checks the CRDs and example CRs look structurally right, and
checks every Mermaid block in the docs declares the nodes it references.
"""

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
errors = []


def check_yaml():
    for path in sorted(ROOT.rglob("*.yaml")) + sorted(ROOT.rglob("*.yml")):
        rel = path.relative_to(ROOT)
        # Helm templates are Go templates; they are checked by `helm lint`.
        if "templates" in rel.parts:
            continue
        try:
            list(yaml.safe_load_all(path.read_text()))
        except yaml.YAMLError as exc:
            errors.append(f"{rel}: invalid YAML: {exc}")


def check_crds():
    for path in sorted((ROOT / "operator" / "crds").glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        rel = path.relative_to(ROOT)
        if doc.get("kind") != "CustomResourceDefinition":
            errors.append(f"{rel}: expected kind CustomResourceDefinition")
            continue
        names = doc.get("spec", {}).get("names", {})
        for key in ("plural", "singular", "kind"):
            if not names.get(key):
                errors.append(f"{rel}: spec.names.{key} is missing")
        if not doc.get("spec", {}).get("versions"):
            errors.append(f"{rel}: spec.versions is empty")

    kinds = {
        yaml.safe_load(p.read_text())["spec"]["names"]["kind"]
        for p in (ROOT / "operator" / "crds").glob("*.yaml")
    }
    for path in sorted((ROOT / "operator" / "examples").glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        rel = path.relative_to(ROOT)
        if doc.get("kind") not in kinds:
            errors.append(f"{rel}: kind {doc.get('kind')!r} has no matching CRD")


def check_topology():
    sys.path.insert(0, str(ROOT / "decision-engine" / "app"))
    from config import load_topology

    for name in ("decision-engine/app/topology.example.yaml",):
        try:
            load_topology(str(ROOT / name))
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    # The chart's default topology must satisfy the same schema.
    values = yaml.safe_load((ROOT / "charts/decision-engine/values.yaml").read_text())
    required = {"upf", "gnb_id", "tai", "site_id", "redis_host"}
    for edge, entry in values["topology"]["edges"].items():
        missing = required - set(entry)
        if missing:
            errors.append(
                f"charts/decision-engine/values.yaml: edge {edge} missing {sorted(missing)}"
            )


MERMAID = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)

# A node id carrying a shape: Name["label"], Name(label), Name{label}.
SHAPED = re.compile(r"(\w+)\s*(?:\[[^\]]*\]|\([^)]*\)|\{[^}]*\})")
# Edge labels come in two spellings: `A -- text --> B` and `A -->|text| B`.
PIPE_LABEL = re.compile(r"\|[^|]*\|")
INLINE_LABEL = re.compile(r"(--|-\.|==)\s+[^->|\n]+?\s+(-+>|\.-*->|=+>)")
ARROW = re.compile(r"\s*(?:-+>|-\.-*->|=+>|---+|-\.-+)\s*")


def normalise(line):
    """Reduce a mermaid line to bare node ids joined by arrows."""
    line = line.split("%%")[0]
    line = PIPE_LABEL.sub("", line)
    line = INLINE_LABEL.sub(r"\1\2", line)
    # Collapse Name["label"] down to Name, so the label cannot read as a node.
    previous = None
    while previous != line:
        previous = line
        line = SHAPED.sub(r"\1", line)
    return line


def check_mermaid():
    checked = 0
    for path in sorted(ROOT.rglob("*.md")):
        rel = path.relative_to(ROOT)
        for block in MERMAID.findall(path.read_text()):
            checked += 1
            kind = block.strip().split("\n")[0].split()[0]
            if kind.startswith("sequence"):
                continue  # participants are declared by keyword, not shape
            declared = set(SHAPED.findall(block))
            declared |= set(re.findall(r"subgraph (\w+)", block))
            for line in block.split("\n"):
                line = normalise(line).strip()
                if not ARROW.search(line):
                    continue
                nodes = [n for n in ARROW.split(line) if n]
                for node in nodes:
                    if not re.fullmatch(r"\w+", node):
                        continue
                    if node not in declared:
                        errors.append(f"{rel}: mermaid node {node!r} is used but never declared")
    if not checked:
        errors.append("no mermaid blocks were found -- is the validator matching?")


def main():
    check_yaml()
    check_crds()
    check_topology()
    check_mermaid()

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
