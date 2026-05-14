#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from typing import NamedTuple


class Code:
    def __init__(self, code: str):
        self.code = code

    def __call__(self, text) -> str:
        return f"{self.code}{text}\033[0m"


class Color:
    BLUE = Code("\033[94m")
    ORANGE = Code("\033[33m")
    GREEN = Code("\033[32m")
    CYAN = Code("\033[36m")
    RED = Code("\033[31m")
    YELLOW = Code("\033[93m")
    PURPLE = Code("\033[35m")
    WHITE = Code("\033[37m")
    DIM = Code("\033[2m")


class RepoInfo(NamedTuple):
    name: str
    branch: str
    added: int
    removed: int


class ContextWindowData(NamedTuple):
    used: str
    size: str
    pct: int


class RateLimitData(NamedTuple):
    pct: int
    reset: int | None


def git(*args: str, cwd: str) -> str:
    out = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)
    return out.stdout.strip()


def git_diff_stats(cwd: str) -> tuple[int, int]:
    out = git("diff", "--shortstat", cwd=cwd)
    added = int(m.group(1)) if (m := re.search(r"(\d+) insertion", out)) else 0
    removed = int(m.group(1)) if (m := re.search(r"(\d+) deletion", out)) else 0
    return added, removed


def fmt_tokens(n: int) -> str:
    match n:
        case n if n >= 1_000_000:
            return f"{n / 1e6:.1f}m"
        case n if n >= 1_000:
            return f"{n // 1000}k"
        case _:
            return str(n)


def repo_info(d: dict) -> RepoInfo | None:
    if not (cwd := d.get("cwd")):
        return None

    name = cwd.split("/")[-1]
    added, removed = git_diff_stats(cwd)
    branch = d.get("worktree", {}).get("branch") or git(
        "rev-parse", "--abbrev-ref", "HEAD", cwd=cwd
    )

    return RepoInfo(name, branch, added, removed)


def context_window_data(d: dict) -> ContextWindowData:
    used = fmt_tokens(d.get("total_input_tokens", 0))
    size = fmt_tokens(d.get("context_window_size", 200000))
    pct = round(d.get("used_percentage", 0))
    return ContextWindowData(used, size, pct)


def rate_limit_data(d: dict) -> RateLimitData | None:
    if (used := d.get("used_percentage")) is None:
        return None

    return RateLimitData(round(used), d.get("resets_at"))


def fmt_time() -> str:
    return Color.WHITE(datetime.now().strftime("%H:%M"))


def fmt_model(name: str) -> str:
    return Color.BLUE(name)


def fmt_repo(info: RepoInfo | None) -> str:
    if info is None:
        return ""

    name, branch, added, removed = info
    directory = Color.CYAN(name)

    if not branch:
        return directory

    branch_str = Color.GREEN(branch)
    added_str = Color.GREEN(f"+{added}")
    removed_str = Color.RED(f"-{removed}")
    diff = f" ({added_str} {removed_str})" if added or removed else ""

    return f"{directory}@{branch_str}{diff}"


def fmt_context_window(used: str, size: str, pct: int) -> str:
    tokens = Color.ORANGE(f"{used}/{size}")
    percent = Color.GREEN(f"{pct}%")
    return f"{tokens} {percent}"


def fmt_effort(level: str) -> str:
    match level:
        case "low":
            return f"effort: {Color.DIM('low')}"
        case "medium":
            return f"effort: {Color.ORANGE('med')}"
        case "high":
            return f"effort: {Color.GREEN('high')}"
        case "xhigh":
            return f"effort: {Color.PURPLE('xhigh')}"
        case "max":
            return f"effort: {Color.RED('max')}"
        case other:
            return f"effort: {Color.GREEN(other)}"


def fmt_usage(pct: int) -> str:
    match pct:
        case p if p >= 90:
            return Color.RED(f"{pct}%")
        case p if p >= 70:
            return Color.ORANGE(f"{pct}%")
        case p if p >= 50:
            return Color.YELLOW(f"{pct}%")
        case _:
            return Color.GREEN(f"{pct}%")


def fmt_rate_limit(label: str, data: RateLimitData | None, *, time_fmt: str) -> str:
    if data is None:
        return ""

    pct, reset = data
    reset_fmt = datetime.fromtimestamp(reset).strftime(time_fmt) if reset else ""
    percent = fmt_usage(pct)
    reset_time = f" {Color.DIM(reset_fmt)}" if reset_fmt else ""
    return f"{Color.WHITE(label)} {percent}{reset_time}"


def fmt_statusline(parts: list[str]) -> str:
    return " | ".join(p for p in parts if p)


def statusline(d: dict) -> str:
    rl = d.get("rate_limits", {})
    model = d.get("model", {}).get("display_name", "Claude")
    repo = repo_info(d)
    cw = context_window_data(d.get("context_window", {}))
    effort = d.get("effort", {}).get("level", "medium")
    five_hour = rate_limit_data(rl.get("five_hour", {}))
    seven_day = rate_limit_data(rl.get("seven_day", {}))

    return fmt_statusline(
        [
            fmt_time(),
            fmt_model(model),
            fmt_repo(repo),
            fmt_context_window(cw.used, cw.size, cw.pct),
            fmt_effort(effort),
            fmt_rate_limit("5h", five_hour, time_fmt="%H:%M"),
            fmt_rate_limit("7d", seven_day, time_fmt="%b %d %H:%M"),
        ]
    )


if __name__ == "__main__":
    if raw := sys.stdin.read().strip():
        print(statusline(json.loads(raw)), end="")
    else:
        print("Claude", end="")
