import re

import pytest

from statusline import (
    context_window_data,
    fmt_context_window,
    fmt_effort,
    fmt_model,
    fmt_rate_limit,
    fmt_repo,
    fmt_tokens,
    rate_limit_data,
    repo_info,
    statusline,
)


def strip_ansi(s: str) -> str:
    return re.sub(r"\033\[[^m]*m", "", s)


def render(d: dict) -> str:
    return strip_ansi(statusline(d))


# --- Model ---


def test_model_default():
    assert strip_ansi(fmt_model("Claude")) == "Claude"


# --- Token formatting ---


@pytest.mark.parametrize(
    "tokens,expected",
    [
        (0, "0"),
        (999, "999"),
        (1000, "1k"),
        (15500, "15k"),
        (1_000_000, "1.0m"),
        (1_500_000, "1.5m"),
    ],
)
def test_fmt_tokens(tokens, expected):
    assert fmt_tokens(tokens) == expected


# --- Effort levels ---


@pytest.mark.parametrize("level", ["low", "medium", "high", "xhigh", "max", "custom"])
def test_effort_levels(level):
    text = strip_ansi(fmt_effort(level))
    assert level in text or (level == "medium" and "med" in text)


# --- Repo ---


def test_repo_info_no_cwd():
    assert repo_info({}) is None


def test_repo_info_worktree_branch():
    info = repo_info({"cwd": "/tmp", "worktree": {"branch": "my-branch"}})
    assert info is not None
    assert info[1] == "my-branch"


def test_repo_shows_diff():
    result = strip_ansi(fmt_repo(("repo", "main", 5, 3)))
    assert "+5" in result
    assert "-3" in result


def test_repo_no_diff():
    result = strip_ansi(fmt_repo(("repo", "main", 0, 0)))
    assert "+" not in result
    assert "-" not in result


def test_repo_no_branch():
    result = strip_ansi(fmt_repo(("repo", "", 0, 0)))
    assert "@" not in result


def test_repo_none():
    assert fmt_repo(None) == ""


def test_repo_segment_uses_dirname():
    result = render({"cwd": "/root/repos/cc-statusline"})
    assert "cc-statusline" in result


# --- Context window ---


def test_context_window_data():
    used, size, pct = context_window_data(
        {
            "total_input_tokens": 15500,
            "context_window_size": 200000,
            "used_percentage": 8,
        }
    )
    assert used == "15k"
    assert size == "200k"
    assert pct == 8


def test_context_window_format():
    result = strip_ansi(fmt_context_window("15k", "200k", 8))
    assert "15k/200k" in result
    assert "8%" in result


# --- Rate limits ---


def test_rate_limit_data_absent():
    assert rate_limit_data({}) is None


def test_rate_limit_data_present():
    data = rate_limit_data({"used_percentage": 23.5, "resets_at": 1738425600})
    assert data == (24, 1738425600)


def test_rate_limit_absent():
    assert fmt_rate_limit("5h", None, time_fmt="%H:%M") == ""


def test_rate_limit_no_reset():
    text = strip_ansi(fmt_rate_limit("5h", (24, None), time_fmt="%H:%M"))
    assert "5h" in text
    assert "24%" in text
    assert "@" not in text


def test_rate_limit_with_reset():
    text = strip_ansi(fmt_rate_limit("5h", (24, 1738425600), time_fmt="%H:%M"))
    assert ":" in text


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
    text = fmt_rate_limit("5h", (pct, None), time_fmt="%H:%M")
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
    assert not result.startswith("|")
    assert not result.endswith("|")
    assert "||" not in result
