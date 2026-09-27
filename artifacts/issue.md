# 시뮬레이션 틱 일시정지/재개 기능

## 목적

실행 중인 시뮬레이션을 API로 일시정지하고 재개할 수 있게 한다.
크레딧 소진 방지, 디버깅, 비용 제어 목적.

## 구현 방식

`/data/PAUSED` 플래그 파일 방식.
- 파일 존재 → `tick()` 실행 건너뜀
- 파일 없음 → 정상 실행
- `/data`는 Fly.io 영구 볼륨 → 재시작·재배포 후에도 상태 유지

## 수용 기준

### AC1. tick() 일시정지
- `/data/PAUSED` 파일이 존재하면 `tick()`은 실행을 건너뛰고 로그 출력
- 현재 실행 중인 tick은 완료까지 진행 (즉시 중단 없음 — 정상 동작)

### AC2. API — 일시정지
- `POST /api/simulation/pause` → `/data/PAUSED` 파일 생성
- 이미 paused이면 `{"status": "already_paused"}` 반환 (오류 아님)
- 응답: `{"status": "paused"}`

### AC3. API — 재개
- `POST /api/simulation/resume` → `/data/PAUSED` 파일 삭제
- 이미 running이면 `{"status": "already_running"}` 반환 (오류 아님)
- 응답: `{"status": "running"}`

### AC4. 상태 확인
- `GET /api/simulation/status` → `{"status": "paused" | "running"}`
- `/api/stats` 응답에 `simulation_status` 필드 추가

### AC5. 재배포 후 상태 유지 명시
- `/data/PAUSED` 파일이 있으면 재배포 후에도 paused 상태 유지 (의도된 동작)
- 로그: `시뮬레이션 일시정지 상태입니다. /api/simulation/resume 으로 재개하세요.`

## 범위 밖

- 진행 중인 tick 즉시 강제 중단 (APScheduler 제약, 구현 복잡도 대비 효용 낮음)
- 대시보드 UI 버튼 (API만 구현, UI는 별도 이슈)

## 파일

- `src/scheduler.py` — `tick()` 앞에 플래그 파일 체크 추가
- `src/web/app.py` — pause/resume/status 엔드포인트 추가, stats에 simulation_status 추가

## 테스트 전략

Test-after (설계 탐색 완료, 구현 후 테스트 추가)
- `tests/test_scheduler.py` — PAUSED 파일 존재 시 tick 건너뜀 확인
- `tests/test_web.py` — pause/resume/status API 응답 확인
