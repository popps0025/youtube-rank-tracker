# -*- coding: utf-8 -*-
"""분석기: history.json(누적 이력)에서 대시보드에 필요한 지표를 계산."""
import json


def _status(v):
    return v.get("s") if isinstance(v, dict) else "beyond"


def analyze(history, cfg):
    keywords = cfg["keywords"]
    records = history.get("records", {})
    dates = sorted(records.keys())
    top_n = int(cfg.get("top_n", 50))

    def cell(date, kw):
        return records.get(date, {}).get(kw)

    per_kw = []
    for kw in keywords:
        series = []          # 순위 시계열 (없으면 None)
        status_series = []   # 상태 시계열 ('ok'|'beyond'|'error'|'none')
        best = None
        ok_days = err_days = beyond_days = 0
        for d in dates:
            v = cell(d, kw)
            if v is None:
                series.append(None); status_series.append("none"); continue
            s = v["s"]
            if s == "ok":
                r = v["r"]; series.append(r); ok_days += 1
                best = r if best is None else min(best, r)
                status_series.append("ok")
            elif s == "error":
                series.append(None); err_days += 1; status_series.append("error")
            else:
                series.append(None); beyond_days += 1; status_series.append("beyond")
        # 최신 / 직전 실제 순위
        latest = prev = None
        latest_status = "no-data"
        for d in reversed(dates):
            v = cell(d, kw)
            if v is not None:
                latest_status = v["s"]
                break
        real_ranks = [(d, cell(d, kw)["r"]) for d in dates
                      if cell(d, kw) and cell(d, kw)["s"] == "ok"]
        if real_ranks:
            latest = real_ranks[-1][1]
            if len(real_ranks) >= 2:
                prev = real_ranks[-2][1]
        delta = (prev - latest) if (latest is not None and prev is not None) else None  # +면 상승
        per_kw.append({
            "kw": kw, "best": best, "latest": latest, "prev": prev, "delta": delta,
            "latest_status": latest_status, "ok_days": ok_days, "err_days": err_days,
            "beyond_days": beyond_days, "series": series,
            "status_series": status_series,
        })

    # 요약 (최신일 기준)
    latest_date = dates[-1] if dates else None
    day = records.get(latest_date, {}) if latest_date else {}
    checked = [v for v in day.values() if isinstance(v, dict)]
    n_ok = sum(1 for v in checked if v["s"] == "ok")
    n_err = sum(1 for v in checked if v["s"] == "error")
    n_beyond = sum(1 for v in checked if v["s"] == "beyond")
    n_checked = len(checked)
    success_rate = round(100 * (n_ok + n_beyond) / n_checked, 1) if n_checked else 0.0

    # 순위 변동 (최신 vs 직전 실측)
    movers = [k for k in per_kw if k["delta"] is not None and k["delta"] != 0]
    gainers = sorted([k for k in movers if k["delta"] > 0], key=lambda x: -x["delta"])[:8]
    losers = sorted([k for k in movers if k["delta"] < 0], key=lambda x: x["delta"])[:8]

    # 데이터 품질
    from collections import Counter
    dup_dates = [d for d, n in Counter(dates).items() if n > 1]  # 우리 구조상 항상 [] 여야 정상
    quality = {
        "dup_dates": dup_dates,
        "today_errors": n_err,
        "today_missing": len(keywords) - n_checked,
        "success_rate": success_rate,
    }

    top50_keywords = sorted([k for k in per_kw if k["latest"] is not None],
                            key=lambda x: x["latest"])

    return {
        "title": cfg.get("dashboard_title", "유튜브 상위노출 자동 대시보드"),
        "dates": dates, "top_n": top_n, "latest_date": latest_date,
        "n_keywords": len(keywords),
        "summary": {
            "n_ok": n_ok, "n_err": n_err, "n_beyond": n_beyond,
            "n_checked": n_checked, "success_rate": success_rate,
            "top50_count": n_ok,
        },
        "per_kw": per_kw, "gainers": gainers, "losers": losers,
        "top50_keywords": top50_keywords, "quality": quality,
        "channel": cfg.get("channel_id") or cfg.get("channel_title_contains") or "(미설정)",
    }


if __name__ == "__main__":
    import os, yaml
    base = os.path.dirname(__file__)
    cfg = yaml.safe_load(open(os.path.join(base, "config.yaml")))
    hist = json.load(open(os.path.join(base, "data", "history.json")))
    a = analyze(hist, cfg)
    print("dates:", len(a["dates"]), "latest:", a["latest_date"])
    print("summary:", a["summary"])
    print("gainers:", [(g["kw"], g["delta"]) for g in a["gainers"]])
    print("top50:", [(k["kw"], k["latest"]) for k in a["top50_keywords"]])
