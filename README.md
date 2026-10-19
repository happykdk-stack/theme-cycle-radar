# 한미 주식 테마 사이클 레이더

한국·미국 대표 테마 ETF의 일별 종가와 거래량을 수집하여 GitHub Pages에서 자동으로 표시하는 프로젝트입니다. CSV 업로드가 필요 없습니다.

## 1. 설치 (GitHub 웹사이트만 사용)

1. GitHub에서 **New repository**를 눌러 `theme-cycle-radar`라는 **Public** 저장소를 만들고, 기본 브랜치를 `main`으로 설정합니다. (Private 저장소의 Pages 사용 가능 여부는 요금제에 따라 다릅니다.)
2. 이 ZIP을 풀고 **숨김 폴더 `.github`를 포함한 모든 파일과 폴더**를 저장소 루트에 업로드합니다. `site/index.html`, `scripts/update.py`, `.github/workflows/pages.yml`, `requirements.txt`가 있어야 합니다.
3. 저장소 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 변경합니다.
4. 저장소 **Actions → Refresh theme radar and deploy → Run workflow**를 실행합니다.
5. 작업이 성공하면 `https://<사용자명>.github.io/theme-cycle-radar/`에서 확인합니다. 첫 배포까지 몇 분 걸릴 수 있습니다.
6. Actions 탭의 작업 로그에서 `Saved N themes; M errors` 메시지를 확인합니다. 일부 ETF가 실패하면 사이트의 **데이터 수집 오류 및 한계**에도 표시됩니다.

> GitHub Actions의 예약 실행은 지연되거나 생략될 수 있으며, 무료 금융 데이터 제공처의 접속 제한이 발생할 수 있습니다. 매일 정시 업데이트를 보장하지 않습니다.

## 2. 갱신 방식

- `.github/workflows/pages.yml`의 `schedule`이 평일 **UTC 00:30, 09:30**에 실행됩니다. 한국시간 **09:30, 18:30**입니다. 미국 장 마감 시각과 서머타임 때문에 09:30 KST의 미국 자료는 직전 거래일 또는 아직 갱신되지 않은 자료일 수 있습니다.
- **Run workflow**로 수동 갱신도 가능합니다.
- 브라우저의 **최신 데이터 다시 읽기** 버튼은 이미 배포된 JSON을 다시 불러옵니다. 서버 수집 작업 자체를 실행하지는 않습니다.
- 데이터가 36시간 이상 오래되면 화면에 경고가 표시됩니다. 주말에는 정상적으로 이 경고가 뜰 수 있습니다.

## 3. 분석 규칙과 해석

**신호:** ETF 종가 기준 전 거래일 대비 **3% 이상 상승**하고 **거래량이 전 거래일의 1.5배 이상**이면 발생합니다. ETF마다 신호를 독립적으로 계산합니다. 해당 일자의 종가가 확정된 뒤에야 신호를 알 수 있습니다.

**점수:** 거래량 강도 30%, 벤치마크 대비 20거래일 상대강도 25%, 가격방향 가중 거래량 대리지표 20%, 테마 확산 **중립값 50** 15%, 최근 10거래일 상승 빈도 10%.

- 한국 벤치마크: `069500.KS` (KODEX 200), 미국: `SPY`.
- 기관/외국인 순매수, 개별 구성종목 동반 상승 데이터는 **제공하지 않습니다**. 따라서 수급·확산을 실제 측정했다고 해석하면 안 됩니다.
- 신호 후 5·20거래일 수익률은 **신호일 종가 기준**이며, 다음날 시가 체결을 가정한 전략 수익률이 아닙니다. 거래비용, 배당 재투자, 세금 및 슬리피지는 제외합니다.
- 가격은 yfinance의 `auto_adjust=True`로 조정된 일별 시세입니다. 공급자 수정에 따라 과거 수치가 바뀔 수 있습니다.
- 종목별 상장 시기·ETF 추종 지수 차이·레버리지 여부가 비교에 영향을 줍니다. 테마 ETF가 테마 전체의 움직임을 완전히 대표하지는 않습니다.
- 점수 임계값(75/60/40)은 실험적이며 검증된 예측 정확도를 의미하지 않습니다.
- ETF 상장폐지나 티커 변경이 있으면 `scripts/update.py`의 `THEMES`를 수정하세요.

## 4. 로컬 테스트

Python 3.11 이상 환경에서:

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/update.py
python -m http.server 8000 --directory site
```

브라우저에서 `http://localhost:8000`을 열어 확인합니다. 단순히 `site/index.html`을 파일로 직접 열면 일부 브라우저에서 JSON fetch가 차단될 수 있습니다.

## 5. 데이터 실패 시

- **전체 수집 실패:** workflow가 실패하며 신규 사이트 배포를 중단합니다. 기존 Pages 사이트가 있다면 마지막 성공 배포본이 남습니다. 화면의 생성 시각을 확인하세요.
- **일부 수집 실패:** 성공한 ETF만 표시하고 실패한 티커 및 원인을 오류 영역에 표시합니다.
- **실패 원인:** Yahoo Finance 접속 제한, 한국 ETF 심볼 변경, 휴장일, API 응답 오류 등. Actions 로그를 확인하고 재실행하세요.
- 데이터 공급자 이용 약관 및 호출 제한을 확인하고 개인 연구용으로 사용하세요.

## 6. 파일 구조

```
.github/workflows/pages.yml   자동 수집 및 GitHub Pages 배포
scripts/update.py             ETF 수집, 점수, 신호 계산
site/index.html               대시보드 UI
site/data.json                실행 시 생성 (처음에는 없음)
tests/test_update.py          단위 테스트
requirements.txt              Python 패키지
```

**주의:** 이 프로젝트는 시장 관찰용 시제품입니다. 1년간 전체 테마에 대한 검증된 정확도 수치는 아직 제공하지 않습니다.
