"""
LOF多数据源支持模块
支持数据源：集思录、新浪财经、腾讯财经、东方财富
降级策略集思录 > 新浪 > 腾讯 > 东方财富
"""

导入请求
导入pandas as pd
导入日志
from typing import  List , Dict , Optional
导入时间
导入re
导入json

logger = logging.getLogger(__name__)


# ==================== 集思录 API ====================

类 JisiluAPI：
    """
    集思录数据接口
    优势：直接提供溢价率，消耗二次计算
    """
    
    BASE_URL = "https://www.jisilu.cn/data/lof/stock_lof_list/"
    
    @staticmethod
    def  get_lof_data () -> pd.DataFrame:
        """
        获取LOF溢价数据（已包含溢价率计算）
        
        返回：
            DataFrame：包含代码、名称、场内价格、净值、溢价率等
        """
        标题 = {
            'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' ,
            '推荐人' : 'https://www.jisilu.cn/data/lof/' ,
            '接受' : 'application/json, text/javascript, */*; q=0.01' ,
            '接受语言' : 'zh-CN,zh;q=0.9,en;q=0.8' ,
            'X-Requested-With' : 'XMLHttpRequest'
        }
        
        尝试：
            logger.info( "🔄 正在从集思录获取LOF数据..." )
            
            响应 = requests.get(
                JisiluAPI.BASE_URL，
                headers=headers，
                超时时间= 15
            ）
            
            如果response.status_code != 200：
                logger.error( f"❌ 集思录响应错误: HTTP {response.status_code} " )
                返回pd.DataFrame()
            
            data = response.json()
            
            如果 “rows” 不在数据 中：
                logger.error( "❌集思录返回数据格式错误" )
                返回pd.DataFrame()
            
            记录 = []
            对于data[ 'rows' ]中的每个 item ：
                cell = item.get( 'cell' , {})
                
                # 提取关键字段
                尝试：
                    fund_id = cell.get( 'fund_id' , '' )
                    fund_nm = cell.get( 'fund_nm' , '' )
                    price = float (cell.get( 'price' , 0 ))
                    nav = float (cell.get( 'nav' , 0 ))
                    discount_rt = float (cell.get( 'discount_rt' , 0 ))
                    amount = float (cell.get( 'amount' , 0 )) / 10000   # 转为万元
                    nav_dt = cell.get( 'nav_dt' , '' )
                    
                    # 过滤无效数据
                    如果 基金 ID不为空或价格小于等于0 或资产净值小于等于0：
                        继续
                    
                    records.append({
                        '基金代码'：fund_id,
                        '基金名称'：fund_nm,
                        '场内价格' : round (价格, 3 ),
                        '基金净值' : round (nav, 4 ),
                        '溢价率(%)' : round (discount_rt, 2 ),
                        '场内成交额(万)' : round (amount, 2 ),
                        '净值日期' : nav_dt
                    })
                    
                except (ValueError, TypeError, KeyError) as e:
                    logger.debug( f"⚠️ 解析数据失败: {e} " )
                    继续
            
            如果 没有记录：
                logger.warning( "⚠️集思录未解析到有效数据" )
                返回pd.DataFrame()
            
            df = pd.DataFrame(records)
            logger.info( f"✅ 集思录：获取{ len (df)}只LOF数据（含溢价率）" )
            返回数据框
            
        除了requests.exceptions.Timeout 之外：
            logger.error( "❌集思录请求超时" )
            返回pd.DataFrame()
        排除requests.exceptions.RequestException作为e：
            logger.error( f"❌集思录网络错误: {e} " )
            返回pd.DataFrame()
        除非出现json.JSONDecodeError异常：
            logger.error( f"❌集思录JSON解析失败: {e} " )
            返回pd.DataFrame()
        除异常e外：
            logger.error( f"❌集思录未知错误: {e} " )
            返回pd.DataFrame()


# ==================== 新浪财经 API ====================

class  SinaFinanceAPI：
    """
    新浪财经数据接口
    优势：稳定性高、延迟低
    """
    
    BASE_URL = "http://hq.sinajs.cn/list="
    
    # 预定义LOF基金代码列表（常见LOF）
    LOF_CODES = [
        #深圳LOF
        "160105" , "160119" , "160127" , "160212" , "160213" , "160216" , "160217" ,
        "160218" , "160219" , "160220" , "160221" , "160222" , "160225" , "160505" ,
        "160512" , "160607" , "160610" , "160611" , "160613" , "160615" , "160616" ,
        "160617" , "160618" , "160620" , "160624" , "160625" , "160626" , "160628" ,
        "160629" , "160630" , "160631" , "160632" , "160633" , "160634" , "160635" ,
        "160636" , "160637" , "160638" , "160639" , "160640" , "160643" , "161022" ,
        "161024" , "161025" , "161026" , "161027" , "161028" , "161029" , "161030" ,
        "161031" , "161032" , "161033" , "161116" , "161117" , "161118" , "161119" ,
        "161120" , "161121" , "161122" , "161123" , "161125" , "161126" , "161127" ,
        "161128" , "161129" , "161130" , "161131" , "161616" , "161715" , "161720" ,
        "161723" , "161725" , "161815" , "161819" , "161827" , "161831" , "162307" ,
        "162411" , "162509" , "162605" , "162607" , "162703" , "162907" , "163001" ,
        "163114" , "163208" , "163209" , "163406" , "163407" , "163412" , "164302" ,
        "164304" , "164402" , "164701" , "164702" , "164703" , "164818" , "164819" ,
        "164821" , "164824" , "164825" , "164902" , "164905" , "164906" , "165309" ,
        "165310" , "165311" , "165312" , "165508" , "165509" , "165511" , "165513" ,
        "165515" , "165516" , "165519" , "165520" , "165521" , "165522" , "165523" ,
        "165524" , "165525" , "165806" , "165810" , "166011" , "166801" , "167901" ,
        “168203”，“184801”，
        #上海LOF
        “501018”、“501021”、“501029”、“501030”、“501050”
    ]
    
    @staticmethod
    def  get_lof_codes () -> List [ str ]:
        """返回LOF基金代码列表"""
        返回SinaFinanceAPI.LOF_CODES
    
    @staticmethod
    def  get_realtime_quote ( codes: List [ str ] = None , batch_size: int = 50 ) -> pd.DataFrame:
        """
        获取实时行情（批量）
        
        参数：
            code: 基金代码列表，默认使用内置列表
            batch_size: 每批查询数量
        返回：
            DataFrame包含实时行情
        """
        如果codes为 None：
            codes = SinaFinanceAPI.LOF_CODES
        
        all_data = []
        
        # 分批查询
        for i in  range ( 0 , len (codes), batch_size):
            batch_codes = codes[i:i + batch_size]
            
            # 构建查询代码（基金海外：f_）
            query_codes = "," .join([ f"f_ {code} "  for code in batch_codes])
            url = f" {SinaFinanceAPI.BASE_URL} {query_codes} "
            
            尝试：
                response = requests.get(url, timeout= 10 )
                response.encoding = 'gbk'
                
                # 解析返回数据
                for line in response.text.strip().split( '\n' ):
                    如果 不是行或 “=” 不在行 中：
                        继续
                    
                    # 正则提取数据：var hq_str_f_160636="..."
                    match = re.search( r'var hq_str_f_(\d+)="(.+)";' , line)
                    如果 未 匹配：
                        继续
                    
                    code = match.group ( 1 )
                    data_str = match.group ( 2 )
                    
                    如果 data_str不是：
                        继续
                    
                    # 分割字段
                    fields = data_str.split( ',' )
                    
                    如果 字段数小于8：
                        继续
                    
                    尝试：
                        price = float (fields[ 1 ])如果fields[ 1 ]为真，否则为 0
                        pre_close = float (fields[ 2 ]) if fields[ 2 ] else  0
                        
                        如果价格 <= 0：
                            继续
                        
                        # 计算涨跌幅
                        change_pct = round (((price - pre_close) / pre_close * 100 ) if pre_close > 0  else  0 , 2 )
                        
                        all_data.append({
                            '代码'：代码，
                            '名称' : 字段[ 0 ],
                            '最新价' : 价格，
                            '去年收' : pre_close,
                            '今开' : float (fields[ 3 ]) if fields[ 3 ] else  0 ,
                            '最高' : float (fields[ 4 ]) if fields[ 4 ] else  0 ,
                            '最低' : float (fields[ 5 ]) if fields[ 5 ] else  0 ,
                            '成交量' : float (fields[ 6 ]) if fields[ 6 ] else  0 ,
                            '成交额' : float (fields[ 7 ]) if fields[ 7 ] else  0 ,
                            '涨跌幅' :change_pct
                        })
                    except (ValueError, IndexError) as e:
                        继续
                
                time.sleep( 0.1 )   # 避免请求过快
                
            除了requests.exceptions.Timeout 之外：
                logger.warning( f"⚠️ 新浪财经批次{i//batch_size + 1 }超时" )
                继续
            除异常e外：
                logger.warning( f"⚠️ 新浪财经批次{i//batch_size + 1 }失败: {e} " )
                继续
        
        如果 并非所有数据都存在：
            logger.warning( "⚠️ 新浪财经：未获取到任何数据" )
            返回pd.DataFrame()
        
        df = pd.DataFrame(all_data)
        logger.info( f"✅ 新浪财经：获取{ len (df)}只LOF行情" )
        返回数据框
    
    @staticmethod
    def  get_fund_nav ( code: str ) -> Optional [ Dict ]:
        """
        获取基金净值
        
        参数：
            代码：6位基金代码
        返回：
            dict: 净值信息
        """
        url = f"http://hq.sinajs.cn/list=f_{code } "
        
        尝试：
            response = requests.get(url, timeout= 5 )
            response.encoding = 'gbk'
            
            match = re.search( r'="(.+)"' , response.text)
            如果 未 匹配：
                返回 None
            
            fields = match.group ( 1 ).split( ',' )
            如果 len (fields) < 2 或 not fields[ 1 ]:
                返回 None
            
            nav = float (fields[ 1 ])
            如果nav <= 0：
                返回 None
            
            返回{
                'fund_code'：代码，
                '导航'：导航，
                'nav_date' : fields[ 8 ] if  len (fields) > 8  else  '' ,
                '估计'：0
            }
            
        除异常e外：
            logger.debug( f"⚠️ 新浪净值查询失败{code} : {e} " )
            返回 None


# ==================== 腾讯财经API ====================

class  ThustenfinanceAPI :
    """
    腾讯财经数据接口
    优势：数据较全，格式统一
    """
    
    BASE_URL = "http://qt.gtimg.cn/q="
    
    @staticmethod
    def  get_realtime_quote ( codes: List [ str ] = None ) -> pd.DataFrame:
        """
        获取实时行情
        
        参数：
            代码： 基金代码列表
        返回：
            数据框
        """
        如果codes为 None：
            codes = SinaFinanceAPI.LOF_CODES
        
        all_data = []
        
        # 腾讯支持一次查询多个
        批次大小 = 50
        
        for i in  range ( 0 , len (codes), batch_size):
            batch_codes = codes[i:i + batch_size]
            
            # 基金海外：of
            query_codes = "," .join([ f"of {code} "  for code in batch_codes])
            url = f" {TencentFinanceAPI.BASE_URL} {query_codes} "
            
            尝试：
                response = requests.get(url, timeout= 10 )
                response.encoding = 'gbk'
                
                for line in response.text.strip().split( '\n' ):
                    如果 不是行或行 中没有“~” ： 
                        继续
                    
                    # 腾讯数据格式：v_ofXXXXXX="字段1~字段2~...";
                    match = re.search( r'v_of(\d+)="(.+)";' , line)
                    如果 未 匹配：
                        继续
                    
                    code = match.group ( 1 )
                    fields = match.group ( 2 ).split( '~' )
                    
                    如果字段 数小于40：
                        继续
                    
                    尝试：
                        price = float (fields[ 3 ]) if fields[ 3 ] else  0
                        
                        如果价格 <= 0：
                            继续
                        
                        all_data.append({
                            '代码'：代码，
                            '名称' : 字段[ 1 ],
                            '最新价' : 价格，
                            '去年收' : float (fields[ 4 ]) if fields[ 4 ] else  0 ,
                            '今开' : float (fields[ 5 ]) if fields[ 5 ] else  0 ,
                            '成交量' : float (fields[ 6 ]) if fields[ 6 ] else  0 ,
                            '成交额' : float (fields[ 37 ]) if fields[ 37 ] else  0 ,
                            '涨跌幅' : float (fields[ 32 ]) if fields[ 32 ] else  0
                        })
                    除(ValueError, IndexError) 外：
                        继续
                
                time.sleep( 0.1 )
                
            除异常e外：
                logger.warning( f"⚠️ 腾讯财经批次失败: {e} " )
                继续
        
        如果 并非所有数据都存在：
            logger.warning( "⚠️腾讯财经：未获取到数据" )
            返回pd.DataFrame()
        
        df = pd.DataFrame(all_data)
        logger.info( f"✅ 腾讯财经：获取{ len (df)}只LOF行情" )
        返回数据框


# ==================== 东方财富 API（Akshare） ====================

 东钱API类：
    """
    东方财富接口数据（通过Akshare）
    优势：数据最全，但海外访问不稳定
    """
    
    @staticmethod
    def  get_lof_data () -> pd.DataFrame:
        """
        获取LOF场内行情
        
        返回：
            数据框
        """
        尝试：
            导入akshare为ak
            
            logger.info( "🔄 正在从东方财富获取LOF数据..." )
            df = ak.fund_lof_spot_em()
            
            如果df为 None 或df.empty：
                logger.warning( "⚠️东方财富：未获取到数据" )
                返回pd.DataFrame()
            
            logger.info( f"✅ 东方财富：获取{ len (df)}只LOF数据" )
            返回数据框
            
        异常ImportError：
            logger.error( "❌ Akshare 未安装" )
            返回pd.DataFrame()
        除异常e外：
            logger.error( f"❌东方财富查询失败: {e} " )
            返回pd.DataFrame()
    
    @staticmethod
    def  get_fund_nav ( code: str ) -> Optional [ Dict ]:
        """
        获取基金净值
        
        参数：
            代码： 基金代码
        返回：
            dict: 净值信息
        """
        尝试：
            导入akshare为ak
            
            df = ak.fund_etf_fund_info_em(fund=code, Indicator= "单位净值走势" )
            如果df为 None 或df.empty：
                返回 None
            
            latest = df.iloc[ -1 ]
            返回{
                'fund_code'：代码，
                'nav' : float (latest[ '单位净值' ]),
                'nav_date' : str (最新[ '净值日期' ]),
                'estimate' : float (latest.get( '日对应' , 0 ) or  0 )
            }
            
        除异常e外：
            logger.debug( f"⚠️ 东方财富净值查询失败{code} : {e} " )
            返回 None


# ====================多数据源聚合器====================

class  MultiSourceDataFetcher：
    """
    多数据源智能切换
    降级策略集思录 > 新浪 > 腾讯 > 东方财富
    """
    
    def  __init__ ( self ):
        self.sources = [
            ( '集思录' , self._fetch_jisilu),
            ( '新浪财经' , self._fetch_sina),
            ( '腾讯财经' , self._fetch_tencent),
            ( '东方财富' , self._fetch_eastmoney)
        ]
    
    def  get_lof_data_with_fallback ( self ) -> Optional [pd.DataFrame]:
        """
        按优先级获取LOF数据（带降级）
        
        返回：
            数据框或无
        """
        对于self.sources中的每个 source_name 和 fetch_func ：
            尝试：
                logger.info( f"🔄 尝试{source_name}数据源..." )
                
                df = fetch_func()
                
                如果df不为 None 且不 为 空：
                    logger.info( f"✅ 使用{source_name}数据源，获取{ len (df)}只LOF" )
                    返回数据框
                别的：
                    logger.warning( f"⚠️ {source_name}返回空数据" )
                    
            除异常e外：
                logger.warning( f"⚠️ {source_name}失败: {e} " )
                继续
        
        logger.error( "❌所有数据源均失败" )
        返回 None
    
    def  _fetch_jisilu ( self ) -> pd.DataFrame:
        """从集思录获取（已包含溢价率）"""
        返回JisiluAPI.get_lof_data()
    
    def  _fetch_sina ( self ) -> pd.DataFrame:
        """从新浪财经获取（需要后续计算溢价率）"""
        返回SinaFinanceAPI.get_realtime_quote()
    
    def  _fetch_tencent ( self ) -> pd.DataFrame:
        """从腾讯财经获取（需要后续计算溢价率）"""
        返回腾讯金融API.get_realtime_quote()
    
    def  _fetch_eastmoney ( self ) -> pd.DataFrame:
        """从东方财富获取（需要后续计算溢价率）"""
        返回EastmoneyAPI.get_lof_data()
    
    def  get_fund_nav ( self, code: str ) -> Optional [ Dict ]:
        """
        从多个来源获取基金净值（降级策略）
        
        参数：
            代码： 基金代码
        返回：
            dict: 净值信息
        """
        #1.尝试新浪
        nav_info = SinaFinanceAPI.get_fund_nav(code)
        如果nav_info 存在且nav_info.get( 'nav' , 0 ) > 0：
            返回导航信息
        
        # 2.尝试东方财富
        nav_info = EastmoneyAPI.get_fund_nav(code)
        如果nav_info 存在且nav_info.get( 'nav' , 0 ) > 0：
            返回导航信息
        
        返回 None

