# 로그인 후 이어하기와 완료 확인

이 문서는 **로컬 설치 에이전트**가 실행합니다. 사용자는 방금 안내받은
로그인·승인을 마치고 “완료했어. 계속해”라고 답하면 됩니다.
설치기 `bootstrap.py`가 이후 모든 단계를 자동 실행하는 것은 아닙니다.
에이전트가 아래 명령과 브라우저 확인을 이어갑니다.

## 1. 사람에게 넘기기 전에 재개 지점을 남기기

선택한 로컬 `--state` 폴더에 `install-progress.md`를 0600으로 기록합니다.
기본 폴더는 `~/.config/oracle-ai-stack/state`입니다. 이는 에이전트용 작업
메모이며, 설치 프로그램이 자동으로 쓰거나 성공 판정에 사용하는 영수증이 아닙니다.

- 저장소 버전과 이번 설치의 secrets/stage/state **경로**; 값·키 내용은 제외
- 대상 서버/도메인, 신규 또는 기존 서버, 접근 모드
- 프로필별 로그인 방식·선택 모델과 실제 검사 결과의 로컬 파일 경로
- 현재 기다리는 일: 예를 들어 `planning의 ChatGPT 로그인` 또는
  `operations Control UI의 내 브라우저 승인`; 열린 터미널/브라우저 위치
- 마지막 성공 단계, 실패·미실행 단계, 다음에 실행할 명령

사용자에게 “지금은 기획 프로필 로그인입니다. 이 창에서 로그인한 뒤
‘완료’라고 알려주세요”처럼 범위를 명확히 말합니다. API 키를 쓰는 프로필에는
ChatGPT 로그인을 요구하지 않습니다.

사용자가 돌아오면 이 메모와 실제 결과를 읽고 **남은 단계만** 실행합니다.
메모가 없으면 기본 경로로 추측하지 말고 기존 handoff/설정 경로를 찾습니다.
`stack.py status`와 `stack.py profiles`(둘 다 `--probe` 없이)로 상태를 확인하고,
어떤 로그인인지 여전히 불명확할 때만 한 번 묻습니다.
한 번의 로그인 완료를 세 프로필과 브라우저 인증 전체의 완료로 해석하지 않습니다.

## 2. 전체 설치를 재실행하지 않기

`INSTALLED_PENDING_ACCEPTANCE`는 **설치는 됐고 아래 검증이 남았다**는 뜻입니다.
이 단계에서 `bootstrap.py --apply`, `stack.py setup`, `repair`, `provision`을
로그인 재개 명령으로 쓰지 않습니다. 기존 VM을 재사용하더라도 설치 단계를
다시 수행하므로 인증 확인보다 범위가 큽니다.

아래 명령은 로컬 저장소에서 에이전트가 실행합니다. 비기본 경로를 썼다면
모든 `stack.py` 명령에 같은 `--secrets`, `--stage`, `--state`를 전달합니다.

| 남은 일 | 에이전트가 할 일 | 통과 근거 |
|---|---|---|
| 프로필 OAuth | `stack.py oauth --profile 이름`을 사용자에게 보이는 대화형 터미널에서 실행하고 그 창의 완료를 기다림 | 터미널 종료 + 다음 모델 검사 |
| 로그인 후 모델 선택/검사 | `stack.py models --profile 이름` | 해당 프로필 `auth_probe=PASS`, 실제 marker 응답과 `model_identity=VERIFIED` |
| 세 프로필 최종 확인 | `stack.py profiles --probe` | 세 프로필 모두 `gateway=PASS`, `auth=PASS`, `model_identity=VERIFIED` |
| CLI 기억 기능 | `stack.py memory-smoke` | 실제 반환 결과; 채팅 기억 검증과 별도 |
| 작업 전달 | `stack.py acceptance` | 실제 모델 응답을 동반한 worker 결과; UI 검증과 별도 |
| 브라우저 접속·대화 | 아래 3절 | 현재 브라우저에서 실제 새 응답 |
| 백업·외부 보관·복원 | 아래 4절 | 각각의 실제 결과 |

명령의 `stack.py` 앞에는 모두 `python3 scripts/`를 붙입니다.
`이름`은 `operations`, `planning`, `development` 중 **현재 대상**입니다.
이미 로그인된 프로필은 재로그인하지 않습니다. 최종 probe까지 끝난 직후
동일한 `status --probe`를 추가로 반복할 필요는 없습니다.

