from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from loguru import logger
import os
import json
import uuid
from datetime import datetime
from typing import Literal

router = APIRouter(tags=["support"])


class TicketRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200, description="工单标题")
    priority: Literal["low", "normal", "high", "urgent"] = Field(..., description="工单优先级")
    category: str = Field(..., min_length=1, max_length=100, description="工单类别")
    description: str = Field(..., min_length=1, max_length=2000, description="工单描述")


class TicketResponse(BaseModel):
    success: bool
    ticket_id: str
    message: str


def _ensure_tickets_directory():
    """确保tickets目录存在"""
    tickets_dir = "tickets"
    if not os.path.exists(tickets_dir):
        os.makedirs(tickets_dir)
        logger.info(f"创建工单存储目录: {tickets_dir}")
    return tickets_dir


def _generate_ticket_id() -> str:
    """生成唯一的工单ID"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"TK_{timestamp}_{unique_id}"


def _save_ticket_to_file(ticket_data: dict, ticket_id: str) -> str:
    """保存工单到本地文件"""
    tickets_dir = _ensure_tickets_directory()
    filename = f"ticket_{ticket_id}.json"
    filepath = os.path.join(tickets_dir, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(ticket_data, f, ensure_ascii=False, indent=2)
        logger.info(f"工单已保存到文件: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"保存工单文件失败: {e}")
        raise HTTPException(status_code=500, detail="保存工单失败")


@router.post("/support/tickets", response_model=TicketResponse)
async def create_ticket(request: Request, ticket_request: TicketRequest):
    """
    创建新的支持工单

    接收前端发送的工单信息，验证后保存到本地文件
    后期将集成数据库存储功能
    """
    try:
        # 生成工单ID
        ticket_id = _generate_ticket_id()

        # 准备工单数据
        ticket_data = {
            "ticket_id": ticket_id,
            "subject": ticket_request.subject,
            "priority": ticket_request.priority,
            "category": ticket_request.category,
            "description": ticket_request.description,
            "status": "new",
            "created_at": datetime.now().isoformat(),
            "metadata": {
                "user_agent": request.headers.get("user-agent"),
                "ip_address": request.client.host if request.client else "unknown",
                "source": "web_frontend"
            }
        }

        # 保存到本地文件
        filepath = _save_ticket_to_file(ticket_data, ticket_id)

        logger.info(f"新工单创建成功: {ticket_id}")

        return TicketResponse(
            success=True,
            ticket_id=ticket_id,
            message=f"工单创建成功，工单号: {ticket_id}"
        )

    except HTTPException:
        # 重新抛出已知的HTTP异常
        raise
    except Exception as e:
        logger.error(f"创建工单时发生未知错误: {e}")
        raise HTTPException(
            status_code=500,
            detail="创建工单时发生内部错误，请稍后重试"
        )


@router.get("/support/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    """
    根据工单ID获取工单信息（可选功能）
    """
    tickets_dir = "tickets"
    filename = f"ticket_{ticket_id}.json"
    filepath = os.path.join(tickets_dir, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="工单不存在")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            ticket_data = json.load(f)
        return JSONResponse(content=ticket_data)
    except Exception as e:
        logger.error(f"读取工单文件失败: {e}")
        raise HTTPException(status_code=500, detail="读取工单信息失败")