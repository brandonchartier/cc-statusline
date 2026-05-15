# cc-statusline

A minimal [Claude Code statusline](https://docs.anthropic.com/en/docs/claude-code/statusline) script. Reads directly from the JSON Claude Code passes via stdin, no API calls, no OAuth, no caching.

## What it shows

```
Sonnet 4.6 | cc-statusline@main | 42k/200k 21% | effort: med | 5h 18% @14:30 | 7d 41% @May 16 09:00 | 14:30
```

- **Model** - current model name
- **Directory + branch** - working directory, git branch, and unstaged diff stats
- **Token usage** - tokens used / context window size and percentage
- **Effort** - current reasoning effort level
- **Rate limits** - 5-hour and 7-day usage with reset times (appears after first message)
- **Time** - current local time

## Requirements

- Python 3.10+
- `git`

## Install

```sh
git clone https://github.com/brandonchartier/cc-statusline ~/.claude/statusline
```

Then point Claude Code at it in `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline/statusline.py"
  }
}
```

## Contributing

```sh
make setup
make test
```
