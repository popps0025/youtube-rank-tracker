# -*- coding: utf-8 -*-
"""전체 파이프라인: 수집 → 이력 누적 → 상위영상/분석 저장 → 2탭 대시보드 생성.

  python run.py            # 실제 수집 (환경변수 또는 api_key.txt 에 API 키)
  python run.py --mock     # API 없이 파이프라인 확인
  python run.py --dashboard-only
"""
import os, sys, json, argparse, datetime, re
import yaml
import collect as collector
import dashboard as dash

BASE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(BASE, "data", "history.json")
COMP = os.path.join(BASE, "data", "latest_comp.json")
OUT = os.path.join(BASE, "data", "dashboard.html")

MED = re.compile(r"성형|클리닉|의원|병원|피부|외과")


def kst_today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")


def load_json(p, default):
    return json.load(open(p)) if os.path.exists(p) else default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--date", default=None)
    ap.add_argument("--dashboard-only", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(os.path.join(BASE, "config.yaml")))
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    history = load_json(HIST, {"records": {}})
    history.setdefault("records", {})
    date = args.date or kst_today()

    if not args.dashboard_only:
        if args.mock:
            print("• MOCK 수집")
            result = collector.collect_mock(cfg, history)
        else:
            key = os.environ.get(cfg["api_key_env"], "")
            if not key:
                kf = os.path.join(BASE, "api_key.txt")
                if os.path.exists(kf):
                    key = open(kf).read().strip()
            if not key:
                sys.exit(f"{cfg['api_key_env']} (또는 api_key.txt)에 API 키가 없습니다.")
            if not (cfg.get("channel_id") or cfg.get("channel_title_contains")):
                sys.exit("config.yaml 의 channel_id 를 설정하세요.")
            print(f"• 실제 수집 — {len(cfg['keywords'])}개 키워드")
            result = collector.collect(cfg, key)

        # 이력(순위)에 저장
        day = {kw: {"r": v.get("r"), "s": v["s"]} for kw, v in result.items()}
        history["records"][date] = day
        json.dump(history, open(HIST, "w"), ensure_ascii=False, indent=1)

        # 상위영상 + 의도불일치 저장 (최신 스냅샷만)
        comp = {kw: v.get("top", []) for kw, v in result.items() if v.get("top")}
        offtopic = []
        for kw, tops in comp.items():
            if tops and not any(MED.search(t.get("c", "")) for t in tops):
                offtopic.append(kw)
        json.dump({"date": date, "comp": comp, "offtopic": offtopic},
                  open(COMP, "w"), ensure_ascii=False, indent=1)

        okc = sum(1 for v in day.values() if v["s"] == "ok")
        erc = sum(1 for v in day.values() if v["s"] == "error")
        print(f"• {date}: TOP50 {okc} · 오류 {erc} · 상위영상 {len(comp)}개 키워드 · 의도불일치 {offtopic}")

    comp_data = load_json(COMP, {"comp": {}, "offtopic": []})
    gen = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    dash.render(cfg, history, comp_data, OUT, generated=gen)
    print(f"• 대시보드 생성 → {OUT}")


if __name__ == "__main__":
    main()
