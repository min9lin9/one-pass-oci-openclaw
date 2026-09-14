# 종합 재검토 — 2026-09-14

## 검토 대상과 방법

대상은 첨부 `oracle-ai-stack-v0.3.zip`의 실제 코드·스킬·참고자료입니다. 기존 104개 테스트를 먼저 실행했고, 통과를 확인했습니다. 이어 주요 설치/상태/권한/프로비저닝/인증/백업/배포 경로를 소스 검토하고 공식 CLI 문서와 비교했습니다.

외부 문서는 CLI 계약 확인에 사용했습니다. 사용자 환경의 실행 결과로 대체하지 않았습니다. 원본에 없는 기능은 이번에 작성한 어댑터로 표시합니다. 원본 v0.3 전체가 안전했거나, 이번 검토가 모든 취약점을 찾았다는 의미는 아닙니다.

## 수정한 문제

| ID | 실제 문제·영향 | 조치 | 확인 |
|---|---|---|---|
| R01 | root 파일 기록에 `.tmp`/`.new` 고정 이름 사용: 미리 놓인 링크를 따라 외부 파일 손상 가능 | 경로별 `O_NOFOLLOW`, 디렉터리 FD, 배타 생성 난수 임시파일, 원자 교체, hardlink/특수파일 거부 | 임시 링크·부모 링크·대상 링크·hardlink·FIFO 실제 임시파일 시험 |
| R02 | 에이전트 소유 홈에 root `copytree` 수행 | GBrain/gstack 및 운영 어댑터 복사를 해당 비특권 UID로 실행; root 소유권 변경은 FD 기반 | 코드 검사·회귀 검사; 실서버 경합 공격 시험은 미실행 |
| R03 | `models list --agent --refresh`가 현재 문서 계약과 불일치 | `models refresh`, `models list --all --provider`로 분리 | 공식 모델 CLI 대조·명령 회귀 검사 |
| R04 | `models status --check` 종료0으로 실제 모델 호출까지 성공한 것처럼 판정 | 실제 Gateway 표식 응답과 모델/제공자 식별을 확인; 실패/미확인 시 준비 기록 무효화 | 메타데이터 echo·다른 모델·빈 응답·오류 반례 검사 |
| R05 | OAuth에서 특정 에이전트 저장소 명시가 빠짐 | `models auth --agent <id> login` 사용 | 공식 문서 대조·회귀 검사 |
| R06 | 작업 rc0만으로 COMPLETED; 프롬프트/오류에 포함된 표식도 성공 가능 | 알려진 payloads 본문만 읽고 error/in_flight/unknown 거부 | 정상/중첩/오류/중간상태/echo/substring 시험 |
| R07 | 자식 stdout/stderr 전부 메모리에 모은 뒤 크기 검사 | 스트림별 상한, 시간 상한, 로컬 프로세스 그룹 정리 | 실제 로컬 자식 프로세스 출력 초과·타임아웃 시험 |
| R08 | 실패한 acceptance 파일도 존재하면 OBSERVED 표시 | 내용·프로필별 PASS를 읽고 실패/미완료/표식만 검증됨 분리 | 실패 기록·한 프로필만 성공·두 프로필 성공 시험 |
| R09 | 백업 후 서비스 재개 실패를 출력만 하고 명령 성공 반환 | 모든 재개 시도, 실패 기록, 스냅샷 보존과 별개로 오류 종료 | 스냅샷 성공 후 docker start 실패를 모의 재현 |
| R10 | 백업 repo가 있는데 암호 파일이 없으면 새 암호 생성 | 원래 키 복구를 요구하고 중단 | 임시 저장소 모의 시험 |
| R11 | 미관리 설치 검사보다 먼저 `/opt` 코드 덮어쓰기 | 업로드 전 읽기 전용 OS/소유권/관리표식/도메인 검사; 업로드 잠금 안에서 재검사 | 기존 계정/파일 보존 및 upload 선행 검사 시험 |
| R12 | OCI 생성 응답 뒤 네트워크 준비 상태 미확인 | AVAILABLE까지 제한된 조회; 예상 밖 상태/시간 초과에 재생성하지 않고 중단 | PROVISIONING→AVAILABLE, UNKNOWN 시험 |
| R13 | `review-notes.md` 원문이 전체 stage와 함께 서버로 전송됨 | 업로드 필터 제외, 검토 해시만 전달 | tar 멤버 필터 시험 |
| R14 | 소스 해시가 실행 비트 변조를 놓침 | 경로·실행 비트·내용 반영 | chmod 후 검토 해시 불일치 시험 |
| R15 | reader egress에서 모든 사설주소의 53번 포트를 예외 허용 | 실제 설정된 DNS 주소만 예외; 새 체인을 완성한 뒤 교체 | 규칙 구성/순서 회귀 검사, 실제 iptables 시험은 미실행 |
| R16 | 설치/인증/백업이 다른 잠금을 사용하거나 잠금 없음 | 공통 root 운영 잠금; 충돌 시 중단 | 각 root 진입점/업로드 소스 확인 |
| R17 | OCI handoff 저장 후 호스트키 등록 실패 시 재개가 불완전 | handoff 재개 시 known_hosts 누락을 확인하고 독립 지문 검증 재수행 | 코드 검토; 실제 OCI 호스트키 회수 미실행 |

