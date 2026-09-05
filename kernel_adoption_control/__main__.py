"""`python3 -m kernel_adoption_control` — the activated Kernel-adoption gate.

A module entry point rather than a `tools/` script, because unlike every other
checker in this repository this one is invoked by OTHER repositories over their
own checkouts: `tools/x.py` is a path into this tree, and a module is something
a pinned Governance checkout exposes.
"""

from __future__ import annotations

from .runner import main

raise SystemExit(main())
