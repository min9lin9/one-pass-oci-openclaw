# one-pass-oci-openclaw

**개인 PC의 Codex에서 호출하는 OCI → OpenClaw 전용 구축 스킬.**

`min9lin9/one-pass-oci-openclaw`라는 요청된 이름을 그대로 사용합니다. 제품 이름은 **OpenClaw**이며, 저장소 이름의 `openclaw`는 의도적으로 보존했습니다.

**버전: 0.4.0-beta · 검토일: 2026-09-14**

> 현재 설계: 사용자 결정에 따라 Buzz를 제외하고 OpenClaw의 웹 화면을 사용합니다.
> 기존 원격 저장소의 보안·CI 개선은 유지합니다. 패키지 검사와 특정 OCI 인스턴스의
> 실사용 검증은 구분하며, 배포 기록은 `references/openclaw-only.md`에 남깁니다.

## 1. 무엇을 하는 스킬인가

사용자가 OCI API 서명 정보와 도메인·DNS·Tailscale·모델 인증 정보를 로컬 파일에 준비하면, **로컬 Codex가 이 스킬과 스크립트를 사용하여** 소스 검토, OCI 생성, SSH 연결, 설치, 인증, 역할 분리, 기능 시험을 진행합니다.

`one-pass`는 “한 스킬 안에서 생성부터 점검까지 이어 간다”는 뜻입니다. 모든 외부 서비스의 최초 승인이나 용량 부족이 사라진다는 의미, 임의의 소스를 검토 없이 root로 실행한다는 의미, 단일 셸 명령의 무조건 성공 보증이 아닙니다.

### 유지한 구성

| 구역 | 구성 |
|---|---|
| OCI | A1 Flex ARM, 2 OCPU / 12GB, Ubuntu 24.04, 기본 부트 50GB |
| 최초 생성 | `min9lin9/oci-instance-creator` 절차를 참고한 공식 OCI SDK 어댑터 |
| 접근 | Tailscale 내부 전용, Cloudflare DNS-only 레코드, DNS-01 HTTPS |
| 사용자 화면 | OpenClaw Control UI |
| 도메인 | `openclaw.<domain>` |
| 운영 | `operations` / Unix `openclaw` / 내부 18789 / GBrain + gstack |
| 기획 | `planning` / Unix `clawplan` / 내부 19789 / ECC Planner + Architect |
| 개발 | `development` / Unix `clawdev` / 내부 20789 / ECC TDD + Code Reviewer |
| 모델 | 각 프로필의 ChatGPT OAuth 또는 OpenCode Go/Zen API 키 |
| 필수 확장 | gstack 네이티브 방법론, insane-search, 프롬프트 스킬, 문서·도식·MCP 보조 도구 |
| 운영 도구 | restic 암호화 백업, Gitleaks, 독립 상태·작업 기록 |

사용자는 Tailscale에 연결한 뒤 `https://openclaw.<domain>`으로 접속합니다.
Gateway 인증과 브라우저 기기 승인은 유지합니다. Buzz 앱, 소유자 키, 방 생성은
필요하지 않습니다. Caddy HTTPS 프록시는 Docker를 사용하지만 Buzz의
Relay/PostgreSQL/Redis/MinIO는 정상 설치·실행 경로에서 제외합니다.

## 2. Codex에 설치

압축을 푼 `one-pass-oci-openclaw` 폴더 안에서 실행합니다.

```bash
python3 scripts/check.py
python3 scripts/install_skill.py
```

사용자 스킬 위치는 `~/.agents/skills/one-pass-oci-openclaw`입니다. 기존 대상이 있으면 덮어쓰지 않고 중단합니다. 이전 `oracle-ai-stack` 스킬이 설치되어 있으면 사용자 수정본을 보존한 뒤, Codex에서 동시에 선택되어 혼동되지 않도록 명시적으로 정리합니다.

호출:

```text
$one-pass-oci-openclaw

~/.config/oracle-ai-stack/secrets.env를 사용해 OCI 생성부터 구축해.
소스를 검토하고 버전을 고정한 뒤 실행해.
OpenClaw만 사용하고 Tailscale 전용 도메인은 유지해. operations에 GBrain·gstack,
planning·development에는 독립 프로필과 지정된 모델 인증을 적용해.
이미 확정한 요구는 다시 묻지 말고, 빠진 필수값·필요한 사용자 승인만 요청해.
실행하지 않은 항목을 완료로 표시하지 마.
```

