#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime


class Text(str):
    def __add__(self, other):
        return Text(str.__add__(self, str(other)))

    def __radd__(self, other):
        return Text(str.__add__(str(other), self))

    def join(self, parts):
        return Text(str.join(self, (str(p) for p in parts)))


class Style:
    def __init__(self, code: str):
        self.code = code

    def __call__(self, text) -> Text:
        return Text(f"{self.code}{text}\033[0m")


BLUE = Style("\033[94m")
ORANGE = Style("\033[33m")
GREEN = Style("\033[32m")
CYAN = Style("\033[36m")
RED = Style("\033[31m")
YELLOW = Style("\033[93m")
PURPLE = Style("\033[35m")
WHITE = Style("\033[37m")
DIM = Style("\033[2m")
SEP = " " + DIM("|") + " "


def git(*args: str, cwd: str) -> str:
    return subprocess.run(
        ["git", "-C", cwd, *args], capture_output=True, text=True
    ).stdout.strip()


def git_diff_stats(cwd: str) -> tuple[int, int]:
    out = git("diff", "--shortstat", cwd=cwd)
    added = int(m.group(1)) if (m := re.search(r"(\d+) insertion", out)) else 0
    removed = int(m.group(1)) if (m := re.search(r"(\d+) deletion", out)) else 0
    return added, removed


@dataclass
class Model:
    display_name: str = "Claude"

    def to_text(self) -> Text:
        return BLUE(self.display_name)

    @classmethod
    def from_dict(cls, d: dict) -> Model:
        return cls(display_name=d.get("display_name", "Claude"))


@dataclass
class ContextWindow:
    size: int = 200000
    used_percentage: float = 0.0
    total_tokens: int = 0

    @staticmethod
    def _fmt_tokens(n: int) -> str:
        match n:
            case n if n >= 1_000_000:
                return f"{n / 1e6:.1f}m"
            case n if n >= 1_000:
                return f"{n // 1000}k"
            case _:
                return str(n)

    def to_text(self) -> Text:
        used = self._fmt_tokens(self.total_tokens)
        size = self._fmt_tokens(self.size)
        tokens = ORANGE(f"{used}/{size}")
        percent = GREEN(f"{round(self.used_percentage)}%")

        return tokens + " " + percent

    @classmethod
    def from_dict(cls, d: dict) -> ContextWindow:
        return cls(
            size=d.get("context_window_size", 200000),
            used_percentage=d.get("used_percentage", 0.0),
            total_tokens=d.get("total_input_tokens", 0),
        )


@dataclass
class RateLimit:
    used_percentage: float | None = None
    resets_at: int | None = None

    @staticmethod
    def _usage_style(pct: float) -> Style:
        match pct:
            case p if p >= 90:
                return RED
            case p if p >= 70:
                return ORANGE
            case p if p >= 50:
                return YELLOW
            case _:
                return GREEN

    def to_text(self, *, label: str, time_fmt: str) -> Text:
        if self.used_percentage is None:
            return Text()

        pct = round(self.used_percentage)
        label = WHITE(label)
        percentage = self._usage_style(pct)(f"{pct}%")

        if not self.resets_at:
            return label + " " + percentage

        reset = DIM(datetime.fromtimestamp(self.resets_at).strftime(time_fmt))

        return label + " " + percentage + " " + reset

    @classmethod
    def from_dict(cls, d: dict) -> RateLimit:
        return cls(
            used_percentage=d.get("used_percentage"),
            resets_at=d.get("resets_at"),
        )


@dataclass
class Effort:
    level: str = "medium"

    def to_text(self) -> Text:
        match self.level:
            case "low":
                label = DIM("low")
            case "medium":
                label = ORANGE("med")
            case "high":
                label = GREEN("high")
            case "xhigh":
                label = PURPLE("xhigh")
            case "max":
                label = RED("max")
            case other:
                label = GREEN(other)
        return "effort: " + label

    @classmethod
    def from_dict(cls, d: dict) -> Effort:
        return cls(level=(d or {}).get("level", "medium"))


@dataclass
class Repo:
    cwd: str
    worktree_branch: str | None = None

    def to_text(self) -> Text:
        directory = CYAN(self.cwd.split("/")[-1])
        branch = self.worktree_branch or git(
            "rev-parse", "--abbrev-ref", "HEAD", cwd=self.cwd
        )

        if not branch:
            return directory

        added, removed = git_diff_stats(self.cwd)
        branch = DIM("@") + GREEN(branch)
        diff = Text()

        if added or removed:
            additions = GREEN(f"+{added}")
            deletions = RED(f"-{removed}")
            diff = " " + DIM("(") + additions + " " + deletions + DIM(")")

        return directory + branch + diff

    @classmethod
    def from_dict(cls, d: dict) -> Repo | None:
        if not (cwd := (d or {}).get("cwd")):
            return None

        return cls(
            cwd=cwd,
            worktree_branch=(d.get("worktree") or {}).get("branch") or None,
        )


@dataclass
class StatusLine:
    model: Model = field(default_factory=Model)
    context_window: ContextWindow = field(default_factory=ContextWindow)
    five_hour: RateLimit = field(default_factory=RateLimit)
    seven_day: RateLimit = field(default_factory=RateLimit)
    repo: Repo | None = None
    effort: Effort = field(default_factory=Effort)

    def to_text(self) -> Text:
        parts = [
            self.model.to_text(),
            self.repo.to_text() if self.repo else Text(),
            self.context_window.to_text(),
            self.effort.to_text(),
            self.five_hour.to_text(label="5h", time_fmt="@%H:%M"),
            self.seven_day.to_text(label="7d", time_fmt="%m/%d %H:%M"),
            WHITE(datetime.now().strftime("%H:%M")),
        ]
        return SEP.join(p for p in parts if p)

    @classmethod
    def from_dict(cls, d: dict) -> StatusLine:
        rl = d.get("rate_limits") or {}
        return cls(
            model=Model.from_dict(d.get("model") or {}),
            context_window=ContextWindow.from_dict(d.get("context_window") or {}),
            five_hour=RateLimit.from_dict(rl.get("five_hour") or {}),
            seven_day=RateLimit.from_dict(rl.get("seven_day") or {}),
            repo=Repo.from_dict(d),
            effort=Effort.from_dict(d.get("effort") or {}),
        )


if __name__ == "__main__":
    if raw := sys.stdin.read().strip():
        print(StatusLine.from_dict(json.loads(raw)).to_text(), end="")
    else:
        print("Claude", end="")
