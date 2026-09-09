// ==UserScript==
// @name         微信公众号数据采集器 v2
// @namespace    https://hermes-agent.nousresearch.com
// @version      2.0
// @description  拦截微信公众平台数据页面的 API 响应，发送到本地采集服务
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
    ];

    let collectedResponses = [];
    let pageType = detectPageType();
    let sent = false;

    function detectPageType() {
        const url = window.location.href;
        if (/appmsganalysis/.test(url)) return 'content_analysis';
        if (/useranalysis/.test(url)) return 'user_analysis';
        if (/menuanalysis/.test(url)) return 'menu_analysis';
        return 'mp_page';
    }

    function shouldIntercept(url) {
        return API_PATTERNS.some(p => p.test(url));
    }

    // Intercept fetch
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
                        console.log('[MP] captured fetch response:', url, Object.keys(json).slice(0,5));
                        collectedResponses.push({url, status: response.status, body: json});
                    } catch(e) { /* not JSON */ }
                }).catch(() => {});
            }
            return response;
        });
    };

    // Intercept XHR
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
            console.log('[MP] XHR →', url);
            xhr.addEventListener('load', function() {
                try {
                    const json = JSON.parse(xhr.responseText);
                    console.log('[MP] captured XHR response:', url, Object.keys(json).slice(0,5));
                    collectedResponses.push({url, status: xhr.status, body: json});
                } catch(e) {}
            });
        }
        return origSend.apply(this, arguments);
    };

    function sendToCollector() {
        if (sent) return;
        sent = true;

        const payload = {
            page_type: pageType,
            url: window.location.href,
            title: document.title,
            collected_at: new Date().toISOString(),
            api_responses: collectedResponses,
            api_count: collectedResponses.length,
        };

        console.log('[MP] Sending to collector:', payload.page_type, payload.api_count, 'responses');

        fetch(COLLECTOR_URL, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(r => r.json()).then(result => {
            console.log('[MP] Collector OK:', result);
            showBadge('✓ 已采集 ' + collectedResponses.length + ' 条 (' + pageType + ')', '#07c160');
        }).catch(err => {
            console.warn('[MP] Collector unreachable:', err.message);
            showBadge('⚠ 采集服务未启动 (localhost:9876)', '#e6a23c');
        });
    }

    function showBadge(text, bg) {
        const id = 'mp-collector-badge';
        const existing = document.getElementById(id);
        if (existing) existing.remove();
        const b = document.createElement('div');
        b.id = id;
        b.textContent = text;
        b.style.cssText = 'position:fixed;bottom:20px;right:20px;background:'+bg+';color:#fff;padding:10px 18px;border-radius:6px;font-size:13px;z-index:99999;font-family:-apple-system,sans-serif;box-shadow:0 2px 12px rgba(0,0,0,.25)';
        document.body.appendChild(b);
        setTimeout(() => { if (document.getElementById(id)) b.remove(); }, 5000);
    }

    console.log('[MP Collector] Loaded on', pageType, window.location.href);

    // Show activation badge immediately
    showBadge('🔍 监听中... (' + pageType + ')', '#409eff');

    // Wait for API calls to complete, then send
    window.addEventListener('load', () => {
        setTimeout(() => {
            console.log('[MP] Sending after 4s wait. Collected:', collectedResponses.length);
            sendToCollector();
        }, 4000);
    });

    window.addEventListener('beforeunload', () => sendToCollector());
})();
