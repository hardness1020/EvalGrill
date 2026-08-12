# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Offline contract tests for the claude-cli Judge Runner (ticket-10 contract,
ADR-0001). No network, no CLI: subprocess.run is stubbed with canned `claude -p`
envelopes; under test are prompt/flag construction, the verdict-validity rule
(exit==0 && !is_error && subtype=="success" && structured_output present — and
the 404-arrives-with-subtype-"success" quirk), and typed RunnerError mapping.

Usage: uv run tests/test_judge_runner.py
"""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]

ok = True


def expect(cond, msg):
    global ok
    if not cond:
        ok = False
        print(f"FAIL {msg}")


spec = importlib.util.spec_from_file_location("audit_pack", ROOT / "plugin" / "scripts" / "audit_pack.py")
ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ap)

pack = pathlib.Path(tempfile.mkdtemp())
(pack / "sources").mkdir()
(pack / "sources" / "doc.md").write_text("KARLSEN TRIAL FULL TEXT: 4.1 points, CI 1.4-6.8.")

SINGLE_ORDINAL = {
    "mode": "single", "task_id": "t1", "candidate_id": "c1", "run": 1,
    "criterion_id": "conflict_handling",
    "payload": {"query": "Does NR-7 work?", "context_docs": ["sources/doc.md"],
                "grading_constraints": ["use_only_provided_sources"],
                "candidate_text": "CANDIDATE SAYS 4.1 POINTS.",
                "criterion": {"id": "conflict_handling", "kind": "ordinal",
                              "description": "Handles conflicting evidence.",
                              "scale": {0: "ignores conflict", 1: "mentions", 2: "weighs"}}}}
SINGLE_VETO = {
    "mode": "single", "task_id": "t1", "candidate_id": "c1", "run": 1,
    "criterion_id": "cites_only_provided_sources",
    "payload": {"query": "Does NR-7 work?", "context_docs": [], "grading_constraints": [],
                "candidate_text": "CANDIDATE.",
                "criterion": {"id": "cites_only_provided_sources", "kind": "veto",
                              "description": "Cites only packet documents."}}}
PAIRWISE = {
    "mode": "pairwise", "task_id": "t1", "run": 1, "first": "c1", "second": "c2",
    "payload": {"query": "Does NR-7 work?", "response_a": "ALPHA TEXT", "response_b": "BETA TEXT"}}


def envelope(**kw):
    env = {"type": "result", "subtype": "success", "is_error": False, "result": "done",
           "structured_output": {"level": 2, "rationale": "weighs the correction"},
           "modelUsage": {"claude-test-model-19990101": {}}, "total_cost_usd": 0.004}
    return env | kw


def stub(env=None, returncode=0, raise_timeout=False, stdout=None):
    """Patch subprocess.run inside the loaded module; record the last call."""
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        if raise_timeout:
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        out = stdout if stdout is not None else json.dumps(env)
        return SimpleNamespace(returncode=returncode, stdout=out, stderr="")

    ap.subprocess.run = fake_run
    return seen


def main():
    runner = ap.ClaudeCliRunner(pack, "claude-test-model-19990101", 120)

    # --- golden single ordinal: verdict, meta, prompt, flags, schema
    seen = stub(envelope())
    verdict, err = runner.judge(SINGLE_ORDINAL)
    expect(err is None and verdict["verdict"] == {"level": 2}, f"ordinal verdict wrong: {verdict} {err}")
    m = verdict["meta"]
    expect(m["source"] == "live" and m["runner"] == "claude-cli" and m["retries"] == 0,
           f"meta contract violated: {m}")
    expect(m["judge"] == "claude-test-model-19990101", f"judge not snapshot id from modelUsage: {m}")
    expect(m["cost_usd"] == 0.004 and isinstance(m["duration_ms"], int), f"cost/duration missing: {m}")

    cmd = seen["cmd"]
    prompt = cmd[cmd.index("-p") + 1]
    for needle in ("KARLSEN TRIAL FULL TEXT", "CANDIDATE SAYS 4.1 POINTS.", "Does NR-7 work?",
                   "use_only_provided_sources", "Handles conflicting evidence.", "- 2: weighs"):
        expect(needle in prompt, f"prompt missing {needle!r}")
    for flag in (["--model", "claude-test-model-19990101"], ["--output-format", "json"],
                 ["--setting-sources", ""], ["--tools", ""], ["--strict-mcp-config"],
                 ["--disable-slash-commands"], ["--no-session-persistence"]):
        i = cmd.index(flag[0])
        expect(len(flag) == 1 or cmd[i + 1] == flag[1], f"flag {flag} not passed verbatim")
    expect(seen["kw"]["timeout"] == 120, "caller-enforced timeout not passed to subprocess")
    expect(seen["kw"]["cwd"] != str(ROOT), "judge call must run from a neutral cwd")
    schema = json.loads(cmd[cmd.index("--json-schema") + 1])
    expect(schema["required"] == ["level", "rationale"]
           and schema["properties"]["level"] == {"type": "integer", "minimum": 0, "maximum": 2},
           f"ordinal schema wrong: {schema}")

    # --- veto mapping
    stub(envelope(structured_output={"tripped": True, "rationale": "cites outside study"}))
    verdict, err = runner.judge(SINGLE_VETO)
    expect(err is None and verdict["verdict"] == {"tripped": True}, f"veto verdict wrong: {verdict} {err}")

    # --- pairwise mapping
    seen = stub(envelope(structured_output={"preferred": "B", "rationale": "tighter"}))
    verdict, err = runner.judge(PAIRWISE)
    expect(err is None and verdict["verdict"] == {"preferred": "B"}, f"pairwise verdict wrong: {verdict} {err}")
    schema = json.loads(seen["cmd"][seen["cmd"].index("--json-schema") + 1])
    expect(schema["properties"]["preferred"] == {"enum": ["A", "B"]}, f"pairwise schema wrong: {schema}")
    prompt = seen["cmd"][seen["cmd"].index("-p") + 1]
    expect("ALPHA TEXT" in prompt and "BETA TEXT" in prompt and "c1" not in prompt,
           "pairwise prompt must show anonymized responses, never candidate ids")

    # --- the 404 quirk: is_error true but subtype "success" -> api_error, NOT retryable
    stub(envelope(is_error=True, api_error_status=404, result="model not found"), returncode=1)
    verdict, err = runner.judge(SINGLE_ORDINAL)
    expect(verdict is None and err["error"]["kind"] == "api_error" and not err["error"]["retryable"],
           f"404 must map to non-retryable api_error: {err}")
    expect(err["call"] is SINGLE_ORDINAL, "RunnerError must carry the originating call")

    # --- 429 / 500 -> retryable api_error
    for status in (429, 500):
        stub(envelope(is_error=True, api_error_status=status, result="try later"), returncode=1)
        _, err = runner.judge(SINGLE_ORDINAL)
        expect(err and err["error"]["kind"] == "api_error" and err["error"]["retryable"],
               f"{status} must be retryable api_error: {err}")

    # --- subtype success but structured_output absent -> invalid_output, retryable
    stub(envelope(structured_output=None))
    _, err = runner.judge(SINGLE_ORDINAL)
    expect(err and err["error"]["kind"] == "invalid_output" and err["error"]["retryable"],
           f"missing structured_output must be retryable invalid_output: {err}")

    # --- structured-output retry exhaustion subtype
    stub(envelope(subtype="error_max_structured_output_retries", structured_output=None))
    _, err = runner.judge(SINGLE_ORDINAL)
    expect(err and err["error"]["kind"] == "invalid_output", f"retry-exhaustion subtype not mapped: {err}")

    # --- unparseable envelope
    stub(stdout="not json at all")
    _, err = runner.judge(SINGLE_ORDINAL)
    expect(err and err["error"]["kind"] == "invalid_output", f"garbage stdout not mapped: {err}")

    # --- caller-enforced timeout
    stub(raise_timeout=True)
    _, err = runner.judge(SINGLE_ORDINAL)
    expect(err and err["error"]["kind"] == "timeout" and err["error"]["retryable"],
           f"timeout must be retryable RunnerError: {err}")

    print("OK: all claude-cli runner contract tests passed" if ok else "FAILED")
    sys.exit(0 if ok else 1)


main()
