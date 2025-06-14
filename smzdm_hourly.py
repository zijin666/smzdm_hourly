#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Last Modified time: 2025-06-14
# @Description: 什么值得买3小时最热商品监控

import os
import json
import time
import random
import requests
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('smzdm-hourly')

# 固定钉钉机器人Webhook URL
DINGTALK_WEBHOOK = ""

# 可选代理配置
PROXY_ENABLE = os.getenv('PROXY_ENABLE', 'false').lower() == 'true'
PROXY_URL = os.getenv('PROXY_URL', '')

# 随机User-Agent列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0"
]

def get_hot_items():
    """获取3小时最热商品信息"""
    # 3小时最热JSON API
    url = "https://faxian.smzdm.com/json_more?filter=h2s0t0f0c1&order=time&page=1"
    
    # 请求头
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "https://faxian.smzdm.com/",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Connection": "keep-alive"
    }
    
    # 代理设置
    proxies = {}
    if PROXY_ENABLE and PROXY_URL:
        proxies = {
            "http": PROXY_URL,
            "https": PROXY_URL
        }
    
    try:
        # 随机延时 (0.5-1.5秒)
        time.sleep(random.uniform(0.5, 1.5))
        
        logger.info(f"开始请求JSON API: {url}")
        response = requests.get(
            url, 
            headers=headers, 
            proxies=proxies if proxies else None,
            timeout=10
        )
        response.raise_for_status()
        
        # 解析JSON数据
        items_data = response.json()
        
        # 检查API返回的数据类型
        if not isinstance(items_data, list):
            logger.error(f"API返回了非列表数据: {type(items_data)}")
            # 打印部分响应内容用于调试
            logger.debug(f"响应内容: {response.text[:200]}")
            return []
        
        if not items_data:
            logger.warning("API返回数据为空")
            return []
        
        logger.info(f"成功获取{len(items_data)}条商品数据")
        
        # 处理商品数据
        items = []
        for item in items_data:
            try:
                # 确保item是字典类型
                if not isinstance(item, dict):
                    continue
                
                # 计算热度值（点赞数 + 评论数）
                worthy = item.get('article_worthy', 0)
                comments = item.get('article_comment', 0)
                
                # 确保热度值是数字
                hot_value = 0
                try:
                    hot_value = int(worthy) + int(comments)
                except:
                    hot_value = 0
                
                # 获取原始链接
                article_link = item.get('article_link', '')
                
                # 构建商品对象
                item_obj = {
                    "title": item.get('article_title', '无标题'),
                    "price": item.get('article_price', '价格未知'),
                    "link": article_link,  # 原始链接
                    "hot": str(hot_value),
                    "image": item.get('article_pic', ''),
                    "mall": item.get('article_mall', '未知平台'),
                    # 新增字段：原始页面链接
                    "source_url": f"https://www.smzdm.com/p/{item.get('article_id')}/" if item.get('article_id') else article_link
                }
                
                # 检查必要字段
                if not item_obj["title"] or not item_obj["link"]:
                    continue
                
                items.append(item_obj)
                
                if len(items) >= 20:  # 限制20条
                    break
                    
            except Exception as e:
                logger.warning(f"处理商品数据时出错: {str(e)}")
                continue
        
        return items
    
    except Exception as e:
        logger.error(f"API请求失败: {str(e)}")
        return []

def send_to_dingtalk(items):
    """推送消息到钉钉"""
    if not items:
        logger.warning("未获取到商品数据，跳过推送")
        return False
    
    # 当前时间
    current_time = datetime.now().strftime("%m-%d %H:%M")
    
    # 构建Markdown消息
    markdown_text = f"### 🔥 什么值得买-3小时最热（{current_time}）\n\n"
    
    for i, item in enumerate(items):
        # 添加商品信息
        markdown_text += f"**{i+1}. [{item['title']}]({item['link']})**\n"
        markdown_text += f"> **💰 价格**: {item['price']}\n"
        markdown_text += f"> **🔥 热度**: {item['hot']} | **🛒 平台**: {item['mall']}\n"
        
        # 添加原始链接（如果与商品链接不同）
        if 'source_url' in item and item['source_url'] != item['link']:
            markdown_text += f"> [查看原始页面]({item['source_url']})\n"
        
        # 添加商品图片（如果存在）
        if item.get('image'):
            markdown_text += f"![商品图]({item['image']})\n\n"
        
        # 添加分隔线
        if i < len(items) - 1:
            markdown_text += "---\n\n"
    
    # 添加数据来源和原链接
    markdown_text += f"\n⏰ 更新时间: {current_time}\n"
    markdown_text += f"📊 数据来源: [什么值得买3小时最热榜单](https://faxian.smzdm.com/h1s0t0f0c1p1/#filter-block)"
    
    # 钉钉消息体
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"🔥 3小时最热优惠 {current_time}",
            "text": markdown_text
        },
        "at": {
            "isAtAll": False
        }
    }
    
    try:
        logger.info("正在推送消息到钉钉...")
        response = requests.post(
            DINGTALK_WEBHOOK,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10
        )
        
        result = response.json()
        if result.get('errcode', -1) == 0:
            logger.info("钉钉推送成功")
            return True
        else:
            logger.error(f"钉钉推送失败: {result.get('errmsg', '未知错误')}")
            return False
    except Exception as e:
        logger.error(f"钉钉推送异常: {str(e)}")
        return False

def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("什么值得买3小时热榜监控任务启动")
    logger.info(f"使用固定钉钉机器人URL")
    logger.info(f"代理状态: {'已启用' if PROXY_ENABLE and PROXY_URL else '未启用'}")
    
    # 获取商品数据
    items = get_hot_items()
    
    # 推送数据
    if items:
        logger.info(f"准备推送{len(items)}条商品")
        send_to_dingtalk(items)
    else:
        logger.warning("未获取到商品数据，不进行推送")
    
    logger.info("任务执行完成")
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
