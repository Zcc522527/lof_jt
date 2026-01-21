"""
LOF套利监控系统 Pro - Render 部署版
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import logging
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time

# ======================== Render 环境变量加载 ========================
# Render 会自动注入环境变量，无需 .env 文件

# 检查必要的环境变量
REQUIRED_ENV_VARS = {
    'SUPABASE_URL': os.environ.get('SUPABASE_URL'),
    'SUPABASE_KEY': os.environ.get('SUPABASE_KEY')
}

# 可选环境变量
OPTIONAL_ENV_VARS = {
    'PUSHPLUS_TOKEN': os.environ.get('PUSHPLUS_TOKEN')
}

# 日志配置检查
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 显示环境变量加载状态
logger.info("=" * 60)
logger.info("🚀 LOF套利监控系统启动中...")
logger.info("=" * 60)

for key, value in REQUIRED_ENV_VARS.items():
    if value:
        logger.info(f"✅ {key}: 已加载")
    else:
        logger.warning(f"⚠️ {key}: 未配置（部分功能受限）")

for key, value in OPTIONAL_ENV_VARS.items():
    if value:
        logger.info(f"✅ {key}: 已加载")
    else:
        logger.info(f"ℹ️ {key}: 未配置（可选功能）")

logger.info("=" * 60)

# 导入自定义模块（保持原有代码不变）
from database import SupabaseDB
from pusher import PushPlusNotifier
from akshare_sources import (
    get_lof_from_akshare,
    get_nav_from_akshare,
    akshare_multi,
    AKSHARE_AVAILABLE
)

# ... 后续代码保持不变 ...


# ======================== 配置日志 ========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ======================== 常量配置 ========================
CACHE_DIR = Path("/tmp/lof_cache")
MAX_WORKERS = 5
CACHE_EXPIRY_MINUTES = 10  # 缓存有效期（分钟）
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ======================== 初始化服务 ========================
db = SupabaseDB()
pusher = PushPlusNotifier()

# 检查 Akshare 可用性
if not AKSHARE_AVAILABLE:
    logger.error("❌ Akshare 模块未安装，系统无法运行")

# ======================== 页面配置 ========================
st.set_page_config(
    page_title="LOF套利监控系统 Pro",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================== 自定义样式 ========================
st.markdown("""
<style>
    /* 主题色 */
    :root {
        --primary-color: #667eea;
        --secondary-color: #764ba2;
        --success-color: #10b981;
        --warning-color: #f59e0b;
        --danger-color: #ef4444;
    }
    
    /* 标题样式 */
    .big-font {
        font-size: 20px !important;
        font-weight: bold;
        color: var(--primary-color);
    }
    
    /* 指标卡片 */
    .metric-card {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        padding: 1.5rem;
        border-radius: 0.75rem;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* 成功提示框 */
    .success-box {
        background-color: #d1fae5;
        border: 2px solid var(--success-color);
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    /* 警告提示框 */
    .warning-box {
        background-color: #fef3c7;
        border: 2px solid var(--warning-color);
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    /* 隐藏默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 表格样式优化 */
    .dataframe {
        font-size: 14px;
    }
    
    /* 按钮样式 */
    .stButton>button {
        border-radius: 0.5rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ======================== 工具函数 ========================

def get_cache_filename():
    """生成当日缓存文件名"""
    today = datetime.now().strftime("%Y%m%d")
    return CACHE_DIR / f"nav_cache_{today}.json"


def load_nav_cache():
    """加载净值缓存"""
    cache_file = get_cache_filename()
    if cache_file.exists():
        try:
            # 检查缓存时间
            file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            age = datetime.now() - file_time
            
            if age > timedelta(minutes=CACHE_EXPIRY_MINUTES):
                logger.info(f"⏰ 缓存已过期（{age.seconds // 60}分钟）")
                return {}
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ 缓存读取失败: {e}")
    return {}


def save_nav_cache(nav_dict):
    """保存净值缓存"""
    cache_file = get_cache_filename()
    try:
        serializable_data = {}
        for code, data in nav_dict.items():
            serializable_data[code] = {
                k: (str(v) if isinstance(v, (pd.Timestamp, datetime)) else v)
                for k, v in data.items()
            }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 缓存已保存")
    except Exception as e:
        logger.error(f"❌ 缓存保存失败: {e}")


# ======================== 核心数据获取函数 ========================

def get_lof_data():
    """
    获取LOF场内行情
    优先级：集思录（含溢价率） > 东方财富 > 天天基金
    
    Returns:
        DataFrame 或 None
    """
    if not AKSHARE_AVAILABLE:
        st.error("❌ Akshare 模块未安装，无法获取数据")
        logger.error("❌ Akshare 模块未安装")
        return None
    
    # 1. 优先使用集思录（已包含溢价率）
    logger.info("🔄 尝试从集思录获取LOF数据...")
    df = get_lof_from_akshare(source='jisilu')
    
    if df is not None and not df.empty:
        logger.info(f"✅ 使用集思录数据源：{len(df)} 只LOF（含溢价率）")
        return df
    
    # 2. 降级到东方财富
    logger.info("🔄 集思录失败，降级到东方财富...")
    df = get_lof_from_akshare(source='eastmoney')
    
    if df is not None and not df.empty:
        logger.info(f"✅ 使用东方财富数据源：{len(df)} 只LOF")
        return df
    
    # 3. 最后尝试天天基金
    logger.info("🔄 东方财富失败，尝试天天基金...")
    df = get_lof_from_akshare(source='tiantian')
    
    if df is not None and not df.empty:
        logger.info(f"✅ 使用天天基金数据源：{len(df)} 只LOF")
        return df
    
    logger.error("❌ 所有数据源均失败")
    return None


def fetch_single_nav(fund_code):
    """
    获取单只基金净值
    
    Args:
        fund_code: 基金代码
    Returns:
        dict 或 None
    """
    return get_nav_from_akshare(fund_code)


def fetch_all_nav_parallel(fund_codes, progress_bar, status_text):
    """
    并行获取净值（带缓存）
    
    Args:
        fund_codes: 基金代码列表
        progress_bar: 进度条组件
        status_text: 状态文本组件
    Returns:
        dict: {code: nav_info}
    """
    nav_cache = load_nav_cache()
    nav_dict = dict(nav_cache)
    
    # 过滤已缓存的代码
    codes_to_fetch = [code for code in fund_codes if code not in nav_cache]
    cached_count = len(nav_cache)
    total_count = len(fund_codes)
    
    logger.info(f"📊 缓存命中: {cached_count}/{total_count}")
    
    if not codes_to_fetch:
        progress_bar.progress(1.0)
        status_text.text(f"✅ 全部从缓存加载 ({cached_count} 只)")
        return nav_dict
    
    # 并行获取未缓存的净值
    completed = 0
    success = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_single_nav, code): code for code in codes_to_fetch}
        
        for future in as_completed(futures):
            completed += 1
            current = cached_count + completed
            progress = current / total_count
            progress_bar.progress(progress)
            status_text.text(f"正在获取净值... ({current}/{total_count})")
            
            result = future.result()
            if result:
                nav_dict[result['fund_code']] = result
                success += 1
            
            time.sleep(0.05)  # 小延迟，避免请求过快
    
    # 保存新获取的数据到缓存
    if success > 0:
        save_nav_cache(nav_dict)
    
    status_text.text(f"✅ 完成！成功: {cached_count + success}/{total_count}")
    return nav_dict


def calculate_premium(df_spot, nav_dict):
    """
    计算溢价率
    
    Args:
        df_spot: 场内行情数据
        nav_dict: 净值数据字典
    Returns:
        DataFrame: 包含溢价率的完整数据
    """
    data_list = []
    
    for _, row in df_spot.iterrows():
        code = str(row.get('基金代码', ''))
        nav_info = nav_dict.get(code)
        
        if not nav_info:
            continue
        
        try:
            price = float(row.get('场内价格', 0))
            nav = float(nav_info.get('nav', 0))
            
            if nav <= 0 or price <= 0:
                continue
            
            premium = ((price - nav) / nav) * 100
            volume = float(row.get('场内成交额(万)', 0))
            
            data_list.append({
                '基金代码': code,
                '基金名称': row.get('基金名称', ''),
                '场内价格': price,
                '基金净值': nav,
                '净值日期': nav_info.get('nav_date', ''),
                '场内成交额(万)': volume,
                '溢价率(%)': round(premium, 2)
            })
        except (ValueError, TypeError) as e:
            logger.debug(f"⚠️ 计算溢价率失败 {code}: {e}")
            continue
    
    df = pd.DataFrame(data_list)
    logger.info(f"✅ 计算 {len(df)} 只基金溢价率")
    return df


# ======================== 数据展示函数 ========================

def highlight_premium_level(row):
    """溢价率高亮显示"""
    premium = row['溢价率(%)']
    
    if premium >= 5:
        return ['background-color: #fee2e2; color: #991b1b; font-weight: bold'] * len(row)
    elif premium >= 3:
        return ['background-color: #fef3c7; color: #92400e'] * len(row)
    elif premium >= 1.5:
        return ['background-color: #dbeafe; color: #1e40af'] * len(row)
    else:
        return [''] * len(row)


def format_dataframe(df):
    """格式化数据表格"""
    return df.style.apply(highlight_premium_level, axis=1).format({
        '场内价格': '{:.3f}',
        '基金净值': '{:.4f}',
        '场内成交额(万)': '{:.2f}',
        '溢价率(%)': '{:.2f}'
    })


# ======================== 主程序 ========================

def main():
    """主程序入口"""
    
    # ============ 页面标题 ============
    st.title("💰 LOF套利监控系统 Pro")
    st.markdown("**🚀 Akshare 多数据源版：集思录 + 东方财富 + 天天基金**")
    
    # ============ 系统状态展示 ============
    with st.expander("🔍 系统状态", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📡 数据源状态")
            st.info("🥇 集思录（优先，含溢价率）")
            st.info("🥈 东方财富（备用）")
            st.info("🥉 天天基金（备用）")
            
            st.markdown("### 🔧 Akshare 状态")
            if AKSHARE_AVAILABLE:
                st.success("✅ Akshare 已安装并可用")
            else:
                st.error("❌ Akshare 未安装")
        
        with col2:
            st.markdown("### 🔐 环境变量")
            env_vars = {
                "SUPABASE_URL": os.environ.get("SUPABASE_URL"),
                "SUPABASE_KEY": os.environ.get("SUPABASE_KEY"),
                "PUSHPLUS_TOKEN": os.environ.get("PUSHPLUS_TOKEN")
            }
            
            for key, value in env_vars.items():
                if value:
                    st.success(f"✅ {key}: 已配置")
                else:
                    st.warning(f"⚠️ {key}: 未配置")
            
            st.markdown("### 💾 服务状态")
            db_status = "🟢 已连接" if db.is_connected() else "🔴 未连接"
            push_status = "🟢 已配置" if pusher.is_configured() else "🔴 未配置"
            
            st.markdown(f"**数据库**: {db_status}")
            st.markdown(f"**推送**: {push_status}")
            st.markdown(f"**并发线程**: {MAX_WORKERS}")
    
    # ============ 侧边栏配置 ============
    with st.sidebar:
        st.header("⚙️ 筛选参数")
        
        min_premium = st.slider(
            "最小溢价率 (%)",
            min_value=0.0,
            max_value=10.0,
            value=1.5,
            step=0.1,
            help="筛选溢价率大于等于此值的基金"
        )
        
        min_volume = st.slider(
            "最小成交额 (万元)",
            min_value=0,
            max_value=1000,
            value=50,
            step=10,
            help="筛选成交额大于等于此值的基金"
        )
        
        st.markdown("---")
        st.subheader("🔔 消息推送")
        
        enable_push = st.checkbox(
            "启用自动推送",
            value=pusher.is_configured(),
            disabled=not pusher.is_configured(),
            help="需要先配置 PushPlus Token"
        )
        
        push_threshold = st.number_input(
            "推送阈值 (%)",
            min_value=3.0,
            max_value=10.0,
            value=5.0,
            step=0.5,
            help="溢价率超过此值时自动推送"
        )
        
        if st.button("📤 测试推送", disabled=not pusher.is_configured()):
            test_data = [{
                '基金代码': '160636',
                '基金名称': '鹏华中证A股资源产业LOF',
                '场内价格': 1.500,
                '基金净值': 1.400,
                '溢价率(%)': 7.14,
                '场内成交额(万)': 100.0
            }]
            if pusher.send_arbitrage_alert(test_data):
                st.success("✅ 测试推送成功！")
            else:
                st.error("❌ 推送失败，请检查Token")
        
        st.markdown("---")
        st.subheader("💾 数据管理")
        
        # 数据库状态
        db_connected = db.is_connected()
        st.markdown(f"**数据库**: {'🟢 已连接' if db_connected else '🔴 未连接'}")
        
        if db_connected:
            if st.button("📊 保存到数据库", use_container_width=True):
                st.session_state.save_to_db = True
        
        # 缓存管理
        cache_files = list(CACHE_DIR.glob("*.json"))
        st.markdown(f"**缓存文件**: {len(cache_files)} 个")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 刷新", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("🗑️ 清缓存", use_container_width=True):
                cache_file = get_cache_filename()
                if cache_file.exists():
                    cache_file.unlink()
                st.success("✅ 缓存已清除")
                time.sleep(1)
                st.rerun()
        
        st.markdown("---")
        st.caption(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        st.caption(f"🔢 版本: v3.0.0")
    
    # ============ 检查依赖 ============
    if not AKSHARE_AVAILABLE:
        st.error("❌ Akshare 模块未安装")
        st.code("pip install akshare", language="bash")
        st.stop()
    
    # ============ 主界面数据获取 ============
    
    # 进度显示
    progress_bar = st.progress(0.0)
    status_text = st.empty()
    
    # 获取LOF数据
    status_text.text("🔄 正在获取LOF行情数据...")
    
    with st.spinner("正在连接数据源（支持多数据源自动降级）..."):
        df_spot = get_lof_data()
    
    if df_spot is None or df_spot.empty:
        st.error("❌ 无法获取LOF行情数据")
        st.warning("""
        **可能的原因：**
        1. 🌐 所有数据源暂时不可用
        2. 🚫 网络连接问题
        3. ⏱️ 非交易时段（周末/节假日数据更新延迟）
        
        **建议操作：**
        - 🔄 点击侧边栏"刷新"按钮重试
        - ⏰ 等待几分钟后再试
        - 🔍 查看"系统状态"了解详情
        """)
        progress_bar.empty()
        status_text.empty()
        return
    
    progress_bar.progress(0.2)
    status_text.text(f"✅ 获取到 {len(df_spot)} 只LOF数据")
    
    # 检查是否已包含溢价率
    has_premium = '溢价率(%)' in df_spot.columns
    
    if has_premium:
        # 数据已包含溢价率（集思录数据源）
        logger.info("✅ 数据源已包含溢价率，跳过净值查询")
        df_full = df_spot.copy()
        
        progress_bar.progress(1.0)
        status_text.text("✅ 数据已就绪（已包含溢价率）")
        
    else:
        # 需要获取净值并计算溢价率
        logger.info("⚠️ 数据源不含溢价率，开始获取净值...")
        status_text.text("正在获取基金净值数据...")
        
        # 提取基金代码
        code_column = '基金代码' if '基金代码' in df_spot.columns else '代码'
        fund_codes = df_spot[code_column].astype(str).tolist()
        
        progress_bar.progress(0.3)
        
        # 获取净值
        nav_dict = fetch_all_nav_parallel(fund_codes, progress_bar, status_text)
        
        # 计算溢价率
        df_full = calculate_premium(df_spot, nav_dict)
        
        if df_full.empty:
            st.warning("⚠️ 无法计算溢价率（所有基金净值获取失败）")
            st.info("💡 建议：点击侧边栏的'清缓存'按钮，然后刷新页面重试")
            progress_bar.empty()
            status_text.empty()
            return
    
    # 清除进度显示
    progress_bar.empty()
    status_text.empty()
    
    # ============ 数据筛选 ============
    
    # 按条件筛选
    df_filtered = df_full[
        (df_full['溢价率(%)'] >= min_premium) &
        (df_full['场内成交额(万)'] >= min_volume)
    ].sort_values('溢价率(%)', ascending=False).reset_index(drop=True)
    
    # 鸡腿机会（溢价率≥5%）
    df_chicken = df_full[
        df_full['溢价率(%)'] >= 5
    ].sort_values('溢价率(%)', ascending=False).reset_index(drop=True)
    
    # ============ 数据库保存 ============
    if hasattr(st.session_state, 'save_to_db') and st.session_state.save_to_db:
        with st.spinner("正在保存到数据库..."):
            data_to_save = df_full.to_dict('records')
            if db.save_premium_data(data_to_save):
                st.success(f"✅ 已保存 {len(data_to_save)} 条数据到 Supabase")
            else:
                st.error("❌ 数据保存失败")
        st.session_state.save_to_db = False
    
    # ============ 自动推送 ============
    if enable_push and not df_chicken.empty:
        # 获取今日已推送记录
        today_alerts = db.get_today_alerts() if db.is_connected() else []
        already_pushed_codes = {alert['fund_code'] for alert in today_alerts}
        
        # 筛选新的机会
        new_chickens = df_chicken[
            ~df_chicken['基金代码'].isin(already_pushed_codes)
        ]
        
        # 如果有新机会且数量>=3，推送
        if not new_chickens.empty and len(new_chickens) >= 3:
            with st.spinner("正在推送套利机会..."):
                opportunities = new_chickens.head(10).to_dict('records')
                
                if pusher.send_arbitrage_alert(opportunities):
                    st.success(f"✅ 已推送 {len(opportunities)} 个鸡腿机会")
                    
                    # 记录推送
                    for opp in opportunities:
                        db.save_alert_record(
                            fund_code=opp['基金代码'],
                            fund_name=opp['基金名称'],
                            premium_rate=opp['溢价率(%)'],
                            alert_type='chicken',
                            push_status='success'
                        )
                else:
                    st.warning("⚠️ 消息推送失败")
    
    # ============ 数据概览卡片 ============
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📊 总LOF数量",
            value=f"{len(df_full)}",
            help="当前数据源获取到的LOF总数"
        )
    
    with col2:
        st.metric(
            label="✅ 符合筛选条件",
            value=f"{len(df_filtered)}",
            delta=f"溢价≥{min_premium}%",
            help=f"溢价率≥{min_premium}% 且 成交额≥{min_volume}万"
        )
    
    with col3:
        chicken_count = len(df_chicken)
        st.metric(
            label="🍗 鸡腿机会",
            value=f"{chicken_count}",
            delta="溢价≥5%" if chicken_count > 0 else None,
            delta_color="normal" if chicken_count > 0 else "off",
            help="溢价率≥5%的高溢价机会"
        )
    
    with col4:
        max_premium = df_full['溢价率(%)'].max() if not df_full.empty else 0
        st.metric(
            label="📈 最高溢价率",
            value=f"{max_premium:.2f}%",
            help="当前市场最高溢价率"
        )
    
    st.markdown("---")
    
    # ============ Tab 分页展示 ============
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 套利机会",
        "🍗 鸡腿专区",
        "📋 全量数据",
        "📊 数据分析"
    ])
    
    # ============ Tab 1: 筛选结果 ============
    with tab1:
        st.subheader(f"🎯 套利机会筛选")
        st.caption(f"筛选条件: 溢价率 ≥ {min_premium}%，成交额 ≥ {min_volume} 万元")
        
        if df_filtered.empty:
            st.info("📭 当前无符合条件的套利机会")
            st.markdown("""
            **建议：**
            - 📉 调低筛选条件（溢价率或成交额）
            - 🔄 等待市场波动
            - 📊 查看"全量数据"了解整体情况
            """)
        else:
            # 显示数据表
            st.dataframe(
                format_dataframe(df_filtered),
                use_container_width=True,
                height=500
            )
            
            # 统计信息
            col1, col2, col3 = st.columns(3)
            with col1:
                avg_premium = df_filtered['溢价率(%)'].mean()
                st.metric("平均溢价率", f"{avg_premium:.2f}%")
            with col2:
                total_volume = df_filtered['场内成交额(万)'].sum()
                st.metric("总成交额", f"{total_volume:,.0f} 万")
            with col3:
                median_premium = df_filtered['溢价率(%)'].median()
                st.metric("中位数溢价率", f"{median_premium:.2f}%")
            
            # 导出按钮
            csv = df_filtered.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 导出筛选数据 (CSV)",
                data=csv,
                file_name=f"lof_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    # ============ Tab 2: 鸡腿专区 ============
    with tab2:
        st.subheader(f"🍗 鸡腿机会专区")
        st.caption(f"溢价率 ≥ 5% 的高溢价机会（共 {len(df_chicken)} 只）")
        
        if df_chicken.empty:
            st.info("📭 当前无鸡腿机会（溢价率≥5%）")
            st.markdown("""
            **什么是鸡腿机会？**
            - 💰 溢价率达到 5% 以上
            - 🎯 套利空间较大
            - ⚡ 适合快速操作
            
            **当前建议：**
            - 📊 查看"套利机会"了解较低溢价的基金
            - ⏰ 耐心等待市场波动
            - 🔔 开启自动推送，第一时间获知机会
            """)
        else:
            # 显示鸡腿数据
            st.dataframe(
                format_dataframe(df_chicken),
                use_container_width=True,
                height=500
            )
            
            # 统计信息
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                avg_premium = df_chicken['溢价率(%)'].mean()
                st.metric("平均溢价率", f"{avg_premium:.2f}%")
            
            with col2:
                total_volume = df_chicken['场内成交额(万)'].sum()
                st.metric("总成交额", f"{total_volume:,.0f} 万")
            
            with col3:
                max_chicken = df_chicken['溢价率(%)'].max()
                st.metric("最高溢价", f"{max_chicken:.2f}%")
            
            with col4:
                high_liquidity = len(df_chicken[df_chicken['场内成交额(万)'] >= 100])
                st.metric("高流动性", f"{high_liquidity} 只", 
                         delta="成交≥100万" if high_liquidity > 0 else None)
            
            st.markdown("---")
            
            # 操作按钮
            col1, col2 = st.columns(2)
            
            with col1:
                # 导出CSV
                csv_chicken = df_chicken.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 导出鸡腿数据 (CSV)",
                    data=csv_chicken,
                    file_name=f"lof_chicken_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                # 一键推送
                if pusher.is_configured():
                    if st.button("📤 立即推送鸡腿机会", use_container_width=True):
                        opportunities = df_chicken.head(10).to_dict('records')
                        with st.spinner("正在推送..."):
                            if pusher.send_arbitrage_alert(opportunities):
                                st.success("✅ 推送成功！")
                            else:
                                st.error("❌ 推送失败")
                else:
                    st.button("📤 推送（未配置）", disabled=True, use_container_width=True)
            
            # 风险提示
            st.markdown("---")
            st.warning("""
            **⚠️ 风险提示**
            - 溢价率会随市场波动变化
            - 套利需考虑交易成本（手续费、冲击成本等）
            - 注意基金申购赎回状态
            - 关注折溢价收敛速度
            - 本系统仅供参考，不构成投资建议
            """)
    
    # ============ Tab 3: 全量数据 ============
    with tab3:
        st.subheader(f"📋 全量LOF数据")
        st.caption(f"共 {len(df_full)} 只LOF基金")
        
        # 排序选项
        col1, col2 = st.columns([2, 1])
        with col1:
            sort_by = st.selectbox(
                "排序方式",
                options=['溢价率(%)', '场内成交额(万)', '场内价格', '基金净值'],
                index=0
            )
        with col2:
            sort_order = st.radio(
                "排序",
                options=['降序', '升序'],
                horizontal=True,
                index=0
            )
        
        # 应用排序
        df_full_sorted = df_full.sort_values(
            sort_by,
            ascending=(sort_order == '升序')
        ).reset_index(drop=True)
        
        # 显示数据
        st.dataframe(
            format_dataframe(df_full_sorted),
            use_container_width=True,
            height=500
        )
        
        # 统计摘要
        st.markdown("---")
        st.markdown("### 📊 数据统计摘要")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**溢价率分布**")
            premium_ranges = {
                '折价(<0%)': len(df_full[df_full['溢价率(%)'] < 0]),
                '0-1%': len(df_full[(df_full['溢价率(%)'] >= 0) & (df_full['溢价率(%)'] < 1)]),
                '1-3%': len(df_full[(df_full['溢价率(%)'] >= 1) & (df_full['溢价率(%)'] < 3)]),
                '3-5%': len(df_full[(df_full['溢价率(%)'] >= 3) & (df_full['溢价率(%)'] < 5)]),
                '≥5%': len(df_full[df_full['溢价率(%)'] >= 5])
            }
            
            for range_name, count in premium_ranges.items():
                percentage = (count / len(df_full) * 100) if len(df_full) > 0 else 0
                st.text(f"{range_name}: {count} 只 ({percentage:.1f}%)")
        
        with col2:
            st.markdown("**成交额分布**")
            volume_ranges = {
                '<10万': len(df_full[df_full['场内成交额(万)'] < 10]),
                '10-50万': len(df_full[(df_full['场内成交额(万)'] >= 10) & (df_full['场内成交额(万)'] < 50)]),
                '50-100万': len(df_full[(df_full['场内成交额(万)'] >= 50) & (df_full['场内成交额(万)'] < 100)]),
                '100-500万': len(df_full[(df_full['场内成交额(万)'] >= 100) & (df_full['场内成交额(万)'] < 500)]),
                '≥500万': len(df_full[df_full['场内成交额(万)'] >= 500])
            }
            
            for range_name, count in volume_ranges.items():
                percentage = (count / len(df_full) * 100) if len(df_full) > 0 else 0
                st.text(f"{range_name}: {count} 只 ({percentage:.1f}%)")
        
        # 导出按钮
        st.markdown("---")
        csv_full = df_full_sorted.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 导出全量数据 (CSV)",
            data=csv_full,
            file_name=f"lof_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    # ============ Tab 4: 数据分析 ============
    with tab4:
        st.subheader("📊 数据分析与历史查询")
        
        if not db.is_connected():
            st.warning("⚠️ 数据库未连接，无法显示历史分析")
            st.info("""
            **配置步骤：**
            1. 注册 Supabase 账号：https://supabase.com
            2. 创建项目并获取 URL 和 Key
            3. 在 Hugging Face Settings → Secrets 中添加：
               - SUPABASE_URL
               - SUPABASE_KEY
            """)
        else:
            # ====== 今日推送记录 ======
            st.markdown("### 📤 今日推送记录")
            today_alerts = db.get_today_alerts()
            
            if today_alerts:
                alert_df = pd.DataFrame(today_alerts)
                
                # 选择显示的列
                display_cols = ['fund_code', 'fund_name', 'premium_rate', 
                               'alert_type', 'push_status', 'created_at']
                available_cols = [col for col in display_cols if col in alert_df.columns]
                
                if available_cols:
                    st.dataframe(
                        alert_df[available_cols].rename(columns={
                            'fund_code': '基金代码',
                            'fund_name': '基金名称',
                            'premium_rate': '溢价率(%)',
                            'alert_type': '提醒类型',
                            'push_status': '推送状态',
                            'created_at': '推送时间'
                        }),
                        use_container_width=True
                    )
                else:
                    st.dataframe(alert_df, use_container_width=True)
            else:
                st.info("📭 今日暂无推送记录")
            
            st.markdown("---")
            
            # ====== TOP溢价基金历史 ======
            st.markdown("### 🏆 历史高溢价 TOP10")
            top_premiums = db.get_top_premiums(limit=10)
            
            if top_premiums:
                top_df = pd.DataFrame(top_premiums)
                
                # 标准化列名
                column_mapping = {
                    'fund_code': '基金代码',
                    'fund_name': '基金名称',
                    'premium_rate': '溢价率(%)',
                    'market_price': '场内价格',
                    'nav': '基金净值',
                    'volume': '成交额(万)',
                    'record_time': '记录时间'
                }
                
                # 重命名存在的列
                rename_dict = {k: v for k, v in column_mapping.items() if k in top_df.columns}
                top_df = top_df.rename(columns=rename_dict)
                
                # 显示数据
                display_cols = ['基金代码', '基金名称', '溢价率(%)', '场内价格', '基金净值', '记录时间']
                available_cols = [col for col in display_cols if col in top_df.columns]
                
                st.dataframe(
                    top_df[available_cols],
                    use_container_width=True
                )
            else:
                st.info("📭 暂无历史数据")
            
            st.markdown("---")
            
            # ====== 单只基金历史查询 ======
            st.markdown("### 🔍 单只基金历史溢价查询")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                search_code = st.text_input(
                    "输入基金代码",
                    placeholder="例如: 160636",
                    help="输入6位基金代码查询历史溢价数据"
                )
            
            with col2:
                search_days = st.number_input(
                    "查询天数",
                    min_value=1,
                    max_value=30,
                    value=7,
                    help="查询最近N天的历史数据"
                )
            
            if search_code:
                with st.spinner(f"正在查询 {search_code} 的历史数据..."):
                    history = db.get_premium_history(search_code, days=search_days)
                
                if history:
                    hist_df = pd.DataFrame(history)
                    
                    # 标准化列名
                    hist_df = hist_df.rename(columns={
                        'premium_rate': '溢价率(%)',
                        'market_price': '场内价格',
                        'nav': '基金净值',
                        'volume': '成交额(万)',
                        'record_time': '记录时间'
                    })
                    
                    # 确保时间列存在且格式正确
                    if '记录时间' in hist_df.columns:
                        hist_df['记录时间'] = pd.to_datetime(hist_df['记录时间'])
                        
                        # 绘制折线图
                        st.markdown("**📈 溢价率趋势图**")
                        st.line_chart(
                            hist_df.set_index('记录时间')['溢价率(%)'],
                            use_container_width=True
                        )
                    
                    # 显示数据表
                    st.markdown("**📋 历史数据明细**")
                    display_cols = ['记录时间', '溢价率(%)', '场内价格', '基金净值', '成交额(万)']
                    available_cols = [col for col in display_cols if col in hist_df.columns]
                    
                    st.dataframe(
                        hist_df[available_cols],
                        use_container_width=True
                    )
                    
                    # 统计信息
                    st.markdown("**📊 统计摘要**")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        max_prem = hist_df['溢价率(%)'].max()
                        st.metric("最高溢价", f"{max_prem:.2f}%")
                    
                    with col2:
                        min_prem = hist_df['溢价率(%)'].min()
                        st.metric("最低溢价", f"{min_prem:.2f}%")
                    
                    with col3:
                        avg_prem = hist_df['溢价率(%)'].mean()
                        st.metric("平均溢价", f"{avg_prem:.2f}%")
                    
                    with col4:
                        std_prem = hist_df['溢价率(%)'].std()
                        st.metric("波动率(标准差)", f"{std_prem:.2f}%")
                    
                else:
                    st.info(f"📭 未找到基金 {search_code} 的历史数据")
            
            st.markdown("---")
            
            # ====== 数据源对比 ======
            st.markdown("### 🔬 数据源对比分析")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                compare_code = st.text_input(
                    "输入基金代码对比数据源",
                    placeholder="例如: 160636",
                    key="compare_code_input"
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                compare_btn = st.button("🔍 开始对比", use_container_width=True)
            
            if compare_btn and compare_code:
                with st.spinner("正在对比多个数据源..."):
                    comparison_df = akshare_multi.compare_sources(compare_code)
                    
                    if not comparison_df.empty:
                        st.markdown("**数据源对比结果**")
                        st.dataframe(comparison_df, use_container_width=True)
                        
                        # 显示详细信息
                        detail = akshare_multi.get_fund_info_detail(compare_code)
                        
                        st.markdown("**基金详细信息**")
                        detail_display = {
                            '基金代码': detail.get('fund_code', '-'),
                            '基金名称': detail.get('fund_name', '-'),
                            '基金类型': detail.get('fund_type', '-'),
                            '基金管理人': detail.get('manager', '-'),
                            '成立日期': detail.get('setup_date', '-'),
                            '当前净值': detail.get('nav', '-'),
                            '净值日期': detail.get('nav_date', '-'),
                            '数据来源': ', '.join(detail.get('source', []))
                        }
                        
                        st.json(detail_display)
                    else:
                        st.warning("⚠️ 未找到对比数据，请检查基金代码是否正确")
    
    # ============ 页脚信息 ============
    st.markdown("---")
    
    footer_col1, footer_col2, footer_col3, footer_col4 = st.columns(4)
    
    with footer_col1:
        st.caption(f"🕐 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    with footer_col2:
        db_icon = "🟢" if db.is_connected() else "🔴"
        st.caption(f"💾 数据库: {db_icon}")
    
    with footer_col3:
        push_icon = "🟢" if pusher.is_configured() else "🔴"
        st.caption(f"📤 推送: {push_icon}")
    
    with footer_col4:
        st.caption(f"📊 数据: {len(df_full)}/{len(df_spot)} 只")
    
    # 版权信息
    st.markdown("---")
    st.caption("""
    💡 **LOF套利监控系统 Pro v3.0.0** | 
    Powered by Akshare + Streamlit | 
    ⚠️ 本系统仅供学习参考，不构成投资建议
    """)


# ======================== 程序入口 ========================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ 程序运行出错: {e}")
        st.error(f"❌ 系统错误: {e}")
        st.exception(e)
