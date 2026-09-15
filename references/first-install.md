# 처음 설치하기: 사용자는 결정·로그인, AI는 파일 준비·실행

이 문서는 README를 받은 **로컬 코딩 에이전트의 진행 순서**입니다.
사용자에게 이 문서 전체나 환경변수 목록을 숙제로 넘기지 않습니다.
도메인 구매와 계정 로그인은 사람이 하지만, 설정 파일 작성과 명령 실행은
에이전트가 맡습니다. 이미 준비된 항목은 다시 묻지 않습니다.

## 1. 첫 응답과 로컬 준비

1. 저장소를 로컬 작업 폴더에 확보하고 README, SKILL, 이 문서를 읽습니다.
   로컬 파일·터미널 실행 권한이 없는 웹 챗봇이라면 그 한계를 먼저 알립니다.
2. 운영체제와 Python 3.11+, Git, OpenSSH를 확인합니다. Windows에서는 WSL2
   내부 경로를 사용합니다. 도구가 없으면 공식 설치 경로를 안내하거나
   사용자의 로컬 설치 요청 범위에서 준비합니다. 준비됐다고 가정하지 않습니다.
3. 기본 설정 경로 `~/.config/oracle-ai-stack/secrets.env`가 없으면 에이전트가
   템플릿으로 준비합니다. 폴더 0700, 파일 0600; 기존 파일은 덮어쓰지 않습니다.
   확인된 비밀 아닌 값은 채우고 모르는 값은 비워 둡니다. 예시 값을 실제
   도메인·OCID·공인 IP로 쓰지 않습니다. 토큰은 사용자가 로컬 편집기에 넣거나
   승인된 비밀 저장소에서 직접 전달하며, 채팅·터미널 로그에는 출력하지 않습니다.
4. `python3 scripts/bootstrap.py`를 실행합니다. 최초 `INPUT_REQUIRED`의
   `required_inputs=["secrets_file"]`는 다른 조건이 충족됐다는 뜻이 아닙니다.
   파일을 준비한 뒤 다시 점검하면 누락 필드가 나옵니다.
5. 새 서버가 기본입니다. 기존 서버가 있다고 하면 그 경로로 전환합니다.
   **설정에 값이 없음은 사용자가 그 자원을 보유하지 않았다는 뜻이 아닙니다.**
   도메인 보유 여부가 아직 확인되지 않았다면 첫 질문은 “이미 가지고 있는
   도메인이 있나요? 있으면 주소만 알려주세요”입니다. 이 단계에서는 구매
   링크나 결제를 다음 행동으로 제시하지 않습니다. 있다고 답하면 그 도메인을
   재사용하고, **없다고 답한 경우에만** 아래 구매 안내로 넘어갑니다.
   OCI 계정·키도 빈 필드만 보고 새로 만들라고 하지 않습니다.
   이미 로컬에서 확인한 OS·계정 경로는 묻지 않습니다.

사용자에게 매번 전달할 내용은 **현재 단계 / AI가 한 일 / 사용자가 지금 할
일 하나 / 완료 후 답할 말**입니다. 예를 들어 사용자가 도메인이 없다고 답했다면:

> 지금은 접속 주소를 준비하는 단계입니다. 설정 파일과 로컬 도구는 제가
> 준비하겠습니다. 먼저 아래 도메인 등록 화면에서 사용할 주소를 선택하고
> 결제는 직접 진행해 주세요. 끝나면 도메인 이름만 알려주세요.

도메인 선택·결제 없이 AI가 임의로 주소를 구매하지 않습니다. 기존 도메인이
있으면 구매를 건너뜁니다. Tailscale을 골라도 이 패키지는 도메인이 필요합니다.

## 2. 접속 주소: 도메인과 Cloudflare

도메인은 `example.com` 같은 접속 주소의 바탕이고, 실제 화면은
`https://openclaw.example.com`에 생깁니다. `DOMAIN`에는 `https://`나
`openclaw.`를 붙이지 않은 보유 도메인을 저장합니다.

