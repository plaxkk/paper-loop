"""Check rendered SEO output after `cd site && npm run build` (stdlib only)."""
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'site/.next/server/app'
ORIGIN = 'https://paper-loop-xi.vercel.app'


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.meta, self.canonical, self.schema, self.images = {}, [], [], []
        self.title, self.h1, self._capture, self._text = '', 0, None, ''
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta':
            self.meta[a.get('name', a.get('property'))] = a.get('content', '')
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonical.append(a['href'])
        if tag == 'img':
            self.images.append(a)
        if tag == 'h1':
            self.h1 += 1
        if tag == 'title' or (tag == 'script' and a.get('type') == 'application/ld+json'):
            self._capture, self._text = tag, ''

    def handle_data(self, text):
        if self._capture:
            self._text += text

    def handle_endtag(self, tag):
        if tag == self._capture:
            if tag == 'title':
                self.title = self._text
            else:
                self.schema.append(json.loads(self._text))
            self._capture = None


def main():
    xml = ET.fromstring((BUILD / 'sitemap.xml.body').read_text())
    urls = [node.text for node in xml.findall('{*}url/{*}loc')]
    assert len(urls) == len(set(urls)) == 17, urls
    assert all((url == ORIGIN or url.startswith(ORIGIN + '/')) and '?' not in url for url in urls)
    assert not any('/history' in u or '/api/' in u or '/classics/dpo' in u for u in urls)
    titles, descriptions = set(), set()
    papers = 0
    for url in urls:
        path = urlparse(url).path or '/'
        # workspace is rendered dynamically; other public content is pre-rendered.
        if path == '/workspace':
            continue
        file = BUILD / ('index.html' if path == '/' else path.lstrip('/') + '.html')
        page = Page(file.read_text())
        assert page.canonical == [url], (path, page.canonical)
        assert page.h1 == 1 and page.title and page.meta.get('description'), path
        assert 'noindex' not in page.meta.get('robots', ''), path
        assert page.title not in titles and page.meta['description'] not in descriptions
        titles.add(page.title)
        descriptions.add(page.meta['description'])
        assert page.meta.get('og:url') == url and page.meta.get('og:image', '').startswith(ORIGIN)
        if path.startswith('/classics/'):
            papers += 1
            article = next(s for s in page.schema if s['@type'] == 'BlogPosting')
            assert article['author']['name'] == 'kk'
            assert article['datePublished'].startswith('2026-'), article
            assert article['citation'].startswith('https://')
            assert next(s for s in page.schema if s['@type'] == 'BreadcrumbList')
            for image in page.images:
                if image.get('src', '').startswith('/papers/archive/'):
                    assert int(image['width']) > 0 and int(image['height']) > 0
                    assert (ROOT / 'site/public' / image['src'].lstrip('/')).is_file()
    assert papers == 12
    for file in ['history.html', 'classics/dpo.html']:
        page = Page((BUILD / file).read_text())
        assert 'noindex' in page.meta['robots'], file
        assert not any(s['@type'] == 'BlogPosting' for s in page.schema)
    robots = (BUILD / 'robots.txt.body').read_text()
    assert f'Sitemap: {ORIGIN}/sitemap.xml' in robots
    assert 'Disallow: /api/' in robots and 'Disallow: /workspace/' in robots
    proof = json.loads((ROOT / 'site/lib/indexnow.json').read_text())
    assert (ROOT / 'site/public' / (proof['key'] + '.txt')).read_text().strip() == proof['key']
    assert (BUILD / 'opengraph-image.body').read_bytes().startswith(b'\x89PNG')
    print('PASS: 17 sitemap URLs; 12 article schemas, unique metadata, canonicals, images, robots and private/draft exclusions.')


if __name__ == '__main__':
    main()
