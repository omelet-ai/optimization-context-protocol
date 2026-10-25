# 좌표 profile과 실제 로컬 연동을 독립 기술 관문으로 검증

상태: 2026-10-25 비공개 후보 결정. 사용자가 실제 로컬 엔진 기동과 이후 좌표 adapter·trial key·한도 연결 및 자율 검증을 명시적으로 위임했다.

현재 Foundry API는 임의 거리행렬을 받지 않고 좌표를 받는다. 기존 basic의 입력을 근사 좌표로 바꾸면 비대칭·거리·비용 의미가 훼손된다. 따라서 [별도 coordinates profile](../../spec/profiles/ROUTING_COORDINATES_0_1.md)을 추가하고 두 엔진이 같은 profile을 소비하도록 했다. Core는 변경하지 않는다. public runtime은 독립 HTTP adapter이며 비공개 solver 또는 다른 checkout의 import가 없다.

[실제 로컬 연결](../../spec/environments/OMELET_LOCAL_TRIAL_0_1.md)은 이미 허가된 무과금 비운영 환경에서 검증 가능하다. 기존 H08에는 외부 운영·권리·실제 신원 발급 조건도 있으므로 이를 제거하거나 로컬 기술 PASS로 바꾸지 않는다. H15(좌표 의미/adapter), H16(실제 로컬 trial 경로), H17(설치 앱 두 개×실제 엔진 두 개)을 독립 후보 게이트로 추가한다. H15는 H03/H05, H16은 H07/H15, H17은 H04/H06/H11/H16의 현재 PASS를 요구한다. 이것은 H08/H09 전체나 D00/D01 승인의 대체가 아니다.

실제 source identity·endpoint·catalog pin은 로컬 제외 설정으로 식별한다. H16/H17은 환경이 없거나 변경되면 실패하며 skip하지 않는다. 파일 기반 stage PASS는 과거 실행의 증거다. 외부 프로세스가 계속 실행 중이라는 보장이 아니므로 재개 시 live readiness와 catalog를 재확인한다.

호환성 검증은 기존 basic/assignment/HTTP/MCP/SDK/저작 경로를 유지하고 새 profile의 schema·독립 평가·네 소비 조합을 추가한다. private 후보는 artifact hash로 정확히 식별한다. 외부 공개 버전·권리·신원 운영·사내 consumer 변경·게시 권한은 기존 관문에 남는다.
