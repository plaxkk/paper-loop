#!/usr/bin/env python3
"""
微信公众号数据飞轮 — 周复盘策略生成器 v3
- 公平排名：日均阅读量（控制发布时间差异）+ 总阅读量
- 差分活跃度：对比两次采集快照的增量
- 输出到 data/weekly_strategy.json（Hermes 撰文时自动注入）
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "mp_analytics.db"
STRATEGY_FILE = BASE_DIR / "data" / "weekly_strategy.json"


def query(conn, sql, params=()):
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def generate_strategy() -> dict:
    """Generate data-driven writing strategy from DB."""
    conn = sqlite3.connect(str(DB_PATH))
    now = datetime.now()
    today = now.date()
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    strategy = {
        "generated_at": now.isoformat(),
        "period": f"{week_ago} ~ {now.strftime('%Y-%m-%d')}",
        "insights": [],
        "writing_strategy": {},
        "raw_stats": {},
    }

    # ── 1. 文章表现分析（公平排名 + 差分活跃度）──
    articles_raw = query(conn, """
        SELECT a.id, a.title, a.publish_date,
               MAX(d.total_read_uv) as total_read_uv,
               MAX(d.share_uv) as share_uv
        FROM articles a
        LEFT JOIN article_daily_metrics d ON d.article_id = a.id
        GROUP BY a.id
    """)

    if not articles_raw:
        conn.close()
        strategy["insights"].append("暂无足够数据，建议继续积累至少7天数据。")
        return strategy

    # 计算日均阅读量 + 30天窗口标记
    cutoff_30d = today - timedelta(days=30)
    for a in articles_raw:
        pub_date = datetime.strptime(a["publish_date"], "%Y-%m-%d").date()
        days_alive = max((today - pub_date).days, 1)
        a["days_alive"] = days_alive
        a["reads_per_day"] = round((a["total_read_uv"] or 0) / days_alive, 1)
        a["in_30d_window"] = pub_date >= cutoff_30d  # 是否在追踪窗口内

    # 差分活跃度：对比最近两次采集
    for a in articles_raw:
        daily_rows = query(conn, """
            SELECT ref_date, total_read_uv
            FROM article_daily_metrics
            WHERE article_id = ?
            ORDER BY ref_date DESC LIMIT 2
        """, (a["id"],))

        if len(daily_rows) >= 2:
            latest = daily_rows[0]["total_read_uv"] or 0
            previous = daily_rows[1]["total_read_uv"] or 0
            a["recent_delta"] = max(0, latest - previous)
            a["is_active"] = a["recent_delta"] > 0
        elif len(daily_rows) == 1:
            a["recent_delta"] = 0
            a["is_active"] = None
        else:
            a["recent_delta"] = 0
            a["is_active"] = False

    # 两份排名
    by_rpd = sorted(articles_raw, key=lambda x: x["reads_per_day"], reverse=True)
    by_total = sorted(articles_raw, key=lambda x: x["total_read_uv"] or 0, reverse=True)

    total_reads = sum(a["total_read_uv"] or 0 for a in articles_raw)
    avg_rpd = round(sum(a["reads_per_day"] for a in articles_raw) / max(len(articles_raw), 1), 1)

    # ── 2. 用户增长 ──
    user_trend = query(conn, """
        SELECT SUM(new_user) as total_new, SUM(cancel_user) as total_cancel,
               SUM(netgain_user) as total_net
        FROM user_daily_metrics
        WHERE source_id='99999999' AND ref_date >= ?
    """, (month_ago,))

    latest_user = query(conn, """
        SELECT cumulate_user FROM user_daily_metrics
        WHERE source_id='99999999' ORDER BY ref_date DESC LIMIT 1
    """)

    # ── 3. 渠道来源 ──
    sources = query(conn, """
        SELECT source_name, SUM(read_uv) as total
        FROM traffic_sources
        GROUP BY source_name ORDER BY total DESC
    """)

    # ── 4. 趋势分析 ──
    weekly_trend = query(conn, """
        SELECT snapshot_date, SUM(metric_value) as daily_reads
        FROM trend_snapshots
        WHERE snapshot_date >= ?
        GROUP BY snapshot_date ORDER BY snapshot_date
    """, (week_ago,))

    # ── Build insights ──
    insights = []

    # 日均阅读冠军
    best_rpd = by_rpd[0]
    active_str = "🔥" if best_rpd["is_active"] else ("⚡" if best_rpd["is_active"] is None else "")
    insights.append({
        "type": "rpd_champion",
        "title": f"🏆 日均阅读冠军: {best_rpd['title'][:30]}",
        "detail": (
            f"{best_rpd['reads_per_day']:.1f} 阅读/天（已发布 {best_rpd['days_alive']} 天，"
            f"总计 {best_rpd['total_read_uv']:,} 阅读）{active_str}"
        ),
        "action": "阅读速度最高——每过一天都能稳定吸来新读者。分析它的标题、话题、分发渠道的共同特征。",
    })

    # 总阅读冠军
    best_total = by_total[0]
    insights.append({
        "type": "total_champion",
        "title": f"📚 累计阅读冠军: {best_total['title'][:30]}",
        "detail": (
            f"{best_total['total_read_uv']:,} 总阅读（日均 {best_total['reads_per_day']:.1f}/天，"
            f"已发布 {best_total['days_alive']} 天）"
        ),
        "action": "长尾之王——虽然日均可能不如冠军，但靠时间积累总阅读最高。适合做搜索 SEO 和内链引路。",
    })

    # 活跃度
    active_count = sum(1 for a in articles_raw if a["is_active"] is True)
    unknown_count = sum(1 for a in articles_raw if a["is_active"] is None)
    dead_count = sum(1 for a in articles_raw if a["is_active"] is False)

    if unknown_count > 0 and active_count == 0:
        insights.append({
            "type": "article_health",
            "title": "📊 活跃度: 待确认（需多次采集对比）",
            "detail": "目前只有一次采集快照，无法判断哪些文章仍在被阅读。明天再次采集后即可对比差值。",
            "action": "明天再次打开公众号后台「内容分析」页面采集数据。",
        })
    elif dead_count > 0 or active_count > 0:
        parts = [f"{active_count} 活跃", f"{dead_count} 沉寂"]
        if unknown_count:
            parts.append(f"{unknown_count} 待确认")
        insights.append({
            "type": "article_health",
            "title": f"📊 文章活跃度: {' / '.join(parts)}",
            "detail": "活跃文章仍在获取新阅读；沉寂文章近两次采集无增量。",
            "action": "沉寂文章考虑：(1)在知乎对应话题下写回答引路；(2)在新文章中加内链指向老文章。",
        })

    # 低阅读文章
    low = [a for a in articles_raw if a["total_read_uv"] and a["total_read_uv"] < 30]
    if low:
        names = ", ".join(a["title"][:15] for a in low)
        insights.append({
            "type": "low_performer",
            "title": f"📉 低阅读文章: {names}",
            "detail": "阅读量低于 30，远低于平均水平。",
            "action": "话题太小众或标题不够吸引人。考虑用更犀利的标题重新包装，或在新文章中做内链引路。",
        })

    # User growth
    if user_trend:
        ut = user_trend[0]
        lu = latest_user[0]["cumulate_user"] if latest_user else 0
        insights.append({
            "type": "user_growth",
            "title": f"👥 粉丝: {lu} 人（近30日 +{ut['total_new']}/-{ut['total_cancel']}）",
            "detail": f"净增 {ut['total_net']} 人，月增速约 {ut['total_net'] / max(lu, 1) * 100:.0f}%",
            "action": "增长速度平缓。建议保持内容质量和发布频率，多平台分发拉新。",
        })

    # Trend
    if weekly_trend and len(weekly_trend) >= 3:
        recent_avg = sum(t["daily_reads"] for t in weekly_trend[-3:]) / 3
        if len(weekly_trend) >= 6:
            prev_avg = sum(t["daily_reads"] for t in weekly_trend[-6:-3]) / 3
            change = (recent_avg - prev_avg) / max(prev_avg, 1) * 100
            trend_dir = "↑" if change > 10 else "↓" if change < -10 else "→"
            insights.append({
                "type": "reading_trend",
                "title": f"📈 阅读趋势: {trend_dir} {change:+.0f}%",
                "detail": f"近3日均 {recent_avg:.0f} vs 前3日均 {prev_avg:.0f}",
                "action": "上升趋势时保持节奏，下降时复盘最近几篇的标题和话题选择。"
                if change >= 0 else "阅读下降，检查最近文章的话题是否偏离读者兴趣。",
            })

    # Source breakdown
    if sources:
        top_source = sources[0]
        insights.append({
            "type": "traffic_source",
            "title": f"📡 主要流量来源: {top_source['source_name']}",
            "detail": f"占比 {top_source['total'] / max(sum(s['total'] for s in sources), 1) * 100:.0f}%",
            "action": "据此优化分发策略。如果主要来源是「公众号消息」，重点提升完读率和分享率；如果是「推荐」，标题和封面是引流关键。",
        })

    strategy["insights"] = insights

    # ── 5. Writing Strategy ──
    lu = latest_user[0]["cumulate_user"] if latest_user else 0
    writing_strategy = {
        "recommended_topics": [],
        "title_style": [],
        "publish_timing": [],
        "content_tips": [],
        "meta": f"基于 {len(articles_raw)} 篇文章和 {lu} 粉丝的数据生成",
    }

    high_performers = [a for a in articles_raw if a["total_read_uv"] and a["total_read_uv"] > 100]
    topic_keywords = []
    for a in high_performers:
        for kw in ["Scaling", "FlashAttention", "ZeRO", "GPT-3", "GPU", "算力", "优化", "显存", "参数", "InstructGPT", "RLHF"]:
            if kw in a["title"] and kw not in topic_keywords:
                topic_keywords.append(kw)
    if topic_keywords:
        writing_strategy["recommended_topics"] = topic_keywords
        writing_strategy["content_tips"].append(
            f"读者对「{', '.join(topic_keywords[:4])}」相关话题兴趣最高，"
            "优先选择算力优化、GPU 技术、大规模训练、对齐等工程向论文。"
        )

    title_patterns = []
    for a in high_performers:
        title = a["title"]
        if "？" in title:
            title_patterns.append("疑问句")
        if "：" in title:
            title_patterns.append("冒号式")
        if any(w in title for w in ["打败", "碾压", "魔法", "艺术", "奇迹"]):
            title_patterns.append("冲击力词汇")
    if title_patterns:
        top_pattern = Counter(title_patterns).most_common(1)[0][0]
        writing_strategy["title_style"].append(f"高阅读文章多用「{top_pattern}」标题，建议沿用。")

    writing_strategy["publish_timing"].append(
        "阅读峰值常在发布后1-3天出现，周末阅读量较低。建议周二至周四发布新文章。"
    )
    writing_strategy["content_tips"].append(
        "高阅读文章共同特征：标题有冲击力、内容偏工程/算力向、类比贴近工程师日常。"
        "低阅读文章问题：话题太小众、标题偏平淡、缺少「为什么重要」的 hook。"
    )

    strategy["writing_strategy"] = writing_strategy

    # ── 6. Raw stats ──
    ranking = []
    for i, a in enumerate(by_rpd):
        ranking.append({
            "rank_rpd": i + 1,
            "rank_total": next(j + 1 for j, b in enumerate(by_total) if b["id"] == a["id"]),
            "title": a["title"][:40],
            "reads_per_day": a["reads_per_day"],
            "total_reads": a["total_read_uv"],
            "days_alive": a["days_alive"],
            "active": a["is_active"],
            "frozen": not a["in_30d_window"],
            "recent_delta": a["recent_delta"],
        })

    # 30天窗口统计
    in_window = sum(1 for a in articles_raw if a["in_30d_window"])
    frozen_count = len(articles_raw) - in_window
    if frozen_count > 0:
        insights.append({
            "type": "frozen_articles",
            "title": f"📦 已冻结: {frozen_count} 篇文章（发布超过 30 天）",
            "detail": f"这些文章的数据为导入快照，不再每日追踪增量。近 30 天活跃文章: {in_window} 篇。",
            "action": "冻结文章的总阅读量保留在排名中作为参考，但不再消耗采集资源。",
        })

    strategy["raw_stats"] = {
        "total_articles": len(articles_raw),
        "total_reads": total_reads,
        "avg_reads_per_article": total_reads // max(len(articles_raw), 1),
        "avg_reads_per_day": avg_rpd,
        "total_followers": lu,
        "active_articles": active_count,
        "dead_articles": dead_count,
        "unknown_activity": unknown_count,
        "ranking": ranking,
    }

    conn.close()
    return strategy


def save_strategy():
    strategy = generate_strategy()
    STRATEGY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STRATEGY_FILE, "w", encoding="utf-8") as f:
        json.dump(strategy, f, ensure_ascii=False, indent=2)
    return strategy


def print_strategy():
    s = generate_strategy()
    print("# 公众号数据飞轮 · 周策略复盘")
    print(f"周期: {s['period']}")
    print()
    for i in s["insights"]:
        print(f"## {i['title']}")
        print(f"  {i['detail']}")
        print(f"  → {i['action']}")
        print()
    print("## ✍️ 撰文策略建议")
    ws = s["writing_strategy"]
    if ws["recommended_topics"]:
        print(f"  推荐话题: {', '.join(ws['recommended_topics'])}")
    for tip in ws["content_tips"]:
        print(f"  • {tip}")
    for t in ws["title_style"]:
        print(f"  • {t}")
    for t in ws["publish_timing"]:
        print(f"  • {t}")
    print()
    print("## 📊 排名对比（日均 vs 总阅读）")
    print(f"  {'':<3} {'文章':<30} {'日均':>6} {'总阅读':>6} {'天数':>4} {'状态':<6}")
    print(f"  {'─'*3} {'─'*30} {'─'*6} {'─'*6} {'─'*4} {'─'*6}")
    for r in s["raw_stats"]["ranking"]:
        if r.get("frozen"):
            mark = "📦"
            status = "冻结"
        elif r["active"] is True:
            mark = "🔥"
            status = "活跃"
        elif r["active"] is None:
            mark = " ?"
            status = "待确认"
        else:
            mark = "  "
            status = ""
        print(f"  {mark:<3} {r['title']:<30} {r['reads_per_day']:>5.1f} {r['total_reads']:>6} {r['days_alive']:>4} {status:<6}")
    print()
    print("## 📊 原始数据速览")
    for k, v in s["raw_stats"].items():
        if k != "ranking":
            print(f"  {k}: {v}")
    print(f"\n策略已保存: {STRATEGY_FILE}")


if __name__ == "__main__":
    print_strategy()
    save_strategy()
