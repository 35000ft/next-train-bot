import asyncio
import urllib.parse
from abc import abstractmethod
from datetime import datetime
from typing import Optional
from lxml import etree
import httpx
from pydantic import BaseModel

_headers = {
    'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0"
}


class APOD(BaseModel):
    date: datetime
    title: str
    img_author: str
    img_url: str
    description: str
    translator: Optional[str] = None
    src: str

    def to_bot_reply(self):
        content = f"""APOD ({self.date.strftime("%Y-%m-%d")}):\n{self.title}:\n{self.description}\n"""
        if self.translator:
            content += "翻译:" + self.translator + "\n"

        content += f"图片来源及版权:{self.img_author}\n"
        content += f"来源:{self.src}\n"
        return content


class APODFetcher(BaseModel):
    src: str

    @abstractmethod
    async def fetch_latest(self) -> Optional[APOD]:
        pass

    @abstractmethod
    async def fetch_date(self, _date: datetime) -> Optional[APOD]:
        pass


class BjpApodFetcher(APODFetcher):
    src: str = '北京天文馆镜像'
    base_url: str = 'https://www.bjp.org.cn'

    def parse_page(self, html: str) -> Optional[APOD]:
        tree = etree.HTML(html)
        # 1. 提取日期：位于 <td height="40"> 内的文本
        date_str = tree.xpath('//td[@height="40" and contains(text(),"-")]/text()')
        if not date_str:
            raise ValueError("提取APOD失败，没有找到日期")
        _date = datetime.strptime(date_str[0], "%Y-%m-%d")

        # 2. 提取标题：在 .juzhong 内 <section> 中，第一个 <strong> 的文本
        title_list = tree.xpath('//div[@class="juzhong"]//p/strong/text()')
        title = title_list[0].strip() if title_list else ''

        # 3. 提取图片作者：第二个 <strong> 标签，去掉前缀“图片来源及版权：”
        if len(title_list) > 1:
            img_author = title_list[1].replace("图片来源及版权：", "").strip()
        else:
            img_author = ''

        # 4. 提取图片 URL：在 .juzhong 内 <img> 的 src 属性
        img_url_list = tree.xpath('//div[@class="juzhong"]//img/@src')
        img_url = img_url_list[0].strip() if img_url_list else None
        if not img_url:
            raise ValueError("提取APOD失败，没有找到图片url")
        img_url = urllib.parse.urljoin(self.base_url, img_url)

        # 5. 提取说明文字：包含“说明：”的 <p> 标签
        desc_list = tree.xpath('//div[@class="juzhong"]//p[contains(text(),"说明：")]/text()')
        description = desc_list[0].replace("说明：", "").strip() if desc_list else ''

        # 6. 提取翻译者：查找以“翻译：”开头的 <p>
        translator_list = tree.xpath('//p[starts-with(normalize-space(text()),"翻译：")]/text()')
        translator = translator_list[0].replace("翻译：", "").strip() if translator_list else "北京天文馆"

        apod_data = {
            "date": _date,
            "title": title,
            "img_author": img_author,
            "img_url": img_url,
            "description": description,
            "translator": translator,
            "src": self.src
        }
        return APOD(**apod_data)

    async def fetch_latest(self) -> Optional[APOD]:
        _url = 'https://www.bjp.org.cn/APOD/today.shtml'
        async with httpx.AsyncClient() as client:
            resp = await client.get(url=_url, headers=_headers)
            resp.raise_for_status()
            return self.parse_page(resp.text)

    async def fetch_date(self, _date: datetime) -> Optional[APOD]:
        list_url = 'https://www.bjp.org.cn/APOD/list.shtml'

        def find_in_page(_tree):
            a_nodes = _tree.xpath(
                f"//td//span[contains(text(),'{_date.strftime('%Y-%m-%d')}')]/following-sibling::*[1]/@href")
            if not a_nodes:
                return None
            return urllib.parse.urljoin(self.base_url, a_nodes[0])

        async with httpx.AsyncClient() as client:
            resp = await client.get(url=list_url, headers=_headers)
            resp.raise_for_status()
            tree = etree.HTML(resp.text)

            target_url = find_in_page(tree)
            if target_url:
                r2 = await client.get(target_url, headers=_headers)
                return self.parse_page(r2.text)

            total_page_str = tree.xpath("//ul[@class='pagination']/div[contains(text(),'共')]/text()")
            if not total_page_str:
                raise ValueError("找不到总页数")
            total_page = int(total_page_str[0].replace("共", "").replace("页", "").strip())
            # 目标日期
            target_date = _date

            # 二分查找：日期是倒序排列的，获取每一页最后一个日期作为参考
            lo = 1
            hi = total_page
            while lo <= hi:
                mid = (lo + hi) // 2
                # 构造分页URL，第一页特殊处理，其余页格式为 /APOD/list_{mid}.shtml
                if mid == 1:
                    page_url = list_url
                else:
                    page_url = urllib.parse.urljoin(self.base_url, f"/APOD/list_{mid}.shtml")

                resp_mid = await client.get(page_url, headers=_headers)
                resp_mid.raise_for_status()
                tree_mid = etree.HTML(resp_mid.text)

                # 尝试查找目标链接
                target_url = find_in_page(tree_mid)
                if target_url:
                    r2 = await client.get(target_url, headers=_headers)
                    return self.parse_page(r2.text)

                # 获取当前页面中最后一个日期节点，其 XPath 为 //td//b/span[last()]
                date_nodes = tree_mid.xpath("//td//b/span")
                if not date_nodes:
                    raise ValueError("找不到日期节点")
                last_date_str = date_nodes[-1].text
                # 去掉末尾的冒号，如 "2024-06-01:" 变成 "2024-06-01"
                last_date_str = last_date_str.strip(": ：").strip()
                try:
                    page_date = datetime.strptime(last_date_str, '%Y-%m-%d')
                except Exception as e:
                    raise ValueError(f"日期格式错误: {last_date_str}") from e

                # 因为日期是倒序排列：第一页最新、最后一页最旧
                # 如果目标日期比当前页最早的日期更近（更大），说明目标应该在更前面（页码更小）的页面
                if target_date > page_date:
                    hi = mid - 1
                # 如果目标日期比当前页最早的日期还旧，则目标可能在后续页面中
                elif target_date < page_date:
                    lo = mid + 1
                else:
                    # 理论上应能找到链接，但万一没有，则直接退出循环
                    return None
            return None


