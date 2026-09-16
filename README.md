# one-pass-oci-openclaw

**저장소 URL을 로컬 코딩 에이전트에게 주고 OCI에 OpenClaw를 설치하는 도구입니다.**

현재 수준은 **운영 베타**입니다. 특정 OCI 서버의 실제 대화·프로필 분리·작업
전달은 검증했지만 모든 신규 계정, 리전, 제공자 조합에서 무인 설치를 보증하지는
않습니다. 실행 결과는 `TEST-REPORT.md`와 `references/`의 배포 기록으로 구분합니다.

## 이렇게 요청하세요

Codex처럼 로컬 파일과 터미널을 사용할 수 있는 코딩 에이전트에게 전달합니다.

```text
https://github.com/min9lin9/one-pass-oci-openclaw

이 저장소의 README와 SKILL.md를 읽고 OpenClaw를 설치해줘.
필수 조건을 먼저 확인하고, 준비된 정보는 재사용해.
조건이 충족되면 내부 설치 명령은 네가 실행하고,
내가 직접 해야 하는 로그인이나 없는 필수 정보만 요청해.
기본 공개 HTTPS를 사용하고 기존 데이터와 모델 인증은 보존해.
실제로 접속하고 대화가 되는지 확인한 결과를 보고해.
```

**사용자가 아래 내부 명령을 하나씩 실행할 필요는 없습니다.** 에이전트가
저장소를 읽고 입력 점검, 소스 준비·검토, 설치, 인증 확인을 이어서 수행합니다.
URL을 읽기만 하는 일반 웹 챗봇은 로컬 파일·서버 설치를 대신 실행할 수 없습니다.

**아무것도 준비하지 않았어도 요청부터 할 수 있습니다.** AI는
[처음 설치하기](references/first-install.md)에 따라 로컬 설정 파일을 준비하고
도메인 연결·OCI 키 발급을 한 단계씩 안내합니다. 사용자가 환경변수 목록을
이해해서 작성하는 방식이 아닙니다. 직접 해야 하는 구매·로그인·비밀값 입력만
현재 단계에서 요청합니다.
로그인 뒤에는 “로그인 했어. 계속해”라고 답하면 됩니다. AI는
[로그인 후 이어하기](references/resume-install.md)에 따라 남은 검증을 진행하며,
전체 설치를 다시 실행하지 않습니다.

설치 과정에서는 로컬 GitHub CLI에 로그인되어 있으면 이 저장소
`min9lin9/one-pass-oci-openclaw`에 **Star를 자동 추가하고 확인**합니다.
GitHub 로그인이 없거나 Star 요청이 실패해도 설치는 계속하며 Star만 미완료로
보고합니다. 입력 점검만 실행할 때는 Star나 클라우드 변경을 하지 않습니다.

## 접속 방식

| 설정 | 동작 |
|---|---|
| 기본 `ACCESS_MODE=public` | 일반 인터넷에서 `https://openclaw.<DOMAIN>` 접속 |
| 선택 `ACCESS_MODE=tailscale` | 같은 Tailnet에 연결된 기기에서만 HTTPS 접속 |

기본 모드에는 Tailscale 계정·앱·등록 키가 필요 없습니다.
**공개 HTTPS는 로그인 없는 공개 챗봇이라는 뜻이 아닙니다.**
OpenClaw의 소유자/토큰 인증과 브라우저 기기 승인은 유지합니다.
세 Gateway 포트는 모두 서버 loopback에 남고 외부에는 HTTPS 443만 제공합니다.

Tailscale 모드를 원하면 설치 요청에 “Tailscale 전용으로 설치해줘”를 추가합니다.
기존 Tailscale 설치나 다른 SSH 접근 경로를 임의로 삭제하지 않습니다.

## 준비할 조건

