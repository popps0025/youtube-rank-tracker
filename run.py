# -*- coding: utf-8 -*-
"""전체 파이프라인 실행: 수집 → 이력 누적 → 분석 → 대시보드 생성.

사용법:
  python run.py                 # 실제 수집 (환경변수에 API 키 필요)
  python run.py --mock          # API 키 없이 가짜 데이터로 파이프라인 확인
  python run.py --date 2026-08-06  # 수집일 지정(기본: 오늘, KST)
  python run.py --dashboard-only   # 수집 없이 기존 이력으로 대시보드만 재생성
"""
import os, sys, json, argparse, datetime
import yaml
import collect as collector
import analyze as analyzer
import dashboard as dash

BASE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(BASE, "data", "history.json")
OUT = os.path.join(BASE, "data", "dashboard.html")


def kst_today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")


def load_history():
    if os.path.exists(HIST):
        return json.load(open(HIST))
    return {"meta": {}, "records": {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--date", default=None)
    ap.add_argument("--dashboard-only", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(os.path.join(BASE, "config.yaml")))
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)  # data 폴더 없으면 생성
    history = load_history()
    history.setdefault("records", {})
    date = args.date or kst_today()

    if not args.dashboard_only:
        if args.mock:
            print("• MOCK 수집 (API 미사용)")
            result = collector.collect_mock(cfg, history)
        else:
            key = os.environ.get(cfg["api_key_env"], "")
            # 환경변수가 없으면 프로젝트 폴더의 api_key.txt 를 읽음 (예약/무인 실행 편의)
            if not key:
                kf = os.path.join(BASE, "api_key.txt")
                if os.path.exists(kf):
                    key = open(kf).read().strip()
            if not key:
                sys.exit(f"환경변수 {cfg['api_key_env']} 에 YouTube API 키가 없습니다. "
                         f"테스트는 `python run.py --mock` 을 쓰세요.")
            if not (cfg.get("channel_id") or cfg.get("channel_title_contains")):
                sys.exit("config.yaml 의 channel_id (또는 channel_title_contains)를 먼저 설정하세요.")
            print(f"• 실제 수집 시작 — {len(cfg['keywords'])}개 키워드")
            result = collector.collect(cfg, key)
        primary = cfg.get("segments", ["all"])[0]
        day = result.get(primary, result.get("all", {}))
        history["records"][date] = day
        json.dump(history, open(HIST, "w"), ensure_ascii=False, indent=1)
        okc = sum(1 for v in day.values() if v["s"] == "ok")
        erc = sum(1 for v in day.values() if v["s"] == "error")
        print(f"• {date} 수집 완료: TOP50 진입 {okc} · 오류 {erc} · 저장 → data/history.json")

    analysis = analyzer.analyze(history, cfg)
    gen = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    dash.render(analysis, OUT, generated=gen)
    print(f"• 대시보드 생성 → {OUT}")
    print(f"  최신일 {analysis['latest_date']} · 누적 {len(analysis['dates'])}일 · "
          f"TOP50 {analysis['summary']['top50_count']}개")


if __name__ == "__main__":
    main()