설치 스킬은 명시적 호출을 기본으로 합니다. 단순한 일반 질문 때문에 OCI 자원 생성이나 설치를 시작하지 않도록 `allow_implicit_invocation: false`를 설정했습니다.

## 3. 로컬 입력 준비

기본 실행 환경은 POSIX 셸, Python 3.11 이상, Git, OpenSSH입니다. Windows는 WSL2 사용을 전제로 합니다. 모든 로컬 OS에서 실기 시험한 것은 아닙니다.

```bash
mkdir -p ~/.config/oracle-ai-stack
chmod 700 ~/.config/oracle-ai-stack
# 기존 파일이 없을 때만 복사합니다.
cp -n templates/secrets.env.example ~/.config/oracle-ai-stack/secrets.env
chmod 600 ~/.config/oracle-ai-stack/secrets.env
```

이 파일을 **로컬 편집기**에서 작성합니다. 토큰·개인키 본문을 Codex 대화나 Git에 붙여 넣지 않습니다.

| 입력 | 용도 |
|---|---|
| `DOMAIN` | 이미 보유·위임된 도메인 |
| `CLOUDFLARE_API_TOKEN` | 해당 Zone 조회 및 DNS 수정 |
| `CLOUDFLARE_DNS01_TOKEN` | 선택: 인증서용 최소 범위 토큰 분리 |
| `TAILSCALE_AUTH_KEY` | 기존 Tailnet에 서버 등록 |
| `OCI_USER`, `OCI_FINGERPRINT`, `OCI_TENANCY`, `OCI_REGION`, `OCI_KEY_FILE` | 등록된 OCI API 서명 정보 |
| `OCI_SSH_ALLOWED_CIDR` | 새 네트워크에 허용할 로컬 PC의 공인 IPv4, 기본 권장 `/32` |
| `OPENCODE_API_KEY` | Go 또는 Zen 이용 권한이 있는 키; 선택 |
| `OPERATIONS_AUTH`, `PLANNING_AUTH`, `DEVELOPMENT_AUTH` | `chatgpt`, `opencode-go`, `opencode` 중 선택 |
| `*_MODEL` | 선택: 해당 제공자 카탈로그에서 검증할 실제 모델 참조 |

OCI 서명키와 SSH 키는 다릅니다. OCI 계정·API 키 등록·도메인 구매·Tailnet 계정·유료 모델 구독은 자동으로 만들어진 것으로 가정하지 않습니다. API 키가 있더라도 Go와 Zen의 이용 권한이 같다고 가정하지 않습니다.

기본 모델 배치는 운영 ChatGPT, 기획/개발 OpenCode Go입니다. OpenCode 키가 없으면 각 프로필의 ChatGPT 인증으로 구성할 수 있습니다. ChatGPT 비밀번호나 OAuth 토큰을 `.env`에 넣지 않습니다.

## 4. 실제 실행 흐름

Codex는 `SKILL.md`를 읽고 다음 절차를 진행합니다. 아래는 내부 작업 단계이며 모든 명령을 사용자가 직접 타이핑해야 한다는 뜻은 아닙니다.

```text
plan → prepare → source review → seal → oci-plan → setup
     → profile OAuth / models → OpenClaw browser authentication
     → gstack full-host checks → GBrain recall → delegation → client acceptance
     → backup / off-host copy / staged restore / recovery drill
```

소스 준비·검토:

```bash
python3 scripts/stack.py plan
python3 scripts/stack.py prepare
python3 scripts/stack.py seal --review-notes /absolute/local/review-notes.md
python3 scripts/stack.py oci-plan
python3 scripts/stack.py setup
```

`prepare`는 소스를 고정할 뿐 설치 스크립트를 실행하지 않습니다. 검토 기록은 로컬에 남기고 **원문 review-notes.md는 서버 업로드에서 제외**합니다. 원본 파일의 경로·실행 비트·내용을 해시로 검증합니다. v0.3에서 만든 소스 검토 기록은 새 방식으로 다시 준비·검토해야 합니다.

