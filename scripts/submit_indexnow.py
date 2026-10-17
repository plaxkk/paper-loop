"""Submit public sitemap URLs to IndexNow; Google uses Search Console instead.

Run manually after a successful production deployment. The public verification
key proves host ownership; it is not a service credential.
"""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET


def main():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / 'site/lib/indexnow.json').read_text())
    origin = 'https://' + config['host']
    key_url = origin + '/' + config['key'] + '.txt'
    with urlopen(key_url, timeout=30) as response:
        assert response.read().decode().strip() == config['key'], 'Ownership file mismatch'
    with urlopen(origin + '/sitemap.xml', timeout=30) as response:
        xml = ET.fromstring(response.read())
    urls = [element.text for element in xml.findall('{*}url/{*}loc')]
    assert 0 < len(urls) <= 10000
    assert all((url == origin or url.startswith(origin + '/')) and '?' not in url for url in urls)
    assert not any('/api/' in u or '/history' in u or '/workspace/' in u for u in urls)
    payload = {**config, 'keyLocation': key_url, 'urlList': urls}
    request = Request('https://api.indexnow.org/indexnow',
                      data=json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json; charset=utf-8'}, method='POST')
    with urlopen(request, timeout=30) as response:
        print(json.dumps({'endpoint': request.full_url, 'status': response.status,
                          'urlCount': len(urls), 'note': 'Receipt only; indexing is not guaranteed.'}))


if __name__ == '__main__':
    main()