## 저장소/스킬 산출물

스킬 명칭을 요청한 `one-pass-oci-openclaw`로 변경했습니다. 내부 `/opt/oracle-ai-stack`, 프로필 데이터 경로와 schema 3은 기존 관리 표식과 혼동되지 않게 유지했습니다. 스킬 호출 이름 변경과 데이터 이관은 같은 작업이 아닙니다.

자체 코드를 재배포하는 명시적 파일 manifest, 로컬 스킬 설치기, 기본 비공개 GitHub 초기 게시기, 오프라인 CI를 추가했습니다. 게시기는 실제 로컬 GitHub 인증·해당 계정·권한·빈 저장소를 확인하고, non-force push 후 원격 ref를 확인합니다. 이 검토에서 실제 GitHub 쓰기는 수행하지 않았습니다.

## 아직 해결했다고 주장하지 않는 것

- 실 OCI/ARM 전체 설치 및 2 OCPU/12GB에서의 실제 부하.
- 사용자 OAuth 및 Go/Zen entitlement, 실제 라이브 API JSON 계약과 응답.
- 전체 gstack 하네스 라우팅: 설치 자산과 별도 검증 절차만 있으며 완전한 무인 실행 구현이 아님.
- 기획의 읽기 전용 정책에 대한 실환경 적대적 테스트, 각 프로필의 자체 인증정보에 대한 모든 유출 차단.
- GBrain 새 세션 회상/정정/철회, 모든 자동 기억 기능.
- Buzz 회원 권한과 방 Bot 역할, 실제 클라이언트 응답 및 파일/미디어 지원 여부.
- 백업 외부 반출·재부팅·실데이터 복구·업데이트 자동 적용.
- 모든 전이 패키지 무결성/라이선스/취약점, 공급망 전체 안전성.
- iptables를 다른 관리자가 변경한 후까지 ready 파일만으로 정책이 유지된다는 보장.

따라서 배포 등급은 **0.4.0-beta / 실환경 검증 후보**입니다. 테스트 수를 완성도나 보안 인증 점수로 사용하지 않습니다.

## 외부 계약 확인 출처

확인일 2026-09-14. 공식 문서 자체의 변경 가능성은 남아 있습니다.

- https://docs.openclaw.ai/cli/models — list/refresh 구분, agent 옵션 적용 범위, check와 probe 차이.
- https://docs.openclaw.ai/cli/agent — payloads/result, in_flight, 모호한 통신 실패와 중복 재실행 위험.
- https://developers.openai.com/codex/skills/ — SKILL.md, 사용자 경로, 명시적 호출.
- https://cli.github.com/manual/gh_repo_create — 계정/저장소 초기 생성.
- https://api.github.com/repos/actions/checkout/git/ref/tags/v4 — CI checkout 커밋 pin 조회.

GBrain/gstack/ECC/OCI 원본 설명은 기존 manifests/references에 보존했습니다. 전체 최신 upstream 코드를 다시 감사했다고 주장하지 않습니다.
