# 초대 시험 운영 후보

사용자가 운영·지원·기술 및 권리 검토 조정 책임을 맡고 합리적인 구현 결정을 위임했다. 권리 검토 결과와 정확한 외부 공개 대상 승인은 별도 기록한다. 첫 시험은 5개 신뢰된 principal, 조직별 하루 5회·총 10회, 전체 50회, 14일이다. 사용자와 principal의 실제 대응은 운영자가 비공개로 보관한다. 공개 self-signup은 없다.

## 설치와 설정

검증된 candidate wheel을 Python 3.12 환경에 설치한다. 운영 설정·키·DB는 mode 0700인 비공개 폴더에 두고 JSON 파일은 0600으로 둔다. 서버는 설치된 package만 사용하며 Foundry checkout을 import하지 않는다. `operator.json`의 항목은 아래와 같고 두 파일 경로는 절대 경로다.

```json
{
  "database": "/private/operator/trial.sqlite",
  "upstream": "http://127.0.0.1:8288",
  "service_token_file": "/private/operator/service.json",
  "catalog_version": "1.3.0",
  "catalog_digest": "COPY_VERIFIED_DIGEST",
  "catalog_document_sha256": "COPY_VERIFIED_DOCUMENT_HASH"
}
```

`service.json`은 `token` 필드 하나를 가진다. 내부 서비스 token과 초대 키는 별개다. 운영 설정은 code repository나 사용자 꾸러미에 넣지 않는다. catalog/policy를 바꾸려고 기존 DB를 삭제하면 안 된다. 기존 기본 Policy DB에는 새 InvitationPolicy를 적용하지 않고 명시적으로 별도 캠페인을 준비한다.

```sh
python -B -m ocp_runtime.trial_ops --config /private/operator/operator.json status
python -B -m ocp_runtime.trial_ops --config /private/operator/operator.json issue --principal tester-1 --endpoint https://approved-host.example --out /private/operator/tester-1.json
python -B -m ocp_runtime.trial_ops --config /private/operator/operator.json serve --port 8190
```

운영 명령과 서버는 동일 OS lock으로 겹치지 않는다. 첫 5개 키는 서버를 멈춘 상태에서 발급하고 운영자가 각 참여자에게 직접 전달한다. `issue`는 재발급해도 조직 quota/만료를 초기화하지 않는다. 분실 시 `revoke --principal tester-1`은 조직의 모든 키를 회수한다. 개별 키 회수는 gateway의 trusted operator API에 있으며 HTTP에는 노출하지 않는다. 회수된 조직을 다른 principal로 대체해 캠페인 한도를 우회하지 않는다.

## 단기 외부 경로

제안 경로는 HTTPS 임시 tunnel → `127.0.0.1:8190` 초대 gateway → 기존 `127.0.0.1:8288` 엔진이다. 엔진 자체와 operator 명령은 tunnel에 연결하지 않는다. public HTTP 원점은 없으며 terminal/stdio MCP client가 HTTPS OCP를 호출한다. 원 HTTP 서버는 최대 8개 connection thread와 4개 처리 slot, 128 KiB body, 10초 읽기 제한, Origin/Host/중복 인증 헤더 거절을 적용한다.

Cloudflare Quick Tunnel 준비 명령은 다음과 같다. **정확한 공개 경로 승인 후** 실행한다. HTTP Host를 gateway loopback 값으로 전달해야 한다.

```sh
cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8190 --http-host-header 127.0.0.1:8190
```

이 임시 주소는 프로세스 종료 시 사라지고 uptime을 보장하지 않는다. 비대화식 SDK에는 브라우저 email 인증이 호환되지 않으므로 별도 trial Bearer key로 인증한다. TLS 종료 지점인 Cloudflare를 요청·키가 통과한다. 합성 데이터만 허용하고 키를 짧게 발급한다. 출처: [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [origin parameters](https://developers.cloudflare.com/tunnel/reference/origin-parameters/). 새 인프라 구매나 유료 API 호출을 이 절차가 허용하지 않는다.

공개 후 실제 URL에서 무키 거부→개인별 key→describe/validate/execute/evaluate→재호출→회수 거부를 재검증한다. 주소만 발급된 것을 사용 가능 판정으로 삼지 않는다. 개발 머신의 전원·네트워크와 upstream 운영 시간을 확인하고 시험 시간을 안내한다. 지속 운영은 별도 환경으로 이행한다.

## 복구·보존·중단

- 긴급 중단: tunnel을 먼저 종료한다. gateway 종료 후 `pause`, 재시작한다. pause 상태는 새 실행을 막고 기존 결과 replay는 유지한다.
- `status`는 합계와 held 작업의 principal/idempotency/job ID만 표시한다. 요청·해·키는 출력하지 않는다.
- 중단된 작업: 서버를 멈추고 `recover --principal ID --idempotency-key KEY`를 실행한다. 저장된 job ID와 동일 tenant로 GET/필요시 DELETE/종료 확인만 한다. 종료 확인 전에는 slot을 풀지 않는다. 확인 후에는 이전 응답을 RESULT_EXPIRED로 닫고 quota는 그대로 남긴다. 새 실행은 새 요청으로만 가능하다.
- 제출 응답이 유실되어 job ID가 없는 경우에는 자동 복구·재제출하지 않는다. 캠페인을 pause하고 운영자가 upstream을 조사한다. DB 삭제나 사용량 초기화는 복구 방법이 아니다.
- `backup --out PRIVATE_PATH`는 일관된 SQLite 사본을 0600으로 만든다. 복구용이며 결과가 포함될 수 있다. 과거 백업으로 원가 ledger를 되돌리지 않는다. 복원은 최신 사용량과 실제 upstream 종료를 대조한 뒤 별도 검증한다.
- 서버는 60초마다 24시간이 지난 완료 결과를 지운다. `purge`도 같은 삭제를 수행한다. SQLite 삭제는 파일의 암호학적 완전 소거를 뜻하지 않는다. native engine의 결과·로그 보존은 별도로 확인해야 하므로 현재는 합성 입력만 제공한다.
- 시험 종료: 모든 key 회수, tunnel 종료, upstream 작업 종료 확인, 필요한 비식별 집계 보존 후 운영자 설정·session·DB·backup을 폐기한다. 외부 실제 운영 기록으로 보존/삭제를 확인한다.

reserved compute ms는 금액 청구서가 아니다. 단기 시험은 기존 로컬 엔진을 사용하고 유료 호출을 추가하지 않는다. H19의 설치·loopback·주입 장애 검사를 H08 외부 운영 또는 H12 실제 사용자 수락으로 승격하지 않는다.
