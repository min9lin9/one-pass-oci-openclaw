# GBrain 전용 PostgreSQL 전환

현재 검증된 운영 서버는 GBrain 0.50.0.0의 저장소를 PGlite 0.4.3에서
전용 PostgreSQL 17 + pgvector로 전환했습니다. 신규 설치 기본값은 여전히
PGlite이며, 모든 신규 설치가 자동으로 PostgreSQL을 구축한다는 뜻은 아닙니다.

## 구성과 보존

- `templates/gbrain-postgres.compose.json`을 서버의 `compose.gbrain.json`으로
  배포합니다. linux/arm64 이미지 digest를 고정했습니다.
- 컨테이너는 `oracle-gbrain-postgres`, 볼륨은 `oracle-gbrain-data`입니다.
  은퇴한 Buzz DB나 볼륨을 재사용하지 않습니다.
- 호스트 포트는 `127.0.0.1:5434`에만 게시합니다. 다른 프로필에는 DB 자격
  증명을 배포하지 않으며, loopback 자체를 UID 간 네트워크 격리로 주장하지 않습니다.
- 앱 역할 `gbrain`은 superuser/createdb/createrole 권한이 없습니다.
  관리자 비밀은 root 0600 파일에서 컨테이너 secret으로 전달합니다.
- `fsync`, `full_page_writes`, `synchronous_commit`을 켭니다.
  컨테이너 정지 유예는 90초이고, DB 데이터는 읽기 전용 루트와 분리된 볼륨에 둡니다.
- 설정 위치는 `GBRAIN_HOME/.gbrain/config.json`입니다.
  `GBRAIN_HOME/config.json`이 아닙니다.
- 원본 PGlite는 보존합니다. 전환 뒤 새 쓰기가 발생하면 이전 PGlite로
  단순 복귀해서는 새 데이터를 보존할 수 없습니다.

## 실제 이관 검증

전환 전 암호화 스냅샷
`62c03d74a08bac7a7c5ad3b09ad25a906ae405040bb08e696c16de70663f54a1`을
Mac으로 반출하고 100개 팩 전체 검사와 격리된 복원을 수행했습니다.
운영 파일을 복원본으로 덮어쓰지 않았습니다.

설치 버전과 일치하는 공식 `@electric-sql/pglite-tools` 0.3.3의 SQL 덤프를
사용했습니다. 초기 임포트 직후 68개 테이블의 건수·전체 행 SHA256과
43개 시퀀스 상태가 일치했으며, 3건의 `fact_withdrawals`도 포함했습니다.
네이티브 GBrain CLI의 저장·새 프로세스 회상·철회를 확인했습니다.
검증용 fact와 추가 철회 표식은 제거했고 시퀀스 진행분은 되돌리지 않았습니다.

컷오버 직전에는 운영 PGlite의 관계 목록·해시가 백업과 여전히 일치하는지,
PostgreSQL이 검증 후 상태와 일치하는지 재확인했습니다. 다르면 전환하지
않습니다. 설정 변경 후 네이티브 PostgreSQL 연결 검사도 통과했습니다.

배포된 GBrain의 기본 `migrate`는 철회 표식, 삭제된 페이지 및 일부 DB 전용
상태를 누락하므로 이 작업의 무손실 이관 수단으로 사용하지 않았습니다.

## 설치·종료·백업

- 설치기는 기존 `engine: postgres`와 `embedding_disabled: true` 설정을
  보존합니다. 재실행으로 PGlite 초기화를 수행하지 않습니다.
- 메모리 래퍼는 접근을 직렬화하고 출력 크기와 실행시간을 제한합니다.
  제한 초과 시 SIGTERM과 30초 종료 유예를 거쳐 강제 정리하며, 완료 여부를
  확인하기 전 쓰기를 자동 재시도하지 않습니다.
- 래퍼는 `GBRAIN_PGLITE_WAL_REPAIR=off`를 전달합니다. 장애 원본을 보관하지
  않은 자동 WAL 초기화나 rebuild를 복구 절차로 삼지 않습니다.
  고정 소스의 [walRepairEnabled()](https://github.com/garrytan/gbrain/blob/a6be012a3bcfac42e279630aedec5cda4a450e29/src/core/pglite-repair.ts#L315-L317)가
  이 환경변수의 `off` 값을 실제로 확인합니다.
- 백업은 관리 대상 PostgreSQL을 정상 정지한 뒤 볼륨을 포함합니다.
  관리되는 loopback 5434 DB가 아닌 PostgreSQL 주소는 별도 검토된 백업
  전략 없이 보호된 것으로 보고하지 않습니다.
- 백업은 암호화, 서버 외부 반출, 실제 복원을 각각 검증해야 합니다.
  주기적 스케줄러, PITR, HA는 이 변경으로 자동 설치되지 않습니다.

## 검증 상태

실제 OpenClaw Flash 대화가 배포된 래퍼로 기억을 저장했고, 별도 새 대화가
그 표식을 전달받지 않은 상태에서 도구로 회상했습니다. PostgreSQL 행과
도구 실행 기록을 대조했고 실제 브라우저의 결과 화면도 확인했습니다.
검증용 행과 입력 파일은 정리했습니다. 임베딩을 끈 기존 구성에 따른
`degraded_dedup`은 남아 있으며 의미 기반 중복 제거를 검증했다고 주장하지 않습니다.

전환 후 스냅샷
`440bcb0ffd6b57b212f81e59542ca58c0279041c769c532cef0536a0fca17788`도
Mac으로 반출하고 102개 팩 전체를 검사했습니다. 복원본을 네트워크 없는
별도 PostgreSQL로 실제 기동하여 백업 시점의 111개 테이블·시퀀스 검증값이
모두 일치함을 확인했습니다. 운영 DB를 복원본으로 덮어쓰지 않았습니다.
