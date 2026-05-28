from __future__ import annotations

import json

from printpipe.cli import build_parser, main


def test_doctor_parser_accepts_json_and_platform_flags():
    parser = build_parser()
    args = parser.parse_args(["doctor", "--json", "--platform", "win32"])

    assert args.command == "doctor"
    assert args.json is True
    assert args.platform == "win32"


def test_doctor_prints_human_report(monkeypatch, capsys):
    monkeypatch.setattr(
        "printpipe.env.doctor.build_environment_report",
        lambda *, platform_name=None: {
            "platform": {"raw": platform_name or "darwin", "normalized": "macos"},
            "dependencies": [],
            "bambu_studio": {"installed_count": 0, "candidate_count": 0},
            "bambu_profiles": {"candidate_count": 0},
            "system": {
                "signing": {
                    "status": "missing_identities",
                    "missing_tools": [],
                    "missing_identities": ["Developer ID Application"],
                }
            },
            "summary": {"dependency_status_counts": {}},
        },
    )

    exit_code = main(["doctor", "--platform", "darwin"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "PrintPipe Doctor" in captured.out
    assert "Platform: macos (darwin)" in captured.out
    assert "macOS signing: missing_identities" in captured.out


def test_doctor_prints_json_report(monkeypatch, capsys):
    monkeypatch.setattr(
        "printpipe.env.doctor.build_environment_report",
        lambda *, platform_name=None: {
            "schema_version": 1,
            "platform": {"raw": platform_name, "normalized": "windows"},
            "dependencies": [],
            "bambu_studio": {"installed_count": 0, "candidate_count": 0},
            "bambu_profiles": {"candidate_count": 0},
            "summary": {"dependency_status_counts": {}},
        },
    )

    exit_code = main(["doctor", "--json", "--platform", "win32"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["platform"] == {
        "raw": "win32",
        "normalized": "windows",
    }
