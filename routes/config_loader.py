"""
配置加载工具模块

从 data/products/ 目录动态加载产品配置，并提供配置缓存机制。
"""

import json
from pathlib import Path
from typing import Dict, Optional
from loguru import logger
from routes.base_plan import PlanConfig


# 配置缓存
_config_cache: Dict[str, PlanConfig] = {}


def load_plan_config(plan_id: str, force_reload: bool = False) -> PlanConfig:
    """
    从JSON文件加载计划配置

    Args:
        plan_id: 计划ID (例如: "free", "advanced", "unlimited")
        force_reload: 是否强制重新加载，忽略缓存

    Returns:
        PlanConfig: 配置对象

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置格式错误或缺少必需字段
        json.JSONDecodeError: JSON解析失败
    """
    # 检查缓存
    if not force_reload and plan_id in _config_cache:
        logger.debug(f"📦 从缓存加载配置: {plan_id}")
        return _config_cache[plan_id]

    # 构建配置文件路径
    config_path = Path(__file__).resolve().parent.parent / 'data' / 'products' / f'{plan_id}.json'

    # 检查文件是否存在
    if not config_path.exists():
        error_msg = f"配置文件不存在: {config_path}"
        logger.error(f"❌ {error_msg}")
        raise FileNotFoundError(error_msg)

    # 加载JSON文件
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        logger.debug(f"📖 成功读取配置文件: {config_path}")
    except json.JSONDecodeError as e:
        error_msg = f"JSON解析失败 ({config_path}): {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise json.JSONDecodeError(error_msg, e.doc, e.pos)
    except Exception as e:
        error_msg = f"读取配置文件失败 ({config_path}): {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise

    # 验证必需字段
    required_fields = ['plan_name', 'plan_id', 'up_mbps', 'down_mbps', 'duration_days']
    missing_fields = [field for field in required_fields if field not in config_data]

    if missing_fields:
        error_msg = f"配置缺少必需字段 ({config_path}): {', '.join(missing_fields)}"
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)

    # 验证数据类型
    try:
        # 验证plan_id匹配
        if config_data['plan_id'] != plan_id:
            logger.warning(
                f"⚠️ 配置文件中的plan_id ({config_data['plan_id']}) "
                f"与请求的plan_id ({plan_id}) 不匹配"
            )

        # 验证数值字段
        if not isinstance(config_data['up_mbps'], (int, float)) or config_data['up_mbps'] <= 0:
            raise ValueError(f"up_mbps 必须是正数: {config_data['up_mbps']}")

        if not isinstance(config_data['down_mbps'], (int, float)) or config_data['down_mbps'] <= 0:
            raise ValueError(f"down_mbps 必须是正数: {config_data['down_mbps']}")

        if not isinstance(config_data['duration_days'], int) or config_data['duration_days'] <= 0:
            raise ValueError(f"duration_days 必须是正整数: {config_data['duration_days']}")

        # 创建PlanConfig对象
        config = PlanConfig(**config_data)

        # 缓存配置
        _config_cache[plan_id] = config

        logger.info(
            f"✅ 成功加载配置: {plan_id} "
            f"(带宽: {config.up_mbps}↑/{config.down_mbps}↓ Mbps, "
            f"时长: {config.duration_days}天)"
        )

        return config

    except TypeError as e:
        error_msg = f"配置数据类型错误 ({config_path}): {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg) from e
    except Exception as e:
        error_msg = f"创建配置对象失败 ({config_path}): {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg) from e


def clear_config_cache(plan_id: Optional[str] = None) -> None:
    """
    清除配置缓存

    Args:
        plan_id: 要清除的计划ID，如果为None则清除所有缓存
    """
    global _config_cache

    if plan_id is None:
        _config_cache.clear()
        logger.info("🗑️ 已清除所有配置缓存")
    elif plan_id in _config_cache:
        del _config_cache[plan_id]
        logger.info(f"🗑️ 已清除配置缓存: {plan_id}")
    else:
        logger.debug(f"配置缓存中不存在: {plan_id}")


def get_cached_config(plan_id: str) -> Optional[PlanConfig]:
    """
    获取缓存的配置（如果存在）

    Args:
        plan_id: 计划ID

    Returns:
        PlanConfig 或 None
    """
    return _config_cache.get(plan_id)


def is_config_cached(plan_id: str) -> bool:
    """
    检查配置是否已缓存

    Args:
        plan_id: 计划ID

    Returns:
        bool: 是否已缓存
    """
    return plan_id in _config_cache