| 구분 | 필요한 것 |
|---|---|
| 로컬 실행 | Python 3.11+, Git, OpenSSH, 파일·터미널 접근 가능한 코딩 에이전트 |
| 도메인 | Cloudflare에 위임한 도메인과 해당 Zone의 조회/DNS 수정 토큰 |
| 기존 서버 사용 | 지원되는 Ubuntu 24.04 ARM64 서버, SSH 키, 검증된 호스트키, sudo 권한 |
| 새 OCI 서버 생성 | OCI 계정/API 서명 정보, 허용된 구획·리전·자원, SSH 허용 공인 CIDR |
| 공개 HTTPS | 서버 공인 IPv4와 OCI 네트워크·호스트 방화벽의 TCP 443 허용 |
| 모델 | ChatGPT 로그인 또는 선택한 OpenCode Go/Zen의 사용 가능한 API 키 |
| Tailscale 선택 시 | 원하는 Tailnet과 서버 등록 수단 |

기존 서버 경로에는 새 OCI 인스턴스 생성용 API 정보가 필요 없습니다.
다만 기존 OCI 네트워크의 443 허용이 없으면 네트워크 관리자 권한이나 콘솔
작업이 필요합니다. 도메인 구매, 계정 생성, 구독, OAuth 로그인, OCI 용량 부족은
설치 프로그램이 성공한 것으로 만들어낼 수 없습니다.

기본 신규 서버는 A1 Flex 2 OCPU/12 GiB, Ubuntu 24.04 ARM, 부트 50 GB입니다.
다른 유료 사양·리전으로 자동 전환하지 않습니다. 이 제한 자체가 무료 사용
보증은 아니므로 계정의 적용 범위와 기존 자원을 확인합니다. Windows는 WSL2를
전제로 하며 모든 로컬 OS 조합에서 실기 시험한 것은 아닙니다.

### 비밀정보는 로컬 파일에만

에이전트는 `templates/secrets.env.example`을 참고해 다음 경로를 확인하고,
없으면 폴더와 파일을 준비합니다. 기존 파일은 보존하며 누락 필드만 안내합니다.

```text
~/.config/oracle-ai-stack/secrets.env
```

파일은 0600, 상위 폴더는 0700 권한으로 관리합니다. 개인키·토큰·비밀번호를
GitHub, 채팅, 로그에 붙여 넣지 않습니다.

주요 입력은 `DOMAIN`, `CLOUDFLARE_API_TOKEN`, `ACCESS_MODE`입니다.
기존 서버에는 `ORACLE_HOST`, `ORACLE_SSH_KEY`, `SSH_KNOWN_HOSTS`를 사용하고,
SSH 주소와 공개 접속 주소가 다르면 `PUBLIC_IP`를 지정합니다.
새 서버에는 템플릿의 `OCI_*` 입력을 사용합니다.
`TAILSCALE_AUTH_KEY`는 Tailscale 모드에서 서버 등록이 필요할 때만 사용합니다.

## 에이전트가 수행하는 설치 흐름

1. 패키지 무결성과 로컬 실행 도구, 비밀 파일 권한, 필요한 입력을 점검합니다.
2. 이미 준비된 서버·호스트키·검토된 소스는 확인 후 재사용합니다.
3. 소스 준비가 필요하면 정확한 버전을 내려받고 에이전트가 실제 코드를
   검토한 후 검토 기록을 봉인합니다. 형식적인 검토 영수증은 만들지 않습니다.
4. 조건이 갖춰지면 기존 구축 도구로 서버 구성과 설치를 실행합니다.
5. 모델 로그인이나 새 브라우저 승인이 필요한 경우 그 단계만 사용자에게
   안내하고, 인증이 끝나면 검증을 이어갑니다.
6. 실제 HTTPS·모델 응답·작업 전달 결과와 미완료 항목을 구분해 보고합니다.

`SKILL.md`가 에이전트의 상세 실행 계약입니다. 준비 명령이나 프로세스의
종료 코드 0만으로 설치·로그인·대화가 모두 끝났다고 보고하지 않습니다.
기존 `stack.py`의 세부 명령과 명시적 스킬 설치도 계속 사용할 수 있습니다.

```bash
# 에이전트용: 입력과 검토 상태만 확인
python3 scripts/bootstrap.py
# 준비된 조건으로 실행; 검토가 필요하면 그 상태와 경로를 반환
python3 scripts/bootstrap.py --apply
# 에이전트가 실제 소스를 검토한 뒤 생성한 로컬 기록 사용
python3 scripts/bootstrap.py --apply --review-notes /absolute/private/review-notes.md

python3 scripts/check.py
python3 scripts/install_skill.py
```

