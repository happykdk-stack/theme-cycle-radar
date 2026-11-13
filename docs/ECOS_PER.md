# 코스피 PER 공식 ECOS 자동 연결

한국은행 ECOS 공식 StatisticSearch API를 지원합니다. 인증키와 **검증된** 코스피 PER 통계표 코드·항목 코드를 입력해야 실제 월별 PER이 표시됩니다.

- GitHub Repository Settings → Secrets and variables → Actions → Secrets: `ECOS_API_KEY`
- 같은 화면 Variables: `ECOS_KOSPI_PER_STAT_CODE`, `ECOS_KOSPI_PER_ITEM_CODE`
- 통계코드와 항목코드는 https://ecos.bok.or.kr 에서 실제 '코스피 주가수익비율(PER)' 시계열의 코드인지 확인해야 합니다. 확인되지 않은 코드를 임의로 넣지 마세요.
- 수집 결과는 `site/per_history.json`의 `indices["^KS11"].history`에 실제 날짜와 PER 배수로 저장됩니다.
- 값이 없거나 인증 실패 시 오류 상태를 표시하고 PER 선은 생성하지 않습니다.
- 데이터 이용 약관과 GitHub Pages 공개 재배포 허용 여부를 확인해야 합니다.

**현재 코드만 반영한 상태에서는 인증키·검증된 항목 코드가 없으므로 실제 코스피 PER 데이터가 자동으로 채워지지 않습니다.**
