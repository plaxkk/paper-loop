"""Explicitly migrate the owner's published paper essays; never export data/ wholesale.

Requires beautifulsoup4==4.14.3 and markdownify==1.2.2 (see --help).
Builds consume committed Markdown and assets, not the private source directory.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'transformer': 'P1_attention_is_all_you_need.json',
    'bert': 'P2_BERT.json',
    'gpt-1': 'P3_GPT1_v1.json',  # The title matches the published record, unlike P3_GPT1.json.
    'gpt-2': 'P4_GPT2.json',
    'gpt-3': 'P5_GPT3.json',
    'scaling-laws': 'P6_ScalingLaws.json',
    'chinchilla': 'P7_Chinchilla.json',
    'flashattention': 'P8_FlashAttention.json',
    'flashattention-2': 'P9_FlashAttention2.json',
    'zero': 'P10_ZeRO.json',
    'instructgpt': 'P11_InstructGPT.json',
    'constitutional-ai': 'P12_ConstitutionalAI.json',
}


class Converter(MarkdownConverter):
    def convert_strong(self, el, text, parent_tags):
        # CommonMark can't close emphasis after punctuation followed by Chinese text.
        # Move punctuation outside the markers; preserve the actual article characters.
        prefix, suffix = '', ''
        while text and unicodedata.category(text[0]).startswith('P'):
            prefix, text = prefix + text[0], text[1:]
        while text and unicodedata.category(text[-1]).startswith('P'):
            text, suffix = text[:-1], text[-1] + suffix
        return prefix + ('**' + text + '**' if text else '') + suffix

    def convert_figure(self, el, text, parent_tags):
        return '\n\n' + text.strip() + '\n\n'

    def convert_figcaption(self, el, text, parent_tags):
        return '\n\n*' + text.strip() + '*\n\n' if text.strip() else ''


def metadata(slug):
    file = ROOT / 'site/content/classics' / (slug + '.md')
    if file.exists():
        return json.loads(file.read_text().split('---', 2)[1])
    return dict(slug=slug, englishTitle='FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning',
                date='2023-07-17', year=2023, stage=4, topic='训练效率', difficulty='进阶',
                source='https://arxiv.org/abs/2307.08691', arxiv='2307.08691',
                contribution='通过改进 GPU 线程块与 warp 的工作划分，提高精确注意力计算的效率。',
                problem='第一版 FlashAttention 减少了显存访问，但仍有并行度和线程间通信开销。',
                glossary=[{'term':'warp','definition':'GPU 中一起调度、执行指令的一组线程。'},
                          {'term':'工作划分','definition':'把计算分配到线程块与 warp，平衡并行度和通信开销。'}])


def published_titles():
    result = {}
    # Use one coherent latest scan; earlier captures can contain stale dates/titles.
    for file in sorted((ROOT / 'data/mp_raw').glob('*published_records.json'))[-1:]:
        value = json.loads(file.read_text())
        for response in value.get('api_responses', []):
            body = response.get('body')
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except ValueError:
                    continue
            if not isinstance(body, dict):
                continue
            for item in body.get('article_list', []):
                if item.get('title') and re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(item.get('publish_date', ''))):
                    result.setdefault(item['title'], set()).add(item['publish_date'])
    return result


def download(item):
    url, path = item
    if not path.exists():
        req = Request(url.replace('http://', 'https://', 1), headers={'User-Agent':'Mozilla/5.0'})
        with urlopen(req, timeout=40) as response:
            content = response.read(15 * 1024 * 1024)
        if not content.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8', b'GIF8', b'RIFF')):
            raise ValueError('The original article image could not be fetched: ' + path.name)
        path.write_bytes(content)
    return path


def migrate(fetch=False):
    published = published_titles()
    assets = ROOT / 'site/public/papers/archive'
    assets.mkdir(parents=True, exist_ok=True)
    manifest, pending, articles = [], [], []
    for slug, filename in FILES.items():
        source = ROOT / 'data/articles' / filename
        value = json.loads(source.read_text())
        if value['title'] not in published:
            raise ValueError('Missing publication evidence for ' + filename)
        soup = BeautifulSoup(value['content'], 'html.parser')
        # Replace platform-only navigation with the website's chronological navigation.
        for node in list(soup.select('div')):
            if 'justify-content: space-between' in node.get('style', ''):
                node.decompose()
        for node in list(soup.find_all('p')):
            text = node.get_text(' ', strip=True)
            if '在公众号内回复' in text or text.startswith('论文链接：'):
                node.decompose()
        for node in soup.find_all(re.compile('^h[1-6]$')):
            node.string = node.get_text('', strip=True)
        headings = soup.find_all(re.compile('^h[1-6]$'))
        if headings:
            # WeChat's visual chapter headings are sometimes h3; expose them to the TOC.
            offset = min(int(node.name[1]) for node in headings) - 2
            for node in headings:
                node.name = 'h' + str(min(6, max(2, int(node.name[1]) - offset)))
        images = []
        for index, node in enumerate(soup.find_all('img'), 1):
            url = node.get('src', '')
            if not re.match(r'^https?://(?:mmbiz\.qpic\.cn|mmbiz\.qlogo\.cn)/', url):
                raise ValueError('Unexpected image host in ' + filename)
            path = assets / f'{slug}-{index:02d}.png'
            pending.append((url, path))
            caption = node.parent.find('figcaption')
            alt = node.get('alt') or (caption.get_text(' ', strip=True) if caption else value['title'] + ' 配图')
            node.attrs = {'src': '/papers/archive/' + path.name, 'alt': alt}
            images.append('/papers/archive/' + path.name)
        # Other attributes and all HTML are discarded by Markdown conversion.
        text = Converter(heading_style='ATX', bullets='-', escape_underscores=False).convert(str(soup))
        text = re.sub(r'\n{3,}', '\n\n', text).strip() + '\n'
        if '<img' in text or 'mmbiz.' in text or '公众号内回复' in text:
            raise ValueError('Unconverted article markup: ' + filename)
        data = metadata(slug)
        data.update(title=value['title'], minutes=max(5, math.ceil(len(soup.get_text('',strip=True))/450)),
                    status='archived', publication={'channel':'微信公众号', 'dates':sorted(published[value['title']])})
        articles.append((ROOT / 'site/content/classics' / (slug + '.md'), '---\n' + json.dumps(data,ensure_ascii=False,indent=2) + '\n---\n\n' + text))
        manifest.append({'slug':slug,'sourceFile':'data/articles/'+filename,'title':value['title'],
                         'publicationDates':sorted(published[value['title']]),
                         'sourceContentSha256':hashlib.sha256(value['content'].encode()).hexdigest(),
                         'bodyCharacters':len(soup.get_text('',strip=True)), 'images':images})
    if fetch:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(download, pending))
    missing = [str(path.relative_to(ROOT)) for _,path in pending if not path.exists()]
    if missing:
        raise ValueError('Missing local assets; run with --fetch-images: ' + ', '.join(missing))
    for path, text in articles:
        path.write_text(text)
    (ROOT/'site/content/published-archive.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(f'Migrated {len(articles)} published essays and {len(pending)} original images.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch-images',action='store_true',help='Download the public original article images once; no WeChat credentials are used.')
    migrate(parser.parse_args().fetch_images)
