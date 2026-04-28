import logging
import os
from typing import AsyncGenerator, Optional

from dify_client import AsyncClient, models
from dify_client.models import ErrorStreamResponse
from dify_client.models.stream import (
    AgentMessageStreamResponse,
    AgentThoughtStreamResponse,
    MessageStreamResponse,
)
from pydantic import BaseModel

logger = logging.getLogger()


class DifyStreamEvent(BaseModel):
    event_type: str
    text: str = ""
    tool: str = ""
    tool_input: str = ""
    conversation_id: str = ""


def get_dify_client():
    api_key = os.getenv('DIFY_API_KEY')
    api_base = os.getenv('DIFY_API_BASE')
    return AsyncClient(api_key=api_key, api_base=api_base)


def _guess_file_type(mime_type: str) -> models.FileType:
    mt = mime_type.lower()
    if mt.startswith("image/"):
        return models.FileType.IMAGE
    if mt.startswith("audio/"):
        return models.FileType.AUDIO
    if mt.startswith("video/"):
        return models.FileType.VIDEO
    return models.FileType.DOCUMENT


async def _upload_files_to_dify(
        files: list[tuple[str, bytes, str]],
        user_id: Optional[str] = None,
) -> list[models.File]:
    """Upload files to Dify and return File references.

    `files` is a list of (filename, content_bytes, mime_type).
    """
    client = get_dify_client()
    result: list[models.File] = []
    for filename, content, mime_type in files:
        try:
            up_resp = await client.aupload_files(
                file=(filename, content, mime_type),
                req=models.UploadFileRequest(user=user_id or "default"),
            )
            result.append(
                models.File(
                    type=_guess_file_type(mime_type),
                    transfer_method=models.TransferMethod.LOCAL_FILE,
                    upload_file_id=up_resp.id,
                )
            )
        except Exception:
            logger.exception(f"Upload file to Dify failed: {filename}")
    return result


async def get_conversation_info(
        conversation_id: str,
        user_id: Optional[str] = None,
) -> Optional[dict]:
    """Fetch conversation metadata (including name/title) from Dify."""
    client = get_dify_client()
    base = str(client.api_base or "https://api.dify.ai/v1").rstrip("/")
    url = f"{base}/conversations?user={user_id or 'default'}&limit=100"
    try:
        resp = await client.arequest(url, "GET")
        data = resp.json()
        for conv in data.get("data", []):
            if conv.get("id") == conversation_id:
                return conv
    except Exception as e:
        logger.exception(f"Fetch Dify conversations failed: {e}")
    return None


async def get_conversation_messages(
        conversation_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[int] = None,
) -> list[dict]:
    """Fetch message history from Dify for a conversation.

    Dify returns one object per turn containing both `query` (user) and
    `answer` (assistant).  We expand each turn into two standard messages
    so the frontend can render the full history.
    """
    client = get_dify_client()
    base = str(client.api_base or "https://api.dify.ai/v1").rstrip("/")
    url = f"{base}/messages?user={user_id or 'default'}&conversation_id={conversation_id}"
    try:
        resp = await client.arequest(url, "GET")
        data = resp.json()
        raw_messages = data.get("data", [])
        # Dify returns newest first; reverse to chronological order
        raw_messages.sort(key=lambda x: x.get("created_at", 0))
        result: list[dict] = []
        for m in raw_messages:
            query = m.get("query") or m.get("content") or ""
            answer = m.get("answer") or ""
            msg_files = m.get("message_files", [])
            user_files: list[dict] = []
            assistant_files: list[dict] = []
            for f in msg_files:
                belongs = f.get("belongs_to", "user")
                upload_file_id = f.get("upload_file_id") or f.get("id")
                file_type = f.get("type", "document")
                file_name = f.get("filename") or f.get("name") or upload_file_id or ""
                preview_url = ""
                if session_id and upload_file_id:
                    preview_url = f"/api/chat/sessions/{session_id}/files/{upload_file_id}"
                file_obj = {
                    "id": upload_file_id,
                    "type": file_type,
                    "url": preview_url,
                    "name": file_name,
                }
                if belongs == "user":
                    user_files.append(file_obj)
                else:
                    assistant_files.append(file_obj)
            if query:
                result.append({"role": "user", "content": query, "files": user_files})
            if answer:
                result.append({"role": "assistant", "content": answer, "files": assistant_files})
        return result
    except Exception as e:
        logger.exception(f"Fetch Dify messages failed: {e}")
        return []


