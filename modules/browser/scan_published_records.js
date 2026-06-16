/**
 * 公众号已发表记录全量采集脚本
 * 
 * 用法：在公众号后台「已发表」页面打开浏览器控制台（F12），粘贴此脚本，回车执行。
 * 脚本会自动翻页扫描所有历史文章，采集后发送到本地采集服务。
 * 
 * 采集数据：msg_id, title, publish_date, total_reads
 * POST 到 http://127.0.0.1:9876/mp-data (page_type: "published_records")
 */

(async function scanPublishedRecords() {
    const COLLECTOR_URL = 'http://127.0.0.1:9876/mp-data';
    const DELAY_MS = 1500; // 翻页间隔，避免风控
    const MAX_PAGES = 200;  // 安全上限

    let allArticles = [];
    let pageCount = 0;

    console.log('🔍 开始扫描已发表记录...');

    // 拦截 API 响应（在翻页时自然触发）
    const originalFetch = window.fetch;
    let capturedResponses = [];

    window.fetch = async function(...args) {
        const response = await originalFetch.apply(this, args);
        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
        
        if (url.includes('appmsgpublish') && url.includes('list')) {
            const clone = response.clone();
            try {
                const data = await clone.json();
                capturedResponses.push({
                    url: url,
                    body: data,
                    captured_at: new Date().toISOString()
                });
            } catch(e) {}
        }
        return response;
    };

    // 检测"下一页"按钮并点击
    async function clickNextPage() {
        const buttons = document.querySelectorAll('button, a, span, div[role="button"]');
        for (const btn of buttons) {
            const text = btn.textContent?.trim() || '';
            if (text.includes('下一页') || text.includes('>') || 
                btn.getAttribute('aria-label')?.includes('next')) {
                btn.click();
                return true;
            }
        }
        // 尝试找分页器中的下箭头
        const pagers = document.querySelectorAll('.weui-desktop-pagination__nav .weui-desktop-btn');
        for (const p of pagers) {
            if (p.querySelector('svg, img, [class*="arrow"], [class*="next"]')) {
                p.click();
                return true;
            }
        }
        return false;
    }

    // 从页面 DOM 提取文章列表
    function extractFromDOM() {
        const articles = [];
        // 尝试多种可能的 DOM 结构
        const rows = document.querySelectorAll('tr, [class*="item"], [class*="row"], [class*="article"]');
        for (const row of rows) {
            const title = row.querySelector('[class*="title"], h3, h4, a')?.textContent?.trim();
            const dateEl = row.querySelector('[class*="time"], [class*="date"], time');
            const readsEl = row.querySelector('[class*="read"], [class*="view"]');
            if (title && dateEl) {
                articles.push({
                    title: title,
                    publish_date: dateEl.textContent?.trim() || dateEl.getAttribute('datetime') || '',
                    reads_text: readsEl?.textContent?.trim() || '0'
                });
            }
        }
        return articles;
    }

    // 从捕获的 API 响应提取文章数据
    function extractFromAPI() {
        const articles = [];
        for (const resp of capturedResponses) {
            const body = resp.body;
            // WeChat API 常见字段名
            const lists = body?.publish_list || body?.article_list || body?.list || body?.items || [];
            for (const item of lists) {
                const msgInfo = item.msg_info || item.article_info || item;
                articles.push({
                    msg_id: String(item.msg_id || msgInfo.msg_id || ''),
                    item_idx: item.item_idx || msgInfo.item_idx || 1,
                    title: msgInfo.title || item.title || '',
                    publish_date: msgInfo.create_time 
                        ? new Date(msgInfo.create_time * 1000).toISOString().slice(0, 10)
                        : (msgInfo.publish_date || item.publish_date || ''),
                    total_reads: item.read_num || msgInfo.read_num || 0,
                });
            }
        }
        return articles;
    }

    // 主循环：翻页直到没有下一页
    try {
        // 第一页：等待数据加载
        await new Promise(r => setTimeout(r, 2000));
        
        while (pageCount < MAX_PAGES) {
            pageCount++;
            capturedResponses = []; // 清空本页缓存
            
            // 等待当前页的 API 响应
            await new Promise(r => setTimeout(r, DELAY_MS));
            
            // 先尝试从 API 响应提取（更准确）
            const apiArticles = extractFromAPI();
            if (apiArticles.length > 0) {
                allArticles.push(...apiArticles);
                console.log(`  第${pageCount}页: API获取 ${apiArticles.length} 篇, 累计 ${allArticles.length}`);
            } else {
                // Fallback: 从 DOM 提取
                const domArticles = extractFromDOM();
                if (domArticles.length > 0) {
                    allArticles.push(...domArticles);
                    console.log(`  第${pageCount}页: DOM获取 ${domArticles.length} 篇, 累计 ${allArticles.length}`);
                } else {
                    console.log(`  第${pageCount}页: 无数据，尝试翻页...`);
                }
            }
            
            // 尝试翻到下一页
            const hasNext = await clickNextPage();
            if (!hasNext) {
                console.log('  已到最后一页');
                break;
            }
        }
    } catch (e) {
        console.error('扫描出错:', e);
    } finally {
        // 恢复 fetch
        window.fetch = originalFetch;
    }

    // 发送结果到采集器
    if (allArticles.length > 0) {
        console.log(`\n✅ 扫描完成: ${allArticles.length} 篇文章`);
        console.log('正在发送到采集服务...');
        
        try {
            const response = await fetch(COLLECTOR_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    page_type: 'published_records',
                    url: window.location.href,
                    title: document.title,
                    collected_at: new Date().toISOString(),
                    page_data: { total_pages: pageCount },
                    api_responses: [{
                        url: 'published_records_scan',
                        body: {
                            article_list: allArticles.filter(a => a.msg_id || a.title)
                        }
                    }]
                })
            });
            
            if (response.ok) {
                console.log('✅ 数据已发送到本地采集服务');
                console.log(`  文章: ${allArticles.length} 篇`);
            } else {
                console.log('❌ 发送失败，请确认采集服务已启动 (http://127.0.0.1:9876)');
            }
        } catch(e) {
            console.log('❌ 无法连接到采集服务:', e.message);
            console.log('请先在终端执行: cd ~/repos/paper-loop && python3 modules/analytics/collector.py');
            // 兜底：打印到控制台可手动保存
            console.log('\n📋 采集数据（可手动复制）:');
            console.log(JSON.stringify(allArticles, null, 2));
        }
    } else {
        console.log('⚠️ 未采集到任何文章数据');
        console.log('可能原因:');
        console.log('  1. 不在「已发表」页面');
        console.log('  2. 页面未完全加载');
        console.log('  3. 文章列表为空');
    }
})();
