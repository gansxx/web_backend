from fastapi import APIRouter, HTTPException, Request, Response, Cookie, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr
from loguru import logger
from typing import Literal, Optional
import os

router = APIRouter(tags=["support"])

# Load admin emails from environment variable
ADMIN_EMAILS = set(email.strip() for email in os.getenv('ADMIN_EMAILS', '').split(',') if email.strip())


# # 优先级映射：前端 → 数据库
# PRIORITY_MAP = {
#     "low": "低",
#     "normal": "中",
#     "high": "高",
#     "urgent": "高"  # urgent 也映射为高
# }

# 优先级映射：数据库 → 前端
# PRIORITY_MAP_REVERSE = {
#     "低": "low",
#     "中": "normal",
#     "高": "high"
# }

# # 状态映射：数据库 → 前端
# STATUS_MAP = {
#     "处理中": "open",
#     "已解决": "resolved"
# }


class TicketRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200, description="工单标题")
    priority: Literal["低", "中", "高"] = Field(..., description="工单优先级")
    category: str = Field(..., min_length=1, max_length=100, description="工单类别")
    description: str = Field(..., min_length=1, max_length=2000, description="工单描述")


class TicketResponse(BaseModel):
    success: bool
    ticket_id: str
    message: str


class TicketReplyRequest(BaseModel):
    status: Literal["处理中", "已解决"] = Field(..., description="工单状态")
    reply: str = Field(..., min_length=1, max_length=5000, description="管理员答复内容")
    send_email: bool = Field(default=True, description="是否发送邮件通知用户")
    admin_email: EmailStr = Field(..., description="管理员邮箱")


def _get_user_email_from_token(
    request: Request,
    response: Response,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None
) -> str:
    """
    从 Cookie 或 token 中获取用户邮箱
    处理 token 过期自动刷新逻辑
    """
    supabase = getattr(request.app.state, "supabase", None)
    do_refresh = getattr(request.app.state, "refresh_session_and_set_cookies", None)

    if not supabase:
        raise HTTPException(500, detail="Supabase 未初始化")

    token_to_use = access_token
    if not token_to_use:
        raise HTTPException(401, detail="未登录，请先登录")

    try:
        try:
            _res = supabase.auth.get_user(token_to_use)
        except Exception as e:
            msg = str(e).lower()
            # 如果 token 过期且有 refresh_token，尝试刷新
            if refresh_token and ("expired" in msg or "invalid" in msg) and callable(do_refresh):
                logger.info("access_token 失效，尝试 refresh_token 刷新")
                new_at = do_refresh(response, refresh_token)
                if not new_at:
                    raise HTTPException(401, detail="登录已过期，请重新登录")
                _res = supabase.auth.get_user(new_at)
            else:
                raise

        user = getattr(_res, "user", None)
        if not user or not getattr(user, "email", None):
            raise HTTPException(401, detail="未登录或用户无邮箱信息")

        email = user.email
        if not isinstance(email, str) or not email:
            raise HTTPException(401, detail="用户邮箱信息无效")

        return email
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        raise HTTPException(401, detail="身份验证失败")


@router.post("/support/submit_ticket", response_model=TicketResponse)
async def submit_ticket(
    request: Request,
    response: Response,
    ticket_request: TicketRequest,
    access_token: Optional[str] = Cookie(default=None),
    refresh_token: Optional[str] = Cookie(default=None)
):
    """
    创建新的支持工单

    前端调用: POST /support/submit_ticket
    需要用户登录（通过 Cookie 验证）
    """
    ticket_db = getattr(request.app.state, "ticket_db", None)
    if not ticket_db:
        raise HTTPException(500, detail="工单系统未初始化")

    try:
        # 获取用户邮箱（包含自动 token 刷新）
        user_email = _get_user_email_from_token(request, response, access_token, refresh_token)

        # 转换优先级
        # db_priority = PRIORITY_MAP.get(ticket_request.priority, "中")

        # 准备元数据
        metadata = {
            "user_agent": request.headers.get("user-agent"),
            "ip_address": request.client.host if request.client else "unknown",
            "source": "web_frontend"
        }

        # 插入工单到数据库
        ticket_id = ticket_db.insert_ticket(
            user_email=user_email,
            subject=ticket_request.subject,
            priority=ticket_request.priority,
            category=ticket_request.category,
            description=ticket_request.description,
            metadata=metadata
        )
        logger.debug(f"插入工单为: {ticket_request}")

        logger.info(f"新工单创建成功: {ticket_id}, 用户: {user_email}")

        return TicketResponse(
            success=True,
            ticket_id=str(ticket_id),
            message=f"工单创建成功，工单号: {ticket_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建工单时发生错误: {e}")
        raise HTTPException(
            status_code=500,
            detail="创建工单失败，请稍后重试"
        )


