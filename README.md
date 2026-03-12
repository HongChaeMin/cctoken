# cctoken

Claude Code token usage monitoring CLI.

Claude Code 토큰 사용량 모니터링 CLI 도구.

---

## Installation / 설치

```bash
git clone git@github.com:HongChaeMin/cctoken.git
cd cctoken
pip install -r requirements.txt
bash install.sh
```

If `~/.local/bin` is not in your PATH, add it to `~/.zshrc`:
`~/.local/bin`이 PATH에 없다면 `~/.zshrc`에 추가:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Usage / 사용법

```bash
cctoken                     # Live watch dashboard (default) | 라이브 대시보드 (기본)
cctoken hour                # Current 5h block detail view | 현재 5시간 블록 상세
cctoken today               # Today detail view | 오늘 상세
cctoken week                # This week detail view | 이번 주 상세
cctoken month               # This month detail view | 이번 달 상세
cctoken projects            # Per-project breakdown (month-to-date) | 프로젝트별 (월간)
cctoken trend               # Hourly usage heatmap (last 7 days) | 시간대별 히트맵 (7일)
cctoken budget set 5000000  # Set monthly token budget | 월간 토큰 예산 설정
cctoken budget show         # Show budget usage | 예산 사용 현황
cctoken budget reset-day 1  # Set billing reset day | 과금 리셋일 설정
```

### Main Dashboard

`cctoken` opens a full-screen live dashboard.

- Hour / Today / Week / Month sparkline cards
- Rate & Reset panel with burn rate graph
- Per-project token bar chart (month-to-date)
- Budget progress bar + all-time stats in the status bar
- Layout auto-adapts to terminal size
- Press `Ctrl+C` to exit

---

`cctoken`을 실행하면 터미널 전체를 채우는 라이브 대시보드가 표시됩니다.

- Hour / Today / Week / Month 스파크라인 카드
- Rate & Reset 패널 (번 레이트 그래프 포함)
- 프로젝트별 토큰 바 차트 (월간)
- 예산 진행바 + 전체 통계 상태바
- 터미널 크기에 따라 레이아웃 자동 조절
- `Ctrl+C`로 종료

### Detail Views

`cctoken hour/today/week/month` opens a period-specific live dashboard with:

- **Budget bar** — proportionally allocated from monthly budget (5h / daily / weekly / monthly)
- **Model usage** — stacked progress bar showing usage ratio per model
- **Project ranking** — token usage ranking with cost
- **Rate & Reset** — period-appropriate burn rate, depletion estimate, and reset countdown

---

`cctoken hour/today/week/month`는 기간별 라이브 대시보드를 표시합니다:

- **예산 바** — 월 예산을 기간별로 비례 배분 (5시간 / 일 / 주 / 월)
- **모델 사용** — 모델별 사용 비율 스택 프로그레스 바
- **프로젝트 랭킹** — 토큰 사용량 랭킹 + 비용
- **Rate & Reset** — 기간별 번 레이트, 예산 소진 예상, 리셋 카운트다운

## Claude Code Integration / Claude Code 연동

See [docs/claude-code-integration.md](docs/claude-code-integration.md) for:
- How cctoken reads Claude Code session data
- Setting up a Stop hook to auto-show stats after each session
- Live monitoring setup

[docs/claude-code-integration.md](docs/claude-code-integration.md) 문서에서 확인:
- cctoken이 Claude Code 데이터를 읽는 방식
- 세션 종료 시 자동 실행을 위한 Stop 훅 설정
- 라이브 모니터링 설정

## Requirements / 요구사항

- Python 3.10+
- [Rich](https://github.com/Textualize/rich)
