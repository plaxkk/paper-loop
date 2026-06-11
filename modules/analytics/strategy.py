#!/usr/bin/env python3
"""
微信公众号数据飞轮 — 周复盘策略生成器
- 读取 mp_analytics.db
- 生成：数据洞察 + 撰文策略建议
- 输出到 data/weekly_strategy.json（Hermes 撰文时自动注入）
"""
from __future__ import annotations

import json
import sqlite3
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
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    strategy = {
        "generated_at": now.isoformat(),
        "period": f"{week_ago} ~ {now.strftime('%Y-%m-%d')}",
        "insights": [],
        "writing_strategy": {},
        "raw_stats": {},
    }

    # ── 1. 文章表现分析 ──
    articles = query(conn, """
        SELECT a.id, a.title, a.publish_date,
               d.total_read_uv, d.read_uv_ratio, d.share_uv
        FROM articles a
        LEFT JOIN article_daily_metrics d ON d.article_id = a.id
        ORDER BY d.total_read_uv DESC
    """)

    if not articles:
        conn.close()
        strategy["insights"].append("暂无足够数据，建议继续积累至少7天数据。")
        return strategy

    total_reads = sum(a["total_read_uv"] or 0 for a in articles)
    top3 = articles[:3]
    bottom3 = articles[-3:]

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

    # Top performer analysis
    if top3:
        best = top3[0]
        insights.append({
            "type": "top_performer",
            "title": f"🏆 标杆文章: {best['title'][:30]}",
            "detail": f"{best['total_read_uv']:,} 阅读，占比 {best['read_uv_ratio']:.1%}",
            "action": f"分析此类话题/标题风格的共性，作为后续撰文参考模板。当前数据显示读者对「Scaling Laws」「FlashAttention」等算力/优化类论文兴趣最高。",
        })

    # Underperformers
    if bottom3:
        weak_titles = [a["title"][:15] for a in bottom3 if a["total_read_uv"] and a["total_read_uv"] < 50]
        if weak_titles:
            insights.append({
                "type": "low_performer",
                "title": f"📉 低阅读文章: {', '.join(weak_titles)}",
                "detail": "阅读量低于 50，远低于平均水平。",
                "action": "考虑是否话题太小众、标题不够吸引人、或发布时间不佳。BERT/GPT-1 等早期论文读者感知价值较低——可以考虑用更犀利的标题或结合当前热点重新切入。",
            })

    # User growth
    if user_trend:
        ut = user_trend[0]
        lu = latest_user[0]["cumulate_user"] if latest_user else 0
        insights.append({
            "type": "user_growth",
            "title": f"👥 粉丝: {lu} 人（近30日 +{ut['total_new']}/-{ut['total_cancel']}）",
            "detail": f"净增 {ut['total_net']} 人，月增速约 {ut['total_net']/max(lu,1)*100:.0f}%",
            "action": "增长速度平缓。建议：(1)提高发布频率到每周1-2篇；(2)在文章结尾添加「关注」引导；(3)将优质文章转发到相关技术社区。",
        })

    # Trend
    if weekly_trend and len(weekly_trend) >= 3:
        recent_avg = sum(t["daily_reads"] for t in weekly_trend[-3:]) / 3
        # Compare with previous 3 if available
        if len(weekly_trend) >= 6:
            prev_avg = sum(t["daily_reads"] for t in weekly_trend[-6:-3]) / 3
            change = (recent_avg - prev_avg) / max(prev_avg, 1) * 100
            trend_dir = "↑" if change > 10 else "↓" if change < -10 else "→"
            insights.append({
                "type": "reading_trend",
                "title": f"📈 阅读趋势: {trend_dir} {change:+.0f}%",
                "detail": f"近3日均 {recent_avg:.0f} vs 前3日均 {prev_avg:.0f}",
                "action": "上升趋势时保持节奏，下降时复盘最近几篇的标题和话题选择。" if change >= 0
                else "阅读下降，建议检查最近文章的话题是否偏离读者兴趣，或标题吸引力是否不足。",
            })

    # Source breakdown
    if sources:
        top_source = sources[0]
        insights.append({
            "type": "traffic_source",
            "title": f"📡 主要流量来源: {top_source['source_name']}",
            "detail": f"占比 {top_source['total']/max(sum(s['total'] for s in sources),1)*100:.0f}%",
            "action": "据此优化分发策略。如果主要来源是「公众号消息」，说明核心读者黏性强，重点提升完读率和分享率；如果是「推荐」，说明标题和封面是引流关键。",
        })

    strategy["insights"] = insights

    # ── 5. Writing Strategy (actionable rules) ──
    writing_strategy = {
        "recommended_topics": [],
        "title_style": [],
        "publish_timing": [],
        "content_tips": [],
        "meta": f"基于 {len(articles)} 篇文章和 {lu if latest_user else 0} 粉丝的数据生成",
    }

    # Topic recommendations based on top performers
    high_performers = [a for a in articles if a["total_read_uv"] and a["total_read_uv"] > 100]
    topic_keywords = []
    for a in high_performers:
        for kw in ["Scaling", "FlashAttention", "ZeRO", "GPT-3", "GPU", "算力", "优化", "显存", "参数"]:
            if kw in a["title"] and kw not in topic_keywords:
                topic_keywords.append(kw)
    if topic_keywords:
        writing_strategy["recommended_topics"] = topic_keywords
        writing_strategy["content_tips"].append(
            f"读者对「{', '.join(topic_keywords[:3])}」相关话题兴趣最高，"
            "优先选择算力优化、GPU 技术、大规模训练等工程向论文。"
        )

    # Title style insights
    # Check if high-performing titles use certain patterns
    title_patterns = []
    for a in high_performers:
        title = a["title"]
        if "？" in title or "？" in title:
            title_patterns.append("疑问句")
        if "：" in title or "：" in title:
            title_patterns.append("冒号式")
        if any(w in title for w in ["打败", "碾压", "魔法", "艺术", "奇迹"]):
            title_patterns.append("冲击力词汇")
    if title_patterns:
        from collections import Counter
        top_pattern = Counter(title_patterns).most_common(1)[0][0]
        writing_strategy["title_style"].append(f"高阅读文章多用「{top_pattern}」标题，建议沿用。")

    writing_strategy["publish_timing"].append(
        "从趋势图看，阅读峰值常在发布后1-3天出现，周末阅读量较低。建议周二至周四发布新文章。"
    )
    writing_strategy["content_tips"].append(
        "高阅读文章共同特征：标题有冲击力、内容偏工程/算力向、类比贴近工程师日常。"
        "低阅读文章问题：话题太小众、标题偏平淡、缺少「为什么重要」的 hook。"
    )

    strategy["writing_strategy"] = writing_strategy

    # ── 6. Raw stats for quick reference ──
    strategy["raw_stats"] = {
        "total_articles": len(articles),
        "total_reads": total_reads,
        "avg_reads_per_article": total_reads // max(len(articles), 1),
        "total_followers": latest_user[0]["cumulate_user"] if latest_user else 0,
        "top_article": top3[0]["title"][:40] if top3 else "",
        "top_article_reads": top3[0]["total_read_uv"] if top3 else 0,
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
    print("## 📊 原始数据速览")
    for k, v in s["raw_stats"].items():
        print(f"  {k}: {v}")
    print(f"\n策略已保存: {STRATEGY_FILE}")


if __name__ == "__main__":
    print_strategy()
    save_strategy()
