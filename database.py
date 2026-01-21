"""
Supabase 数据库操作封装
功能：LOF溢价数据持久化存储
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
import streamlit as st

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("⚠️ Supabase 未安装，数据库功能不可用")


class SupabaseDB:
    """Supabase 数据库管理类"""
    
    def __init__(self, url: str = None, key: str = None):
        """初始化数据库连接"""
        if not SUPABASE_AVAILABLE:
            self.client = None
            return
        
        try:
            # 优先使用参数，其次使用环境变量
            self.url = url or st.secrets.get("supabase", {}).get("url")
            self.key = key or st.secrets.get("supabase", {}).get("key")
            
            if not self.url or not self.key:
                logger.warning("⚠️ Supabase 配置缺失")
                self.client = None
                return
            
            self.client: Client = create_client(self.url, self.key)
            logger.info("✅ Supabase 数据库连接成功")
            
            # 自动创建表
            self._init_tables()
            
        except Exception as e:
            logger.error(f"❌ Supabase 连接失败: {e}")
            self.client = None
    
    def is_connected(self) -> bool:
        """检查数据库是否连接"""
        return self.client is not None
    
    def _init_tables(self):
        """初始化数据库表（首次使用）"""
        # 注意：表结构需要在 Supabase 控制台手动创建
        # 这里只是记录表结构说明
        logger.info("📊 数据库表结构说明：")
        logger.info("""
        -- lof_premium_history (溢价历史记录)
        CREATE TABLE lof_premium_history (
            id BIGSERIAL PRIMARY KEY,
            fund_code TEXT NOT NULL,
            fund_name TEXT,
            market_price NUMERIC(10, 4),
            nav NUMERIC(10, 4),
            premium_rate NUMERIC(10, 2),
            volume NUMERIC(15, 2),
            record_time TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- lof_alerts (推送提醒记录)
        CREATE TABLE lof_alerts (
            id BIGSERIAL PRIMARY KEY,
            fund_code TEXT NOT NULL,
            fund_name TEXT,
            premium_rate NUMERIC(10, 2),
            alert_type TEXT,
            push_status TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- 创建索引
        CREATE INDEX idx_premium_fund_code ON lof_premium_history(fund_code);
        CREATE INDEX idx_premium_time ON lof_premium_history(record_time);
        CREATE INDEX idx_alerts_time ON lof_alerts(created_at);
        """)
    
    def save_premium_data(self, data: List[Dict]) -> bool:
        """
        批量保存溢价数据
        
        Args:
            data: 溢价数据列表
        Returns:
            bool: 是否成功
        """
        if not self.is_connected():
            return False
        
        try:
            records = []
            for item in data:
                records.append({
                    'fund_code': item['基金代码'],
                    'fund_name': item['基金名称'],
                    'market_price': float(item['场内价格']),
                    'nav': float(item['基金净值']),
                    'premium_rate': float(item['溢价率(%)']),
                    'volume': float(item['场内成交额(万)']),
                    'record_time': datetime.now().isoformat()
                })
            
            # 批量插入
            result = self.client.table('lof_premium_history').insert(records).execute()
            logger.info(f"💾 保存 {len(records)} 条溢价数据到数据库")
            return True
            
        except Exception as e:
            logger.error(f"❌ 数据保存失败: {e}")
            return False
    
    def get_premium_history(self, fund_code: str, days: int = 7) -> List[Dict]:
        """
        获取指定基金的历史溢价数据
        
        Args:
            fund_code: 基金代码
            days: 查询天数
        Returns:
            历史数据列表
        """
        if not self.is_connected():
            return []
        
        try:
            from datetime import timedelta
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            result = self.client.table('lof_premium_history')\
                .select('*')\
                .eq('fund_code', fund_code)\
                .gte('record_time', start_date)\
                .order('record_time', desc=True)\
                .execute()
            
            return result.data
            
        except Exception as e:
            logger.error(f"❌ 查询历史数据失败: {e}")
            return []
    
    def save_alert_record(self, fund_code: str, fund_name: str, 
                         premium_rate: float, alert_type: str, 
                         push_status: str) -> bool:
        """
        保存推送提醒记录
        
        Args:
            fund_code: 基金代码
            fund_name: 基金名称
            premium_rate: 溢价率
            alert_type: 提醒类型
            push_status: 推送状态
        Returns:
            bool: 是否成功
        """
        if not self.is_connected():
            return False
        
        try:
            record = {
                'fund_code': fund_code,
                'fund_name': fund_name,
                'premium_rate': premium_rate,
                'alert_type': alert_type,
                'push_status': push_status
            }
            
            self.client.table('lof_alerts').insert(record).execute()
            logger.info(f"📝 保存推送记录: {fund_name} ({premium_rate}%)")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存推送记录失败: {e}")
            return False
    
    def get_today_alerts(self) -> List[Dict]:
        """获取今日推送记录"""
        if not self.is_connected():
            return []
        
        try:
            today = datetime.now().date().isoformat()
            
            result = self.client.table('lof_alerts')\
                .select('*')\
                .gte('created_at', today)\
                .order('created_at', desc=True)\
                .execute()
            
            return result.data
            
        except Exception as e:
            logger.error(f"❌ 查询推送记录失败: {e}")
            return []
    
    def get_top_premiums(self, limit: int = 10) -> List[Dict]:
        """
        获取最新的高溢价基金
        
        Args:
            limit: 返回数量
        Returns:
            基金列表
        """
        if not self.is_connected():
            return []
        
        try:
            # 获取最新记录时间
            latest = self.client.table('lof_premium_history')\
                .select('record_time')\
                .order('record_time', desc=True)\
                .limit(1)\
                .execute()
            
            if not latest.data:
                return []
            
            latest_time = latest.data[0]['record_time']
            
            # 获取该时间的TOP数据
            result = self.client.table('lof_premium_history')\
                .select('*')\
                .eq('record_time', latest_time)\
                .order('premium_rate', desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data
            
        except Exception as e:
            logger.error(f"❌ 查询TOP溢价失败: {e}")
            return []
