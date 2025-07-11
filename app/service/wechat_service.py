from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, join, and_
from sqlalchemy.future import select

from app.models.wechat import WechatArticle
from app.schemas.wechat import Article


async def query_articles(db: AsyncSession, keyword: str) -> List[Article]:
    stmt = (
        select(WechatArticle)
        .where(WechatArticle.title.like(f'%{keyword}%'))
        .where(WechatArticle.is_active == True)
        .order_by(WechatArticle.create_time.desc())
    )

    result = await db.execute(stmt)
    article_model_list: List[WechatArticle] = list(result.scalars().all())
    articles = [Article.from_model(x) for x in article_model_list]
    return articles
