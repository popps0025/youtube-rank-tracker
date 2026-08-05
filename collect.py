# -*- coding: utf-8 -*-
"""수집기: 각 키워드에 대해 유튜브를 검색하고 타깃 채널의 순위를 계산.

- YouTube Data API v3 (search.list)를 표준 라이브러리(urllib)로 호출 → 추가 설치 최소화.
- 결과: {키워드: {"r": 순위 or None, "s": "ok"|"beyond"|"error"}}
    ok     = top_n 안에서 타깃 채널 영상을 찾음 (r = 순위)
    beyond = 검색은 됐지만 top_n 안에 없음 (r = None)
    error  = 수집 실패 (r = None)
- 실제 키 없이도 파이프라인을 확인할 수 있도록 --mock 모드 제공.
"""
import os, sys, json, time, urllib.parse, urllib.request, urllib.error

API = "https://www.googleapis.com/youtube/v3/search"


def _search_page(keyword, api_key, cfg, page_token=None):
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "maxResults": 50,
        "order": "relevance",
        "regionCode": cfg.get("region", "KR"),
        "relevanceLanguage": cfg.get("language", "ko"),
        "key": api_key,
    }
    seg = cfg.get("_segment")
    if seg == "short":
        params["videoDuration"] = "short"      # 4분 미만 (쇼츠 근사)
    elif seg == "long":
        params["videoDuration"] = "long"       # 20분 초과
    if page_token:
        params["pageToken"] = page_token
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def rank_for_keyword(keyword, api_key, cfg):
    """타깃 채널의 순위를 top_n 안에서 탐색."""
    top_n = int(cfg.get("top_n", 50))
    cid = (cfg.get("channel_id") or "").strip()
    ctitle = (cfg.get("channel_title_contains") or "").strip()
    pos = 0
    token = None
    for _ in range((top_n + 49) // 50):
        # 간단 재시도 (일시적 오류 대비)
        data = None
        for attempt in range(3):
            try:
                data = _search_page(keyword, api_key, cfg, token)
                break
            except urllib.error.HTTPError as e:
                if e.code in (403, 429) and attempt < 2:  # 쿼터/레이트 → 대기 후 재시도
                    time.sleep(2 * (attempt + 1)); continue
                return {"r": None, "s": "error", "err": f"HTTP {e.code}"}
            except Exception as e:
                if attempt < 2:
                    time.sleep(2); continue
                return {"r": None, "s": "error", "err": str(e)[:80]}
        for item in data.get("items", []):
            pos += 1
            if pos > top_n:
                return {"r": None, "s": "beyond"}
            sn = item.get("snippet", {})
            hit = (cid and sn.get("channelId") == cid) or \
                  (ctitle and ctitle in (sn.get("channelTitle") or ""))
            if hit:
                return {"r": pos, "s": "ok"}
        token = data.get("nextPageToken")
        if not token:
            break
    return {"r": None, "s": "beyond"}


def collect(cfg, api_key, sleep=0.0, log=print):
    """모든 키워드 × 세그먼트 수집."""
    out = {}
    segments = cfg.get("segments") or ["all"]
    for seg in segments:
        cfg["_segment"] = None if seg == "all" else seg
        seg_out = {}
        for i, kw in enumerate(cfg["keywords"], 1):
            seg_out[kw] = rank_for_keyword(kw, api_key, cfg)
            if sleep:
                time.sleep(sleep)
            if i % 10 == 0:
                log(f"  [{seg}] {i}/{len(cfg['keywords'])} 수집…")
        out[seg] = seg_out
    cfg.pop("_segment", None)
    return out


def collect_mock(cfg, history, seed=42, log=print):
    """API 키 없이 파이프라인을 확인하기 위한 가짜 수집.
    직전 순위에서 소폭 변동시킨 값을 생성(결정적)."""
    import random
    rnd = random.Random(seed)
    # 직전 기록 찾기
    last = {}
    if history.get("records"):
        last_date = sorted(history["records"].keys())[-1]
        last = history["records"][last_date]
    out = {"all": {}}
    for kw in cfg["keywords"]:
        prev = last.get(kw, {"r": None, "s": "beyond"})
        roll = rnd.random()
        if roll < 0.04:
            out["all"][kw] = {"r": None, "s": "error"}
        elif prev["s"] == "ok" and prev["r"]:
            nr = max(1, min(cfg["top_n"], prev["r"] + rnd.randint(-4, 4)))
            out["all"][kw] = {"r": nr, "s": "ok"}
        elif roll > 0.93:  # 가끔 새로 진입
            out["all"][kw] = {"r": rnd.randint(20, cfg["top_n"]), "s": "ok"}
        else:
            out["all"][kw] = {"r": None, "s": "beyond"}
    return out


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "config.yaml")))
    if "--mock" in sys.argv:
        hist_path = os.path.join(os.path.dirname(__file__), "data", "history.json")
        history = json.load(open(hist_path)) if os.path.exists(hist_path) else {"records": {}}
        print(json.dumps(collect_mock(cfg, history), ensure_ascii=False, indent=1))
    else:
        key = os.environ.get(cfg["api_key_env"], "")
        if not key:
            sys.exit(f"환경변수 {cfg['api_key_env']} 에 YouTube API 키가 없습니다. --mock 로 테스트하세요.")
        print(json.dumps(collect(cfg, key), ensure_ascii=False, indent=1))
