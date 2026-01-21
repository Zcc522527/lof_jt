---
title: LOF套利监控系统 Pro
emoji: 💰
colorFrom: red
colorTo: yellow
sdk: streamlit
sdk_version: 1.28.0
app_file: app.py
pinned: false
license: mit
---

# 💰 LOF套利监控系统 Pro

实时监控中国市场LOF基金的场内外价差套利机会，支持数据库存储和消息推送。

## ✨ 核心功能

- 📊 **实时监控**: 390+只LOF基金实时行情
- 💹 **溢价计算**: 自动计算场内外价差
- 🎨 **智能高亮**: 红/黄/白三级溢价分级
- 💾 **数据持久化**: Supabase 数据库存储
- 📤 **消息推送**: PushPlus 鸡腿机会提醒
- 📈 **历史分析**: 溢价趋势图表展示

## 🚀 快速开始

### 1. 配置 Supabase

1. 访问 https://supabase.com/ 创建项目
2. 创建数据表（SQL编辑器执行）：

```sql
-- 溢价历史记录表
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

-- 推送记录表
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