@router.get("/support/tickets")
async def get_user_tickets(
    request: Request,
    response: Response,
    access_token: Optional[str] = Cookie(default=None),
    refresh_token: Optional[str] = Cookie(default=None)
):
    """
    获取当前用户的所有工单

    前端调用: GET /support/tickets
    需要用户登录（通过 Cookie 验证）
    返回格式: [{id, subject, priority, category, status, created_at}, ...]
    """
    ticket_db = getattr(request.app.state, "ticket_db", None)
    if not ticket_db:
        raise HTTPException(500, detail="工单系统未初始化")

    try:
        # 获取用户邮箱（包含自动 token 刷新）
        user_email = _get_user_email_from_token(request, response, access_token, refresh_token)

        # 查询用户工单
        tickets = ticket_db.fetch_user_tickets(user_email=user_email)

        # 转换为前端格式
        result = []
        # logger.debug(f"查询到的工单数据: {tickets}")
        for ticket in tickets:
            result.append({
                "id": str(ticket.get("id", "")),
                "subject": ticket.get("subject", ""),
                "priority": ticket.get("priority", "中"),
                "category": ticket.get("category", ""),
                "status": ticket.get("status", "处理中"),
                "created_at": ticket.get("created_at", ""),
                "reply": ticket.get("reply"),
                "replied_at": ticket.get("replied_at")
            })

        logger.info(f"查询用户工单成功: {user_email}, 数量: {len(result)}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工单列表失败: {e}")
        raise HTTPException(500, detail="获取工单列表失败")


@router.get("/support/tickets/{ticket_id}")
async def get_ticket_detail(
    ticket_id: str,
    request: Request,
    response: Response,
    access_token: Optional[str] = Cookie(default=None),
    refresh_token: Optional[str] = Cookie(default=None)
):
    """
    获取工单详细信息

    需要用户登录，且只能查看自己的工单
    """
    ticket_db = getattr(request.app.state, "ticket_db", None)
    if not ticket_db:
        raise HTTPException(500, detail="工单系统未初始化")

    try:
        # 获取用户邮箱
        user_email = _get_user_email_from_token(request, response, access_token, refresh_token)

        # 查询工单
        ticket = ticket_db.get_ticket_by_id(ticket_id)
        if not ticket:
            raise HTTPException(404, detail="工单不存在")

        # 验证工单所有权
        if ticket.get("user_email") != user_email:
            raise HTTPException(403, detail="无权访问此工单")

        return ticket

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工单详情失败: {e}")
        raise HTTPException(500, detail="获取工单详情失败")


@router.get("/support/admin/tickets")
async def get_all_tickets_admin(
    request: Request,
    admin_email: EmailStr = Query(..., description="管理员邮箱"),
    status: Optional[str] = Query(None, description="筛选状态"),
    priority: Optional[str] = Query(None, description="筛选优先级"),
    limit: int = Query(100, ge=1, le=500, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """
    获取所有工单（管理员功能）

    需要admin_email参数进行管理员身份验证
    支持按状态、优先级筛选，以及分页
    """
    ticket_db = getattr(request.app.state, "ticket_db", None)
    if not ticket_db:
        raise HTTPException(500, detail="工单系统未初始化")

    try:
        # 验证管理员邮箱
        if admin_email not in ADMIN_EMAILS:
            logger.warning(f"非管理员邮箱尝试访问所有工单: {admin_email}")
            raise HTTPException(403, detail="无管理员权限")

        # 查询所有工单
        tickets = ticket_db.fetch_all_tickets(
            status=status,
            priority=priority,
            limit=limit,
            offset=offset
        )

        logger.info(f"管理员 {admin_email} 查询所有工单: 数量={len(tickets)}, status={status}, priority={priority}")
        return tickets

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取所有工单失败: {e}")
        raise HTTPException(500, detail="获取所有工单失败")


@router.patch("/support/tickets/{ticket_id}/reply")
async def reply_to_ticket(
    ticket_id: str,
    reply_request: TicketReplyRequest,
    request: Request
):
    """
    管理员答复工单（需要管理员权限）

    前端调用: PATCH /support/tickets/{ticket_id}/reply
    Body参数中需包含admin_email字段进行管理员身份验证
    """
    ticket_db = getattr(request.app.state, "ticket_db", None)
    if not ticket_db:
        raise HTTPException(500, detail="工单系统未初始化")

    try:
        # 验证管理员邮箱是否在白名单中
        if reply_request.admin_email not in ADMIN_EMAILS:
            logger.warning(f"非管理员邮箱尝试答复工单: {reply_request.admin_email}")
            raise HTTPException(403, detail="无管理员权限")

        logger.info(f"管理员 {reply_request.admin_email} 正在答复工单: {ticket_id}")

        # 先获取工单详情（用于发送邮件）
        ticket = ticket_db.get_ticket_by_id(ticket_id)
        if not ticket:
            raise HTTPException(404, detail="工单不存在")

        # 更新工单状态和答复
        success = ticket_db.update_ticket_status(
            ticket_id=ticket_id,
            status=reply_request.status,
            reply=reply_request.reply
        )

        if not success:
            raise HTTPException(500, detail="更新工单失败")

        # 发送邮件通知用户
        email_sent = False
        if reply_request.send_email:
            try:
                email_sent = ticket_db.send_ticket_reply_email(
                    user_email=ticket.get("user_email"),
                    ticket_subject=ticket.get("subject"),
                    reply_content=reply_request.reply,
                    ticket_id=ticket_id
                )
                if email_sent:
                    logger.info(f"工单答复邮件已发送到: {ticket.get('user_email')}")
                else:
                    logger.warning(f"工单答复邮件发送失败: {ticket.get('user_email')}")
            except Exception as e:
                logger.error(f"发送邮件时出错: {e}")

        return {
            "success": True,
            "message": "工单答复成功",
            "ticket_id": ticket_id,
            "email_sent": email_sent
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"答复工单失败: {e}")
        raise HTTPException(500, detail="答复工单失败")