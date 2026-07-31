"""Allow ``python3 -m agent_control`` to invoke the CLI."""

from .cli import main

raise SystemExit(main())