### 도메인이 없는 경우

- [Cloudflare 도메인 등록](https://dash.cloudflare.com/?to=/:account/domains/register)
  또는 사용자가 선택한 등록업체에서 본인이 주소·갱신 가격을 확인하고 구매합니다.
- Cloudflare Registrar로 구매한 도메인은 Cloudflare DNS를 사용하므로 아래
  외부 업체 네임서버 변경은 건너뜁니다. 다른 업체에서 샀다면 다음 절차를 따릅니다.

### 다른 업체에 도메인이 있는 경우

1. [Cloudflare](https://dash.cloudflare.com)의 **Domains → Onboard a domain**에서
   보유 도메인을 추가합니다. DNS용 Free 플랜으로 시작할 수 있습니다.
2. 기존 웹사이트·메일 DNS 기록을 확인합니다. 자동 검색이 모든 기록을
   가져온다고 가정하거나 기존 기록을 삭제하지 않습니다.
3. 안내된 두 네임서버 이름을 도메인 등록업체의 네임서버 설정에 입력합니다.
   기존 DNSSEC가 활성화돼 있으면 아래 공식 안내의 이전 절차를 먼저 확인합니다.
4. Cloudflare에서 도메인이 **Active**가 됐는지 확인합니다. Pending이면
   아직 설치 준비 완료가 아닙니다. AI는 NS 조회로 확인하고, 등록업체의 반영이
   필요한 경우 그 상태와 다시 확인할 방법을 알려줍니다.

### DNS 수정 토큰

1. [My Profile → API Tokens](https://dash.cloudflare.com/profile/api-tokens/)에서
   **Create Token → Edit zone DNS** 템플릿을 선택합니다.
2. 권한을 **Zone / DNS / Edit**, **Zone / Zone / Read**로 맞춥니다.
3. Zone Resources는 **Include / Specific zone / 사용할 도메인**으로 제한합니다.
   전체 계정 키나 Tunnel 권한은 필요하지 않습니다.
4. **Continue to summary → Create Token**을 누릅니다.
5. 한 번 표시되는 토큰을 AI가 준비한 로컬 설정 파일의
   `CLOUDFLARE_API_TOKEN`에 넣습니다. 사용자에게는 “토큰을 로컬 파일에
   저장했어요”라고 답하도록 안내합니다. 토큰 자체를 답변으로 받지 않습니다.

`CLOUDFLARE_DNS01_TOKEN`은 별도 인증서 전용 토큰을 쓸 때만 필요합니다.
없으면 기본 토큰을 재사용합니다. 토큰에 IP 제한을 걸면 로컬 PC의 DNS 작업과
서버의 인증서 발급·갱신 요청 양쪽이 허용돼야 합니다.
AI는 서명 없는 변수 존재 검사와 실제 Zone 접근·DNS 권한 확인을 구분합니다.

## 3. 새 OCI 서버: 가입 다음에 필요한 것

OCI API 키는 **AI가 사용자의 OCI 계정으로 서버를 만드는 데 쓰는 서명 키**입니다.
서버 SSH 키, ChatGPT 로그인, 모델 API 키와 다릅니다.
`ORACLE_HOST`로 기존 서버를 쓰는 경우 이 API 키 준비를 건너뜁니다.

1. [OCI Console](https://cloud.oracle.com/)에 사용자가 직접 로그인합니다.
2. **Profile → User settings → API Keys → Add API Key**로 이동합니다.
   계정 화면이 다르면 사용자 상세 화면의 API Keys를 찾고 아래 공식 문서를
   확인합니다. AI가 보지 않은 화면에서 클릭을 완료했다고 보고하지 않습니다.
3. **Generate API Key Pair**에서 **Download Private Key**로 개인키를 저장하고
   **Add**를 누릅니다. 에이전트가 파일 경로를 확인하고 0600 권한을 설정합니다.
   이미 등록한 키가 있으면 그 키의 **View configuration file**을 재사용합니다.
4. **Configuration File Preview** 내용을 새 로컬 파일
   `~/.oci/openclaw-config`에 저장합니다. 에이전트가 폴더·빈 파일·편집기를
   준비할 수 있습니다. 기존 `~/.oci/config`나 다른 프로필을 덮어쓰지 않습니다.
5. 사용자에게 “설정 미리보기를 저장했고 개인키 파일은 이 경로에 있어요”라고
   답하도록 합니다. 에이전트가 아래처럼 변환하므로 사용자는 변수명을 외울
   필요가 없습니다. `key_file` 예시 경로 대신 실제 다운로드 경로를 사용합니다.

| OCI 미리보기 | 설치 설정 |
|---|---|
| `user` | `OCI_USER` |
| `fingerprint` | `OCI_FINGERPRINT` |
| `tenancy` | `OCI_TENANCY` |
| `region` | `OCI_REGION` |
| 실제 개인키 경로 | `OCI_KEY_FILE` |

에이전트는 사용할 구획·홈 리전·A1 2 OCPU/12 GiB·50 GB 계획을 확인하고,
현재 SSH를 시작하는 PC의 공인 IPv4를 확인해 `OCI_SSH_ALLOWED_CIDR`의 `/32`로
만듭니다. VPN을 쓰면 실제 SSH 출발 주소가 달라질 수 있습니다.
기존 OCI 사용량·비용과 해당 구획의 compute/network/console-history 권한은
별도 확인합니다. 권한 오류는 작업명과 필요한 관리자 조치를 알려주며,
자동으로 관리자 정책을 만들거나 유료 사양으로 바꾸지 않습니다.
API 설정을 모았다는 사실만으로 서버 할당·SSH 접속 성공을 표시하지 않습니다.

## 4. 기존 서버가 있는 경우

에이전트가 필요한 것은 주소, 접속 계정, **개인키 파일 경로**, 호스트 신뢰
정보입니다. 사용자에게 개인키 내용을 채팅으로 달라고 하지 않습니다.
Ubuntu 24.04 ARM64와 sudo 접근을 확인하고 기존 데이터가 있는 서버는 설치
대상과 관리 상태를 점검합니다. 관리되지 않은 기존 설치는 새 설치로 덮지 않습니다.

`SSH_KNOWN_HOSTS`에 검증된 항목이 없으면 서버 콘솔 등 독립 경로에서
호스트키 fingerprint를 확인한 뒤 `stack.py trust-host --fingerprint ...`를
사용합니다. `ssh-keyscan` 출력만 그대로 신뢰하면 검증이 아닙니다.
기존 OCI 네트워크가 443을 허용하지 않으면 대상 VNIC/NSG/보안 목록을 식별하고
그 서버에 한정한 변경을 제시합니다. SSH가 된다고 HTTPS도 된다고 가정하지 않습니다.

## 5. 준비가 끝나면 AI가 이어서 실행

에이전트가 동일한 secrets/stage/state 경로로 `bootstrap.py --apply`를 실행하고,
반환 상태를 읽습니다. 소스 검토는 사용자가 채울 서식이 아니라 에이전트가
실제 소스를 읽고 수행할 작업입니다. `REVIEW_REQUIRED`에서 검토 후 같은
stage를 봉인해 재개하며, 준비를 매번 새로 하거나 검토 영수증을 꾸미지 않습니다.
계정·소스·용량 문제는 해당 단계만 처리하고, 설치된 상태를 지워 재시도하지 않습니다.

`INSTALLED_PENDING_ACCEPTANCE`부터는 [로그인 후 이어하기](resume-install.md)로
넘어갑니다. “로그인 했어요”라는 답을 받았다고 `bootstrap.py --apply`나
`setup`을 다시 실행하지 않습니다.

## 공식 근거

2026-09-15 문서를 확인했습니다. 콘솔 화면은 계정·버전에 따라 달라질 수 있습니다.

- [Cloudflare 도메인 연결](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/)
- [Cloudflare API 토큰 생성](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
- [OCI API 서명 키와 설정 미리보기](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/apisigningkey.htm)
