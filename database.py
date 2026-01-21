"""
Supabase 数据库操作封装 - Render 部署版
功能：LOF溢价数据持久化存储 + 推送记录管理
版本：v3.0.0 - Render Optimized
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# ==================== 依赖检查 ====================

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("⚠️ Supabase 库未安装，数据库功能不可用")
    logger.info("💡 安装方法: pip install supabase")


# ==================== 数据库管理类 ====================

class SupabaseDB:
    """
    Supabase 数据库管理类
    
    功能：
    1. LOF溢价历史数据存储
    2. 推送提醒记录管理
    3. 数据查询与分析
    
    环境变量：
    - SUPABASE_URL: Supabase 项目 URL
    - SUPABASE_KEY: Supabase 匿名密钥
    """
    
    def __init__(self, url: str = None, key: str = None):
        """
        初始化数据库连接
        
        Args:
            url: Supabase URL（可选，默认从环境变量读取）
            key: Supabase Key（可选，默认从环境变量读取）
        """
        self.client = None
        self.url = None
        self.key = None
        
        if not SUPABASE_AVAILABLE:
            logger.error("❌ Supabase 库未安装")
            return
        
        try:
            # 优先级：参数 > 环境变量
            self.url = (
                url or 
                os.environ.get("SUPABASE_URL") or 
                os.getenv("SUPABASE_URL")
            )
            
            self.key = (
                key or 
                os.environ.get("SUPABASE_KEY") or 
                os.getenv("SUPABASE_KEY")
            )
            
            # 调试日志
            logger.info("=" * 60)
            logger.info("🔍 Supabase 数据库配置检查:")
            logger.info(f"   SUPABASE_URL: {'✅ 已设置' if self.url else '❌ 未设置'}")
            
            if self.url:
                # 显示URL前缀（安全起见不显示完整URL）
                url_prefix = self.url[:30] + "..." if len(self.url) > 30 else self.url
                logger.info(f"   URL 前缀: {url_prefix}")
            
            if self.key:
                logger.info(f"   SUPABASE_KEY: ✅ 已设置 (长度={len(self.key)})")
                # 显示Key前缀（安全）
                key_prefix = self.key[:20] + "..." if len(self.key) > 20 else self.key
                logger.info(f"   KEY 前缀: {key_prefix}")
            else:
                logger.info("   SUPABASE_KEY: ❌ 未设置")
            
            logger.info("=" * 60)
            
            # 检查配置完整性
            if not self.url or not self.key:
                logger.warning("⚠️ Supabase 配置不完整，数据库功能不可用")
                logger.info("💡 请在 Render Dashboard → Environment 中配置:")
                logger.info("   - SUPABASE_URL")
                logger.info("   - SUPABASE_KEY")
                return
            
            # 创建客户端连接
            self.client: Client = create_client(self.url, self.key)
            
            # 测试连接
            self._test_connection()
            
            logger.info("✅ Supabase 数据库连接成功")
            
        except Exception as e:
            logger.error(f"❌ Supabase 连接失败: {e}")
            logger.debug(f"详细错误信息: {type(e).__name__}: {str(e)}")
            self.client = None
    
    def _test_connection(self):
        """测试数据库连接"""
        try:
            # 尝试查询一条数据（不会实际返回，仅测试连接）
            self.client.table('lof_premium_history').select('*').limit(1).execute()
        except Exception as e:
            logger.warning(f"⚠️ 数据库表可能不存在，需要初始化: {e}")
    
    def is_connected(self) -> bool:
        """
        检查数据库是否已连接
        
        Returns:
            bool: True=已连接，False=未连接
        """
        return self.client is not None
    
    # ==================== 溢价数据管理 ====================
    
    def save_premium_data(self, data: List[Dict]) -> bool:
        """
        批量保存溢价数据
        
        Args:
            data: 数据列表，每条包含：
                - 基金代码 (fund_code)
                - 基金名称 (fund_name)
                - 场内价格 (market_price)
                - 基金净值 (nav)
                - 溢价率 (premium_rate)
                - 成交额 (volume)
        
        Returns:
            bool: True=成功，False=失败
        """
        if not self.is_connected():
            logger.warning("⚠️ 数据库未连接，无法保存数据")
            return False
        
        if not data:
            logger.warning("⚠️ 没有数据需要保存")
            return False
        
        try:
            records = []
            for item in data:
                try:
                    record = {
                        'fund_code': str(item.get('基金代码', '')),
                        'fund_name': str(item.get('基金名称', '')),
                        'market_price': float(item.get('场内价格', 0)),
                        'nav': float(item.get('基金净值', 0)),
                        'premium_rate': float(item.get('溢价率(%)', 0)),
                        'volume': float(item.get('场内成交额(万)', 0)),
                        'record_time': datetime.now().isoformat()
                    }
                    
                    # 验证必要字段
                    if record['fund_code'] and record['market_price'] > 0 and record['nav'] > 0:
                        records.append(record)
                    
                except (ValueError, TypeError, KeyError) as e:
                    logger.debug(f"⚠️ 跳过无效记录: {e}")
                    continue
            
            if not records:
                logger.warning("⚠️ 没有有效记录可以保存")
                return False
            
            # 批量插入
            result = self.client.table('lof_premium_history').insert(records).execute()
            
            logger.info(f"💾 成功保存 {len(records)} 条溢价数据到数据库")
            return True
            
        except Exception as e:
            logger.error(f"❌ 数据保存失败: {e}")
            logger.debug(f"详细错误: {type(e).__name__}: {str(e)}")
            return False
    
    def get_premium_history(self, fund_code: str, days: int = 7) -> List[Dict]:
        """
        获取指定基金的历史溢价数据
        
        Args:
            fund_code: 基金代码
            days: 查询天数（默认7天）
        
        Returns:
            List[Dict]: 历史数据列表
        """
        if not self.is_connected():
            logger.warning("⚠️ 数据库未连接")
            return []
        
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            result = self.client.table('lof_premium_history')\
                .select('*')\
                .eq('fund_code', fund_code)\
                .gte('record_time', start_date)\
                .order('record_time', desc=True)\
                .execute()
            
            data = result.data if hasattr(result, 'data') else []
            
            if data:
                logger.info(f"📊 查询到 {len(data)} 条历史数据 (基金={fund_code}, 天数={days})")
            else:
                logger.info(f"📭 未查询到数据 (基金={fund_code})")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ 查询历史数据失败: {e}")
            logger.debug(f"详细错误: {type(e).__name__}: {str(e)}")
            return []
    
    def get_top_premiums(self, limit: int = 10, date: str = None) -> List[Dict]:
        """
        获取最新的高溢价基金
        
        Args:
            limit: 返回数量（默认10条）
            date: 指定日期（可选，默认最新记录时间）
        
        Returns:
            List[Dict]: TOP溢价基金列表
        """
        if not self.is_connected():
            logger.warning("⚠️ 数据库未连接")
            return []
        
        try:
            # 如果没有指定日期，获取最新记录时间
            if not date:
                latest = self.client.table('lof_premium_history')\
                    .select('record_time')\
                    .order('record_time', desc=True)\
                    .limit(1)\
                    .execute()
                
                if not latest.data:
                    logger.info("📭 数据库中暂无历史数据")
                    return []
                
                date = latest.data[0]['record_time']
            
            # 获取指定时间的TOP数据
            result = self.client.table('lof_premium_history')\
                .select('*')\
                .eq('record_time', date)\
                .order('premium_rate', desc=True)\
                .limit(limit)\
                .execute()
            
            data = result.data if hasattr(result, 'data') else []
            
            if data:
                logger.info(f"🏆 查询到 TOP {len(data)} 高溢价基金")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ 查询TOP溢价失败: {e}")
            logger.debug(f"详细错误: {type(e).__name__}: {str(e)}")
            return []
    
    # ==================== 推送记录管理 ====================
    
    def save_alert_record(self, fund_code: str, fund_name: str, 
                         premium_rate: float, alert_type: str = 'chicken', 
                         push_status: str = 'success') -> bool:
        """
        保存推送提醒记录
        
        Args:
            fund_code: 基金代码
            fund_name: 基金名称
            premium_rate: 溢价率
            alert_type: 提醒类型（chicken=鸡腿机会）
            push_status: 推送状态（success/failed）
        
        Returns:
            bool: True=成功，False=失败
        """
        if not self.is_connected():
            logger.warning("⚠️ 数据库未连接，无法保存推送记录")
            return False
        
        try:
            record = {
                'fund_code': fund_code,
                'fund_name': fund_name,
                'premium_rate': premium_rate,
                'alert_type': alert_type,
                'push_status': push_status,
                'created_at': datetime.now().isoformat()
            }
            
            self.client.table('lof_alerts').insert(record).execute()
            
            logger.info(f"📝 保存推送记录: {fund_name} ({premium_rate}%) - {push_status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存推送记录失败: {e}")
            logger.debug(f"详细错误: {type(e).__name__}: {str(e)}")
            return False
    
    def get_today_alerts(self) -> List[Dict]:
        """
        获取今日推送记录
        
        Returns:
            List[Dict]: 今日推送记录列表
        """
        if not self.is_connected():
            logger.warning("⚠️ 数据库未连接")
            return []
        
        try:
            today = datetime.now().date().isoformat()
            
            result = self.client.table('lof_alerts')\
                .select('*')\
                .gte('created_at', today)\
                .order('created_at', desc=True)\
                .execute()
            
            data = result.data if hasattr(result, 'data') else []
            
            if data:
                logger.info(f"📤 查询到今日 {len(data)} 条推送记录")
            else:
                logger.info("📭 今日暂无推送记录")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ 查询推送记录失败: {e}")
            logger.debug(f"详细错误: {type(e).__name__}: {str(e)}")
            return []
    
    def get_alert_history(self, days: int = 7) -> List[Dict]:
        """
        获取历史推送记录
        
        Args:
            days: 查询天数（默认7天）
        
        Returns:
            List[Dict]: 历史推送记录
        """
        if not self.is_connected():
            return []
        
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            result = self.client.table('lof_alerts')\
                .select('*')\
                .gte('created_at', start_date)\
                .order('created_at', desc=True)\
                .execute()
            
            return result.data if hasattr(result, 'data') else []
            
        except Exception as e:
            logger.error(f"❌ 查询历史推送记录失败: {e}")
            return []
    
    # ==================== 数据库维护 ====================
    
    def cleanup_old_data(self, days: int = 30) -> bool:
        """
        清理旧数据（保留最近N天）
        
        Args:
            days: 保留天数（默认30天）
        
        Returns:
            bool: True=成功，False=失败
        """
        if not self.is_connected():
            logger.warning("⚠️ 数据库未连接")
            return False
        
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # 清理溢价历史数据
            result1 = self.client.table('lof_premium_history')\
                .delete()\
                .lt('record_time', cutoff_date)\
                .execute()
            
            # 清理推送记录
            result2 = self.client.table('lof_alerts')\
                .delete()\
                .lt('created_at', cutoff_date)\
                .execute()
            
            logger.info(f"🗑️ 清理 {days} 天前的旧数据完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 清理旧数据失败: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            dict: 统计信息
        """
        if not self.is_connected():
            return {'status': 'disconnected'}
        
        try:
            # 溢价历史记录总数
            premium_count = self.client.table('lof_premium_history')\
                .select('*', count='exact')\
                .execute()
            
            # 推送记录总数
            alert_count = self.client.table('lof_alerts')\
                .select('*', count='exact')\
                .execute()
            
            # 今日记录数
            today = datetime.now().date().isoformat()
            today_count = self.client.table('lof_premium_history')\
                .select('*', count='exact')\
                .gte('record_time', today)\
                .execute()
            
            stats = {
                'status': 'connected',
                'total_premium_records': premium_count.count if hasattr(premium_count, 'count') else 0,
                'total_alert_records': alert_count.count if hasattr(alert_count, 'count') else 0,
                'today_records': today_count.count if hasattr(today_count, 'count') else 0,
                'last_check': datetime.now().isoformat()
            }
            
            logger.info(f"📊 数据库统计: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ 获取数据库统计失败: {e}")
            return {'status': 'error', 'message': str(e)}


# ==================== 测试函数 ====================

def test_database_connection():
    """测试数据库连接"""
    print("=" * 60)
    print("🧪 测试 Supabase 数据库连接")
    print("=" * 60)
    
    db = SupabaseDB()
    
    if db.is_connected():
        print("✅ 数据库连接成功")
        
        # 获取统计信息
        stats = db.get_database_stats()
        print(f"📊 数据库统计: {stats}")
        
        # 测试保存数据
        test_data = [{
            '基金代码': '160636',
            '基金名称': '测试基金',
            '场内价格': 1.500,
            '基金净值': 1.400,
            '溢价率(%)': 7.14,
            '场内成交额(万)': 100.0
        }]
        
        if db.save_premium_data(test_data):
            print("✅ 数据保存测试成功")
        else:
            print("❌ 数据保存测试失败")
        
    else:
        print("❌ 数据库连接失败")
        print("💡 请检查环境变量配置:")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_KEY")


if __name__ == "__main__":
    test_database_connection()
