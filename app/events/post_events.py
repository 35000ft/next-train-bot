import os
import uuid

from async_lru import alru_cache
from botpy import logging
from botpy.message import GroupMessage, C2CMessage
from sqlalchemy import select, func

from app.config import get_db_session
from app.models.Common import RobotConfig
from app.models.Post import Post
from app.service.file_service import download_and_save_image, get_local_image
from app.utils.message_utils import post_group_base64_file

logger = logging.get_logger()


@alru_cache(maxsize=16, ttl=300)
async def parse_to_accepted_type_code(post_type: str) -> str | None:
    async with get_db_session() as session:
        stmt = select(RobotConfig).where(
            RobotConfig.params == post_type,
            RobotConfig.status == 1,
            RobotConfig.parent_uni_key == 'accept_post_type'
        )
        result = await session.execute(stmt)
        config = result.scalars().first()
        # Return a desired field (e.g., uni_key) if record exists, else None
        return config.uni_key if config else None


async def handle_post(message: GroupMessage | C2CMessage, post_type: str, name: str, **kwargs):
    if os.getenv('ENV') != 'prod':
        await message.reply(content='目前运行在开发环境，不能投稿帖子哦')
        return
    post_type_code = await parse_to_accepted_type_code(post_type)
    if not post_type_code:
        await message.reply(content=f'不支持的投稿类型:{post_type}')
        return
    logger.info(f'post_type_code:{post_type_code} attachments:{message.attachments}')
    if not message.attachments:
        await message.reply(content='请附上图片')
        return

    img_url = message.attachments[0].url
    user_id = message.author.member_openid
    # todo nickname 狗腾讯不返回昵称
    user_name = kwargs.get('n') or message.author.member_openid[-6:]
    post_id = str(uuid.uuid4())
    p = Post(user_name=user_name, user_id=user_id, post_id=post_id, post_type=post_type_code, name=name, status=1)
    try:
        p.file_path = await download_and_save_image(img_url, file_name=post_id, sub_folder='posts')
        async with get_db_session() as session:
            session.add(p)
            await session.commit()
    except Exception as e:
        logger.error(f'投稿失败 name:{name} err:{e}')
        await message.reply(content=f'投稿失败，帖子标题:{name}')
        return
    await message.reply(content=f'投稿成功，使用"/帖子 {p.post_id}"指令查看')
    # img_url = kwargs.get('i')
    # if img_url:
    #     if not is_http_url(img_url):
    #         await message.reply(content='图片url无效，请提供合法的http/https url')
    #         return
    #     try:
    #         async with httpx.AsyncClient() as client:
    #             # todo 接受图片类型
    #             resp = await client.get(url=img_url)
    #             # 检查返回是否为图片
    #     except Exception as e:
    #         # todo
    #         await message.reply()
    #         return


async def handle_get_post(message: GroupMessage | C2CMessage, post_type: str, **kwargs):
    post_type_code = await parse_to_accepted_type_code(post_type)
    if not post_type_code:
        await message.reply(content=f'不支持的topic:{post_type}')
        return

    async with get_db_session() as session:
        stmt = select(Post).where(Post.post_type == post_type_code,
                                  Post.status == 1,
                                  Post.file_path.is_not(None)) \
            .order_by(func.random()).limit(1)
        result = await session.execute(stmt)
        result: Post = result.scalars().first()
    if not result:
        await message.reply(content='这个topic下暂时没有投稿呢')
        return

    base64_data = await get_local_image(result.file_path)
    if not base64_data:
        await message.reply(content='帖子图片已失效')
        return

    upload_media = await post_group_base64_file(
        _message=message,
        file_data=base64_data,
        group_openid=message.group_openid,
        file_type=1,  # 文件类型要对应上，具体支持的类型见方法说明
    )
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=7,
        msg_id=message.id,
        media=upload_media,
        msg_seq=2,
    )
