import re

import pytest

from statusline import (
    ContextWindow,
    Effort,
    RateLimit,
    Repo,
    StatusLine,
    Text,
)


def strip_ansi(s: str) -> str:
    return re.sub(r"\033\[[^m]*m", "", s)


def render(d: dict) -> str:
    return strip_ansi(str(StatusLine.from_dict(d).to_text()))


# --- Empty input ---


def test_empty_input():
    assert strip_ansi(str(Text())) == ""


# --- Token formatting ---


@pytest.mark.parametrize(
    "tokens,expected",
    [
        (0, "0/200k"),
        (999, "999/200k"),
        (1000, "1k/200k"),
        (15500, "15k/200k"),
        (1_000_000, "1.0m/200k"),
        (1_500_000, "1.5m/200k"),
    ],
)
def test_fmt_tokens(tokens, expected):
    cw = ContextWindow.from_dict(
        {
            "total_input_tokens": tokens,
            "context_window_size": 200000,
            "used_percentage": 0,
        }
    )
    assert expected in strip_ansi(str(cw.to_text()))


# --- Effort levels ---


@pytest.mark.parametrize("level", ["low", "medium", "high", "xhigh", "max", "custom"])
def test_effort_levels(level):
    effort = Effort.from_dict({"level": level})
    text = strip_ansi(str(effort.to_text()))
    assert level in text or (level == "medium" and "med" in text)


# --- Repo ---


def test_repo_no_cwd():
    assert Repo.from_dict({}) is None


def test_repo_worktree_branch():
    repo = Repo.from_dict({"cwd": "/tmp", "worktree": {"branch": "my-branch"}})
    assert repo is not None
    assert repo.worktree_branch == "my-branch"


def test_repo_segment_uses_dirname():
    result = render({"cwd": "/root/repos/cc-statusline"})
    assert "cc-statusline" in result


# --- Rate limits ---


def test_rate_limit_absent():
    rl = RateLimit.from_dict({})
    assert str(rl.to_text(label="5h", time_fmt="%H:%M")) == ""


def test_rate_limit_no_reset():
    rl = RateLimit.from_dict({"used_percentage": 23.5})
    text = strip_ansi(str(rl.to_text(label="5h", time_fmt="%H:%M")))
    assert "5h" in text
    assert "24%" in text
    assert "@" not in text


def test_rate_limit_with_reset():
    rl = RateLimit.from_dict({"used_percentage": 23.5, "resets_at": 1738425600})
    text = strip_ansi(str(rl.to_text(label="5h", time_fmt="@%H:%M")))
    assert "@" in text


@pytest.mark.parametrize(
    "pct,color_code",
    [
        (20, "\033[32m"),  # green
        (55, "\033[93m"),  # yellow
        (75, "\033[33m"),  # orange
        (95, "\033[31m"),  # red
    ],
)
def test_rate_limit_usage_colors(pct, color_code):
    rl = RateLimit.from_dict({"used_percentage": pct})
    text = str(rl.to_text(label="5h", time_fmt="%H:%M"))
    assert color_code in text


# --- StatusLine assembly ---


def test_no_repo_segment_when_no_cwd():
    result = render({"model": {"display_name": "Claude"}})
    assert "@" not in result


def test_all_segments_present():
    result = render(
        {
            "model": {"display_name": "Sonnet 4.6"},
            "cwd": "/root/repos/cc-statusline",
            "context_window": {
                "total_input_tokens": 15500,
                "context_window_size": 200000,
                "used_percentage": 8,
            },
            "effort": {"level": "high"},
            "rate_limits": {
                "five_hour": {"used_percentage": 23.5, "resets_at": 1738425600},
                "seven_day": {"used_percentage": 41.2, "resets_at": 1738857600},
            },
        }
    )
    assert "Sonnet 4.6" in result
    assert "cc-statusline" in result
    assert "15k/200k" in result
    assert "high" in result
    assert "5h" in result
    assert "7d" in result


FULL_SCHEMA = {
    "cwd": "/current/working/directory",
    "session_id": "abc123...",
    "session_name": "my-session",
    "transcript_path": "/path/to/transcript.jsonl",
    "model": {"id": "claude-opus-4-7", "display_name": "Opus"},
    "workspace": {
        "current_dir": "/current/working/directory",
        "project_dir": "/original/project/directory",
        "added_dirs": [],
        "git_worktree": "feature-xyz",
    },
    "version": "2.1.90",
    "output_style": {"name": "default"},
    "cost": {
        "total_cost_usd": 0.01234,
        "total_duration_ms": 45000,
        "total_api_duration_ms": 2300,
        "total_lines_added": 156,
        "total_lines_removed": 23,
    },
    "context_window": {
        "total_input_tokens": 15500,
        "total_output_tokens": 1200,
        "context_window_size": 200000,
        "used_percentage": 8,
        "remaining_percentage": 92,
        "current_usage": {
            "input_tokens": 8500,
            "output_tokens": 1200,
            "cache_creation_input_tokens": 5000,
            "cache_read_input_tokens": 2000,
        },
    },
    "exceeds_200k_tokens": False,
    "effort": {"level": "high"},
    "thinking": {"enabled": True},
    "rate_limits": {
        "five_hour": {"used_percentage": 23.5, "resets_at": 1738425600},
        "seven_day": {"used_percentage": 41.2, "resets_at": 1738857600},
    },
    "vim": {"mode": "NORMAL"},
    "agent": {"name": "security-reviewer"},
    "worktree": {
        "name": "my-feature",
        "path": "/path/to/.claude/worktrees/my-feature",
        "branch": "worktree-my-feature",
        "original_cwd": "/path/to/project",
        "original_branch": "main",
    },
}


def test_full_schema():
    result = render(FULL_SCHEMA)
    assert "Opus" in result
    assert "directory" in result
    assert "worktree-my-feature" in result
    assert "15k/200k" in result
    assert "8%" in result
    assert "high" in result
    assert "5h" in result
    assert "7d" in result


def test_sep_joins_non_empty_parts():
    result = render({"model": {"display_name": "Claude"}})
    # Should not start or end with separator
    assert not result.startswith("|")
    assert not result.endswith("|")
    # No double separators from empty parts
    assert "||" not in result
