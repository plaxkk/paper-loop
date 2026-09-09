// ==UserScript==
// @name         微信公众号数据采集器 v3
// @namespace    https://hermes-agent.nousresearch.com
// @version      5.0
// @description  拦截微信公众平台数据页面的 API 响应 + 已发表记录一键全量扫描
// @author       Hermes Agent
// @match        https://mp.weixin.qq.com/*
// @grant        unsafeWindow
// @grant        GM_xmlhttpRequest
// @grant        GM.xmlHttpRequest
// @connect      127.0.0.1
// @connect      localhost
// @updateURL    http://127.0.0.1:9876/mp_analytics_injector.user.js
// @downloadURL  http://127.0.0.1:9876/mp_analytics_injector.user.js
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    const pageWindow = typeof unsafeWindow !== 'undefined' ? unsafeWindow : window;
    const SCRIPT_VERSION = '5.0';
    const FULL_SCAN_BUTTON_TEXT = '📊 v' + SCRIPT_VERSION + ' 从第一页全量扫描已发表记录';
    const COLLECTOR_URL = 'http://127.0.0.1:9876/mp-data';
    const PAGE_SESSION_KEY = 'mp_collector_page_session_id_v1';
    const SCAN_STATE_KEY = 'mp_collector_full_scan_state_v1';
    const SCAN_STATE_TTL_MS = 2 * 60 * 60 * 1000;
    const MAX_PAGE_TURNS = 100;
    const SCAN_PAGE_SIZE = 10;
    const SCAN_PAGE_DELAY_MS = 1200;
    const PAGE_SESSION_ID = getOrCreatePageSessionId();
    const API_PATTERNS = [
        /appmsganalysis/, /useranalysis/, /menuanalysis/,
        /article_analysis/, /datacube/, /cgi-bin\/.*analysis/,
        /cgi-bin\/.*report/, /cgi-bin\/.*stat/,
        /appmsgpublish/, /cgi-bin\/appmsg/, /appmsg_list/, /operate_appmsg/,   // 已发表记录
    ];

    let collectedResponses = [];
    let pageType = detectPageType();
    let sent = false;
    let isScanning = false;
    let scanAllArticles = [];
    let scanSeenKeys = new Set();
    let scanPageApiArticles = [];
    let scanLastDomDebug = [];
    let scanPageSources = [];
    let currentScanSessionId = '';
    let scanState = null;
    let scanResumeStarted = false;

    const startupScanState = pageType === 'published_records' ? loadScanState() : null;
    if (startupScanState) {
        hydrateScanState(startupScanState);
    }

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

    function wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function sessionId(prefix) {
        const random = Math.random().toString(36).slice(2, 10);
        return prefix + '_' + Date.now().toString(36) + '_' + random;
    }

    function safeSessionStorage() {
        try {
            return window.sessionStorage;
        } catch (e) {
            return null;
        }
    }

    function storageGet(key) {
        const storage = safeSessionStorage();
        if (!storage) return null;
        try {
            return storage.getItem(key);
        } catch (e) {
            return null;
        }
    }

    function storageSet(key, value) {
        const storage = safeSessionStorage();
        if (!storage) return false;
        try {
            storage.setItem(key, value);
            return true;
        } catch (e) {
            return false;
        }
    }

    function storageRemove(key) {
        const storage = safeSessionStorage();
        if (!storage) return;
        try {
            storage.removeItem(key);
        } catch (e) {}
    }

    function getOrCreatePageSessionId() {
        const existing = storageGet(PAGE_SESSION_KEY);
        if (existing) return existing;
        const id = sessionId('page');
        storageSet(PAGE_SESSION_KEY, id);
        return id;
    }

    function setScanButtonText(btn, text) {
        btn.textContent = text;
        btn.title = '主扫描会先回到第一页，再逐页向后采集；这里显示的是本次扫描的新增篇数和累计篇数。';
    }

    function onDomReady(fn) {
        if (document.body) {
            fn();
            return;
        }
        document.addEventListener('DOMContentLoaded', fn, {once: true});
    }

    function onWindowLoad(fn) {
        if (document.readyState === 'complete') {
            fn();
            return;
        }
        window.addEventListener('load', fn, {once: true});
    }

    // ── API interception (fetch) ────────────────────────────────
    const originalFetch = pageWindow.fetch;
    pageWindow.fetch = function(...args) {
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
                            queueScanApiArticles(articles, url);
                        } else {
                            console.log('[MP] captured fetch response:', url);
                            collectedResponses.push(cachedResponse(url, response.status, json));
                        }
                    } catch(e) {}
                }).catch(() => {});
            }
            return response;
        });
    };

    // ── API interception (XHR) ───────────────────────────────────
    const OrigXHR = pageWindow.XMLHttpRequest;
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
                        queueScanApiArticles(articles, url);
                    } else {
                        collectedResponses.push(cachedResponse(url, xhr.status, json));
                    }
                } catch(e) {}
            });
        }
        return origSend.apply(this, arguments);
    };

    // ── Article extraction from API responses ───────────────────
    function extractArticlesFromAPI(body, url) {
        const articles = [];
        articles.push(...extractArticlesFromPublishPage(body));
        const lists = candidateArticleLists(body);

        for (const list of lists) {
            for (const item of list) {
                if (!item || typeof item !== 'object') continue;
                const info = articleInfo(item);
                const nested = firstArray(
                    item.appmsgex,
                    item.appmsg_list,
                    item.article_list,
                    info.appmsgex,
                    info.appmsg_list,
                    info.article_list
                );

                if (nested && nested.length > 0) {
                    nested.forEach((child, idx) => {
                        const article = normalizeArticle(child, item, idx + 1);
                        if (article) articles.push(article);
                    });
                    continue;
                }

                const article = normalizeArticle(item, null, 1);
                if (article) articles.push(article);
            }
        }
        return schemaUniqueArticles(articles);
    }

    function extractArticlesFromPublishPage(body) {
        const publishPage = parsePublishPage(body);
        const publishList = publishPage?.publish_list;
        if (!Array.isArray(publishList)) return [];

        const articles = [];
        publishList.forEach(item => {
            const publishInfo = parseMaybeJSON(item?.publish_info);
            if (!publishInfo || typeof publishInfo !== 'object') return;

            const appmsgex = firstArray(
                parseMaybeJSON(publishInfo.appmsgex),
                publishInfo.appmsgex,
                parseMaybeJSON(publishInfo.appmsg_list),
                publishInfo.appmsg_list
            ) || [];
            const appmsgInfo = firstArray(
                parseMaybeJSON(publishInfo.appmsg_info),
                publishInfo.appmsg_info
            ) || [];
            const sentTime = publishInfo.sent_info?.time || publishInfo.publish_info?.publish_time || publishInfo.publish_time;

            appmsgex.forEach((child, idx) => {
                if (!child || typeof child !== 'object') return;
                const meta = appmsgInfo[idx] || {};
                const article = normalizeArticle(Object.assign({}, meta, child, {
                    msg_id: firstValue(child.appmsgid, meta.appmsgid, publishInfo.msgid),
                    item_idx: firstValue(child.itemidx, meta.itemidx, idx + 1),
                    create_time: firstValue(sentTime, child.create_time, child.update_time, publishInfo.create_time),
                }), publishInfo, idx + 1);
                if (article) articles.push(article);
            });
        });
        return articles;
    }

    function parsePublishPage(body) {
        if (!body || typeof body !== 'object') return null;
        const parsed = parseMaybeJSON(body.publish_page);
        if (parsed && typeof parsed === 'object') return parsed;
        if (body.publish_page && typeof body.publish_page === 'object') return body.publish_page;
        return null;
    }

    function candidateArticleLists(body) {
        const lists = [];
        const listSeen = new WeakSet();
        [
            body?.publish_list,
            body?.article_list,
            body?.list,
            body?.items,
            body?.data?.publish_list,
            body?.data?.article_list,
            body?.data?.list,
            body?.data?.items,
            body?.publish_page?.publish_list,
            body?.publish_page?.list,
        ].forEach(value => addListCandidate(value, lists, listSeen));

        scanNestedArticleLists(body, lists, new Set(), 0, listSeen);
        return lists;
    }

    function parseMaybeJSON(value) {
        if (typeof value !== 'string') return value;
        const trimmed = value.trim();
        if (!trimmed || !/^[\[{]/.test(trimmed)) return value;
        try {
            return JSON.parse(trimmed);
        } catch (e) {
            return value;
        }
    }

    function pushListCandidate(value, lists, listSeen) {
        if (!Array.isArray(value) || listSeen.has(value)) return;
        listSeen.add(value);
        lists.push(value);
    }

    function addListCandidate(value, lists, listSeen) {
        const parsed = parseMaybeJSON(value);
        if (Array.isArray(parsed)) {
            pushListCandidate(parsed, lists, listSeen);
            return;
        }
        if (parsed && typeof parsed === 'object') {
            [
                parsed.publish_list,
                parsed.article_list,
                parsed.list,
                parsed.items,
                parsed.appmsgex,
                parsed.appmsg_list,
            ].forEach(v => addListCandidate(v, lists, listSeen));
        }
    }

    function scanNestedArticleLists(value, lists, seen, depth, listSeen) {
        if (!value || typeof value !== 'object' || depth > 4 || seen.has(value)) return;
        seen.add(value);
        if (Array.isArray(value)) {
            if (value.some(looksLikeArticleItem)) pushListCandidate(value, lists, listSeen);
            value.slice(0, 10).forEach(item => scanNestedArticleLists(item, lists, seen, depth + 1, listSeen));
            return;
        }
        Object.keys(value).forEach(key => {
            const parsed = parseMaybeJSON(value[key]);
            if (Array.isArray(parsed) && parsed.some(looksLikeArticleItem)) {
                pushListCandidate(parsed, lists, listSeen);
            } else if (parsed && typeof parsed === 'object') {
                scanNestedArticleLists(parsed, lists, seen, depth + 1, listSeen);
            }
        });
    }

    function looksLikeArticleItem(item) {
        if (!item || typeof item !== 'object') return false;
        const info = articleInfo(item);
        return Boolean(
            firstValue(info.title, item.title) ||
            item.appmsgex || item.appmsg_list || item.article_list ||
            item.comm_msg_info || item.common_msg_info ||
            item.msg_info || item.article_info || item.appmsg_info
        );
    }

    function articleInfo(item) {
        return item?.msg_info || item?.article_info || item?.appmsg_info || item?.publish_info || item || {};
    }

    function firstArray(...values) {
        return values.find(Array.isArray);
    }

    function firstValue(...values) {
        return values.find(v => v !== undefined && v !== null && v !== '');
    }

    function normalizeArticle(item, parent, fallbackIdx) {
        if (!item || typeof item !== 'object') return null;

        const info = articleInfo(item);
        const parentInfo = articleInfo(parent);
        const commInfo = item.comm_msg_info || item.common_msg_info || parent?.comm_msg_info || parent?.common_msg_info || {};
        const title = firstValue(info.title, item.title, parentInfo.title, parent?.title);
        if (!title) return null;

        const msgId = firstValue(
            item.msg_id, info.msg_id, item.appmsgid, info.appmsgid,
            item.appmsg_id, info.appmsg_id, item.id, info.id,
            parent?.msg_id, parentInfo.msg_id, parent?.appmsgid, parentInfo.appmsgid,
            parent?.appmsg_id, parentInfo.appmsg_id, parent?.id, parentInfo.id,
            commInfo.id, commInfo.msg_id
        );
        const itemIdx = firstValue(item.item_idx, info.item_idx, item.itemidx, info.itemidx, parent?.item_idx, parent?.itemidx, fallbackIdx, 1);
        const reads = firstValue(
            item.read_num, info.read_num, item.total_read_uv, info.total_read_uv,
            item.read_count, info.read_count, item.read_uv, info.read_uv, item.readnum, info.readnum,
            parent?.read_num, parentInfo.read_num, parent?.total_read_uv, parentInfo.total_read_uv,
            0
        );
        const publishDate = normalizeDate(firstValue(
            info.create_time, item.create_time, info.publish_time, item.publish_time,
            info.publish_date, item.publish_date, parentInfo.create_time, parent?.create_time,
            parentInfo.publish_time, parent?.publish_time, parentInfo.publish_date, parent?.publish_date,
            commInfo.datetime, commInfo.create_time, commInfo.publish_time,
            ''
        ));

        return {
            msg_id: String(msgId || ''),
            item_idx: parseInt(itemIdx, 10) || 1,
            title: String(title),
            publish_date: publishDate,
            total_reads: parseReads(reads),
        };
    }

    function normalizeDate(value) {
        if (!value) return '';
        const n = Number(value);
        if (Number.isFinite(n) && n > 1000000000) {
            const ms = n > 1000000000000 ? n : n * 1000;
            return new Date(ms).toISOString().slice(0, 10);
        }
        return String(value).slice(0, 10).replace(/\//g, '-');
    }

    function parseReads(value) {
        if (typeof value === 'string' && value.includes('万')) {
            const n = parseFloat(value.replace(/,/g, ''));
            return Number.isFinite(n) ? Math.round(n * 10000) : 0;
        }
        const n = parseInt(String(value ?? 0).replace(/,/g, ''), 10);
        return Number.isFinite(n) ? n : 0;
    }

    function articleKeys(article) {
        const keys = [];
        const msgId = String(article?.msg_id || '').trim();
        const itemIdx = article?.item_idx || 1;
        const title = normalizeTitle(article?.title || '').toLowerCase();
        const publishDate = String(article?.publish_date || '').trim();

        if (msgId) return ['id:' + msgId + ':' + itemIdx];
        if (title && publishDate) return ['title_date:' + title + ':' + publishDate + ':' + itemIdx];
        if (title) return ['title:' + title + ':' + itemIdx];

        return keys;
    }

    function addScannedArticles(articles) {
        let added = 0;
        for (const article of articles) {
            const keys = articleKeys(article);
            if (keys.length === 0 || keys.some(key => scanSeenKeys.has(key))) continue;
            keys.forEach(key => scanSeenKeys.add(key));
            scanAllArticles.push(article);
            added++;
        }
        return added;
    }

    function queueScanApiArticles(articles, url) {
        if (!articles || articles.length === 0) return;
        scanPageApiArticles.push(...articles);
        console.log('[MP Scan] queued API articles:', articles.length, 'url:', url, 'queued:', scanPageApiArticles.length);
    }

    function cachedResponse(url, status, body) {
        return {
            url,
            status,
            body,
            captured_href: canonicalPageHref(window.location.href),
            captured_at: new Date().toISOString(),
        };
    }

    function extractArticlesFromCachedResponses() {
        const articles = [];
        for (const resp of collectedResponses) {
            if (!resp || !resp.body) continue;
            if (!cachedResponseLooksLikeCurrentPage(resp)) continue;
            articles.push(...extractArticlesFromAPI(resp.body, resp.url || ''));
        }
        return articles;
    }

    function seedScanFromCurrentPage(label) {
        return seedScanFromCurrentPageAsync(label);
    }

    async function seedScanFromCurrentPageAsync(label) {
        const apiSeeded = await seedScanFromPublishedApi(label);
        if (apiSeeded !== null) return apiSeeded;

        const queuedArticles = scanPageApiArticles;
        scanPageApiArticles = [];

        if (queuedArticles.length > 0) {
            const apiAdded = addScannedArticles(queuedArticles);
            recordPageSource(label, 'live_api', queuedArticles.length, apiAdded);
            console.log('[MP Scan] seeded from live page API:', apiAdded, 'candidates:', queuedArticles.length, 'total:', scanAllArticles.length);
            return apiAdded;
        }

        const cachedArticles = extractArticlesFromCachedResponses();
        if (cachedArticles.length > 0) {
            const cachedAdded = addScannedArticles(cachedArticles);
            recordPageSource(label, 'cached_api', cachedArticles.length, cachedAdded);
            console.log('[MP Scan] seeded from cached current-page API:', cachedAdded, 'candidates:', cachedArticles.length, 'total:', scanAllArticles.length);
            return cachedAdded;
        }

        const domArticles = extractArticlesFromDOM();
        const domAdded = addScannedArticles(domArticles);
        if (domArticles.length > 0) {
            recordPageSource(label, 'dom_fallback', domArticles.length, domAdded);
            console.log('[MP Scan] seeded from visible DOM fallback:', domAdded, 'candidates:', domArticles.length, 'total:', scanAllArticles.length);
            return domAdded;
        }

        recordPageSource(label, 'none', 0, 0);
        return 0;
    }

    async function seedScanFromPublishedApi(label) {
        try {
            const begin = currentBegin();
            const url = publishedRecordsApiUrl(begin);
            const response = await originalFetch.call(pageWindow, url, {
                credentials: 'include',
                headers: {
                    Accept: 'application/json, text/javascript, */*; q=0.01',
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
            if (!response || !response.ok) return null;
            const body = await response.json();
            const articles = extractArticlesFromAPI(body, url);
            if (!articles.length) return null;
            const added = addScannedArticles(articles);
            const publishPage = parsePublishPage(body);
            recordPageSource(label, 'api_fetch', articles.length, added, {
                total_count: publishPage?.total_count,
                begin,
            });
            console.log('[MP Scan] seeded from official published API:', added, 'candidates:', articles.length, 'total:', scanAllArticles.length);
            return added;
        } catch (e) {
            console.warn('[MP Scan] official published API fallback:', e);
            return null;
        }
    }

    function recordPageSource(label, source, candidates, added, extra) {
        scanPageSources.push(Object.assign({
            label: label || '',
            source,
            candidates,
            added,
            total: scanAllArticles.length,
            href: window.location.href,
        }, extra || {}));
        persistScanState();
    }

    function currentBegin() {
        if (scanState?.active) {
            if (scanState.phase === 'seed_first_page') return 0;
            if (scanState.phase === 'seed_after_next') {
                const turn = scanState.pending_page_turn || scanState.page_turns || 0;
                return Math.max(0, turn * SCAN_PAGE_SIZE);
            }
        }
        const value = queryParam(window.location.href, 'begin');
        const begin = parseInt(value || '0', 10);
        return Number.isFinite(begin) && begin >= 0 ? begin : 0;
    }

    function publishedRecordsApiUrl(begin) {
        const current = new URL(window.location.href);
        const url = new URL('/cgi-bin/appmsgpublish', current.origin);
        url.searchParams.set('sub', 'list');
        url.searchParams.set('begin', String(begin || 0));
        url.searchParams.set('count', current.searchParams.get('count') || String(SCAN_PAGE_SIZE));
        url.searchParams.set('query', '');
        url.searchParams.set('type', '101_1_102_103');
        url.searchParams.set('show_type', '');
        url.searchParams.set('free_publish_type', '1_102_103');
        url.searchParams.set('sub_action', 'list_ex');
        url.searchParams.set('search_card', '0');
        const fingerprint = current.searchParams.get('fingerprint');
        if (fingerprint) url.searchParams.set('fingerprint', fingerprint);
        const token = current.searchParams.get('token');
        if (token) url.searchParams.set('token', token);
        url.searchParams.set('lang', current.searchParams.get('lang') || 'zh_CN');
        url.searchParams.set('f', 'json');
        url.searchParams.set('ajax', '1');
        return url.toString();
    }

    function previewCurrentPageArticles() {
        const cachedArticles = extractArticlesFromCachedResponses();
        if (cachedArticles.length > 0) {
            return {
                source: 'cached_api',
                articles: schemaUniqueArticles(cachedArticles),
                candidates: cachedArticles.length,
            };
        }

        const domArticles = extractArticlesFromDOM();
        return {
            source: domArticles.length > 0 ? 'dom_fallback' : 'none',
            articles: schemaUniqueArticles(domArticles),
            candidates: domArticles.length,
        };
    }

    function schemaUniqueArticles(articles) {
        const seen = new Set();
        const result = [];
        for (const article of articles) {
            const key = articleKeys(article)[0];
            if (!key || seen.has(key)) continue;
            seen.add(key);
            result.push(article);
        }
        return result;
    }

    function cachedResponseLooksLikeCurrentPage(resp) {
        if (resp.captured_href && resp.captured_href !== canonicalPageHref(window.location.href)) {
            return false;
        }
        return responseLooksLikeCurrentPage(resp.url || '');
    }

    function responseLooksLikeCurrentPage(url) {
        const pageBegin = queryParam(window.location.href, 'begin');
        const responseBegin = queryParam(url, 'begin');
        if (pageBegin !== null && responseBegin !== null) return pageBegin === responseBegin;

        const pageSub = queryParam(window.location.href, 'sub');
        const responseSub = queryParam(url, 'sub');
        if (pageSub && responseSub && pageSub !== responseSub) return false;

        return true;
    }

    function canonicalPageHref(href) {
        try {
            const u = new URL(href, window.location.href);
            u.hash = '';
            return u.pathname + '?' + u.searchParams.toString();
        } catch (e) {
            return String(href || '').split('#')[0];
        }
    }

    function queryParam(url, name) {
        try {
            return new URL(url, window.location.href).searchParams.get(name);
        } catch (e) {
            return null;
        }
    }

    function firstPageHrefFrom(href) {
        try {
            const u = new URL(href, window.location.href);
            if (u.searchParams.has('begin')) u.searchParams.set('begin', '0');
            return u.toString();
        } catch (e) {
            return String(href || '');
        }
    }

    function createScanState(scanSessionId, startHref) {
        const now = new Date().toISOString();
        return {
            active: true,
            script_version: SCRIPT_VERSION,
            scan_session_id: scanSessionId,
            page_session_id: PAGE_SESSION_ID,
            phase: 'returning_to_first',
            scan_mode: 'from_first_page',
            started_from_current_page: false,
            start_href: startHref,
            first_page_href: firstPageHrefFrom(startHref),
            current_href: window.location.href,
            pre_scan_page_turns: 0,
            page_turns: 0,
            pending_page_turn: 0,
            scanned_pages: 0,
            last_page_added: 0,
            stop_reason: 'no_next_page',
            articles: [],
            seen_keys: [],
            page_sources: [],
            created_at: now,
            updated_at: now,
        };
    }

    function normalizeScanState(state) {
        if (!state || typeof state !== 'object') return null;
        const normalized = Object.assign(createScanState(
            state.scan_session_id || sessionId('scan'),
            state.start_href || window.location.href
        ), state);
        normalized.active = state.active !== false;
        normalized.script_version = SCRIPT_VERSION;
        normalized.articles = Array.isArray(state.articles) ? state.articles : [];
        normalized.seen_keys = Array.isArray(state.seen_keys) ? state.seen_keys : [];
        normalized.page_sources = Array.isArray(state.page_sources) ? state.page_sources : [];
        normalized.pre_scan_page_turns = Number(state.pre_scan_page_turns || 0);
        normalized.page_turns = Number(state.page_turns || 0);
        normalized.pending_page_turn = Number(state.pending_page_turn || 0);
        normalized.scanned_pages = Number(state.scanned_pages || 0);
        normalized.last_page_added = Number(state.last_page_added || 0);
        return normalized;
    }

    function loadScanState() {
        const raw = storageGet(SCAN_STATE_KEY);
        if (!raw) return null;
        try {
            const parsed = JSON.parse(raw);
            if (!parsed || parsed.active !== true) {
                storageRemove(SCAN_STATE_KEY);
                return null;
            }
            if (parsed.script_version && parsed.script_version !== SCRIPT_VERSION) {
                storageRemove(SCAN_STATE_KEY);
                return null;
            }
            const updatedAt = Date.parse(parsed.updated_at || parsed.created_at || '');
            if (Number.isFinite(updatedAt) && Date.now() - updatedAt > SCAN_STATE_TTL_MS) {
                storageRemove(SCAN_STATE_KEY);
                return null;
            }
            return normalizeScanState(parsed);
        } catch (e) {
            storageRemove(SCAN_STATE_KEY);
            return null;
        }
    }

    function hydrateScanState(state) {
        const normalized = normalizeScanState(state);
        if (!normalized || !normalized.active) return false;
        scanState = normalized;
        currentScanSessionId = scanState.scan_session_id || '';
        scanAllArticles = scanState.articles.slice();
        scanSeenKeys = new Set(scanState.seen_keys);
        scanAllArticles.forEach(article => {
            articleKeys(article).forEach(key => scanSeenKeys.add(key));
        });
        scanPageApiArticles = [];
        scanLastDomDebug = [];
        scanPageSources = scanState.page_sources.slice();
        isScanning = true;
        return true;
    }

    function persistScanState(extra) {
        if (!scanState || !scanState.active) return;
        Object.assign(scanState, extra || {});
        scanState.script_version = SCRIPT_VERSION;
        scanState.scan_session_id = currentScanSessionId || scanState.scan_session_id || sessionId('scan');
        scanState.page_session_id = PAGE_SESSION_ID;
        scanState.current_href = window.location.href;
        scanState.articles = scanAllArticles.slice();
        scanState.seen_keys = Array.from(scanSeenKeys);
        scanState.page_sources = scanPageSources.slice();
        scanState.updated_at = new Date().toISOString();
        storageSet(SCAN_STATE_KEY, JSON.stringify(scanState));
    }

    function clearScanState() {
        scanState = null;
        storageRemove(SCAN_STATE_KEY);
    }

    function extractArticlesFromDOM() {
        const groups = new Map();
        const seenElements = new Set();
        const recordIds = new WeakMap();
        let nextRecordId = 1;
        const selectors = [
            'a[href*="mp.weixin.qq.com/s"]',
            'a[href*="__biz"]',
            'a[href*="mid="]',
            'a[href*="appmsgid="]',
            '[class*="title"] a',
            '[class*="Title"] a',
            '[class*="appmsg"] [class*="title"]',
            '[class*="mass"] [class*="title"]',
            '[class*="publish"] [class*="title"]',
        ];

        selectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                if (seenElements.has(el) || !isVisibleElement(el)) return;
                seenElements.add(el);
                const article = articleFromElement(el);
                if (!article) return;

                const record = articleRecordContainerForElement(el);
                const recordKey = domRecordKey(record, article, recordIds, () => nextRecordId++);
                const candidate = domCandidate(article, el, selector, record);
                if (!groups.has(recordKey)) groups.set(recordKey, []);
                groups.get(recordKey).push(candidate);
            });
        });

        return selectDomArticleCandidates(Array.from(groups.values()));
    }

    function domCandidate(article, el, selector, record) {
        const container = record || articleContainerForElement(el);
        const rect = container?.getBoundingClientRect?.() || el.getBoundingClientRect();
        const text = (container?.textContent || el.textContent || '').replace(/\s+/g, ' ').trim();
        const href = el.href || el.getAttribute('href') || '';

        return {
            article,
            selector,
            text,
            href,
            top: rect?.top ?? 0,
        };
    }

    function domRecordKey(record, article, recordIds, nextId) {
        if (record) {
            if (!recordIds.has(record)) recordIds.set(record, 'record:' + nextId());
            return recordIds.get(record);
        }

        const keys = articleKeys(article);
        return keys.find(k => k.startsWith('id:')) || keys.find(k => k.startsWith('title_date:')) || keys[0] || ('candidate:' + nextId());
    }

    function selectDomArticleCandidates(groups) {
        const selectedCandidates = [];
        const debugItems = [];

        for (const group of groups) {
            const sortedGroup = group.slice().sort((a, b) => a.top - b.top);
            const selected = choosePrimaryDomCandidate(sortedGroup);
            if (selected) selectedCandidates.push(selected);

            sortedGroup.forEach(candidate => {
                debugItems.push({
                    title: candidate.article.title,
                    publish_date: candidate.article.publish_date,
                    msg_id: candidate.article.msg_id,
                    selected: candidate === selected,
                    selector: candidate.selector,
                    href: candidate.href.slice(0, 160),
                    group_size: sortedGroup.length,
                });
            });
        }

        scanLastDomDebug = debugItems;
        return selectedCandidates.sort((a, b) => a.top - b.top).map(candidate => candidate.article);
    }

    function choosePrimaryDomCandidate(candidates) {
        if (candidates.length === 0) return null;
        const withArticleId = candidates.find(candidate => candidate.article.msg_id);
        if (withArticleId) return withArticleId;
        const withArticleHref = candidates.find(candidate => /mp\.weixin\.qq\.com\/s|[?&](mid|appmsgid|msgid)=/.test(candidate.href));
        return withArticleHref || candidates[0];
    }

    function articleContainerForElement(el) {
        return articleRecordContainerForElement(el) || el.parentElement?.closest('tr, li, [class*="item"], [class*="Item"], [class*="card"], [class*="Card"], [class*="appmsg"], [class*="mass"], [class*="publish"]') || el.parentElement || el;
    }

    function articleRecordContainerForElement(el) {
        let node = el.parentElement;
        let fallback = null;
        while (node && node !== document.body) {
            if (isVisibleElement(node)) {
                const text = (node.textContent || '').replace(/\s+/g, ' ').trim();
                const className = String(node.className || '');
                if (!fallback && /\b(tr|li)\b/i.test(node.tagName)) fallback = node;
                if (!fallback && /(publish|mass|appmsg|item|card)/i.test(className)) fallback = node;
                if (recordTextLooksScoped(text)) return node;
            }
            node = node.parentElement;
        }
        return fallback;
    }

    function recordTextLooksScoped(text) {
        const usableDates = dateCandidates(text).filter(date => !isFuturePublishDate(date));
        return text.length < 3000 && usableDates.length > 0 && usableDates.length <= 3;
    }

    function isVisibleElement(el) {
        if (!el || !el.isConnected || !el.getClientRects || el.getClientRects().length === 0) return false;
        let node = el;
        while (node && node.nodeType === 1) {
            const style = window.getComputedStyle(node);
            if (
                style.display === 'none' ||
                style.visibility === 'hidden' ||
                style.visibility === 'collapse' ||
                node.getAttribute('aria-hidden') === 'true'
            ) {
                return false;
            }
            node = node.parentElement;
        }
        return true;
    }

    function articleFromElement(el) {
        const title = cleanArticleTitle(el.textContent || el.getAttribute('title') || '');
        if (!title || isLikelyNonArticleTitle(title)) return null;

        const container = articleContainerForElement(el);
        if (!isVisibleElement(container)) return null;
        const text = (container.textContent || '').replace(/\s+/g, ' ');
        const href = el.href || el.getAttribute('href') || '';

        return {
            msg_id: extractMsgId(href, container) || '',
            item_idx: extractItemIdx(href) || 1,
            title: title,
            publish_date: extractDate(text),
            total_reads: extractReadCount(text),
        };
    }

    function normalizeTitle(raw) {
        return String(raw || '').replace(/\s+/g, ' ').trim();
    }

    function cleanArticleTitle(raw) {
        let title = normalizeTitle(raw);
        title = title.replace(/\s+(原创|转载)\s+(已修改\s+)?第\d+次修改\s+20\d{2}年\d{1,2}月\d{1,2}日.*$/u, '');
        title = title.replace(/\s+(原创|转载)\s+已修改\s+20\d{2}年\d{1,2}月\d{1,2}日.*$/u, '');
        title = title.replace(/\s+(原创|转载)\s+20\d{2}年\d{1,2}月\d{1,2}日.*$/u, '');
        title = title.replace(/\s+(原创|转载|已修改)$/u, '');
        return normalizeTitle(title);
    }

    function isLikelyNonArticleTitle(title) {
        if (title.length < 2 || title.length > 120) return true;
        const uiFragments = [
            '替换详情',
            '扫码验证',
            '已发送操作申请',
            '设置仅自己可见',
            '是否继续设置',
            '发表相关数据',
            '发表记录 发表',
            '原创保护',
            '后续不可恢复',
            '第1次修改',
            '第2次修改',
        ];
        if (uiFragments.some(fragment => title.includes(fragment))) return true;
        if (/^(¥|￥)\s*\d[\d,.]*(?:\.\d+)?$/.test(title)) return true;
        if (/^\d[\d,.]*(?:\.\d+)?\s*万?$/.test(title)) return true;
        if (/^第\d+次修改$/.test(title)) return true;
        if (/^(已修改|未修改|原创|转载|群发|发布|发表|删除|编辑|预览|统计|详情|分享|留言|赞赏)$/.test(title)) return true;
        if (/^(阅读|分享|收藏|留言|点赞|赞赏)\s*\d/.test(title)) return true;
        if (/20\d{2}年\d{1,2}月\d{1,2}日/.test(title) && /(原创|转载|已修改|第\d+次修改)/.test(title)) return true;
        return /^(首页|发表记录|草稿箱|素材库|原创|合集|下一页|上一页|详情|数据|删除|编辑|转载)$/.test(title);
    }

    function extractMsgId(href, container) {
        const urlText = String(href || '');
        for (const param of ['mid', 'appmsgid', 'msgid']) {
            const match = urlText.match(new RegExp('[?&]' + param + '=([^&#]+)'));
            if (match) return decodeURIComponent(match[1]);
        }
        for (const attr of ['data-msgid', 'data-msg-id', 'data-appmsgid', 'data-id']) {
            const value = container?.getAttribute?.(attr);
            if (value) return value;
        }
        return '';
    }

    function extractItemIdx(href) {
        const match = String(href || '').match(/[?&](?:idx|itemidx|item_idx)=([^&#]+)/);
        return match ? parseInt(match[1], 10) || 1 : 1;
    }

    function extractDate(text) {
        const dates = dateCandidates(text).filter(date => !isFuturePublishDate(date));
        if (dates.length > 0) return dates[0];
        return '';
    }

    function dateCandidates(text) {
        const full = String(text || '');
        const dates = [];
        const ymdRegex = /20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:日)?/g;
        for (const match of full.matchAll(ymdRegex)) {
            dates.push(normalizeDate(match[0].replace('年', '-').replace('月', '-').replace('日', '')));
        }

        const withoutFullDates = full.replace(ymdRegex, ' ');
        const mdRegex = /(\d{1,2})月(\d{1,2})日/g;
        for (const match of withoutFullDates.matchAll(mdRegex)) {
            const y = new Date().getFullYear();
            dates.push(`${y}-${String(match[1]).padStart(2, '0')}-${String(match[2]).padStart(2, '0')}`);
        }
        return dates;
    }

    function isFuturePublishDate(date) {
        const parsed = new Date(date + 'T00:00:00');
        if (!Number.isFinite(parsed.getTime())) return false;
        const latestAllowed = new Date();
        latestAllowed.setDate(latestAllowed.getDate() + 1);
        latestAllowed.setHours(23, 59, 59, 999);
        return parsed > latestAllowed;
    }

    function extractReadCount(text) {
        const match = String(text || '').match(/(?:阅读|阅读数|阅读人数|读过)[^\d]*(\d[\d,.]*\s*万?)/);
        return match ? parseReads(match[1].replace(/\s+/g, '')) : 0;
    }

    // ── Send to collector ────────────────────────────────────────
    function sendToCollector(payloadOverride) {
        if (sent && !payloadOverride) return Promise.resolve(null);
        if (!payloadOverride) sent = true;

        const payload = payloadOverride || {
            page_type: pageType,
            url: window.location.href,
            title: document.title,
            collected_at: new Date().toISOString(),
            page_data: sessionPageData({}),
            api_responses: collectedResponses,
            api_count: collectedResponses.length,
        };

        const label = payload.page_type || pageType;
        console.log('[MP] Sending to collector:', label);

        return postCollectorPayload(payload).then(result => {
            if (!payloadOverride) {
                showBadge('✓ 已采集 ' + collectedResponses.length + ' 条 (' + pageType + ')', '#07c160');
            }
            console.log('[MP] Collector OK:', result);
        }).catch(err => {
            console.warn('[MP] Collector unreachable:', err.message);
            showBadge('⚠ 采集服务未启动 (localhost:9876)', '#e6a23c');
            throw err;
        });
    }

    function sendDiagnostic(kind, extra) {
        const pageData = sessionPageData({
            kind,
            diagnostics: diagnostics(),
        }, extra || {});

        return sendToCollector({
            page_type: 'diagnostic',
            url: window.location.href,
            title: document.title,
            collected_at: new Date().toISOString(),
            page_data: pageData,
            api_responses: [],
            api_count: 0,
        });
    }

    function sessionPageData(base, extra) {
        return Object.assign({
            page_session_id: PAGE_SESSION_ID,
            scan_session_id: currentScanSessionId || '',
        }, base || {}, extra || {});
    }

    function postCollectorPayload(payload) {
        const body = JSON.stringify(payload);
        if (typeof GM_xmlhttpRequest === 'function') {
            return new Promise((resolve, reject) => {
                GM_xmlhttpRequest({
                    method: 'POST',
                    url: COLLECTOR_URL,
                    headers: {'Content-Type': 'application/json'},
                    data: body,
                    responseType: 'json',
                    onload: response => {
                        if (response.status < 200 || response.status >= 300) {
                            reject(new Error('collector status ' + response.status));
                            return;
                        }
                        resolve(response.response || JSON.parse(response.responseText || '{}'));
                    },
                    onerror: () => reject(new Error('GM_xmlhttpRequest failed')),
                    ontimeout: () => reject(new Error('GM_xmlhttpRequest timeout')),
                });
            });
        }
        if (typeof GM !== 'undefined' && typeof GM.xmlHttpRequest === 'function') {
            return GM.xmlHttpRequest({
                method: 'POST',
                url: COLLECTOR_URL,
                headers: {'Content-Type': 'application/json'},
                data: body,
                responseType: 'json',
            }).then(response => {
                if (response.status < 200 || response.status >= 300) {
                    throw new Error('collector status ' + response.status);
                }
                return response.response || JSON.parse(response.responseText || '{}');
            });
        }

        return fetch(COLLECTOR_URL, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body,
        }).then(r => r.json());
    }

    function diagnostics() {
        return {
            script_version: SCRIPT_VERSION,
            page_session_id: PAGE_SESSION_ID,
            scan_session_id: currentScanSessionId || '',
            page_type: pageType,
            cached_responses: collectedResponses.length,
            current_page_cached_responses: collectedResponses.filter(cachedResponseLooksLikeCurrentPage).length,
            scan_articles: scanAllArticles.length,
            scan_phase: scanState?.phase || '',
            persisted_scan_articles: scanState?.articles?.length || 0,
            dom_articles: extractArticlesFromDOM().length,
            dom_candidates: scanLastDomDebug.length,
            dom_merged: scanLastDomDebug.filter(item => !item.selected).slice(0, 20),
            dom_debug: scanLastDomDebug.slice(0, 40),
            has_gm_xmlhttp_request: typeof GM_xmlhttpRequest === 'function',
            has_gm_object_xhr: typeof GM !== 'undefined' && typeof GM.xmlHttpRequest === 'function',
            has_unsafe_window: typeof unsafeWindow !== 'undefined',
            href: window.location.href,
        };
    }

    // ── UI badge ─────────────────────────────────────────────────
    function showBadge(text, bg) {
        if (!document.body) {
            onDomReady(() => showBadge(text, bg));
            return;
        }
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
        if (!document.body) {
            onDomReady(addScanButton);
            return;
        }
        if (document.getElementById('mp-scan-all-btn')) return;

        const btn = document.createElement('button');
        btn.id = 'mp-scan-all-btn';
        btn.textContent = FULL_SCAN_BUTTON_TEXT;
        btn.style.cssText = 'position:fixed;top:20px;right:20px;z-index:99998;'
            + 'background:#07c160;color:#fff;border:none;padding:10px 18px;'
            + 'border-radius:6px;font-size:14px;cursor:pointer;font-family:-apple-system,sans-serif;'
            + 'box-shadow:0 2px 12px rgba(0,0,0,.2);';
        btn.onmouseover = () => { if (!btn.disabled) btn.style.background = '#06ad56'; };
        btn.onmouseout = () => { if (!btn.disabled) btn.style.background = '#07c160'; };

        btn.onclick = async function() {
            if (scanState?.active) {
                if (isScanning) return;
                hydrateScanState(scanState);
                prepareScanButton(btn, `⏳ 继续扫描 · 合计${scanAllArticles.length}篇`);
                await runFullScan(btn);
                return;
            }
            await startFullScan(btn);
        };

        if (scanState && scanState.active) {
            setScanButtonText(btn, `⏳ 继续扫描 · 合计${scanAllArticles.length}篇`);
            btn.style.background = '#999';
            btn.disabled = true;
        }

        document.body.appendChild(btn);
        addConnectivityButton();
        resumeScanIfNeeded(btn);
    }

    async function startFullScan(btn) {
        if (isScanning && scanState?.active) return;
        currentScanSessionId = sessionId('scan');
        scanAllArticles = [];
        scanSeenKeys = new Set();
        scanPageApiArticles = [];
        scanLastDomDebug = [];
        scanPageSources = [];
        scanState = createScanState(currentScanSessionId, window.location.href);
        isScanning = true;
        persistScanState();
        prepareScanButton(btn, '⏳ 扫描中...');

        try {
            await sendDiagnostic('published_records_scan_started', {
                expected_payload: 'published_records',
                scan_mode: 'from_first_page',
                current_href: scanState.start_href,
                scan_session_id: currentScanSessionId,
            });
        } catch (e) {
            console.warn('[MP Scan] scan_started diagnostic failed:', e);
        }

        await runFullScan(btn);
    }

    function resumeScanIfNeeded(btn) {
        if (!scanState || !scanState.active || scanResumeStarted) return;
        scanResumeStarted = true;
        prepareScanButton(btn, `⏳ 继续扫描 · 合计${scanAllArticles.length}篇`);
        setTimeout(() => {
            runFullScan(btn).catch(e => {
                console.error('[MP Scan] resume failed:', e);
                showBadge('⚠ 续扫失败: ' + (e.message || e), '#e6a23c');
                resetScanButton(btn);
            });
        }, 100);
    }

    function prepareScanButton(btn, text) {
        setScanButtonText(btn, text);
        btn.style.background = '#999';
        btn.disabled = true;
    }

    function resetScanButton(btn) {
        btn.textContent = FULL_SCAN_BUTTON_TEXT;
        btn.title = '';
        btn.style.background = '#07c160';
        btn.disabled = false;
        isScanning = false;
        currentScanSessionId = '';
        scanResumeStarted = false;
    }

    async function runFullScan(btn) {
        if (!scanState || !scanState.active) return;
        let stopReason = scanState.stop_reason || 'no_next_page';

        try {
            if (scanState.phase === 'returning_to_first') {
                await returnToFirstPage(btn, MAX_PAGE_TURNS, SCAN_PAGE_DELAY_MS);
                persistScanState({
                    phase: 'seed_first_page',
                    first_page_href: firstPageHrefFrom(window.location.href),
                });
            }

            if (scanState.phase === 'seed_first_page') {
                const initialAdded = await seedScanFromCurrentPage('page_1');
                const scannedPages = initialAdded > 0 ? Math.max(scanState.scanned_pages || 0, 1) : (scanState.scanned_pages || 0);
                persistScanState({
                    phase: 'scan_next_pages',
                    scanned_pages: scannedPages,
                    last_page_added: initialAdded,
                });
                setScanButtonText(btn, `⏳ 第1页新增${initialAdded}篇 · 合计${scanAllArticles.length}篇`);
            }

            while ((scanState.page_turns || 0) < MAX_PAGE_TURNS) {
                if (scanState.phase === 'seed_after_next') {
                    await seedPendingNextPage(btn);
                    continue;
                }

                setScanButtonText(btn, `⏳ 翻页中 · 合计${scanAllArticles.length}篇`);
                scanPageApiArticles = [];
                const nextTurn = (scanState.page_turns || 0) + 1;
                const found = await clickNextPage(() => {
                    persistScanState({
                        phase: 'seed_after_next',
                        page_turns: nextTurn,
                        pending_page_turn: nextTurn,
                    });
                });
                if (!found) {
                    console.log('[MP Scan] No more pages after turns:', scanState.page_turns || 0);
                    stopReason = 'no_next_page';
                    break;
                }
            }
            if ((scanState.page_turns || 0) >= MAX_PAGE_TURNS) stopReason = 'max_page_turns';
        } catch(e) {
            stopReason = 'error: ' + (e.message || e);
            console.error('[MP Scan] Error:', e);
        }

        persistScanState({phase: 'sending', stop_reason: stopReason});
        await sendFullScanPayload(btn);
    }

    async function seedPendingNextPage(btn) {
        await wait(SCAN_PAGE_DELAY_MS);
        const beforeCount = scanAllArticles.length;
        if (scanAllArticles.length === beforeCount) {
            await wait(600);
        }
        const pageTurn = scanState.pending_page_turn || scanState.page_turns || 1;
        await seedScanFromCurrentPage('page_turn_' + pageTurn);
        const addedThisPage = scanAllArticles.length - beforeCount;
        const scannedPages = addedThisPage > 0 ? (scanState.scanned_pages || 0) + 1 : (scanState.scanned_pages || 0);
        persistScanState({
            phase: 'scan_next_pages',
            pending_page_turn: 0,
            scanned_pages: scannedPages,
            last_page_added: addedThisPage,
        });
        if (addedThisPage > 0) {
            setScanButtonText(btn, `⏳ 本页新增${addedThisPage}篇 · 合计${scanAllArticles.length}篇`);
        } else {
            setScanButtonText(btn, `⏳ 本页未新增 · 合计${scanAllArticles.length}篇`);
        }
    }

    async function sendFullScanPayload(btn) {
        const state = scanState || {};
        const payload = {
            page_type: 'published_records',
            url: window.location.href,
            title: document.title,
            collected_at: new Date().toISOString(),
            page_data: sessionPageData({
                total_pages: state.scanned_pages || 0,
                scanned_pages: state.scanned_pages || 0,
                page_turns: state.page_turns || 0,
                article_count: scanAllArticles.length,
                queued_api_articles: scanPageApiArticles.length,
                page_sources: scanPageSources,
                last_page_added: state.last_page_added || 0,
                stop_reason: state.stop_reason || 'no_next_page',
                scan_mode: 'from_first_page',
                started_from_current_page: false,
                start_href: state.start_href || window.location.href,
                first_page_href: state.first_page_href || firstPageHrefFrom(window.location.href),
                pre_scan_page_turns: state.pre_scan_page_turns || 0,
                diagnostics: diagnostics(),
            }),
            api_responses: [{
                url: 'published_records_scan',
                body: { article_list: scanAllArticles }
            }]
        };

        try {
            await sendToCollector(payload);
            if (scanAllArticles.length > 0) {
                showBadge('✅ 已扫描 ' + scanAllArticles.length + ' 篇文章', '#07c160');
            } else {
                showBadge('⚠ 已连接，但未解析到文章；诊断已上报', '#e6a23c');
            }
            clearScanState();
            resetScanButton(btn);
        } catch (e) {
            showBadge('⚠ 采集发送失败: ' + (e.message || e), '#e6a23c');
            persistScanState({
                phase: 'sending',
                stop_reason: 'send_failed: ' + (e.message || e),
            });
            setScanButtonText(btn, `⚠ 发送失败，点击重试 · 已扫${scanAllArticles.length}篇`);
            btn.style.background = '#e6a23c';
            btn.disabled = false;
            isScanning = false;
            scanResumeStarted = false;
        }
    }

    function addConnectivityButton() {
        if (document.getElementById('mp-test-collector-btn')) return;

        const btn = document.createElement('button');
        btn.id = 'mp-test-collector-btn';
        btn.textContent = '🔌 测试采集连接 v' + SCRIPT_VERSION;
        btn.style.cssText = 'position:fixed;top:66px;right:20px;z-index:99998;'
            + 'background:#409eff;color:#fff;border:none;padding:8px 14px;'
            + 'border-radius:6px;font-size:13px;cursor:pointer;font-family:-apple-system,sans-serif;'
            + 'box-shadow:0 2px 12px rgba(0,0,0,.18);';

        btn.onclick = async function() {
            btn.disabled = true;
            btn.textContent = '🔌 测试中...';
            try {
                const result = await sendDiagnostic('manual_connectivity_test');
                console.log('[MP] Connectivity test OK:', result);
                showBadge('✅ 采集连接正常', '#07c160');
                btn.textContent = '✅ 连接正常';
            } catch (e) {
                console.warn('[MP] Connectivity test failed:', e);
                showBadge('⚠ 采集连接失败: ' + (e.message || e), '#e6a23c');
                btn.textContent = '⚠ 连接失败';
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    btn.textContent = '🔌 测试采集连接 v' + SCRIPT_VERSION;
                }, 2500);
            }
        };

        document.body.appendChild(btn);
        addCurrentPagePreviewButton();
    }

    function addCurrentPagePreviewButton() {
        if (document.getElementById('mp-preview-current-btn')) return;

        const btn = document.createElement('button');
        btn.id = 'mp-preview-current-btn';
        btn.textContent = '🔎 当前页预检 v' + SCRIPT_VERSION;
        btn.style.cssText = 'position:fixed;top:110px;right:20px;z-index:99998;'
            + 'background:#606266;color:#fff;border:none;padding:8px 14px;'
            + 'border-radius:6px;font-size:13px;cursor:pointer;font-family:-apple-system,sans-serif;'
            + 'box-shadow:0 2px 12px rgba(0,0,0,.18);';

        btn.onclick = async function() {
            btn.disabled = true;
            btn.textContent = '🔎 预检中...';
            try {
                const preview = previewCurrentPageArticles();
                const payload = {
                    page_type: 'published_records_preview',
                    url: window.location.href,
                    title: document.title,
                    collected_at: new Date().toISOString(),
                    page_data: sessionPageData({
                        kind: 'current_page_preview',
                        source: preview.source,
                        article_count: preview.articles.length,
                        candidates: preview.candidates,
                        diagnostics: diagnostics(),
                    }),
                    api_responses: [{
                        url: 'published_records_current_page_preview',
                        body: { article_list: preview.articles }
                    }],
                    api_count: 1,
                };
                await sendToCollector(payload);
                showBadge('当前页预检：' + preview.source + ' · ' + preview.articles.length + ' 篇', '#606266');
                btn.textContent = '已预检 ' + preview.articles.length + ' 篇';
            } catch (e) {
                showBadge('⚠ 当前页预检失败: ' + (e.message || e), '#e6a23c');
                btn.textContent = '预检失败';
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    btn.textContent = '🔎 当前页预检 v' + SCRIPT_VERSION;
                }, 2500);
            }
        };

        document.body.appendChild(btn);
    }

    async function returnToFirstPage(btn, maxTurns, delay) {
        let turns = scanState?.pre_scan_page_turns || 0;
        while (turns < maxTurns) {
            setScanButtonText(btn, `⏳ 回到第一页中 · 已回退${turns}页`);
            const previousButton = findPreviousPageButton();
            if (!previousButton) break;
            scanPageApiArticles = [];
            persistScanState({
                phase: 'returning_to_first',
                pre_scan_page_turns: turns + 1,
            });
            previousButton.click();
            turns++;
            await wait(delay);
        }
        if (turns >= maxTurns) throw new Error('max_previous_page_turns');
        persistScanState({pre_scan_page_turns: turns});
        return turns;
    }

    // Click next page button on published records page
    async function clickNextPage(beforeClick) {
        // Method 1: WeChat pagination buttons
        const btns = document.querySelectorAll('.weui-desktop-pagination__nav .weui-desktop-btn');
        for (const b of btns) {
            if (isDisabledPaginationButton(b)) continue;
            if (isNextPageControl(b)) {
                if (beforeClick) beforeClick(b);
                b.click();
                return true;
            }
        }
        // Method 2: Generic "下一页" text
        const allBtns = document.querySelectorAll('button, a, span[role="button"], div[role="button"]');
        for (const b of allBtns) {
            if (isDisabledPaginationButton(b)) continue;
            if (isNextPageControl(b)) {
                if (beforeClick) beforeClick(b);
                b.click();
                return true;
            }
        }
        return false;
    }

    async function clickPreviousPage() {
        const button = findPreviousPageButton();
        if (!button) return false;
        button.click();
        return true;
    }

    function findPreviousPageButton() {
        const btns = document.querySelectorAll('.weui-desktop-pagination__nav .weui-desktop-btn');
        for (const b of btns) {
            if (isDisabledPaginationButton(b)) continue;
            if (isPreviousPageControl(b)) {
                return b;
            }
        }

        const allBtns = document.querySelectorAll('button, a, span[role="button"], div[role="button"]');
        for (const b of allBtns) {
            if (isDisabledPaginationButton(b)) continue;
            if (isPreviousPageControl(b)) {
                return b;
            }
        }
        return null;
    }

    function isNextPageControl(el) {
        const text = paginationControlText(el);
        return text.includes('下一页') || /\b(next|pager-next|pagination-next)\b/i.test(text);
    }

    function isPreviousPageControl(el) {
        const text = paginationControlText(el);
        return text.includes('上一页') || /\b(prev|previous|pager-prev|pagination-prev)\b/i.test(text);
    }

    function paginationControlText(el) {
        const parts = [
            el.textContent || '',
            el.getAttribute?.('aria-label') || '',
            el.getAttribute?.('title') || '',
            String(el.className || ''),
        ];
        el.querySelectorAll?.('[class]').forEach(child => parts.push(String(child.className || '')));
        return parts.join(' ').replace(/\s+/g, ' ').trim();
    }

    function isDisabledPaginationButton(el) {
        const cls = String(el.className || '');
        return Boolean(
            el.disabled ||
            el.getAttribute('aria-disabled') === 'true' ||
            /\b(disabled|is-disabled|weui-desktop-btn_disabled|btn_disabled|pagination__btn_disabled)\b/.test(cls)
        );
    }

    // ── Init ─────────────────────────────────────────────────────
    console.log('[MP Collector v' + SCRIPT_VERSION + '] Loaded on', pageType, window.location.href);

    window.addEventListener('beforeunload', () => {
        if (scanState?.active) persistScanState();
    });

    if (pageType === 'published_records') {
        // Add scan button, don't auto-send
        showBadge('📊 已发表记录页 · MP Collector v' + SCRIPT_VERSION, '#409eff');
        onWindowLoad(() => setTimeout(() => {
            addScanButton();
            sendDiagnostic('published_records_page_loaded').catch(() => {});
        }, 1000));
    } else {
        // Normal behavior: wait for API calls, auto-send
        showBadge('🔍 监听中... (' + pageType + ')', '#409eff');
        onWindowLoad(() => {
            setTimeout(() => {
                console.log('[MP] Sending after 4s. Collected:', collectedResponses.length);
                sendToCollector().catch(() => {});
            }, 4000);
        });
        window.addEventListener('beforeunload', () => sendToCollector().catch(() => {}));
    }
})();
