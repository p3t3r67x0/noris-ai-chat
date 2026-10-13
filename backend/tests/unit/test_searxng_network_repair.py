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
        print("type filter hook forward priority filter; policy "
              + os.environ.get("FAKE_POLICY", "drop") + ";")
        bridge = os.environ.get("FAKE_BRIDGE") or "br-aaaaaaaaaaaa"
        uplink = os.environ.get("NORIS_SEARXNG_UPLINK") or "wlp0s20f3"
        for suffix in os.environ.get("FAKE_EXISTING", "").split(","):
            if suffix:
                print(f'comment "noris-searxng:{bridge}:{uplink}:{suffix}"')
    elif args == ["--check", "-f", "-"]:
        sys.exit(int(os.environ.get("FAKE_CHECK_EXIT", "0")))
    elif args != ["-f", "-"]:
        raise AssertionError(args)
elif name == "docker":
    assert args[:3] == ["network", "inspect", "--format"]
    assert args[-1] == os.environ.get("NORIS_SEARXNG_NETWORK", "noris-searxng")
    fields = {
        '{{index .Labels "com.docker.compose.project"}}': ("FAKE_PROJECT", "noris-searxng"),
        '{{index .Labels "com.docker.compose.network"}}': ("FAKE_ROLE", "search"),
        '{{.Driver}}': ("FAKE_DRIVER", "bridge"),
        '{{.Internal}}': ("FAKE_INTERNAL", "false"),
        '{{index .Options "com.docker.network.bridge.name"}}': ("FAKE_BRIDGE", ""),
        '{{.Id}}': ("FAKE_NETWORK_ID", "a" * 64),
    }
    key, default = fields[args[3]]
    print(os.environ.get(key, default))
elif name == "ip":
    if args == ["-4", "route", "get", "1.1.1.1"]:
        print(os.environ.get("FAKE_ROUTE", "1.1.1.1 via 192.0.2.1 dev wlp0s20f3 src 192.0.2.2"))
    else:
        assert args[:3] == ["link", "show", "dev"]
        sys.exit(int(os.environ.get("FAKE_LINK_EXIT", "0")))
else:
    raise AssertionError(name)
"""


@pytest.fixture
def run_repair(tmp_path: Path) -> RepairRunner:
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    for name in ("id", "docker", "nft", "ip"):
        executable = stub_bin / name
        executable.write_text(f"#!{sys.executable}\n{STUB}")
        executable.chmod(0o700)
    root = Path(__file__).resolve().parents[3]
    calls_file = tmp_path / "calls.jsonl"

    def run(updates: dict[str, str]) -> RepairResult:
        result = subprocess.run(
            ["/bin/sh", "infrastructure/scripts/repair-searxng-network.sh"],
            cwd=root,
            env={
                **os.environ,
                "PATH": f"{stub_bin}{os.pathsep}{os.environ['PATH']}",
                "FAKE_CALLS": str(calls_file),
                "NORIS_SEARXNG_NETWORK": "noris-searxng",
                "NORIS_SEARXNG_UPLINK": "",
                **updates,
            },
            capture_output=True,
            text=True,
            check=False,
        )
        calls = [json.loads(line) for line in calls_file.read_text().splitlines()]
        return result, cast(list[dict[str, object]], calls)

    return run


def test_allows_only_search_dns_https_and_replies_in_one_checked_transaction(
    run_repair: RepairRunner,
) -> None:
    result, calls = run_repair({})
    assert result.returncode == 0, result.stderr
    changes = [call for call in calls if call["cmd"] == "nft" and call["stdin"]]
    assert [call["args"] for call in changes] == [["--check", "-f", "-"], ["-f", "-"]]
    assert changes[0]["stdin"] == changes[1]["stdin"]
    rules = str(changes[1]["stdin"]).splitlines()
    assert len(rules) == 3
    outbound = 'iifname "br-aaaaaaaaaaaa" oifname "wlp0s20f3"'
    assert outbound in rules[0] and "udp dport 53" in rules[0]
    assert outbound in rules[1] and "tcp dport { 53, 443 }" in rules[1]
    assert 'iifname "wlp0s20f3" oifname "br-aaaaaaaaaaaa"' in rules[2]
    assert "ct state { established, related }" in rules[2]
    assert "new" not in rules[2]
    assert all("meta nfproto ipv4" in rule for rule in rules)
    assert all("insert rule inet filter forward" in rule for rule in rules)
    assert all("noris-searxng:br-aaaaaaaaaaaa:wlp0s20f3:" in rule for rule in rules)
    assert all("flush" not in rule and "policy" not in rule and "*" not in rule for rule in rules)


@pytest.mark.parametrize(
    "updates",
    [
        {"FAKE_UID": "1000"},
        {"FAKE_POLICY": "accept"},
        {"FAKE_PROJECT": "other-project"},
        {"FAKE_ROLE": "default"},
        {"FAKE_DRIVER": "host"},
        {"FAKE_INTERNAL": "true"},
        {"FAKE_BRIDGE": 'bad"; flush ruleset'},
        {"FAKE_BRIDGE": "bridge-name-too-long"},
        {"FAKE_NETWORK_ID": "not-hex"},
        {"FAKE_NETWORK_ID": "a" * 63},
        {"FAKE_ROUTE": "unreachable 1.1.1.1"},
        {"NORIS_SEARXNG_UPLINK": "lo"},
        {"NORIS_SEARXNG_UPLINK": 'bad"; flush ruleset'},
        {"NORIS_SEARXNG_UPLINK": "br-aaaaaaaaaaaa"},
        {"FAKE_LINK_EXIT": "1"},
        {"FAKE_CHECK_EXIT": "1"},
    ],
)
def test_failed_preconditions_never_change_firewall(
    run_repair: RepairRunner, updates: dict[str, str]
) -> None:
    result, calls = run_repair(updates)
    assert result.returncode != 0
    assert not any(call["cmd"] == "nft" and call["args"] == ["-f", "-"] for call in calls)


def test_custom_network_bridge_and_uplink(run_repair: RepairRunner) -> None:
    result, calls = run_repair(
        {
            "NORIS_SEARXNG_NETWORK": "custom-search",
            "FAKE_BRIDGE": "noris-search0",
            "NORIS_SEARXNG_UPLINK": "eth0",
        }
    )
    assert result.returncode == 0, result.stderr
    changes = [call for call in calls if call["cmd"] == "nft" and call["args"] == ["-f", "-"]]
    assert 'iifname "noris-search0" oifname "eth0"' in str(changes[0]["stdin"])
    assert 'iifname "eth0" oifname "noris-search0"' in str(changes[0]["stdin"])
    assert not any(
        call["cmd"] == "ip" and "route" in cast(list[str], call["args"]) for call in calls
    )


def test_existing_rules_are_not_duplicated(run_repair: RepairRunner) -> None:
    result, calls = run_repair({"FAKE_EXISTING": "dns,https,replies"})
    assert result.returncode == 0, result.stderr
    assert "bereits vorhanden" in result.stdout
    assert not any(call["cmd"] == "nft" and call["stdin"] for call in calls)


def test_partial_repair_adds_only_missing_rule(run_repair: RepairRunner) -> None:
    result, calls = run_repair({"FAKE_EXISTING": "dns,replies"})
    assert result.returncode == 0, result.stderr
    changes = [call for call in calls if call["cmd"] == "nft" and call["args"] == ["-f", "-"]]
    rules = str(changes[0]["stdin"]).splitlines()
    assert len(rules) == 1
    assert "tcp dport { 53, 443 }" in rules[0]
