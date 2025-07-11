from typing import Optional, List

from botpy import logging
from botpy.message import GroupMessage

from app.config import get_db_session
from app.models.auth import BotUser
from app.models.wechat import WechatArticle
from app.schemas.auth import UserCreate
from app.schemas.wechat import Article, WechatMedia
from app.service.user_service import create_user
from app.service.wechat_service import query_articles
from app.utils.common import command_wrapper, generate_username
from app.utils.exceptions import BusinessException
from app.utils.security_utils import generate_invite_code
from app.utils.wechat_utils import get_article

logger = logging.get_logger()


async def handle_register(message: GroupMessage, invite_code: str, username: str, **kwargs):
    now_invite_code = generate_invite_code('NKG-TRANS')
    if invite_code != now_invite_code:
        return await message.reply(content='邀请码无效')
    form = UserCreate(username=username or generate_username(), openid=message.author.member_openid)
    try:
        async with get_db_session() as session:
            bot_user: BotUser = await create_user(session, form)
    except BusinessException as e:
        return await message.reply(content=f'注册失败: {e.message}')
    return await message.reply(content=f'注册成功，你的用户名为:{bot_user.username}')


# @command_wrapper(help='推文 客流月报(按关键词搜索推文) | 推文 list(查询近期推文)')
async def handle_query_wechat_article(message: GroupMessage, keyword: str, **kwargs):
    async with get_db_session() as session:
        articles: List[Article] = await query_articles(session, keyword)
    if articles:
        media: WechatMedia = WechatMedia(articles=[articles[0]], type='news')
        return await message.reply(media=media)
    else:
        return await message.reply(content='没有找到文章')


# TODO 自定义关键词
# @command_wrapper(help='添加推文 <推文URL> [关键词，使用"，"分割多个关键词](仅限有权限的用户) eg:添加推文 https://mp.weixin.qq.com/s/oX6wSEXPKARnkyb2r76RSA 6号线，试运行')
async def handle_add_auto_reply_wechat_article(message: GroupMessage, url: str, keyword: str = None, **kwargs):
    try:
        article: Article = await get_article(url)
    except Exception as e:
        logger.exception('解析微信文章失败', exc_info=e)
        return await message.reply(content='解析文章链接失败')
    article_model = WechatArticle(title=article.Title, description=article.Description,
                                  url=url, picurl=article.PicUrl, )
    async with get_db_session() as session:
        session.add(article_model)
        await session.commit()
    return await message.reply(content=f'添加成功，文章id:{article_model.id} 标题:{article_model.title}')