class NasaApodFetcher(APODFetcher):
    src: str = 'NASA'
    base_url: str = 'https://apod.nasa.gov'

    def parse_page(self, html: str) -> Optional[APOD]:
        tree = etree.HTML(html)

        # 1. 提取日期
        date_str = tree.xpath('//center[1]/p[2]/text()')
        if not date_str:
            raise ValueError("提取APOD失败，没有找到日期")
        _date = datetime.strptime(date_str[0].strip(), "%Y %B %d")

        # 2. 提取标题
        title_list = tree.xpath('//center[2]/b[1]/text()')
        title = title_list[0].strip() if title_list else ''

        # 3. 提取图片作者
        img_author_list = tree.xpath('//center/b[contains(text(), "Credit")]/following-sibling::a/text()')
        img_author = ', '.join(img_author_list).strip() if img_author_list else ''

        # 4. 提取图片URL
        img_url_list = tree.xpath('//center//a/img/@src')
        img_url = img_url_list[0].strip() if img_url_list else None
        base_url = "https://apod.nasa.gov/apod/"
        img_url = urllib.parse.urljoin(base_url, img_url)

        # 5. 提取说明文字
        desc_list = tree.xpath('//b[contains(text(), "Explanation")]/..//text()')
        desc_list = [x.strip().replace("\n", "") for x in desc_list if len(x.strip()) > 0]
        description = ' '.join(desc_list).strip() if desc_list else ''

        apod_data = {
            "date": _date,
            "title": title,
            "img_author": img_author,
            "img_url": img_url,
            "description": description,
            "translator": None,
            "src": self.src
        }
        return APOD(**apod_data)

    async def fetch_latest(self) -> Optional[APOD]:
        _url = 'https://apod.nasa.gov/apod/astropix.html'
        async with httpx.AsyncClient() as client:
            resp = await client.get(url=_url, headers=_headers)
            resp.raise_for_status()
            return self.parse_page(resp.text)

    async def fetch_date(self, _date: datetime) -> Optional[APOD]:
        _url = f'https://apod.nasa.gov/apod/ap{_date.strftime("%y%m%d")}.html'
        async with httpx.AsyncClient() as client:
            resp = await client.get(url=_url, headers=_headers)
            resp.raise_for_status()
            return self.parse_page(resp.text)
