import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux host firewall helper")

RepairResult = tuple[subprocess.CompletedProcess[str], list[dict[str, object]]]
RepairRunner = Callable[[dict[str, str]], RepairResult]

STUB = r"""
import json
import os
import sys
from pathlib import Path

name = Path(sys.argv[0]).name
args = sys.argv[1:]
stdin = sys.stdin.read() if name == "nft" and "-f" in args else ""
with Path(os.environ["FAKE_CALLS"]).open("a") as log:
    log.write(json.dumps({"cmd": name, "args": args, "stdin": stdin}) + "\n")

if name == "id":
    print(os.environ.get("FAKE_UID", "0"))
elif name == "nft":
    if args == ["list", "chain", "inet", "filter", "forward"]:
        policy = os.environ.get("FAKE_POLICY", "drop")
        print("type filter hook forward priority filter; policy " + policy + ";")
        if os.environ.get("FAKE_EXISTING"):
            bridge = os.environ.get("FAKE_BRIDGE") or "br-aaaaaaaaaaaa"
            print(f'iifname "{bridge}" oifname "{bridge}" accept '
                  f'comment "noris-ai-chat:{bridge}"')
    elif args == ["--check", "-f", "-"]:
        sys.exit(int(os.environ.get("FAKE_CHECK_EXIT", "0")))
    elif args != ["-f", "-"]:
        raise AssertionError(args)
elif name == "docker":
    if args == ["compose", "version"]:
        print("Docker Compose version v2.39.4")
    elif args[:3] == ["compose", "exec", "-T"]:
        assert args[3:6] == ["postgres", "sh", "-c"]
        assert "pg_isready -h 127.0.0.1 -p 5432" in args[6]
        sys.exit(int(os.environ.get("FAKE_POSTGRES_EXIT", "0")))
    else:
        assert args[:3] == ["network", "inspect", "--format"]
        assert args[-1] == "noris-ai-chat_default"
        fields = {
            '{{index .Labels "com.docker.compose.project"}}': ("FAKE_PROJECT", "noris-ai-chat"),
            '{{.Driver}}': ("FAKE_DRIVER", "bridge"),
            '{{index .Options "com.docker.network.bridge.enable_icc"}}': ("FAKE_ICC", ""),
            '{{index .Options "com.docker.network.bridge.name"}}': ("FAKE_BRIDGE", ""),
            '{{.Id}}': ("FAKE_NETWORK_ID", "a" * 64),
        }
        key, default = fields[args[3]]
        print(os.environ.get(key, default))
else:
    raise AssertionError(name)
"""


@pytest.fixture
def run_repair(tmp_path: Path) -> RepairRunner:
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    for name in ("id", "docker", "nft"):
        executable = stub_bin / name
        executable.write_text(f"#!{sys.executable}\n{STUB}")
        executable.chmod(0o700)
    root = Path(__file__).resolve().parents[3]
    calls_file = tmp_path / "calls.jsonl"

    def run(updates: dict[str, str]) -> RepairResult:
        result = subprocess.run(
            ["/bin/sh", "infrastructure/scripts/repair-docker-network.sh"],
            cwd=root,
            env={
                **os.environ,
                "PATH": f"{stub_bin}{os.pathsep}{os.environ['PATH']}",
                "FAKE_CALLS": str(calls_file),
                **updates,
            },
            capture_output=True,
            text=True,
            check=False,
        )
        calls = [json.loads(line) for line in calls_file.read_text().splitlines()]
        return result, cast(list[dict[str, object]], calls)

    return run


def test_accepts_only_traffic_within_project_bridge_after_syntax_check(
    run_repair: RepairRunner,
) -> None:
    result, calls = run_repair({})
    assert result.returncode == 0, result.stderr
    changes = [call for call in calls if call["cmd"] == "nft" and call["stdin"]]
    assert [call["args"] for call in changes] == [["--check", "-f", "-"], ["-f", "-"]]
    assert changes[0]["stdin"] == changes[1]["stdin"]
    rule = str(changes[1]["stdin"])
    assert 'iifname "br-aaaaaaaaaaaa" oifname "br-aaaaaaaaaaaa"' in rule
    assert 'counter accept comment "noris-ai-chat:br-aaaaaaaaaaaa"' in rule
    assert "flush" not in rule
    assert "policy" not in rule
    assert "*" not in rule


@pytest.mark.parametrize(
    "updates",
    [
        {"FAKE_UID": "1000"},
        {"FAKE_POLICY": "accept"},
        {"FAKE_PROJECT": "other-project"},
        {"FAKE_DRIVER": "host"},
        {"FAKE_ICC": "false"},
        {"FAKE_BRIDGE": 'bad"; flush ruleset'},
        {"FAKE_CHECK_EXIT": "1"},
        {"FAKE_POSTGRES_EXIT": "2"},
    ],
)
def test_failed_preconditions_never_apply_a_firewall_rule(
    run_repair: RepairRunner, updates: dict[str, str]
) -> None:
    result, calls = run_repair(updates)
    assert result.returncode != 0
    assert not any(call["cmd"] == "nft" and call["args"] == ["-f", "-"] for call in calls)


def test_uses_configured_bridge_name_for_both_interfaces(run_repair: RepairRunner) -> None:
    result, calls = run_repair({"FAKE_BRIDGE": "noris-chat0"})
    assert result.returncode == 0, result.stderr
    changes = [call for call in calls if call["cmd"] == "nft" and call["args"] == ["-f", "-"]]
    assert len(changes) == 1
    rule = str(changes[0]["stdin"])
    assert 'iifname "noris-chat0" oifname "noris-chat0"' in rule
    assert 'comment "noris-ai-chat:noris-chat0"' in rule
    assert not any(
        call["cmd"] == "docker" and "{{.Id}}" in cast(list[str], call["args"]) for call in calls
    )


@pytest.mark.parametrize("bridge", ["", "noris-chat0"])
def test_existing_tag_does_not_duplicate_rule(run_repair: RepairRunner, bridge: str) -> None:
    result, calls = run_repair({"FAKE_EXISTING": "1", "FAKE_BRIDGE": bridge})
    assert result.returncode == 0, result.stderr
    assert "bereits vorhanden" in result.stdout
    assert not any(call["cmd"] == "nft" and call["stdin"] for call in calls)
