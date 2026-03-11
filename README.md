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
cctoken                     # Today / week / month summary | 오늘 / 이번 주 / 이번 달 요약
cctoken projects            # Per-project breakdown (month-to-date) | 프로젝트별 토큰/비용 (월간)
cctoken trend               # Hourly usage heatmap (last 7 days) | 시간대별 사용량 히트맵 (최근 7일)
cctoken watch               # Live dashboard, refreshes every 5s | 라이브 대시보드 (5초 자동 갱신)
cctoken budget set 5000000  # Set monthly token budget | 월간 토큰 예산 설정
cctoken budget show         # Show budget usage | 예산 사용 현황
```

### watch dashboard

`cctoken watch` opens a full-screen live dashboard.

- Hour / Today / Week / Month sparkline cards
- Per-project token bar chart (month-to-date)
- Budget progress bar + all-time stats in the status bar
- Layout auto-adapts to terminal size
- Press `Ctrl+C` to exit

---

`cctoken watch`를 실행하면 터미널 전체를 채우는 라이브 대시보드가 표시됩니다.

- Hour / Today / Week / Month 스파크라인 카드
- 프로젝트별 토큰 바 차트 (월간)
- 예산 진행바 + 전체 통계 상태바
- 터미널 크기에 따라 레이아웃 자동 조절
- `Ctrl+C`로 종료

## Requirements / 요구사항

- Python 3.10+
- [Rich](https://github.com/Textualize/rich)
