"""
Akshare 多数据源整合模块
利用 Akshare 内置接口获取多源数据
"""

import logging
import pandas as pd
from typing import Optional, Dict, List
import time
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
    logger.info("✅ Akshare 模块加载成功")
except ImportError:
    AKSHARE_AVAILABLE = False
    logger.error("❌ Akshare 未安装")


# ==================== 基础工具函数 ====================

def safe_float(value, default=0.0):
    """安全转换为浮点数"""
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


def retry_request(func, max_retries=3, delay=2):
    """重试包装器"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ 第 {attempt + 1} 次尝试失败: {e}，{delay}秒后重试...")
                time.sleep(delay)
            else:
                raise
    return None


# ==================== 东方财富数据源（Akshare 主力） ====================

class EastmoneySource:
    """东方财富数据源（通过 Akshare）"""
    
    @staticmethod
    def get_lof_realtime() -> pd.DataFrame:
        """
        获取LOF实时行情
        接口：fund_lof_spot_em
        """
        if not AKSHARE_AVAILABLE:
            return pd.DataFrame()
        
        try:
            logger.info("🔄 [东方财富] 获取LOF实时行情...")
            
            df = retry_request(lambda: ak.fund_lof_spot_em(), max_retries=3, delay=3)
            
            if df is None or df.empty:
                logger.warning("⚠️ [东方财富] 未获取到数据")
                return pd.DataFrame()
            
            # 标准化列名
            df = df.rename(columns={
                '代码': '基金代码',
                '名称': '基金名称',
                '最新价': '场内价格',
                '成交额': '场内成交额(万)'
            })
            
            # 转换成交额单位（元 → 万元）
            if '场内成交额(万)' in df.columns:
                df['场内成交额(万)'] = df['场内成交额(万)'] / 10000
            
            logger.info(f"✅ [东方财富] 获取 {len(df)} 只LOF")
            return df
            
        except Exception as e:
            logger.error(f"❌ [东方财富] 失败: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def get_fund_nav(fund_code: str) -> Optional[Dict]:
        """
        获取基金净值
        接口：fund_etf_fund_info_em
        """
        if not AKSHARE_AVAILABLE:
            return None
        
        try:
            df = ak.fund_etf_fund_info_em(fund=fund_code, indicator="单位净值走势")
            
            if df is None or df.empty:
                return None
            
            latest = df.iloc[-1]
            
            return {
                'fund_code': fund_code,
                'nav': safe_float(latest['单位净值']),
                'nav_date': str(latest['净值日期']),
                'estimate': safe_float(latest.get('日增长率', 0))
            }
            
        except Exception as e:
            logger.debug(f"⚠️ [东方财富] 净值获取失败 {fund_code}: {e}")
            return None
    
    @staticmethod
    def get_fund_info(fund_code: str) -> Optional[Dict]:
        """
        获取基金详细信息
        接口：fund_individual_basic_info_xq
        """
        if not AKSHARE_AVAILABLE:
            return None
        
        try:
            df = ak.fund_individual_basic_info_xq(symbol=fund_code)
            
            if df is None or df.empty:
                return None
            
            info = df.set_index('item')['value'].to_dict()
            
            return {
                'fund_code': fund_code,
                'fund_name': info.get('基金简称', ''),
                'fund_type': info.get('基金类型', ''),
                'manager': info.get('基金管理人', ''),
                'setup_date': info.get('成立日期', '')
            }
            
        except Exception as e:
            logger.debug(f"⚠️ [东方财富] 基金信息获取失败 {fund_code}: {e}")
            return None


# ==================== 天天基金数据源 ====================

class TianTianFundSource:
    """天天基金数据源（通过 Akshare）"""
    
    @staticmethod
    def get_fund_list() -> pd.DataFrame:
        """
        获取基金列表
        接口：fund_name_em
        """
        if not AKSHARE_AVAILABLE:
            return pd.DataFrame()
        
        try:
            logger.info("🔄 [天天基金] 获取基金列表...")
            
            df = ak.fund_name_em()
            
            if df is None or df.empty:
                logger.warning("⚠️ [天天基金] 未获取到数据")
                return pd.DataFrame()
            
            # 筛选LOF基金
            df_lof = df[df['基金类型'].str.contains('LOF', na=False)]
            
            logger.info(f"✅ [天天基金] 获取 {len(df_lof)} 只LOF")
            return df_lof
            
        except Exception as e:
            logger.error(f"❌ [天天基金] 失败: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def get_fund_net_value(fund_code: str) -> Optional[Dict]:
        """
        获取基金净值
        接口：fund_open_fund_info_em
        """
        if not AKSHARE_AVAILABLE:
            return None
        
        try:
            df = ak.fund_open_fund_info_em(fund=fund_code, indicator="单位净值走势")
            
            if df is None or df.empty:
                return None
            
            latest = df.iloc[-1]
            
            return {
                'fund_code': fund_code,
                'nav': safe_float(latest['单位净值']),
                'accumulated_nav': safe_float(latest['累计净值']),
                'nav_date': str(latest['净值日期']),
                'growth_rate': safe_float(latest.get('日增长率', 0))
            }
            
        except Exception as e:
            logger.debug(f"⚠️ [天天基金] 净值获取失败 {fund_code}: {e}")
            return None


# ==================== 新浪财经数据源 ====================

class SinaFinanceSource:
    """新浪财经数据源（通过 Akshare）"""
    
    @staticmethod
    def get_realtime_quote(symbol: str) -> Optional[Dict]:
        """
        获取实时行情
        接口：stock_zh_a_spot_em (虽然是股票接口，但也支持基金)
        """
        if not AKSHARE_AVAILABLE:
            return None
        
        try:
            # Akshare 的新浪数据主要在股票模块
            # 对于基金，建议直接用东方财富接口
            logger.debug("💡 新浪财经建议使用东方财富接口替代")
            return None
            
        except Exception as e:
            logger.debug(f"⚠️ [新浪财经] 失败: {e}")
            return None


# ==================== 集思录数据源 ====================

class JisiluSource:
    """集思录数据源（自定义爬虫）"""
    
    BASE_URL = "https://www.jisilu.cn/data/lof/stock_lof_list/"
    
    @staticmethod
    def get_lof_premium() -> pd.DataFrame:
        """
        获取LOF溢价数据
        注意：Akshare 暂不支持集思录，需自定义爬虫
        """
        try:
            logger.info("🔄 [集思录] 获取LOF溢价数据...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.jisilu.cn/data/lof/',
                'Accept': 'application/json'
            }
            
            response = requests.get(
                JisiluSource.BASE_URL,
                headers=headers,
                timeout=15
            )
            
            if response.status_code != 200:
                logger.error(f"❌ [集思录] HTTP {response.status_code}")
                return pd.DataFrame()
            
            data = response.json()
            
            if 'rows' not in data:
                logger.error("❌ [集思录] 数据格式错误")
                return pd.DataFrame()
            
            records = []
            for item in data['rows']:
                cell = item.get('cell', {})
                
                try:
                    records.append({
                        '基金代码': cell.get('fund_id', ''),
                        '基金名称': cell.get('fund_nm', ''),
                        '场内价格': safe_float(cell.get('price')),
                        '基金净值': safe_float(cell.get('nav')),
                        '溢价率(%)': safe_float(cell.get('discount_rt')),
                        '场内成交额(万)': safe_float(cell.get('amount')) / 10000,
                        '净值日期': cell.get('nav_dt', '')
                    })
                except Exception:
                    continue
            
            df = pd.DataFrame(records)
            
            # 过滤无效数据
            df = df[df['场内价格'] > 0]
            
            logger.info(f"✅ [集思录] 获取 {len(df)} 只LOF（含溢价率）")
            return df
            
        except Exception as e:
            logger.error(f"❌ [集思录] 失败: {e}")
            return pd.DataFrame()


# ==================== 多数据源整合器 ====================

class AkshareMultiSource:
    """Akshare 多数据源整合器"""
    
    def __init__(self):
        """初始化"""
        if not AKSHARE_AVAILABLE:
            logger.error("❌ Akshare 不可用")
        
        self.sources = {
            'eastmoney': EastmoneySource(),
            'tiantian': TianTianFundSource(),
            'jisilu': JisiluSource(),
            'sina': SinaFinanceSource()
        }
    
    def get_lof_data_unified(self, preferred_source: str = 'eastmoney') -> pd.DataFrame:
        """
        获取LOF数据（统一接口）
        
        Args:
            preferred_source: 优先数据源
                - 'eastmoney': 东方财富（推荐）
                - 'jisilu': 集思录（含溢价率）
                - 'tiantian': 天天基金
        
        Returns:
            DataFrame
        """
        if not AKSHARE_AVAILABLE:
            logger.error("❌ Akshare 不可用")
            return pd.DataFrame()
        
        # 优先使用指定数据源
        logger.info(f"🎯 优先使用: {preferred_source}")
        
        if preferred_source == 'jisilu':
            df = self.sources['jisilu'].get_lof_premium()
            if not df.empty:
                return df
            logger.warning("⚠️ 集思录失败，降级到东方财富")
        
        # 降级到东方财富
        df = self.sources['eastmoney'].get_lof_realtime()
        if not df.empty:
            return df
        
        # 最后尝试天天基金
        logger.warning("⚠️ 东方财富失败，尝试天天基金")
        df = self.sources['tiantian'].get_fund_list()
        
        return df
    
    def get_fund_nav_unified(self, fund_code: str) -> Optional[Dict]:
        """
        获取基金净值（统一接口，多源降级）
        
        Args:
            fund_code: 基金代码
        
        Returns:
            dict 或 None
        """
        if not AKSHARE_AVAILABLE:
            return None
        
        # 1. 尝试东方财富
        nav = self.sources['eastmoney'].get_fund_nav(fund_code)
        if nav and nav.get('nav', 0) > 0:
            return nav
        
        # 2. 尝试天天基金
        nav = self.sources['tiantian'].get_fund_net_value(fund_code)
        if nav and nav.get('nav', 0) > 0:
            return nav
        
        return None
    
    def get_fund_info_detail(self, fund_code: str) -> Dict:
        """
        获取基金详细信息（整合多源）
        
        Args:
            fund_code: 基金代码
        
        Returns:
            dict: 包含基金详细信息
        """
        info = {
            'fund_code': fund_code,
            'source': []
        }
        
        # 从东方财富获取基本信息
        basic_info = self.sources['eastmoney'].get_fund_info(fund_code)
        if basic_info:
            info.update(basic_info)
            info['source'].append('eastmoney')
        
        # 从天天基金获取净值
        nav_info = self.sources['tiantian'].get_fund_net_value(fund_code)
        if nav_info:
            info['nav'] = nav_info.get('nav')
            info['nav_date'] = nav_info.get('nav_date')
            info['source'].append('tiantian')
        
        return info
    
    def compare_sources(self, fund_code: str) -> pd.DataFrame:
        """
        对比不同数据源的数据
        
        Args:
            fund_code: 基金代码
        
        Returns:
            DataFrame: 对比结果
        """
        comparison = []
        
        # 东方财富
        em_nav = self.sources['eastmoney'].get_fund_nav(fund_code)
        if em_nav:
            comparison.append({
                '数据源': '东方财富',
                '净值': em_nav.get('nav'),
                '日期': em_nav.get('nav_date'),
                '涨幅': em_nav.get('estimate')
            })
        
        # 天天基金
        tt_nav = self.sources['tiantian'].get_fund_net_value(fund_code)
        if tt_nav:
            comparison.append({
                '数据源': '天天基金',
                '净值': tt_nav.get('nav'),
                '日期': tt_nav.get('nav_date'),
                '涨幅': tt_nav.get('growth_rate')
            })
        
        return pd.DataFrame(comparison)


# ==================== 便捷函数 ====================

# 创建全局实例
akshare_multi = AkshareMultiSource()


def get_lof_from_akshare(source: str = 'eastmoney') -> pd.DataFrame:
    """
    从 Akshare 获取LOF数据（便捷函数）
    
    Args:
        source: 数据源选择
            - 'eastmoney': 东方财富（默认，最全）
            - 'jisilu': 集思录（含溢价率）
            - 'tiantian': 天天基金
    
    Returns:
        DataFrame
    """
    return akshare_multi.get_lof_data_unified(preferred_source=source)


def get_nav_from_akshare(fund_code: str) -> Optional[Dict]:
    """
    从 Akshare 获取净值（便捷函数）
    
    Args:
        fund_code: 基金代码
    
    Returns:
        dict 或 None
    """
    return akshare_multi.get_fund_nav_unified(fund_code)


def get_fund_detail_from_akshare(fund_code: str) -> Dict:
    """
    从 Akshare 获取基金详情（便捷函数）
    
    Args:
        fund_code: 基金代码
    
    Returns:
        dict
    """
    return akshare_multi.get_fund_info_detail(fund_code)
