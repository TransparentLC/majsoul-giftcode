import asyncio
import bilibili_api
import cv2
import httpx
import itertools
import re
import rfeed
import os
import orjson
import subprocess
import tempfile
import typing
from datetime import datetime, UTC

class GiftCode(typing.TypedDict):
    code: str
    time: datetime
    items: tuple[str, ...]
    source: str

# https://game.maj-soul.com/1/v0.11.86.w/res/atlas/myres/bothui.png
# https://game.maj-soul.com/1/v0.11.86.w/res/atlas/chs_t/myres/bothui.png
titleImageCHS = os.path.join('image', 'title-chs.png')
titleImageCHT =  os.path.join('image', 'title-cht.png')

itemImages = {
    k: os.path.join('image', v)
    for k, v in {
        '喵趣券': 'coffeeticket_0.png',
        '月光福袋': 'fudai_moon_0.jpg',
        '日光福袋': 'fudai_sun_1.jpg',
        '旅人福袋': 'fudai_lvren_0.jpg',
        '贵人福袋': 'fudai_guiren_0.jpg',
        '贤人福袋': 'fudai_xianren_0.jpg',
        '光明宝玉': 'jade_bright_0.jpg',
        '勇气宝玉': 'jade_courage_0.jpg',
        '诚实宝玉': 'jade_honest_0.jpg',
        '希望宝玉': 'jade_hope_0.jpg',
        '智慧宝玉': 'jade_knowledge_0.jpg',
        '纯真宝玉': 'jade_pure_0.jpg',
        '慈爱宝玉': 'jade_tender_0.jpg',
        '意志宝玉': 'jade_will_0.jpg',
        '香喷喷曲奇': 'biscuit2_2.jpg',
        '次世代游戏机': 'console2_2.jpg',
        '经典名画': 'art2_0.jpg',
        '82 年的拉菲': 'wine2_2.jpg',
        '海洋之心': 'diamond2_2.jpg',
        '熊公仔 XXL': 'toy2_4.jpg',
        '精美同人志': 'book2_2.jpg',
        '华丽的小裙子': 'dress2_0.jpg',
    }.items()
}

sift = cv2.SIFT_create()
flann = cv2.FlannBasedMatcher({'algorithm': 1, 'trees': 5}, {'checks': 50})
descriptorsPatternCache = {}
s = httpx.AsyncClient(
    http2=True,
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
        'Referer': 'https://www.bilibili.com/',
    },
)

def imageMatch(image: str, pattern: str, minMatchCount: int = 8) -> bool:
    _, descriptorsImage = sift.detectAndCompute(cv2.imread(image), None)
    if pattern not in descriptorsPatternCache:
        _, descriptors = sift.detectAndCompute(cv2.imread(pattern), None)
        descriptorsPatternCache[pattern] = descriptors
    descriptorsPattern = descriptorsPatternCache[pattern]

    matches = flann.knnMatch(descriptorsPattern, descriptorsImage, 2)
    good = tuple(m for m, n in matches if m.distance < n.distance * .7)
    return len(good) > minMatchCount

