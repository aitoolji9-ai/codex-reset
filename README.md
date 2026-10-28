# Codex 리셋 Slack 알림

Codex 리셋 **예정 / 완료 기록**을 구분해 Slack으로 알려주는 작은 Python 프로그램입니다.
조회·판별·발송에 AI를 호출하지 않아 **AI 토큰을 사용하지 않습니다.** 인터넷 연결과 실행 중인 컴퓨터는 필요합니다.

## 알림 예시

```text
⏰ Codex 리셋 예정
예정: 26.10.29 03:00 (한국시간)
사용량 한도 리셋 · 대상: 전체
출처: WhenReset · 티보 X 원문
```

```text
✅ Codex 리셋 완료 기록
완료 기록: 26.10.29 16:00 (한국시간)
사용량 한도 리셋 · 대상: 전체
발견 시각: 26.10.29 16:05 (한국시간)
지연 발견: 완료 기록보다 약 5분 뒤 확인
출처: WhenReset · 티보 X 원문
```

실제 메시지 하단의 출처는 클릭 가능한 링크입니다. `Banked Reset`은 `리셋권 지급`으로 표시합니다.

## 동작

- 기본 확인 간격 **20분**. 처리 완료 후 대기하므로 요청 처리 시간이 더해집니다.
- 예고 시각 **30분 전부터 5분 간격**. 해당 ID의 완료를 확인하거나 예정 시각 **1시간 후**가 되면 20분으로 복귀합니다.
- 예고가 일시적으로 API에서 사라져도 저장된 원장으로 유지합니다. 구간 진입·종료 시점에는 남은 시간만 대기합니다.
- 예정 시각이 지났다는 이유로 완료라고 알리지 않습니다. API의 완료 기록이 있어야 합니다.
- 같은 공지의 예고·완료는 각각 한 번, 같은 단계의 반복 조회는 중복 발송하지 않습니다. ID가 다른 완료를 같은 예고로 추측하지 않습니다.
- 최초 실행은 현재 기록을 기준선으로 저장하고 **과거 알림을 보내지 않습니다**. 이후 새 공지/완료 단계부터 발송합니다.
- API 오류 시 재시도 대기 및 `Retry-After`를 적용합니다. Slack 전송이 불명확하면 자동 재발송하지 않습니다.

