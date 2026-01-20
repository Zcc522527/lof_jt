import streamlit as st
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RobustDataFetcher:
    """健壮的数据获取器，带多重降级策略"""
    
    def __init__(self):
        self.session = self._create_session()
        
    @staticmethod
    @st.cache_resource
    def _create_session():
        """创建带重试和连接池的会话"""
        session = requests.Session()
        
        # 更激进的重试策略
        retry_strategy = Retry(
            total=10,  # 增加重试次数
            backoff_factor=3,  # 增加退避时间
            status_forcelist=[429, 500, 502, 503, 504, 520, 522, 524],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=50,
            pool_maxsize=50,
            pool_block=False
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 设置默认请求头（模拟真实浏览器）
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'http://fund.eastmoney.com/',
            'X-Requested-With': 'XMLHttpRequest'
        })
        
        return session
    
    def fetch_lof_data_direct(self, max_attempts=5):
        """直接调用东方财富 API（绕过 Akshare）"""
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        
        params = {
            'pn': '1',
            'pz': '5000',  # 获取所有数据
            'po': '1',
            'np': '1',
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': '2',
            'invt': '2',
            'fid': 'f3',
            'fs': 'm:8+t:2',  # LOF 基金
            'fields': 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f26,f22,f11,f62,f128,f136,f115,f152',
            '_': str(int(time.time() * 1000))
        }
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"🔄 尝试 {attempt + 1}/{max_attempts} - 直接调用 API")
                
                response = self.session.get(
                    url,
                    params=params,
                    timeout=(30, 90),  # 超长超时时间
                    verify=False  # 禁用 SSL 验证（如果证书问题）
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('data') and data['data'].get('diff'):
                        df = pd.DataFrame(data['data']['diff'])
                        
                        # 重命名列
                        column_mapping = {
                            'f12': '代码',
                            'f14': '名称',
                            'f2': '最新价',
                            'f3': '涨跌幅',
                            'f4': '涨跌额',
                            'f5': '成交量',
                            'f6': '成交额',
                            'f15': '最高',
                            'f16': '最低',
                            'f17': '今开',
                            'f18': '昨收',
                        }
                        
                        df = df.rename(columns=column_mapping)
                        
                        # 选择需要的列
                        required_cols = [col for col in column_mapping.values() if col in df.columns]
                        df = df[required_cols]
                        
                        # 数据类型转换
                        numeric_cols = ['最新价', '涨跌幅', '涨跌额', '成交量', '成交额', '最高', '最低', '今开', '昨收']
                        for col in numeric_cols:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce')
                        
                        logger.info(f"✅ 成功获取 {len(df)} 条数据")
                        return df
                
                logger.warning(f"⚠️ API 返回状态码: {response.status_code}")
                
            except requests.exceptions.SSLError:
                logger.warning(f"🔐 SSL 错误，尝试禁用验证...")
                continue
                
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️ 请求超时 (尝试 {attempt + 1})")
                time.sleep((attempt + 1) * 5)
                
            except Exception as e:
                logger.error(f"❌ 错误: {str(e)}")
                
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 8
                    logger.info(f"⏳ {wait_time}秒后重试...")
                    time.sleep(wait_time)
        
        return None
    
    def fetch_via_akshare(self):
        """尝试使用 Akshare（备用方案）"""
        try:
            import akshare as ak
            
            # Monkey patch akshare 的 session
            if hasattr(ak.fund.fund_lof_em, 'session'):
                ak.fund.fund_lof_em.session = self.session
            
            logger.info("📊 尝试使用 Akshare...")
            df = ak.fund_lof_spot_em()
            logger.info(f"✅ Akshare 成功获取 {len(df)} 条数据")
            return df
            
        except Exception as e:
            logger.error(f"❌ Akshare 失败: {str(e)}")
            return None
            
    PROXY_URL = "misty-morning-49ef.zcc522527.workers.dev"
    def fetch_with_proxy(self, proxy_url):
        """通过 Cloudflare Workers 代理获取"""
        try:
            api_url = "http://push2.eastmoney.com/api/qt/clist/get"
            proxy_request = f"{proxy_url}?target={requests.utils.quote(api_url)}"
            
            logger.info(f"🌐 尝试使用代理: {proxy_url}")
            
            response = self.session.get(proxy_request, timeout=(20, 60))
            
            if response.status_code == 200:
                data = response.json()
                # 处理数据...
                return pd.DataFrame(data)
                
        except Exception as e:
            logger.error(f"❌ 代理失败: {str(e)}")
            return None
    
    @st.cache_data(ttl=300, show_spinner=False)
    def get_lof_data(_self):
        """多重降级策略获取数据"""
        
        strategies = [
            ("直接 API 调用", _self.fetch_lof_data_direct),
            ("Akshare 库", _self.fetch_via_akshare),
        ]
        
        for strategy_name, fetch_func in strategies:
            try:
                st.info(f"🔍 策略: {strategy_name}")
                df = fetch_func()
                
                if df is not None and not df.empty:
                    st.success(f"✅ {strategy_name} 成功！获取 {len(df)} 条数据")
                    return df
                    
            except Exception as e:
                st.warning(f"⚠️ {strategy_name} 失败: {str(e)}")
                continue
        
        st.error("❌ 所有数据获取策略均失败")
        return None


# 全局单例
@st.cache_resource
def get_data_fetcher():
    return RobustDataFetcher()