async def getItemFromAVID(avid: int) -> tuple[str, ...]:
    try:
        r = await s.get('https://api.injahow.cn/bparse/', params={
            'av': avid,
            'p': 1,
            'q': 80,
            'format': 'mp4',
            'otype': 'url',
        })
        videoUrl = r.text

        with (
            tempfile.NamedTemporaryFile('wb', delete=False) as video,
            tempfile.TemporaryDirectory() as frameDir,
        ):
            async with s.stream('GET', videoUrl) as r:
                async for d in r.aiter_bytes():
                    video.write(d)
            video.close()

            subprocess.check_output((
                'ffmpeg',
                '-i', video.name,
                '-vf' , 'crop=w=min(iw*2/3\\,ih*2/3):h=min(iw*2/3\\,ih*2/3)',
                '-r', '3',
                '-c:v', 'libwebp',
                '-quality', '90',
                os.path.join(frameDir, '%04d.webp'),
            ))

            os.remove(video.name)

            frames = sorted(os.path.join(frameDir, x) for x in os.listdir(frameDir))
            if len(frames) > 270:
                return tuple()

            firstFrameIndexWithTitle: int = None
            lastFrameIndexWithTitle: int = None
            items = []

            for index, frame in enumerate(frames):
                print(frame)
                if imageMatch(frame, titleImageCHS) or imageMatch(frame, titleImageCHT):
                    firstFrameIndexWithTitle = index
                    break

            if firstFrameIndexWithTitle is None:
                return tuple()

            for index, frame in enumerate(frames[::-1]):
                print(frame)
                if imageMatch(frame, titleImageCHS) or imageMatch(frame, titleImageCHT):
                    lastFrameIndexWithTitle = len(frames) - 1 - index
                    break

            if firstFrameIndexWithTitle is not None and lastFrameIndexWithTitle is not None:
                frame = frames[(firstFrameIndexWithTitle + lastFrameIndexWithTitle) // 2]
                print(frame)
                for k, v in itemImages.items():
                    if imageMatch(frame, v):
                        items.append(k)

        return tuple(items)
    except Exception as ex:
        return (f'{type(ex).__name__}: {ex}',)

async def main():
    result: list[GiftCode] = []
    if os.path.exists('giftcode.json'):
        with open('giftcode.json', 'rb') as f:
            result.extend(orjson.loads(f.read()))
    for r in result:
        if isinstance(r['time'], str):
            r['time'] = datetime.fromisoformat(r['time'] )
    codes = set(r['code'] for r in result)

    for keyword, page in itertools.product(
        (
            '雀魂礼包码',
            # '雀魂礼品码',
        ),
        range(1, 11),
    ):
        d = await bilibili_api.search.search_by_type(
            keyword=keyword,
            search_type=bilibili_api.search.SearchObjectType.VIDEO,
            order_type=bilibili_api.search.OrderVideo.PUBDATE,
            page=page,
        )

        if 'numPages' not in d:
            print('No numPages, what the fuck?')
            print(d)
            continue

        if page > d['numPages']:
            break

        for e in d['result']:
            if e['type'] != 'video':
                continue
            title = re.sub(r'<em class="keyword">(.*?)</em>', lambda m: m[1], e['title'])
            if '雀魂' not in title:
                continue
            # print(title)
            pubtime = datetime.fromtimestamp(e['pubdate'], UTC)
            avid = int(e['id'])
            if m := re.search(r'([\dA-Z]{8,})', title):
                code = m.group(1)
                if not code.isdigit() and not code.isalpha() and code not in codes:
                    codes.add(code)
                    print(avid, code)
                    items = await getItemFromAVID(avid)
                    print(items)
                    result.append(GiftCode(
                        code=code,
                        time=pubtime,
                        items=items,
                        source=f'https://www.bilibili.com/video/av{avid}',
                    ))

    result.sort(key=lambda e: e['time'], reverse=True)

    with open('giftcode.json', 'wb') as f:
        f.write(orjson.dumps(result, option=orjson.OPT_INDENT_2 | orjson.OPT_UTC_Z))

    with open('giftcode.xml', 'w', encoding='utf-8') as f:
        f.write(rfeed.Feed(
            title='雀魂礼品码',
            link='https://i.akarin.dev/majsoul-giftcode.xml',
            description=(
                '雀魂礼品码相关情报 by ✨小透明・宸✨<br>'
                '数据出处：屑站搜索“雀魂礼品码”的视频标题<br>'
                'JSON 格式数据：https://i.akarin.dev/majsoul-giftcode.json<br>'
                '爬取用源代码：https://github.com/TransparentLC/majsoul-giftcode'
            ),
            lastBuildDate=datetime.now(UTC),
            items=tuple(
                rfeed.Item(
                    title=f'[雀魂礼品码 {e['time'].strftime('%Y-%m-%d')}] {e['code']}',
                    author='✨小透明・宸✨',
                    link=e['source'],
                    description=(
                        f'<p>礼品码：<code>{e['code']}</code></p>'
                        f'<p>奖励内容：{'、'.join(e['items']) if e['items'] else '<em>识别失败了…… (&lt;_&gt;｡)</em>'}</p>'
                        f'<hr>'
                        f'<p>礼品码一般会在<strong>第二天中午十二点</strong>失效，请及时领取～</p>'
                        f'<p>上面的奖励内容来自对<a href="{e['source']}">相关录像</a>的图像识别，可能存在错误，请以实际为准。</p>'
                    ),
                    guid=rfeed.Guid(f'majsoul-giftcode-{e['code']}'),
                    pubDate=e['time'],
                )
                for e in result
            ),
        ).rss())

if __name__ == '__main__':
    asyncio.run(main())
