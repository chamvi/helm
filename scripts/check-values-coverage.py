#!/usr/bin/env python3
"""Fail when a template references a .Values path absent from values.yaml.

Adapted from authup/helm/scripts/check-values-coverage.py. A reference resolves
when every segment walks through the parsed values tree. Empty maps and
non-mapping leaves cover dynamic access beneath them. This audits literal
.Values references only, not aliases or computed index expressions.
"""
import re
import sys
from pathlib import Path

import yaml

chart = Path(sys.argv[1] if len(sys.argv) > 1 else "charts/agent-app")
values = yaml.safe_load((chart / "values.yaml").read_text()) or {}
refs = set()
pattern = re.compile(r"\.Values\.([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*)")
for template in chart.glob("templates/**/*"):
    if template.is_file():
        refs.update(pattern.findall(template.read_text()))

failures = []
for ref in sorted(refs):
    node = values
    for segment in ref.split("."):
        if isinstance(node, dict):
            if segment in node:
                node = node[segment]
            elif not node and node is not values:
                break
            else:
                failures.append(ref)
                break
        else:
            break

if failures:
    for ref in failures:
        print(f"MISSING values key referenced by templates: {ref}")
    sys.exit(1)
print(f"values coverage OK ({len(refs)} referenced paths)")
