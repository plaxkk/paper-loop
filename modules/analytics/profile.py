#!/usr/bin/env python3
"""
微信公众号用户画像 & 运营分析 v2
- 直接从 mp_analytics.db 读取
- 分析文章表现、趋势、渠道分布
- 生成 actionable 的运营建议
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "mp_analytics.db"
REPORT_DIR = BASE_DIR / "data" / "reports"


def query_db(query: str, params=()) -> list:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def generate_profile() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        "# 微信公众号用户画像 & 运营分析",
        f"生成时间: {now}",
        "",
        "---",
        "",
    ]

    # ── 1. 文章总览 ──
    articles = query_db("SELECT * FROM articles ORDER BY publish_date DESC")
    if not articles:
        lines.append("暂无数据。请在公众号后台浏览「内容分析」页面以触发数据采集。")
        return "\n".join(lines)

    lines.append("## 一、文章总览")
    lines.append(f"已追踪文章: {len(articles)} 篇")
    lines.append("")
    lines.append("| # | 标题 | 发布日期 | 总阅读 | 阅读占比 |")
    lines.append("|---|------|----------|--------|----------|")
    for a in articles:
        dm = query_db(
            "SELECT total_read_uv, read_uv_ratio FROM article_daily_metrics WHERE article_id=? ORDER BY ref_date DESC LIMIT 1",
            (a["id"],)
        )
        read_uv = dm[0]["total_read_uv"] if dm else 0
        ratio = dm[0]["read_uv_ratio"] if dm else 0
        title = a["title"][:30] + ("..." if len(a["title"]) > 30 else "")
        lines.append(f"| {a['id']} | {title} | {a['publish_date']} | {read_uv:,} | {ratio:.1%} |")
    lines.append("")

    # ── 2. 阅读量排行 ──
    lines.append("## 二、阅读量 TOP 5")
    top5 = query_db("""
        SELECT a.title, a.publish_date, d.total_read_uv, d.read_uv_ratio
        FROM article_daily_metrics d
        JOIN articles a ON a.id = d.article_id
        ORDER BY d.total_read_uv DESC LIMIT 5
    """)
    for i, t in enumerate(top5, 1):
        lines.append(f"{i}. **{t['title'][:40]}** — {t['total_read_uv']:,} 阅读 ({t['read_uv_ratio']:.1%})")
    lines.append("")

    # ── 3. 趋势分析 ──
    lines.append("## 三、阅读趋势（近30日）")
    # Get trend data for all articles aggregated by date
    trends = query_db("""
        SELECT snapshot_date, SUM(metric_value) as total_reads
        FROM trend_snapshots
        GROUP BY snapshot_date
        ORDER BY snapshot_date DESC
        LIMIT 30
    """)
    if trends:
        max_reads = max(t["total_reads"] for t in trends)
        lines.append("")
        lines.append("```")
        for t in reversed(trends):
            bar_len = int(t["total_reads"] / max(max_reads, 1) * 40)
            bar = "█" * bar_len
            lines.append(f"  {t['snapshot_date']} │ {bar} {t['total_reads']:.0f}")
        lines.append("```")
    lines.append("")

    # 单篇趋势（阅读最高的文章）
    top_article = query_db("""
        SELECT a.id, a.title, d.total_read_uv
        FROM article_daily_metrics d
        JOIN articles a ON a.id = d.article_id
        ORDER BY d.total_read_uv DESC LIMIT 1
    """)
    if top_article:
        a = top_article[0]
        lines.append(f"### 最佳文章趋势: {a['title'][:35]}")
        atrends = query_db("""
            SELECT snapshot_date, metric_value FROM trend_snapshots
            WHERE article_id=? ORDER BY snapshot_date DESC LIMIT 30
        """, (a["id"],))
        if atrends:
            max_v = max(t["metric_value"] for t in atrends)
            lines.append("```")
            for t in reversed(atrends):
                bar_len = int(t["metric_value"] / max(max_v, 1) * 30)
                bar = "▓" * bar_len
                lines.append(f"  {t['snapshot_date']} │ {bar} {t['metric_value']:.0f}")
            lines.append("```")
        lines.append("")

    # ── 4. 渠道分析 ──
    lines.append("## 四、流量来源分布")
    sources = query_db("""
        SELECT source_type, source_name, SUM(read_uv) as total
        FROM traffic_sources
        GROUP BY source_type, source_name
        ORDER BY total DESC
    """)
    if sources:
        total_all = sum(s["total"] for s in sources)
        lines.append("")
        lines.append("| 渠道 | 阅读量 | 占比 |")
        lines.append("|------|--------|------|")
        for s in sources:
            name = s["source_name"] or s["source_type"] or "未知"
            lines.append(f"| {name} | {s['total']:,} | {s['total']/total_all:.1%} |")
    lines.append("")

    # ── 5. 内容方向分析 ──
    lines.append("## 五、内容方向分析")
    paper_articles = [a for a in articles if any(kw in a["title"] for kw in [
        "Transformer", "BERT", "GPT", "Scaling", "FlashAttention", "ZeRO",
        "Chinchilla", "InstructGPT", "Constitutional", "DPO", "RLHF"
    ])]
    non_paper = [a for a in articles if a not in paper_articles]

    if paper_articles and non_paper:
        paper_reads = sum(
            (query_db("SELECT total_read_uv FROM article_daily_metrics WHERE article_id=?", (a["id"],)) or [{"total_read_uv": 0}])[0]["total_read_uv"]
            for a in paper_articles
        )
        other_reads = sum(
            (query_db("SELECT total_read_uv FROM article_daily_metrics WHERE article_id=?", (a["id"],)) or [{"total_read_uv": 0}])[0]["total_read_uv"]
            for a in non_paper
        )
        lines.append(f"- 论文解读类: {len(paper_articles)} 篇, 合计 {paper_reads:,} 阅读")
        lines.append(f"- 其他内容: {len(non_paper)} 篇, 合计 {other_reads:,} 阅读")
        lines.append("")

    # ── 6. 运营建议 ──
    lines.append("## 六、运营建议")
    lines.append("")

    # Best performing article analysis
    if top5:
        best = top5[0]
        lines.append(f"**标杆文章**: {best['title'][:30]} ({best['total_read_uv']:,} 阅读, {best['read_uv_ratio']:.1%} 占比)")
        lines.append("分析: 这篇是当前读者群体最感兴趣的内容方向。")

    # Trend analysis
    if trends and len(trends) >= 7:
        recent = sum(t["total_reads"] for t in trends[:7])
        older = sum(t["total_reads"] for t in trends[7:14]) if len(trends) >= 14 else 0
        if older > 0:
            change = (recent - older) / older * 100
            direction = "↑" if change > 0 else "↓"
            lines.append(f"**阅读趋势**: 近7日 vs 前7日 {direction}{abs(change):.0f}%")
            if change < -20:
                lines.append("⚠ 阅读量下滑明显，建议增加发布频率或调整内容方向。")
            elif change < 0:
                lines.append("阅读量略有下滑，持续关注。")
            else:
                lines.append("阅读量保持增长，内容策略有效。")

    lines.append("")
    lines.append("**后续建议**:")
    lines.append("1. 继续浏览公众号后台的「内容分析」页面以累积更多数据点")
    lines.append("2. 积累至少 7 天连续数据后可启用 cron 自动采集 + 日报推送")
    lines.append("3. 对比各文章的完读率、分享率，识别最优发布时间和文章结构")
    lines.append("")
    lines.append("---")
    lines.append("*数据源: Tampermonkey 插件自动采集 → mp_collector → mp_schema → 本报告*")

    # ── 7. 用户分析 ──
    user_data = query_db("""
        SELECT source_id, source_name, SUM(new_user) as total_new, SUM(cancel_user) as total_cancel,
               (SELECT cumulate_user FROM user_daily_metrics WHERE source_id='99999999' ORDER BY ref_date DESC LIMIT 1) as latest_cum
        FROM user_daily_metrics
        GROUP BY source_id, source_name
        ORDER BY total_new DESC
    """)
    if user_data:
        total_cum = user_data[0]["latest_cum"] if user_data else 0
        lines.append("")
        lines.append("## 七、用户增长分析")
        lines.append(f"当前累计粉丝: **{total_cum}** 人")
        lines.append("")
        # Get daily net growth
        daily = query_db("""
            SELECT ref_date, new_user, cancel_user, netgain_user, cumulate_user
            FROM user_daily_metrics WHERE source_id='99999999'
            ORDER BY ref_date DESC LIMIT 14
        """)
        if daily:
            lines.append("### 近14日净增趋势")
            lines.append("| 日期 | 新增 | 取关 | 净增 | 累计 |")
            lines.append("|------|------|------|------|------|")
            for d in reversed(daily):
                lines.append(f"| {d['ref_date']} | {d['new_user']} | {d['cancel_user']} | {d['netgain_user']} | {d['cumulate_user']} |")
            lines.append("")
        # Source breakdown
        sources = [s for s in user_data if s["total_new"] > 0 and s["source_id"] not in ("99999999", "0")]
        if sources:
            lines.append("### 新增粉丝来源")
            for s in sources:
                lines.append(f"- {s['source_name']}: +{s['total_new']} 人")
            lines.append("")
        # Account info
        ai = query_db("SELECT * FROM account_info LIMIT 1")
        if ai:
            a = ai[0]
            lines.append(f"账号: {a.get('nick_name','')} (服务号={a.get('service_type','')=='2'})")
            lines.append(f"本月群发剩余: {a.get('mass_send_left','')}")
            lines.append("")

    return "\n".join(lines)


def main():
    report = generate_profile()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = REPORT_DIR / f"user_profile_{ts}.md"
    path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n报告已保存: {path}")


if __name__ == "__main__":
    main()
