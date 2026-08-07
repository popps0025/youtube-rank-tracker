# -*- coding: utf-8 -*-
"""수집기: 각 키워드에 대해 유튜브를 검색하고 타깃 채널의 순위 + 상위 영상을 수집.

- YouTube Data API v3 (search.list)를 표준 라이브러리(urllib)로 호출.
- 결과: {키워드: {"r": 순위 or None, "s": ok/beyond/error, "top": [{t,c,mine} x5]}}
- --mock: API 키 없이 파이프라인 확인용 가짜 데이터.
"""
import os, sys, json, time, urllib.parse, urllib.request, urllib.error

API = "https://www.googleapis.com/youtube/v3/search"


def _search_page(keyword, api_key, cfg, page_token=None):
    params = {
        "part": "snippet", "q": keyword, "type": "video", "maxResults": 50,
        "order": "relevance", "regionCode": cfg.get("region", "KR"),
        "relevanceLanguage": cfg.get("language", "ko"), "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def rank_for_keyword(keyword, api_key, cfg):
    """타깃 채널 순위(top_n 내) + 상위 5개 영상 정보."""
    top_n = int(cfg.get("top_n", 50))
    cid = (cfg.get("channel_id") or "").strip()
    ctitle = (cfg.get("channel_title_contains") or "").strip()
    pos = 0
    token = None
    rank = None
    top5 = []
    for _ in range((top_n + 49) // 50):
        data = None
        for attempt in range(3):
            try:
                data = _search_page(keyword, api_key, cfg, token)
                break
            except urllib.error.HTTPError as e:
                if e.code in (403, 429) and attempt < 2:
                    time.sleep(2 * (attempt + 1)); continue
                return {"r": None, "s": "error", "top": []}
            except Exception:
                if attempt < 2:
                    time.sleep(2); continue
                return {"r": None, "s": "error", "top": []}
        for item in data.get("items", []):
            pos += 1
            sn = item.get("snippet", {})
            mine = (cid and sn.get("channelId") == cid) or \
                   (ctitle and ctitle in (sn.get("channelTitle") or ""))
            if len(top5) < 5:
                top5.append({"t": (sn.get("title") or "")[:60],
                             "c": (sn.get("channelTitle") or "")[:24],
                             "mine": bool(mine)})
            if mine and rank is None and pos <= top_n:
                rank = pos
        token = data.get("nextPageToken")
        if not token:
            break
    return {"r": rank, "s": "ok" if rank is not None else "beyond", "top": top5}


def collect(cfg, api_key, sleep=0.15, log=print):
    out = {}
    for i, kw in enumerate(cfg["keywords"], 1):
        out[kw] = rank_for_keyword(kw, api_key, cfg)
        if sleep:
            time.sleep(sleep)
        if i % 10 == 0:
            log(f"  {i}/{len(cfg['keywords'])} 수집…")
    return out


def collect_mock(cfg, history, seed=42, log=print):
    import random
    rnd = random.Random(seed)
    last = {}
    if history.get("records"):
        last = history["records"][sorted(history["records"].keys())[-1]]
    out = {}
    for kw in cfg["keywords"]:
        prev = last.get(kw, {"r": None, "s": "beyond"})
        roll = rnd.random()
        if roll < 0.04:
            out[kw] = {"r": None, "s": "error", "top": []}
        elif prev.get("s") == "ok" and prev.get("r"):
            nr = max(1, min(cfg["top_n"], prev["r"] + rnd.randint(-4, 4)))
            out[kw] = {"r": nr, "s": "ok", "top": []}
        elif roll > 0.93:
            out[kw] = {"r": rnd.randint(20, cfg["top_n"]), "s": "ok", "top": []}
        else:
            out[kw] = {"r": None, "s": "beyond", "top": []}
    return out


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "config.yaml")))
    if "--mock" in sys.argv:
        hp = os.path.join(os.path.dirname(__file__), "data", "history.json")
        history = json.load(open(hp)) if os.path.exists(hp) else {"records": {}}
        print(json.dumps(collect_mock(cfg, history), ensure_ascii=False, indent=1))
    else:
        key = os.environ.get(cfg["api_key_env"], "")
        if not key:
            sys.exit(f"환경변수 {cfg['api_key_env']} 에 API 키가 없습니다.")
        print(json.dumps(collect(cfg, key), ensure_ascii=False, indent=1))