**모델 검사는 순수 조회가 아닙니다.** `models`와 `profiles --probe`는 catalog를
확인하고 정책의 모델을 설정한 뒤 실제 추론을 합니다. `models`는 세 프로필의
인증 정책도 저장합니다. 기존 설치를 이어갈 때는 먼저 로컬 `*_AUTH`/`*_MODEL`,
서버 `/var/lib/oracle-ai-stack/profile-auth-policy.json`, 현재 각 프로필의
`openclaw.json`에 지정된 제공자/모델이 일치하는지 비밀값 출력 없이 확인합니다.
이미 선택한 모델을 기본값으로 바꾸지 않도록 그 선택을 로컬 설정에 명시합니다.
일치 여부가 불명확하면 정책을 덮지 말고 차이를 먼저 해결합니다.
프로필별 인증 저장소를 복사해 로그인 단계를 생략하지 않습니다.
진행 중인 worker 때문에 검사가 보류되면 작업을 강제로 종료하지 않습니다.

## 3. OpenClaw 화면 연결과 내 브라우저 승인

### 사용자에게 안내할 순서

1. `https://openclaw.<실제 도메인>`을 평소 사용할 브라우저에서 엽니다.
   공개 모드는 Tailscale이 필요 없습니다. 개인 창은 이후 재접속마다 기기
   정보가 사라질 수 있으므로 주 브라우저는 일반 프로필을 사용합니다.
2. 로그인/연결 화면의 Gateway token 또는 **Settings → Gateway → Gateway
   secret** 입력란에 에이전트가 안전하게 전달한 **기존 operations Gateway
   토큰**을 입력하고 Connect를 누릅니다. 이름은 설치 버전에 따라 다릅니다.
   ChatGPT 비밀번호나 OCI/Cloudflare API 키를 여기에 넣지 않습니다.
3. `pairing required`가 보이면 “지금 이 브라우저에서 연결했어요”라고 답합니다.
   에이전트가 아래 절차로 본인 요청을 확인해 승인한 뒤 다시 연결합니다.
4. 채팅에서 새 대화를 만들고 에이전트가 정한 일회성 확인 문장을 보냅니다.
   입력란에 쓴 문장이 아니라 **실제 assistant 응답**을 확인합니다.

### 에이전트의 토큰 전달

이 패키지의 기본 원본은 서버
`/home/openclaw/.openclaw-operations/openclaw.json`의
`gateway.auth.mode=token`, `gateway.auth.token`입니다.
설치 당시 만든 값을 재사용합니다. 비밀번호 방식 등으로 사용자가 변경한 경우
실제 설정을 따르고 토큰을 새로 만들거나 인증을 비활성화하지 않습니다.

사용자 전용 비밀 저장소/보안 입력 도구가 있으면 토큰을 직접 입력합니다.
없으면 검증된 SSH 경로의 root 읽기 결과 중 **토큰 필드만** 로컬 0600 파일로
직접 스트리밍하고 사용자 로컬 편집기로 엽니다. 부모 폴더는 0700이며 기존
파일을 덮지 않습니다. SSH 출력이 LLM 응답·명령 로그에 반환되지 않는 방식이어야
합니다. 사용자에게는 파일 경로와 입력 위치만 알려줍니다. 완료 후 이 임시
전달 파일만 정리하며 서버의 토큰/인증 저장소는 보존합니다.
그런 비밀 전달 경로가 없는 에이전트는 사용자 전용 터미널에서 처리하도록
안내하고 이 단계를 PENDING으로 남깁니다. 채팅에 토큰을 붙이는 대안은 쓰지 않습니다.

### 에이전트의 기기 요청 확인

아래는 **검증된 SSH로 접속한 서버의 operator Bash**에서 실행할 예시입니다.
OpenClaw는 Docker 컨테이너가 아니라 native 설치입니다. 기본 프로필이나 root의
OpenClaw 설정을 잘못 읽지 않도록 operations의 사용자·환경·바이너리를 지정합니다.
먼저 설치된 버전의 `devices --help`를 확인합니다.

```bash
oc=(sudo -u openclaw -H env
  OPENCLAW_STATE_DIR=/home/openclaw/.openclaw-operations
  OPENCLAW_CONFIG_PATH=/home/openclaw/.openclaw-operations/openclaw.json
  PATH=/home/openclaw/.local/lib/openclaw-cli/tools/node/bin:/usr/bin:/bin
  /home/openclaw/.local/lib/openclaw-cli/bin/openclaw --profile operations)
"${oc[@]}" devices --help
"${oc[@]}" devices list --json
```

연결 시각·기기/클라이언트 정보·요청 권한을 사용자의 방금 연결과 대조합니다.
여럿이면 가장 최근 것을 자동 선택하지 말고 사용자 기기를 식별합니다.
민감한 응답은 로컬에서 필요한 메타데이터만 추출해 다룹니다.
확인한 **현재 requestId만** `REQUEST_ID`에 저장하고 다음 명령을 실행합니다.

