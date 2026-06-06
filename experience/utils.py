"""经验沉淀引擎 — 工具函数"""

import re
import os
from pathlib import Path
from typing import List


def _slugify(text: str) -> str:
    """生成 slug（过滤路径穿越）"""
    text = text.lower().strip()
    text = text.replace("..", "").replace("/", "-").replace("\\", "-")
    text = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text)
    return text[:50]


def _extract_error_keywords(error_msg: str) -> List[str]:
    """从错误消息提取关键词"""
    keywords = re.findall(r'[a-zA-Z_]+|[\u4e00-\u9fff]+', error_msg)
    stopwords = {"error", "failed", "the", "is", "a", "an", "in", "on", "at", "to"}
    keywords = [k.lower() for k in keywords if k.lower() not in stopwords and len(k) > 2]
    return keywords[:5]


def _extract_domain(text: str) -> str:
    """从任务描述提取领域"""
    domain_keywords = {
        "memory": ["记忆", "memory", "tencentdb", "gbrain", "同步"],
        "finance": ["金融", "finance", "dcf", "估值", "财报"],
        "coding": ["代码", "code", "开发", "编程", "bug"],
        "deployment": ["部署", "deploy", "nginx", "systemd"],
        "review": ["审查", "review", "评审"],
    }
    text_lower = text.lower()
    for domain, keywords in domain_keywords.items():
        if any(kw in text_lower for kw in keywords):
            return domain
    return "general"


def _get_profile_db_path(profile: str) -> Path:
    """根据 profile 获取数据库路径"""
    if profile == "default":
        return Path.home() / ".hermes" / "experience-feedback.db"
    return Path.home() / ".hermes" / "profiles" / profile / "experience-feedback.db"
