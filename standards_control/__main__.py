"""Allow ``python3 -m standards_control`` to invoke the CLI."""

from .cli import main

raise SystemExit(main())
