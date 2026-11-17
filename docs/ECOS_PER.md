# 공식 코스피 PER 자동 수집

기존에는 ECOS 통계표·항목 코드까지 수동 입력해야 했습니다. 이제 `ECOS_API_KEY`가 설정되면 공식 ECOS 통계표·항목 목록에서 **코스피 PER이라고 명확히 확인되는 단일 월별 시계열**을 찾아 수집하도록 개선했습니다.

- 필요한 값: GitHub Actions Secret `ECOS_API_KEY` (한국은행 ECOS에서 발급)
- 선택 사항: `ECOS_KOSPI_PER_STAT_CODE`, `ECOS_KOSPI_PER_ITEM_CODE` (정확히 검증된 경우)
- 찾은 시계열이 0개이거나 여러 개이면 임의 선택하지 않고 오류를 기록합니다.
- 공식 시계열이 제공되지 않거나 라이선스상 공개 게시가 허용되지 않으면 공개 Pages에 PER을 게시하지 마세요.
- PER 원자료가 없으면 주가지수 가격으로 PER을 추정하지 않습니다.

API 키는 GitHub 저장소 코드나 공개 CSV에 적지 마세요. 인증키는 GitHub Settings → Secrets and variables → Actions → Repository secrets에 보관합니다.
