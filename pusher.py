"""
PushPlus 消息推送封装 - Render 部署版
官网：https://www.pushplus.plus/
功能：微信消息推送、套利提醒、日报推送
版本：v3.0.0 - Render Optimized
"""

import logging
import requests
import os
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ==================== 推送管理类 ====================

class PushPlusNotifier:
    """
    PushPlus 推送通知类
    
    功能：
    1. LOF套利机会推送
    2. 每日市场汇总
    3. 自定义消息推送
    
    环境变量：
    - PUSHPLUS_TOKEN: PushPlus 用户Token
    """
    
    API_URL = "http://www.pushplus.plus/send"
    
    def __init__(self, token: str = None):
        """
        初始化推送器
        
        Args:
            token: PushPlus Token（可选，默认从环境变量读取）
        """
        # 优先级：参数 > 环境变量
        self.token = (
            token or 
            os.environ.get("PUSHPLUS_TOKEN") or 
            os.getenv("PUSHPLUS_TOKEN")
        )
        
        # 调试日志
        logger.info("=" * 60)
        logger.info("🔍 PushPlus 推送配置检查:")
        
        if self.token:
            logger.info(f"   PUSHPLUS_TOKEN: ✅ 已设置 (长度={len(self.token)})")
            # 显示Token前缀（安全）
            token_prefix = self.token[:15] + "..." if len(self.token) > 15 else self.token
            logger.info(f"   TOKEN 前缀: {token_prefix}")
        else:
            logger.info("   PUSHPLUS_TOKEN: ❌ 未设置")
            logger.info("💡 推送功能不可用，如需启用请在 Render Dashboard 配置")
        
        logger.info("=" * 60)
        
        if not self.token:
            logger.warning("⚠️ PushPlus Token 未配置，推送功能将被禁用")
    
    def is_configured(self) -> bool:
        """
        检查推送是否已配置
        
        Returns:
            bool: True=已配置，False=未配置
        """
        return bool(self.token)
    
    def send_message(self, title: str, content: str, 
                    template: str = "html", 
                    topic: str = None,
                    channel: str = "wechat") -> bool:
        """
        发送消息
        
        Args:
            title: 消息标题
            content: 消息内容
            template: 消息模板（html/txt/json/markdown）
            topic: 群组主题（可选）
            channel: 发送渠道（wechat/mail/webhook）
        
        Returns:
            bool: True=成功，False=失败
        """
        if not self.is_configured():
            logger.warning("⚠️ PushPlus 未配置，无法推送消息")
            return False
        
        try:
            # 构建请求数据
            data = {
                'token': self.token,
                'title': title,
                'content': content,
                'template': template,
                'channel': channel
            }
            
            # 可选参数
            if topic:
                data['topic'] = topic
            
            # 发送请求
            response = requests.post(
                self.API_URL, 
                json=data, 
                timeout=10
            )
            
            # 解析响应
            result = response.json()
            
            if result.get('code') == 200:
                logger.info(f"✅ 推送成功: {title}")
                return True
            else:
                error_msg = result.get('msg', '未知错误')
                logger.error(f"❌ 推送失败: {error_msg}")
                logger.debug(f"完整响应: {result}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ 推送请求超时")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 推送网络错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 推送异常: {e}")
            logger.debug(f"详细错误: {type(e).__name__}: {str(e)}")
            return False
    
    def send_arbitrage_alert(self, opportunities: List[Dict]) -> bool:
        """
        发送套利机会提醒
        
        Args:
            opportunities: 套利机会列表，每条包含：
                - 基金代码 (fund_code)
                - 基金名称 (fund_name)
                - 场内价格 (market_price)
                - 基金净值 (nav)
                - 溢价率 (premium_rate)
                - 成交额 (volume)
        
        Returns:
            bool: True=成功，False=失败
        """
        if not opportunities:
            logger.warning("⚠️ 没有套利机会需要推送")
            return False
        
        # 构建标题
        title = f"🍗 LOF套利提醒：发现 {len(opportunities)} 个鸡腿机会！"
        
        # 构建HTML内容
        content = self._build_arbitrage_html(opportunities)
        
        return self.send_message(title, content, template="html")
    
    def _build_arbitrage_html(self, opportunities: List[Dict]) -> str:
        """
        构建套利机会HTML消息
        
        Args:
            opportunities: 套利机会列表
        
        Returns:
            str: HTML内容
        """
        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .header h2 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .summary {{
                    background: #f0f9ff;
                    border-left: 4px solid #3b82f6;
                    padding: 15px;
                    margin-bottom: 20px;
                    border-radius: 4px;
                }}
                .fund-card {{
                    background: white;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 15px;
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                }}
                .fund-card h3 {{
                    margin: 0 0 10px 0;
                    color: #1f2937;
                    font-size: 18px;
                }}
                .fund-info {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 10px;
                }}
                .info-item {{
                    padding: 8px;
                    background: #f9fafb;
                    border-radius: 4px;
                }}
                .info-label {{
                    font-size: 12px;
                    color: #6b7280;
                    margin-bottom: 4px;
                }}
                .info-value {{
                    font-size: 16px;
                    font-weight: bold;
                    color: #111827;
                }}
                .premium {{
                    color: #dc2626;
                    font-size: 20px !important;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    text-align: center;
                    color: #6b7280;
                    font-size: 14px;
                }}
                .warning {{
                    background: #fef3c7;
                    border-left: 4px solid #f59e0b;
                    padding: 15px;
                    margin-top: 20px;
                    border-radius: 4px;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>💰 LOF套利机会提醒</h2>
            </div>
            
            <div class="summary">
                <strong>🕐 推送时间：</strong>{self._get_current_time()}<br>
                <strong>📊 机会数量：</strong>{len(opportunities)} 个<br>
                <strong>🎯 筛选条件：</strong>溢价率 ≥ 5%
            </div>
        """
        
        # 添加基金列表（最多显示10个）
        for i, item in enumerate(opportunities[:10], 1):
            fund_code = item.get('基金代码', item.get('fund_code', ''))
            fund_name = item.get('基金名称', item.get('fund_name', ''))
            price = item.get('场内价格', item.get('market_price', 0))
            nav = item.get('基金净值', item.get('nav', 0))
            premium = item.get('溢价率(%)', item.get('premium_rate', 0))
            volume = item.get('场内成交额(万)', item.get('volume', 0))
            
            html += f"""
            <div class="fund-card">
                <h3>#{i} {fund_name}</h3>
                <div class="fund-info">
                    <div class="info-item">
                        <div class="info-label">基金代码</div>
                        <div class="info-value">{fund_code}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">溢价率</div>
                        <div class="info-value premium">{premium:.2f}%</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">场内价格</div>
                        <div class="info-value">{price:.3f}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">基金净值</div>
                        <div class="info-value">{nav:.4f}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">成交额</div>
                        <div class="info-value">{volume:.2f} 万</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">价差</div>
                        <div class="info-value">{(price - nav):.4f}</div>
                    </div>
                </div>
            </div>
            """
        
        # 如果超过10个，显示提示
        if len(opportunities) > 10:
            html += f"""
            <div style="text-align: center; padding: 15px; color: #6b7280;">
                ... 还有 {len(opportunities) - 10} 个机会未显示
            </div>
            """
        
        # 添加风险提示
        html += """
            <div class="warning">
                ⚠️ <strong>风险提示</strong><br>
                • 套利有风险，投资需谨慎<br>
                • 请结合申购赎回状态、交易成本等综合判断<br>
                • 溢价率会随市场波动，建议及时操作<br>
                • 本系统仅供参考，不构成投资建议
            </div>
        """
        
        # 添加页脚
        html += f"""
            <div class="footer">
                <p>LOF套利监控系统 Pro v3.0.0</p>
                <p>Powered by Akshare + Streamlit</p>
                <p style="font-size: 12px; color: #9ca3af;">
                    {self._get_current_date()}
                </p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_daily_summary(self, total_count: int, premium_count: int, 
                          max_premium: float, top_funds: List[Dict]) -> bool:
        """
        发送每日市场汇总
        
        Args:
            total_count: LOF总数
            premium_count: 鸡腿机会数量
            max_premium: 最高溢价率
            top_funds: TOP基金列表
        
        Returns:
            bool: True=成功，False=失败
        """
        title = f"📊 LOF套利日报 - {self._get_current_date()}"
        
        content = self._build_daily_summary_html(
            total_count, premium_count, max_premium, top_funds
        )
        
        return self.send_message(title, content, template="html")
    
    def _build_daily_summary_html(self, total_count: int, premium_count: int,
                                  max_premium: float, top_funds: List[Dict]) -> str:
        """
        构建每日汇总HTML
        
        Args:
            total_count: LOF总数
            premium_count: 鸡腿机会数量
            max_premium: 最高溢价率
            top_funds: TOP基金列表
        
        Returns:
            str: HTML内容
        """
        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .stats {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 15px;
                    margin-bottom: 20px;
                }}
                .stat-card {{
                    background: white;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    padding: 15px;
                    text-align: center;
                }}
                .stat-value {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #667eea;
                    margin: 10px 0;
                }}
                .stat-label {{
                    font-size: 14px;
                    color: #6b7280;
                }}
                .top-list {{
                    background: white;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 20px;
                }}
                .top-item {{
                    padding: 10px;
                    border-bottom: 1px solid #f3f4f6;
                }}
                .top-item:last-child {{
                    border-bottom: none;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>📈 LOF市场每日汇总</h2>
                <p style="margin: 5px 0 0 0; font-size: 14px;">
                    {self._get_current_time()}
                </p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-label">总LOF数量</div>
                    <div class="stat-value">{total_count}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">鸡腿机会</div>
                    <div class="stat-value" style="color: #dc2626;">{premium_count}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">最高溢价率</div>
                    <div class="stat-value" style="color: #f59e0b;">{max_premium:.2f}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">机会占比</div>
                    <div class="stat-value" style="color: #10b981;">
                        {(premium_count / total_count * 100) if total_count > 0 else 0:.1f}%
                    </div>
                </div>
            </div>
            
            <div class="top-list">
                <h3 style="margin-top: 0;">🏆 TOP 5 高溢价基金</h3>
        """
        
        # 添加TOP基金
        for i, fund in enumerate(top_funds[:5], 1):
            fund_code = fund.get('基金代码', fund.get('fund_code', ''))
            fund_name = fund.get('基金名称', fund.get('fund_name', ''))
            premium = fund.get('溢价率(%)', fund.get('premium_rate', 0))
            
            html += f"""
                <div class="top-item">
                    <strong>{i}. {fund_name}</strong> ({fund_code})<br>
                    <span style="color: #dc2626; font-size: 18px; font-weight: bold;">
                        溢价率：{premium:.2f}%
                    </span>
                </div>
            """
        
        html += """
            </div>
            
            <div style="background: #dbeafe; padding: 15px; border-radius: 8px; margin-top: 20px;">
                💡 <strong>提示</strong><br>
                及时关注申购赎回状态变化，把握套利时机
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #6b7280; font-size: 12px;">
                <p>LOF套利监控系统 Pro</p>
                <p>Powered by Akshare + Streamlit</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_test_message(self) -> bool:
        """
        发送测试消息
        
        Returns:
            bool: True=成功，False=失败
        """
        title = "🧪 PushPlus 测试消息"
        
        content = f"""
        <h2>✅ 推送功能测试成功！</h2>
        <p>🕐 测试时间：{self._get_current_time()}</p>
        <p>📱 推送渠道：微信</p>
        <hr>
        <p>如果您收到此消息，说明 PushPlus 推送已正常配置。</p>
        <p>您将会收到以下类型的消息：</p>
        <ul>
            <li>🍗 LOF套利机会提醒（溢价率≥5%）</li>
            <li>📊 每日市场汇总（可选）</li>
            <li>⚠️ 重要系统通知</li>
        </ul>
        <hr>
        <p style="color: #666; font-size: 12px;">
            LOF套利监控系统 Pro v3.0.0
        </p>
        """
        
        return self.send_message(title, content, template="html")
    
    # ==================== 工具方法 ====================
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def _get_current_date(self) -> str:
        """获取当前日期字符串"""
        return datetime.now().strftime('%Y年%m月%d日')


# ==================== 测试函数 ====================

def test_pushplus():
    """测试 PushPlus 推送功能"""
    print("=" * 60)
    print("🧪 测试 PushPlus 推送功能")
    print("=" * 60)
    
    pusher = PushPlusNotifier()
    
    if pusher.is_configured():
        print("✅ PushPlus 已配置")
        
        # 测试推送
        print("\n📤 发送测试消息...")
        if pusher.send_test_message():
            print("✅ 测试消息发送成功！")
            print("💡 请检查微信是否收到推送")
        else:
            print("❌ 测试消息发送失败")
        
        # 测试套利提醒
        print("\n📤 测试套利提醒...")
        test_opportunities = [
            {
                '基金代码': '160636',
                '基金名称': '鹏华中证A股资源产业LOF',
                '场内价格': 1.500,
                '基金净值': 1.400,
                '溢价率(%)': 7.14,
                '场内成交额(万)': 100.0
            },
            {
                '基金代码': '501018',
                '基金名称': '南方原油LOF',
                '场内价格': 1.200,
                '基金净值': 1.100,
                '溢价率(%)': 9.09,
                '场内成交额(万)': 200.0
            }
        ]
        
        if pusher.send_arbitrage_alert(test_opportunities):
            print("✅ 套利提醒发送成功！")
        else:
            print("❌ 套利提醒发送失败")
    
    else:
        print("❌ PushPlus 未配置")
        print("💡 请配置环境变量：PUSHPLUS_TOKEN")
        print("📝 获取Token：https://www.pushplus.plus/")


if __name__ == "__main__":
    test_pushplus()