정보원은 [WhenReset](https://whenreset.dev)의 [공개 JSON API](https://whenreset.dev/api/resets)입니다. OpenAI 공식 API가 아니며, 원문 링크는 티보의 X 공지를 가리킵니다. 개인 계정에 로그인하거나 실제 사용량·리셋 적용을 확인하지 않습니다. 정보원 반영 지연·누락과 조회 간격만큼 알림이 늦을 수 있습니다.

## 설치 — macOS / Linux / Windows WSL

Python 3.9 이상(3.12 권장), Git, Slack Incoming Webhook이 필요합니다. 실행에는 Python 표준 라이브러리만 사용합니다.

```sh
git clone https://github.com/aitoolji9-ai/codex-reset.git
cd codex-reset
sh install.sh
```

1. Slack 앱 설정에서 **Incoming Webhooks**를 켜고, 알림을 받을 채널의 Webhook을 만드세요.
2. 설치된 `.env`를 로컬 편집기로 열고 `SLACK_WEBHOOK_URL=`에 입력하세요. 이 URL 자체가 인증정보이므로 공유하지 마세요.
3. `SLACK_THREAD_TS`는 비워 두면 채널에 새 메시지를 보냅니다. 대상 채널은 Webhook을 만들 때 선택한 채널이며 채널 ID를 넣어 바꾸는 방식은 아닙니다.

```sh
.venv/bin/python cli.py --dry-run  # API 읽기·형식 검사만, 발송/원장 저장 없음
.venv/bin/python cli.py --once     # 최초 기준선 저장, 이후 실행은 새 항목 처리 가능
.venv/bin/python cli.py            # 계속 실행. 종료: Ctrl+C
```

`.env`는 `source`로 실행하지 마세요. 프로그램이 허용된 키만 읽습니다. 이미 설정된 환경변수가 `.env`보다 우선합니다. `--dry-run`은 Slack 연결을 시험하지 않습니다.

**Windows:** 현재 파일 잠금은 Unix `fcntl` 기반이므로 Windows Python에서 직접 실행하지 않습니다. WSL(Ubuntu) 터미널에서 위 절차를 수행하거나 Linux Docker 컨테이너를 사용하세요. WSL의 절전·로그아웃·자동 시작은 호스트 설정에 따라 다릅니다.

**이 공유본은 독립 실행판입니다.** Hermes·Codex 봇이나 개인 계정 설정이 필요 없습니다. 운영자의 개인 Slack Bot 연결·DM·채널 ID·실제 발송 원장은 포함하지 않습니다. Incoming Webhook의 성공 응답만 확인하며 Bot API로 발송 후 메시지를 다시 조회하는 기능은 포함하지 않습니다.

## Docker / Linux 자동 시작

Docker가 이미 설치된 환경에서 `.env` 설정 후:

```sh
docker compose build
docker compose run --rm notifier --dry-run
docker compose up -d
docker compose logs --tail 30 notifier
docker compose down
```

Compose의 `reset-state` 볼륨에 이력이 남습니다. `down -v`로 지우면 중복 방지 이력도 사라집니다. 오류 후 무조건 다시 보내지 않도록 자동 재시작은 꺼져 있습니다.

Linux 사용자 systemd 예시는 [codex-reset-notifier.service](codex-reset-notifier.service)입니다. 코드 폴더를 `~/.local/share/codex-reset-notifier`에 두고 그곳에서 설치하세요.

```sh
mkdir -p ~/.config/systemd/user ~/.local/state/codex-reset-notifier
chmod 700 ~/.local/state/codex-reset-notifier
cp codex-reset-notifier.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now codex-reset-notifier
systemctl --user status codex-reset-notifier
journalctl --user -u codex-reset-notifier -n 30
```

서비스는 별도 state 경로를 사용합니다. 기존 수동 실행에서 전환할 때는 먼저 종료한 뒤 `state/ledger.json`을 `~/.local/state/codex-reset-notifier/ledger.json`으로 옮겨 이력을 유지하세요. 동일 프로그램을 서로 다른 원장으로 동시에 실행하지 마세요. macOS 자동 시작을 원하면 본인 경로·Python을 지정한 LaunchAgent로 CLI를 실행할 수 있습니다. 기기가 꺼지거나 잠들면 알림도 멈춥니다.

## 실패·복구

- API 일시 오류는 제한된 재시도 대기를 적용합니다. 잘못된 스키마·오래된 피드·설정 오류는 종료 코드 2로 멈춥니다.
- Slack 발송 전 `sending`을 저장합니다. HTTP 200 + 정확한 `ok` 응답 후 `sent`로 저장합니다. 응답 불명확 시 `unknown` 상태로 멈춥니다.
- `sending`/`unknown`이 있으면 실제 채널의 원문 링크·시각을 먼저 대조하세요. 프로그램 종료와 원장 백업 후, 게시를 확인한 항목만 `sent`와 확인한 `sent_at`으로 보완합니다. 미게시를 확인하고 재발송하기로 결정한 항목만 제거하고 재시작하세요. 원장 전체를 지우지 마세요.
- 원장 손상은 기존 백업과 Slack 실제 게시 내역을 대조해 복구합니다. 자동 장애 알림이나 정확히 한 번 전달 보장은 없습니다.
- Webhook·API 오류의 원문에는 인증정보가 섞일 수 있어 로그에는 안전한 오류 요약만 남깁니다.

## 검증

```sh
python3 -m unittest discover -s tests -v
python3 cli.py --dry-run --snapshot tests/fixtures/api-live.json
```

시험 데이터는 합성 자료이며 실제 공지·개인 발송 이력이 아닙니다. 단위시험·로컬 모의 HTTP로 예고/완료, 시간 전환, 재시작/중복 방지, 오류·불명 발송과 한국시간 표기를 검증합니다. Docker·WSL·systemd 실제 가동은 각 설치 환경에서 확인하세요. GitHub Actions는 macOS/Linux에서 시험만 실행하며 알림 봇을 상시 운영하지 않습니다.

## AI에게 설치를 맡길 때

> 이 저장소의 README와 코드를 읽고 내 환경에 설치해줘. Windows이면 WSL/Linux Docker 사용 여부를 먼저 확인해. Slack Webhook은 채팅에 공개하지 말고 로컬 .env에 설정하도록 안내해. dry-run과 테스트를 실행하고, 중복 실행 없이 시작해. 최초 실행은 과거 알림을 보내지 않는다는 점과 원장 위치를 알려줘. 실제 시험 메시지는 내 명시 요청이 있을 때만 보내줘.

## 라이선스

[MIT](LICENSE) — 수정·재배포 가능합니다. Slack과 정보원의 이용 조건은 각각 적용됩니다.
