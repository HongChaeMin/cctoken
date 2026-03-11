# Claude Code Integration

cctoken reads Claude Code's session logs directly from `~/.claude/projects/`.
No extra configuration is needed — just install cctoken and run it.

cctoken은 Claude Code의 세션 로그(`~/.claude/projects/`)를 직접 읽습니다.
별도 설정 없이 설치 후 바로 실행하면 됩니다.

---

## How it works / 동작 방식

Claude Code stores every session as JSONL files under:

```
~/.claude/projects/<project-path>/<session-id>.jsonl
```

cctoken parses these files to extract token usage per request and aggregates them by time period and project.

---

## Hook setup (optional) / 훅 설정 (선택)

You can configure Claude Code to automatically show a token summary at the end of every session using a **Stop hook**.

Claude Code의 **Stop 훅**을 사용하면 세션 종료 시 자동으로 토큰 요약을 표시할 수 있습니다.

### 1. Open Claude Code settings / 설정 파일 열기

```bash
~/.claude/settings.json
```

### 2. Add the hook / 훅 추가

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cctoken"
          }
        ]
      }
    ]
  }
}
```

After this, `cctoken` runs automatically when you end a Claude Code session (`/exit` or Ctrl+C).

이후 Claude Code 세션 종료 시(`/exit` 또는 Ctrl+C) `cctoken`이 자동으로 실행됩니다.

---

## Live monitoring / 라이브 모니터링

Run `cctoken watch` in a separate terminal while using Claude Code to see usage update in real time.

Claude Code를 사용하는 동안 별도 터미널에서 `cctoken watch`를 실행하면 실시간으로 사용량을 확인할 수 있습니다.

```bash
cctoken watch
```

---

## Data source / 데이터 소스

| Item | Path |
|------|------|
| Session logs | `~/.claude/projects/**/*.jsonl` |
| cctoken config | `~/.config/cctoken/config.json` |

Token counts reflect **input + output tokens** (cache tokens shown separately).
토큰 수는 **입력 + 출력 토큰** 기준입니다 (캐시 토큰은 별도 표시).
