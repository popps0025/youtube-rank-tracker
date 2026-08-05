# 유튜브 상위노출 자동 트래커

구글시트 자동화 대신, **우리가 직접 순위를 수집 → 분석 → 대시보드 자동 생성**하는 파이프라인입니다.
YouTube Data API로 키워드별 순위를 매일 수집하고, 누적 이력에서 지표를 계산해
자체 완결형 HTML 대시보드(`data/dashboard.html`)를 자동으로 만들어 줍니다.

기존 시트에서 뽑아둔 **2026-07-07 ~ 08-05 실측 데이터 30일치가 초기 이력으로 이미 들어가 있어**,
설정만 마치면 첫날부터 채워진 대시보드가 나옵니다.

---

## 1. 폴더 구성

```
youtube-rank-tracker/
├─ config.yaml            ← 여기만 설정하면 됩니다 (키워드·채널·옵션)
├─ collect.py             수집기 (YouTube Data API)
├─ analyze.py             분석기
├─ dashboard.py           대시보드 생성기
├─ run.py                 실행 진입점
├─ requirements.txt
├─ data/
│  ├─ history.json        누적 순위 이력 (초기 30일 실측 시드 포함)
│  └─ dashboard.html      ← 자동 생성되는 결과물
└─ .github/workflows/daily.yml   (선택) GitHub 자동 실행 설정
```

## 2. 최초 1회 설정

### (1) YouTube Data API 키 발급 — 무료
1. https://console.cloud.google.com 접속 → 프로젝트 생성
2. 좌측 **API 및 서비스 → 라이브러리** → "YouTube Data API v3" 검색 → **사용 설정**
3. **사용자 인증 정보 → 사용자 인증 정보 만들기 → API 키** → 생성된 키 복사
   - 하루 무료 할당량 10,000 units. 검색 1회 = 100 units → 키워드 55개면 하루 약 5,500 units로 여유 있음.

### (2) 채널 지정
`config.yaml` 에서 순위를 추적할 **본인 채널**을 지정합니다.
```yaml
channel_id: "UCxxxxxxxxxxxxxxxxxxxxxx"   # 채널 ID (권장, 정확)
# 또는 채널명 부분일치로 매칭하려면:
channel_title_contains: "병원명"
```
> 채널 ID 확인: 유튜브 채널 페이지 → 정보/공유 → 채널 ID 복사, 또는 studio.youtube.com → 설정 → 채널 → 고급.

### (3) 키워드 확인
`config.yaml` 의 `keywords:` 목록에 시트에 있던 키워드 51개가 이미 들어 있습니다. 자유롭게 추가·삭제하세요.

## 3. 실행

```bash
pip install -r requirements.txt

# ① API 키 없이 먼저 파이프라인 확인 (가짜 데이터)
python run.py --mock

# ② 실제 수집 (API 키를 환경변수로 전달)
export YOUTUBE_API_KEY="발급받은_키"
python run.py

# 기존 이력으로 대시보드만 다시 만들기
python run.py --dashboard-only
```
실행하면 `data/history.json` 에 오늘 순위가 누적되고 `data/dashboard.html` 이 새로 생성됩니다.
브라우저로 `data/dashboard.html` 을 열면 됩니다.

---

## 4. 매일 자동 실행하기

### 방법 A — GitHub Actions (가장 안정적, 완전 무인) ⭐추천
서버·PC를 켜둘 필요 없이 GitHub이 매일 대신 실행하고, 이력·대시보드를 저장소에 자동 커밋합니다.

1. 이 폴더를 GitHub 저장소(private 권장)에 올립니다.
2. 저장소 **Settings → Secrets and variables → Actions → New repository secret**
   - 이름 `YOUTUBE_API_KEY`, 값에 API 키 입력 *(키가 코드에 노출되지 않습니다)*
3. `.github/workflows/daily.yml` 이 매일 자동 실행합니다. 완료. 
   결과 대시보드는 저장소의 `data/dashboard.html` 에서 확인하거나 GitHub Pages로 공개할 수 있습니다.

### 방법 B — Cowork 예약 작업
Claude에게 "예약 작업으로 매일 돌려줘"라고 하면 매일 정해진 시각에 실행하도록 등록해 둡니다.
단, 클라우드 세션은 매번 새로 시작되므로 **이 폴더가 데스크톱 앱에 연결된 폴더 안에 있어야** 이력이 유지됩니다
(예약 실행 시각에 데스크톱 앱이 켜져 있어야 함). 자세한 세팅은 Claude가 안내합니다.

### 방법 C — 내 컴퓨터 스케줄러
- macOS/Linux: `crontab -e` 에 `0 9 * * * cd /경로/youtube-rank-tracker && YOUTUBE_API_KEY=키 python3 run.py`
- Windows: 작업 스케줄러에서 매일 `python run.py` 실행 등록

---

## 5. 수집 방식에 대한 참고
- 순위는 YouTube Data API의 검색 결과(relevance 기준, 지역 KR·한국어) 순서로 계산합니다.
  이는 실제 유튜브 앱 화면의 개인화된 노출 순서와 **약간 차이가 날 수 있습니다.**
- `top_n`(기본 50) 안에 본인 채널 영상이 있으면 그 순위를, 없으면 "50위 밖"으로 기록합니다.
- 수집 실패 시 "오류"로 기록되며, 대시보드의 수집 성공률·오류 지표로 자동 감지됩니다.
- 롱폼/쇼츠 분리 추적은 `config.yaml`의 `segments: [long, short]` 로 켤 수 있습니다(할당량 2배).