원본 및 직접 지정한 패키지 버전을 고정하지만, **모든 전이 의존성의 완전한 재현성·무해성이 보증되는 것은 아닙니다.** npm integrity는 현재 기록 항목이며 모든 다운로드 경로에서 독립 검증하는 장치로 오인하지 않습니다.

### OCI 생성과 안전한 재개

관리 태그·OCID·재시도 토큰을 사용합니다. VCN/서브넷 등은 AVAILABLE 상태를 확인한 뒤 다음 단계에 사용합니다. 자동 생성은 지역 서브넷을 사용하며, 별도로 준 AD 전용 서브넷은 검토 없이 사용하지 않습니다.

용량 부족은 제한된 재시도 후 중단합니다. 다른 리전·유료 사양·확대 자원·무한 cron은 활성화하지 않습니다. 2/12/50 제한은 비용 보증이 아니므로 계정의 기존 자원과 무료 적용 범위를 별도로 확인합니다.

SSH 호스트키는 OCI 제어 평면에서 확보한 지문과 비교합니다. `StrictHostKeyChecking=no`나 단순 TOFU로 대체하지 않습니다. 기존 서버를 사용할 때도 업로드 전 읽기 전용 검사에서 OS·소유권·관리 표식·도메인을 검증합니다.

### 인증

```bash
python3 scripts/stack.py oauth --profile operations
python3 scripts/stack.py models --profile operations
python3 scripts/stack.py models --profile planning
python3 scripts/stack.py models --profile development
```

`models list --agent/--refresh`는 사용하지 않습니다. 현재 문서에 맞춰 `models refresh`와 `models list --all --provider`를 분리했습니다. 인증 메타데이터 검사 후 실제 Gateway에 작은 표식 응답을 요청하고, **응답 본문과 선택된 모델 식별자가 일치해야** 준비 완료로 기록합니다. 이 검사는 모델 사용량을 소비할 수 있습니다.

프로필별 OAuth 저장소는 별도입니다. 로컬 Codex 인증 캐시를 복사하지 않습니다. 전체 gstack용 별도 Codex 하네스 인증도 OpenCode API 키로 대체하지 않습니다.

## 5. 오케스트레이션과 권한

운영은 OpenClaw 웹 화면의 요청을 받고 GBrain 기억과 gstack 방법론을 사용해 기획·개발에 일을 분배합니다. 운영은 **인프라 관리자 계정이 아닙니다**. OCI 서명키·Cloudflare 키·Docker 소켓·무제한 sudo를 받지 않습니다.

작업 전달은 이 패키지의 Unix 소켓 어댑터입니다. OpenClaw 네이티브 기능이 독립 프로필 간 작업을 자동 전달한다고 설명하지 않습니다. 같은 UUID의 다른 입력은 거부하고, 통신 중단으로 결과가 불명확하면 자동 재실행하지 않습니다.

기획은 읽기·검색 도구만 허용하고, 개발은 자신의 작업공간에서 구현·테스트합니다. 역할 지침은 작업 순서를 정하며, 실제 권한은 도구 정책·Unix 계정·서비스 설정으로 나눕니다. `approved_plan`은 작업 흐름 필드이지 사람의 서명된 승인 증거가 아닙니다.

GBrain/gstack은 운영 전용입니다. GBrain은 키 없는 메모리 경로만 사용하며 유료 임베딩·자동 수집·Dream 작업을 활성화하지 않습니다. 전체 gstack의 인증·실제 하네스 연결은 여전히 추가 검증이 필요한 단계입니다. 파일 설치를 전체 기능 사용 가능 상태로 표시하지 않습니다.

insane-search는 별도 `clawfetch` 계정으로 제한합니다. 원본의 Star 요청·무제한 재시도·유료 경로 자동 실행은 사용하지 않습니다. egress 규칙은 이 계정의 네트워크 범위에만 적용되며 **OpenClaw의 모든 네트워크 도구를 격리하지는 않습니다.**

## 6. 점검·백업·복구

```bash
python3 scripts/stack.py status
python3 scripts/stack.py profiles --probe
python3 scripts/stack.py memory-smoke
python3 scripts/stack.py acceptance
python3 scripts/stack.py backup
python3 scripts/stack.py restore --snapshot <실제_snapshot_id>
```