기존 설치의 네트워크 모드만 변경할 때는 명시한 모드와 검토된 stage로
`python3 scripts/stack.py network`를 사용합니다. 전체 런타임 재설치나
모델 재인증 대신 네트워크 변경 후 실제 클라이언트 접속을 확인합니다.

스킬 위치는 `~/.agents/skills/one-pass-oci-openclaw`이며 기존 사용자 수정본을
덮어쓰지 않습니다. “이 URL을 설치해줘”는 명시적인 설치 요청입니다.
단순 정보 질문을 자동 설치 요청으로 취급하지 않습니다.

## 설치되는 구성

| 역할 | 구성 |
|---|---|
| 사용자 화면 | OpenClaw Control UI |
| 운영 | `operations` / Unix `openclaw` / 18789 / GBrain·gstack |
| 기획 | `planning` / Unix `clawplan` / 19789 / ECC 기획·설계 방법론 |
| 개발 | `development` / Unix `clawdev` / 20789 / ECC TDD·리뷰 방법론 |
| HTTPS | Docker 기반 Caddy, Cloudflare DNS-01 인증서 |
| 보조 도구 | 제한된 공개 페이지 읽기, 문서·Mermaid·MCP 보조 도구 |
| 복구 | restic 암호화 백업, 관리되는 GBrain PostgreSQL 볼륨 포함, 별도 위치 복원 검증 |

Buzz는 설치·실행에 필요하지 않습니다. 과거 Buzz 데이터는 별도 삭제 요청
없이 지우지 않습니다. 운영은 인프라 관리자가 아니며 OCI/SSH/DNS 관리 키,
Docker 소켓이나 무제한 sudo를 받지 않습니다.

프로필은 UID·작업공간·인증 저장소를 분리합니다. 작업 전달은 이 패키지의
Unix 소켓 어댑터이며 OpenClaw 네이티브 cross-profile 기능으로 설명하지
않습니다. GBrain/gstack은 운영 전용이고, 외부 MCP 서버는 자동 연결하지 않습니다.
전체 gstack은 별도 하네스 인증과 실제 실행을 확인해야 합니다.

현재 검증된 운영 서버의 GBrain은 전용 PostgreSQL로 전환했습니다.
신규 설치 기본값은 PGlite이며, 기존 PostgreSQL 설정은 보존합니다.
전환·데이터 보존·백업 범위는 [GBrain PostgreSQL 기록](references/gbrain-postgres.md)을
참조합니다.

## 운영과 현재 한계

- `status`의 `SERVICES_RUNNING`은 서비스 실행 상태입니다. 실제 클라이언트나
  모든 확장의 검증 완료를 뜻하지 않습니다.
- 최초 OAuth·기기 승인, 제3자 소스 변경에 따른 검토, OCI 용량 부족 등의
  외부 조건은 명시적으로 남깁니다.
- 백업은 암호화·외부 반출·복원 확인을 구분합니다. 복원 명령은 별도 staging
  경로까지이며 운영 데이터를 자동 덮어쓰지 않습니다.
- 재시작·업데이트·삭제는 `references/lifecycle.md`를 따릅니다. 사용자 수정,
  기존 데이터, 불명확하게 끝난 작업을 임의로 덮어쓰거나 재실행하지 않습니다.
- Gateway는 `Restart=always`를 사용해 플러그인 변경에 따른 정상 종료 후에도
  다시 시작합니다. 명시적인 유지보수 정지는 그대로 존중합니다.

근거: `TEST-REPORT.md`, `REVIEW.md`, `SECURITY.md`,
`references/openclaw-only.md`, `references/source-review.md`.
현재 공개 접속 전환과 설치 완성도는 `references/public-installation.md`에서
완료 사실과 외부 미완료 조건을 구분합니다.
패키지 파일 목록·해시는 `PACKAGE-MANIFEST.json`으로 확인합니다.
MIT 라이선스는 자체 코드에 적용되며 외부 소스는 각 원본 라이선스를 따릅니다.
