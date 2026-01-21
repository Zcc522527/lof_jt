"""
PushPlus 消息推送封装
官网：https://www.pushplus.plus/
"""

import logging
import requests
from typing import List, Dict, Optional
import streamlit as st

logger = logging.getLogger(__name__)


class PushPlusNotifier:
    """PushPlus 推送通知类"""
    
    API_URL = "http://www.pushplus.plus/send"
    
    def __init__(self, token: str = None):
        """
        初始化推送器
        
        Args:
            token: PushPlus Token
        """
        self.token = token or st.secrets.get("pushplus", {}).get("token")
        
        if not self.token:
            logger.warning("⚠️ PushPlus Token 未配置")
    
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.token)
    
    def send_message(self, title: str, content: str, 
                    template: str = "html", 
                    topic: str = None) -> bool:
        """
        发送消息
        
        Args:
            title: 消息标题
            content: 消息内容（支持HTML）
            template: 模板类型（html/txt/json/markdown）
            topic: 群组编码（一对多推送）
        Returns:
            bool: 是否成功
        """
        if not self.is_configured():
            logger.warning("⚠️ PushPlus 未配置，无法推送")
            return False
        
        try:
            data = {
                'token': self.token,
                'title': title,
                'content': content,
                'template': template
            }
            
            if topic:
                data['topic'] = topic
            
            response = requests.post(self.API_URL, json=data, timeout=10)
            result = response.json()
            
            if result.get('code') == 200:
                logger.info(f"✅ 推送成功: {title}")
                return True
            else:
                logger.error(f"❌ 推送失败: {result.get('msg')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 推送异常: {e}")
            return False
    
    def send_arbitrage_alert(self, opportunities: List[Dict]) -> bool:
        """
        发送套利机会提醒
        
        Args:
            opportunities: 套利机会列表
        Returns:
            bool: 是否成功
        """
        if not opportunities:
            return False
        
        # 构建HTML消息
        title = f"🍗 LOF套利提醒：发现 {len(opportunities)} 个鸡腿机会！"
        
        content = f"""
        <h2>💰 LOF高溢价套利机会</h2>
        <p>🕐 时间：{self._get_current_time()}</p>
        <p>📊 共发现 <strong>{len(opportunities)}</strong> 个溢价≥5%的机会</p>
        <hr>
        """
        
        # 添加基金列表
        for i, item in enumerate(opportunities[:10], 1):  # 最多10个
            content += f"""
            <div style="margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 5px;">
                <h3 style="margin: 0;">#{i} {item['基金名称']}</h3>
                <p style="margin: 5px 0;">
                    <strong>代码：</strong>{item['基金代码']}<br>
                    <strong>场内价格：</strong>{item['场内价格']:.3f}<br>
                    <strong>基金净值：</strong>{item['基金净值']:.4f}<br>
                    <strong style="color: red; font-size: 1.2em;">溢价率：{item['溢价率(%)']:.2f}%</strong><br>
                    <strong>成交额：</strong>{item['场内成交额(万)']:.2f}万
                </p>
            </div>
            """
        
        if len(opportunities) > 10:
            content += f"<p>... 还有 {len(opportunities) - 10} 个机会未显示</p>"
        
        content += """
        <hr>
        <p style="color: #666; font-size: 0.9em;">
            ⚠️ 风险提示：套利有风险，投资需谨慎。请结合申购状态、赎回时间等综合判断。
        </p>
        """
        
        return self.send_message(title, content, template="html")
    
    def send_daily_summary(self, total_count: int, premium_count: int, 
                          max_premium: float, top_funds: List[Dict]) -> bool:
        """
        发送每日汇总
        
        Args:
            total_count: 总基金数
            premium_count: 高溢价数量
            max_premium: 最高溢价率
            top_funds: TOP基金列表
        Returns:
            bool: 是否成功
        """
        title = f"📊 LOF套利日报 - {self._get_current_date()}"
        
        content = f"""
        <h2>📈 LOF市场每日汇总</h2>
        <p>🕐 时间：{self._get_current_time()}</p>
        <hr>
        
        <h3>📊 市场概况</h3>
        <ul>
            <li>总LOF数量：<strong>{total_count}</strong></li>
            <li>鸡腿机会（≥5%）：<strong>{premium_count}</strong></li>
            <li>最高溢价率：<strong style="color: red;">{max_premium:.2f}%</strong></li>
        </ul>
        
        <h3>🏆 TOP 5 高溢价基金</h3>
        """
        
        for i, fund in enumerate(top_funds[:5], 1):
            content += f"""
            <p>
                <strong>{i}. {fund['基金名称']}</strong> ({fund['基金代码']})<br>
                溢价率：<span style="color: red; font-size: 1.1em;">{fund['溢价率(%)']:.2f}%</span>
            </p>
            """
        
        content += """
        <hr>
        <p style="color: #666;">💡 提示：及时关注申购状态变化</p>
        """
        
        return self.send_message(title, content, template="html")
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def _get_current_date(self) -> str:
        """获取当前日期字符串"""
        from datetime import datetime
        return datetime.now().strftime('%Y年%m月%d日')