설치·OAuth·업로드·백업의 root 작업은 공통 잠금으로 중복 실행을 막습니다. 인증 설정·백업은 서비스 중단이 생길 수 있으므로 사용 중인 작업을 정리한 유지보수 구간에 수행합니다. 실행 중인 위임 작업을 암묵적으로 죽이지 않습니다.

백업 중지 후 서비스가 재시작되지 않으면 **백업 명령도 실패**하며, 스냅샷과 재개 실패 구성 요소를 별도 기록합니다. 기존 백업 저장소의 암호 파일이 없으면 임의 새 암호를 만들지 않습니다.

**복원 명령은 별도 경로로 복원·검증하는 단계까지입니다.** 실행 중인 데이터 덮어쓰기와 실제 복구 훈련, 업데이트 적용, OCI 자원 삭제까지 완전 자동 구현했다고 주장하지 않습니다. 자세한 절차는 `references/lifecycle.md`를 따릅니다.

`status`는 보수적인 상태 보고이며 클라이언트 TLS와 실제 OpenClaw 응답 등
미검증 항목을 구분합니다. Buzz 상태나 방 권한은 완료 조건이 아닙니다.
`SERVICES_RUNNING`은 실행 중인 서비스 상태이며 전체 인수 검증 완료가 아닙니다.
단순 파일 존재, 표식 응답, 컨테이너 명령 종료를 전체 성공으로 승격하지 않습니다.

## 7. 저장소에 게시

**이 배포 파일 자체는 GitHub 게시 완료의 증거가 아닙니다.** 게시 도구는 로컬 GitHub CLI가 `min9lin9`로 인증되어 있을 때만 실행됩니다.

```bash
# 게시할 파일과 기본 비공개 설정만 확인: 네트워크/쓰기 없음
python3 scripts/publish.py

# 정확한 저장소 생성 및 초기 커밋 게시, 원격 커밋 확인
python3 scripts/publish.py --apply
```

기본 대상은 **`min9lin9/one-pass-oci-openclaw`**, 기본 공개 범위는 **비공개**입니다. 공개 배포를 명시적으로 결정한 경우에만 `--public`을 추가합니다. 원격 저장소가 비어 있지 않으면 덮어쓰기·force push 없이 중단합니다. 이미 존재하는 저장소의 업데이트는 해당 저장소를 읽은 뒤 일반 브랜치/PR로 검토합니다.

명시한 파일만 게시하고, 로컬 secret·OCI 키·상태·소스 staging·검토 원문은 포함하지 않습니다. `PACKAGE-MANIFEST.json`과 실제 바이트가 다르면 게시를 거부합니다. 해시와 탐지 규칙은 검토 보조 장치이지 악성 코드·모든 비밀정보 부재의 증명은 아닙니다.

## 8. 검토 결과와 남은 한계

변경 근거는 `REVIEW.md`, 실행한 검사는 `TEST-REPORT.md`, 보안 경계는 `SECURITY.md`에 있습니다.

새 OCI 인스턴스 생성, 모든 제공자·사양의 부하, 호스트 재부팅과 실제 운영 데이터의
덮어쓰기 복구를 보편적으로 검증했다고 주장하지 않습니다. WineyCellar의 실제 결과와
현재 검사 결과는 `references/openclaw-only.md`를 확인합니다.

루트의 `Design.md` 같은 강의 디자인 자료나 개인 자료는 이 저장소의 코드/검증 근거가 아니며 포함하지 않습니다.

### 공식 참고자료

- Codex Skills: https://developers.openai.com/codex/skills/
- OpenClaw 복수 Gateway: https://docs.openclaw.ai/gateway/multiple-gateways
- OpenClaw 모델 CLI: https://docs.openclaw.ai/cli/models
- OpenClaw Agent CLI: https://docs.openclaw.ai/cli/agent
- GitHub CLI 저장소 생성: https://cli.github.com/manual/gh_repo_create
- 원본 저장소·구성 근거: `references/sources.md`, `manifests/`

MIT 라이선스는 이 패키지의 자체 코드에 적용합니다. 외부 프로젝트는 각 원본 라이선스를 따릅니다.