```bash
"${oc[@]}" devices approve "${REQUEST_ID:?먼저 사용자 기기의 요청 ID를 확인하세요}"
```

`--latest`, 일괄 승인, 기기 목록 초기화, 인증 우회는 재개 절차가 아닙니다.
요청 ID가 재접속으로 바뀌면 새 요청을 다시 확인합니다. CLI 권한이 없으면
기존 승인된 소유자 화면의 기기 관리에서 그 요청만 승인하거나 권한 문제를
보고합니다. 관리 권한을 얻으려고 토큰·기기 ID를 바꾸지 않습니다.

### 완료로 표시할 실제 근거

- 선택한 경로의 HTTPS 연결과 실제 대상 IP. 공개 모드 검증에 Tailnet IP를
  사용하지 않습니다. `/healthz`의 200만으로 로그인·대화 성공을 표시하지 않습니다.
- 해당 브라우저에서 확인한 새 assistant 응답. 브라우저 도구가 없으면
  사용자에게 같은 채팅을 수행하도록 안내하되, 직접 보지 못한 결과는
  `SELF_REPORTED`로 구분하고 “AI가 직접 검증”으로 표시하지 않습니다.
- 별도 미인증 브라우저에서는 모델 작업을 실행할 수 없음. 정적 화면이
  열리는 것 자체는 실패가 아닙니다. 주 브라우저의 로그인 정보를 지우지 않습니다.
- 채팅에서의 새 대화 기억·수정·철회, 실제 기획→개발 작업과 샘플 테스트는
  [acceptance.md](acceptance.md)의 별도 항목입니다. CLI marker 성공으로 대체하지 않습니다.

## 4. 백업은 세 결과로 나누기

1. `python3 scripts/stack.py backup`으로 암호화 스냅샷을 만들고 반환된
   snapshot ID와 서비스 재개 결과를 기록합니다. 이 작업은 관리 서비스의
   쓰기를 잠시 멈춥니다. 진행 중인 작업을 임의로 중단하지 않습니다.
2. [lifecycle.md](lifecycle.md#encrypted-backup)의 operator 잠금 아래 서버
   `/var/backups/oracle-ai-stack/restic` 전체를 SSH 스트림으로 **다른 머신인
   로컬 PC의 보호된 보관 폴더**에 복사합니다. 같은 VM의 다른 폴더는 외부
   보관이 아닙니다. `/etc/oracle-ai-stack/restic-password`는 별도 보호된
   복구 키 파일로 전달하며 stdout을 채팅/로그에 노출하지 않습니다.
   외부 저장 서비스 새 가입/업로드를 임의로 추가하지 않습니다.
3. 복사한 저장소에 대해 로컬 restic의 `--repo`, `--password-file` 옵션으로
   `check`와 `snapshots --json`을 실행하고 원래 ID를 확인합니다.
   `python3 scripts/stack.py restore --snapshot <반환된 정확한 ID>`는 서버의
   별도 staging 복원이며 결과와 공간을 확인합니다. 운영 데이터 덮어쓰기가 아닙니다.

외부 복사나 검사 도구가 준비되지 않았다면 정확히 그 단계만 PENDING입니다.
암호화 백업, 외부 복사 확인, staging 복원, 실제 운영 장애 복구를 하나의
“복구 완료”로 합치지 않습니다. 재부팅과 운영 데이터 복원은 이번 로그인 재개의
자동 동작이 아닙니다.

## 5. 마지막 보고와 중단 후 재개

보고에는 접속 URL, 프로필별 실제 인증/응답, 브라우저 대화, 작업 전달·기억,
백업/외부 복사/staging 복원, Star를 각각 완료·실패·미실행으로 구분합니다.
소스 검토, 테스트 통과, 사용자 보고와 실제 서버 실행을 서로 바꿔 쓰지 않습니다.
미완료가 있으면 최소 다음 행동과 `install-progress.md` 경로를 남깁니다.
새 세션에서도 그 파일과 원래 handoff를 읽고 이어가며, state 폴더를 지우거나
새 VM을 만들지 않습니다.

## 공식 근거와 버전 차이

2026-09-15 확인한 [Control UI](https://docs.openclaw.ai/web/control-ui)와
[devices CLI](https://docs.openclaw.ai/cli/devices)가 기본 근거입니다.
현재 문서의 UI 레이블/토큰 명령이 설치 버전과 다를 수 있으므로 로컬 help와
실제 화면을 우선 확인합니다. 이 안내는 새로운 실제 로그인·기기 승인·복구
실행 증거가 아니라, 에이전트가 수행할 구체적인 절차입니다.
