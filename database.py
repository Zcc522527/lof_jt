"""
Supabase 数据库操作封装 - Render 版本
"""

import logging
import os
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("⚠️ Supabase 未安装，数据库功能不可用")


class SupabaseDB:
    """Supabase 数据库管理类 - Render 优化版"""
    
    def __init__(self, url: str = None, key: str = None):
        """初始化数据库连接"""
        if not SUPABASE_AVAILABLE:
            self.client = None
            return
        
        try:
            # Render 环境变量读取（优先级最高）
            self.url = url or os.environ.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
            self.key = key or os.environ.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
            
            # 调试日志
            logger.info(f"🔍 Supabase 配置检查:")
            logger.info(f"   URL: {'✅ 已设置' if self.url else '❌ 未设置'}")
            logger.info(f"   KEY: {'✅ 已设置 (长度={len(self.key)})' if self.key else '❌ 未设置'}")
            
            if not self.url or not self.key:
                logger.warning("⚠️ Supabase 配置缺失，数据库功能不可用")
                self.client = None
                return
            
            self.client: Client = create_client(self.url, self.key)
            logger.info("✅ Supabase 数据库连接成功")
            
        except Exception as e:
            logger.error(f"❌ Supabase 连接失败: {e}")
            self.client = None
    
    # ... 其他方法保持不变 ...
