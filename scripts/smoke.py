# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Smoke-check bundled-script plumbing: uv resolves PEP 723 deps from inside the plugin.

Usage: uv run ${CLAUDE_PLUGIN_ROOT}/scripts/smoke.py

ponytail: placeholder stub; real phase scripts land with the skill-content tickets (15-19).
"""
import sys

import yaml

assert yaml.safe_load("ok: true") == {"ok": True}
print(f"ok: pyyaml {yaml.__version__} python {sys.version.split()[0]}")
