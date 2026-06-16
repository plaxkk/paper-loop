// ==UserScript==
// @name         微信公众号数据采集器 v3
// @namespace    https://hermes-agent.nousresearch.com
// @version      3.0
// @description  拦截微信公众平台数据页面的 API 响应 + 已发表记录一键全量扫描
// @author       Hermes Agent
// @match        https://mp.weixin.qq.com/*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    const COLLECTOR_URL = 'http://127.0.0.1:9876/mp-data';
    const API_PATTERNS = [
        /appmsganalysis/, /useranalysis/, /menuanalysis/,
        /article_analysis/, /datacube/, /cgi-bin\/.*analysis/,
        /cgi-bin\/.*report/, /cgi-bin\/.*stat/,
        /appmsgpublish/,   // 已发表记录
    ];

    let collectedResponses = [];
    let pageType = detectPageType();
    let sent = false;
    let isScanning = false;
    let scanAllArticles = [];

    // ── Page detection ──────────────────────────────────────────
    function detectPageType() {
        const url = window.location.href;
        if (/appmsganalysis/.test(url)) return 'content_analysis';
        if (/useranalysis/.test(url)) return 'user_analysis';
        if (/menuanalysis/.test(url)) return 'menu_analysis';
        if (/appmsgpublish/.test(url) || /cgi-bin\/appmsg/.test(url)) return 'published_records';
        return 'mp_page';
    }

    function shouldIntercept(url) {
        return API_PATTERNS.some(p => p.test(url));
    }

    // ── API interception (fetch) ────────────────────────────────
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const resource = args[0];
        const url = typeof resource === 'string' ? resource : (resource && resource.url);
        if (url && shouldIntercept(url)) {
            console.log('[MP] fetch →', url);
        }
        return originalFetch.apply(this, args).then(response => {
            if (url && shouldIntercept(url)) {
                const clone = response.clone();
                clone.text().then(body => {
                    try {
                        const json = JSON.parse(body);
                        if (isScanning) {
                            // During scan: extract articles from API response
                            const articles = extractArticlesFromAPI(json, url);
                            if (articles.length > 0) scanAllArticles.push(...articles);
                            console.log('[MP] scan captured', articles.length, 'articles, total:', scanAllArticles.length);
                        } else {
                            console.log('[MP] captured fetch response:', url);
                            collectedResponses.push({url, status: response.status, body: json});
                        }
                    } catch(e) {}
                }).catch(() => {});
            }
            return response;
        });
    };

    // ── API interception (XHR) ───────────────────────────────────
    const OrigXHR = window.XMLHttpRequest;
    const origOpen = OrigXHR.prototype.open;
    const origSend = OrigXHR.prototype.send;
    OrigXHR.prototype.open = function(method, url) {
        this._mp = {method, url};
        return origOpen.apply(this, arguments);
    };
    OrigXHR.prototype.send = function() {
        const xhr = this;
        const url = xhr._mp && xhr._mp.url;
        if (url && shouldIntercept(url)) {
            xhr.addEventListener('load', function() {
                try {
                    const json = JSON.parse(xhr.responseText);
                    if (isScanning) {
                        const articles = extractArticlesFromAPI(json, url);
                        if (articles.length > 0) scanAllArticles.push(...articles);
                    } else {
                        collectedResponses.push({url, status: xhr.status, body: json});
                    }
                } catch(e) {}
            });
        }
        return origSend.apply(this, arguments);
    };

    // ── Article extraction from API responses ───────────────────
    function extractArticlesFromAPI(body, url) {
        const articles = [];
        const lists = body?.publish_list || body?.article_list || 
                      body?.list || body?.items || body?.data?.list || [];
        for (const item of lists) {
            const msgInfo = item.msg_info || item.article_info || item;
            const title = msgInfo.title || item.title || '';
            const reads = item.read_num || msgInfo.read_num || 
                          item.total_read_uv || msgInfo.total_read_uv || 0;
            if (!title) continue;
            articles.push({
                msg_id: String(item.msg_id || msgInfo.msg_id || ''),
                item_idx: item.item_idx || msgInfo.item_idx || 1,
                title: title,
                publish_date: msgInfo.create_time
                    ? new Date(msgInfo.create_time * 1000).toISOString().slice(0, 10)
                    : (msgInfo.publish_date || item.publish_date || ''),
                total_reads: parseInt(reads) || 0,
            });
        }
        return articles;
    }

    // ── Send to collector ────────────────────────────────────────
    function sendToCollector(payloadOverride) {
        if (sent && !payloadOverride) return;
        if (!payloadOverride) sent = true;

        const payload = payloadOverride || {
            page_type: pageType,
            url: window.location.href,
            title: document.title,
            collected_at: new Date().toISOString(),
            api_responses: collectedResponses,
            api_count: collectedResponses.length,
        };

        const label = payload.page_type || pageType;
        console.log('[MP] Sending to collector:', label);

        fetch(COLLECTOR_URL, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(r => r.json()).then(result => {
            if (!payloadOverride) {
                showBadge('✓ 已采集 ' + collectedResponses.length + ' 条 (' + pageType + ')', '#07c160');
            }
            console.log('[MP] Collector OK:', result);
        }).catch(err => {
            console.warn('[MP] Collector unreachable:', err.message);
            showBadge('⚠ 采集服务未启动 (localhost:9876)', '#e6a23c');
        });
    }

    // ── UI badge ─────────────────────────────────────────────────
    function showBadge(text, bg) {
        const id = 'mp-collector-badge';
        const existing = document.getElementById(id);
        if (existing) existing.remove();
        const b = document.createElement('div');
        b.id = id;
        b.textContent = text;
        b.style.cssText = 'position:fixed;bottom:20px;right:20px;background:'+bg+';color:#fff;padding:10px 18px;border-radius:6px;font-size:13px;z-index:99999;font-family:-apple-system,sans-serif;box-shadow:0 2px 12px rgba(0,0,0,.25)';
        document.body.appendChild(b);
        setTimeout(() => { if (document.getElementById(id)) b.remove(); }, 8000);
    }

    // ── Published records: full scan button ─────────────────────
    function addScanButton() {
        if (document.getElementById('mp-scan-all-btn')) return;

        const btn = document.createElement('button');
        btn.id = 'mp-scan-all-btn';
        btn.textContent = '📊 一键扫描全部已发表记录';
        btn.style.cssText = 'position:fixed;top:20px;right:20px;z-index:99998;'
            + 'background:#07c160;color:#fff;border:none;padding:10px 18px;'
            + 'border-radius:6px;font-size:14px;cursor:pointer;font-family:-apple-system,sans-serif;'
            + 'box-shadow:0 2px 12px rgba(0,0,0,.2);';
        btn.onmouseover = () => btn.style.background = '#06ad56';
        btn.onmouseout = () => btn.style.background = '#07c160';

        btn.onclick = async function() {
            if (isScanning) return;
            isScanning = true;
            scanAllArticles = [];
            btn.textContent = '⏳ 扫描中...';
            btn.style.background = '#999';
            btn.disabled = true;

            const MAX_PAGES = 100;
            const DELAY = 1200;
            let pageCount = 0;

            try {
                while (pageCount < MAX_PAGES) {
                    pageCount++;
                    await new Promise(r => setTimeout(r, DELAY));

                    const found = await clickNextPage();
                    if (!found && pageCount > 1) {
                        console.log('[MP Scan] No more pages at', pageCount);
                        break;
                    }
                    if (scanAllArticles.length > 0) {
                        btn.textContent = `⏳ 第${pageCount}页 · ${scanAllArticles.length}篇`;
                    }
                }
            } catch(e) {
                console.error('[MP Scan] Error:', e);
            }

            // Send collected articles
            if (scanAllArticles.length > 0) {
                const payload = {
                    page_type: 'published_records',
                    url: window.location.href,
                    title: document.title,
                    collected_at: new Date().toISOString(),
                    page_data: { total_pages: pageCount },
                    api_responses: [{
                        url: 'published_records_scan',
                        body: { article_list: scanAllArticles }
                    }]
                };
                sendToCollector(payload);
                showBadge('✅ 已扫描 ' + scanAllArticles.length + ' 篇文章', '#07c160');
            }

            btn.textContent = '📊 一键扫描全部已发表记录';
            btn.style.background = '#07c160';
            btn.disabled = false;
            isScanning = false;
        };

        document.body.appendChild(btn);
    }

    // Click next page button on published records page
    async function clickNextPage() {
        // Method 1: WeChat pagination buttons
        const btns = document.querySelectorAll('.weui-desktop-pagination__nav .weui-desktop-btn');
        for (const b of btns) {
            if (b.textContent.includes('下一页') || 
                b.querySelector('[class*="next"], [class*="arrow"]')) {
                b.click();
                return true;
            }
        }
        // Method 2: Generic "下一页" text
        const allBtns = document.querySelectorAll('button, a, span[role="button"], div[role="button"]');
        for (const b of allBtns) {
            if (b.textContent.trim() === '下一页' || 
                b.getAttribute('aria-label')?.includes('next')) {
                b.click();
                return true;
            }
        }
        return false;
    }

    // ── Init ─────────────────────────────────────────────────────
    console.log('[MP Collector v3] Loaded on', pageType, window.location.href);

    if (pageType === 'published_records') {
        // Add scan button, don't auto-send
        showBadge('📊 已发表记录页 · 点击右上按钮扫描全部', '#409eff');
        window.addEventListener('load', () => {
            setTimeout(() => addScanButton(), 1000);
        });
    } else {
        // Normal behavior: wait for API calls, auto-send
        showBadge('🔍 监听中... (' + pageType + ')', '#409eff');
        window.addEventListener('load', () => {
            setTimeout(() => {
                console.log('[MP] Sending after 4s. Collected:', collectedResponses.length);
                sendToCollector();
            }, 4000);
        });
        window.addEventListener('beforeunload', () => sendToCollector());
    }
})();
