# 사례

- [Greedy 미발견 반례](failure-semantics/greedy-feasible.json): 용량 6인 자원 두 개와 수요 3,3,2,2,2. 기존 greedy는 일부를 놓치지만 전체 배정 가능한 witness가 있다.
- [라우팅 설계 사례](routing/design-case.json): 실제 wire schema가 아닌 작은 합성 검산 사례. 새 profile의 입력·결과 설계에 사용한다.
- [라우팅 실패 검증 목록](routing/README.md): 개발할 시험과 실행되지 않은 항목을 구분한다.

원본 template의 합성 CSV와 ContractSuite fixture도 원본 snapshot에 보존했다. 합성 사례 검사와 실제 API·MCP·trial의 end-to-end 검증은 별도다.