async def get_file_preview(file_id: str) -> tuple[bytes, str]:
    """Fetch a file preview from Dify and return (content, content_type)."""
    client = get_dify_client()
    base = str(client.api_base or "https://api.dify.ai/v1").rstrip("/")
    url = f"{base}/files/{file_id}/preview"
    resp = await client.arequest(url, "GET")
    content_type = resp.headers.get("content-type", "application/octet-stream")
    return resp.content, content_type


async def chat_stream(
        query: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        inputs: Optional[dict] = None,
        on_conversation_id: Optional[callable] = None,
        files: Optional[list[tuple[str, bytes, str]]] = None,
) -> AsyncGenerator[str, None]:
    client = get_dify_client()
    file_refs: list[models.File] = []
    if files:
        file_refs = await _upload_files_to_dify(files, user_id)
    req = models.ChatRequest(
        inputs=inputs or {},
        query=query,
        response_mode=models.ResponseMode.STREAMING,
        conversation_id=conversation_id,
        user=user_id or "default",
        files=file_refs,
    )
    try:
        resp = await client.achat_messages(req, timeout=90.)
        seen_cid: str | None = None
        async for chunk in resp:
            if hasattr(chunk, "conversation_id") and chunk.conversation_id:
                if on_conversation_id and chunk.conversation_id != seen_cid:
                    seen_cid = chunk.conversation_id
                    await on_conversation_id(chunk.conversation_id)
            if hasattr(chunk, "answer") and chunk.answer:
                yield chunk.answer
            elif isinstance(chunk, ErrorStreamResponse):
                err_msg = f"[Error {chunk.status}] {chunk.message}"
                logger.error(f"Dify stream error: {err_msg}")
                yield err_msg
    except Exception as e:
        logger.exception(f"Request dify chat stream error: {e}")
        yield f"[请求异常] {e}"


async def chat_stream_enhanced(
        query: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        inputs: Optional[dict] = None,
        files: Optional[list[tuple[str, bytes, str]]] = None,
) -> AsyncGenerator[DifyStreamEvent, None]:
    client = get_dify_client()
    file_refs: list[models.File] = []
    if files:
        file_refs = await _upload_files_to_dify(files, user_id)
    req = models.ChatRequest(
        inputs=inputs or {},
        query=query,
        response_mode=models.ResponseMode.STREAMING,
        conversation_id=conversation_id,
        user=user_id or "default",
        files=file_refs,
    )
    try:
        resp = await client.achat_messages(req, timeout=90.)
        seen_cid: str | None = None
        async for chunk in resp:
            cid = getattr(chunk, "conversation_id", None)
            if cid and cid != seen_cid:
                seen_cid = cid

            if isinstance(chunk, AgentThoughtStreamResponse):
                if chunk.tool:
                    yield DifyStreamEvent(
                        event_type="tool_call",
                        tool=chunk.tool,
                        tool_input=chunk.tool_input,
                        conversation_id=cid or "",
                    )
            elif isinstance(chunk, (AgentMessageStreamResponse, MessageStreamResponse)):
                if chunk.answer:
                    yield DifyStreamEvent(
                        event_type="text",
                        text=chunk.answer,
                        conversation_id=cid or "",
                    )
            elif isinstance(chunk, ErrorStreamResponse):
                yield DifyStreamEvent(
                    event_type="error",
                    text=f"[Error {chunk.status}] {chunk.message}",
                    conversation_id=cid or "",
                )
    except Exception as e:
        logger.exception(f"Request dify chat stream error: {e}")
        yield DifyStreamEvent(event_type="error", text=f"[请求异常] {e}")
