#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻数据清理任务
功能：清理超过1个月的新闻数据及其相关联的数据
包括：新闻内容、嵌入向量、标签关系、摘要、推送关系等
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.db import SessionLocal
from utils.model import News, NewsEmbedding, NewsTagRelation, NewsSummary, PushNewsRelation

# 加载环境变量
load_dotenv(override=True)

def cleanup_old_news(days_to_keep=30):
    """
    清理超过指定天数的新闻数据
    
    参数:
    - days_to_keep: 保留天数，默认30天
    
    返回:
    - dict: 清理结果统计
    """
    session = SessionLocal()
    
    # 计算截止日期
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    result = {
        "success": True,
        "cutoff_date": cutoff_date.isoformat(),
        "deleted_counts": {},
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        print(f"开始清理 {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')} 之前的新闻数据...")
        
        # 1. 获取需要删除的新闻ID列表
        old_news_query = session.query(News.id).filter(News.ctime < cutoff_date)
        old_news_ids = [row.id for row in old_news_query.all()]
        
        if not old_news_ids:
            print("✅ 没有需要清理的新闻数据")
            result["deleted_counts"] = {
                "news": 0,
                "embeddings": 0,
                "tag_relations": 0,
                "summaries": 0,
                "push_relations": 0
            }
            return result
        
        print(f"🔍 发现 {len(old_news_ids)} 条需要清理的新闻")
        
        # 2. 按表清理相关数据（由于设置了CASCADE，部分会自动删除，但为了统计我们手动处理）
        
        # 清理推送新闻关系
        push_relations_count = session.query(PushNewsRelation).filter(
            PushNewsRelation.news_id.in_(old_news_ids)
        ).count()
        if push_relations_count > 0:
            session.query(PushNewsRelation).filter(
                PushNewsRelation.news_id.in_(old_news_ids)
            ).delete(synchronize_session=False)
            print(f"🗑️  清理推送关系: {push_relations_count} 条")
        result["deleted_counts"]["push_relations"] = push_relations_count
        
        # 清理新闻摘要
        summaries_count = session.query(NewsSummary).filter(
            NewsSummary.news_id.in_(old_news_ids)
        ).count()
        if summaries_count > 0:
            session.query(NewsSummary).filter(
                NewsSummary.news_id.in_(old_news_ids)
            ).delete(synchronize_session=False)
            print(f"🗑️  清理新闻摘要: {summaries_count} 条")
        result["deleted_counts"]["summaries"] = summaries_count
        
        # 清理新闻标签关系
        tag_relations_count = session.query(NewsTagRelation).filter(
            NewsTagRelation.news_id.in_(old_news_ids)
        ).count()
        if tag_relations_count > 0:
            session.query(NewsTagRelation).filter(
                NewsTagRelation.news_id.in_(old_news_ids)
            ).delete(synchronize_session=False)
            print(f"🗑️  清理标签关系: {tag_relations_count} 条")
        result["deleted_counts"]["tag_relations"] = tag_relations_count
        
        # 清理新闻嵌入向量
        embeddings_count = session.query(NewsEmbedding).filter(
            NewsEmbedding.news_id.in_(old_news_ids)
        ).count()
        if embeddings_count > 0:
            session.query(NewsEmbedding).filter(
                NewsEmbedding.news_id.in_(old_news_ids)
            ).delete(synchronize_session=False)
            print(f"🗑️  清理嵌入向量: {embeddings_count} 条")
        result["deleted_counts"]["embeddings"] = embeddings_count
        
        # 3. 最后清理新闻主表
        news_count = session.query(News).filter(News.ctime < cutoff_date).count()
        if news_count > 0:
            session.query(News).filter(News.ctime < cutoff_date).delete(synchronize_session=False)
            print(f"🗑️  清理新闻主表: {news_count} 条")
        result["deleted_counts"]["news"] = news_count
        
        # 提交所有删除操作
        session.commit()
        
        # 输出清理结果统计
        total_deleted = sum(result["deleted_counts"].values())
        print(f"\n✅ 清理完成！总计删除 {total_deleted} 条记录")
        print("📊 详细统计:")
        for table, count in result["deleted_counts"].items():
            if count > 0:
                print(f"   - {table}: {count} 条")
        
        return result
        
    except SQLAlchemyError as e:
        session.rollback()
        error_msg = f"数据库清理失败: {str(e)}"
        print(f"❌ {error_msg}")
        result["success"] = False
        result["error"] = error_msg
        return result
    
    except Exception as e:
        session.rollback()
        error_msg = f"清理过程出错: {str(e)}"
        print(f"❌ {error_msg}")
        result["success"] = False
        result["error"] = error_msg
        return result
    
    finally:
        session.close()

def cleanup_orphaned_data():
    """
    清理孤立数据：清理没有对应新闻记录的相关表数据
    """
    session = SessionLocal()
    
    try:
        print("\n🔍 检查并清理孤立数据...")
        
        orphaned_counts = {}
        
        # 1. 清理孤立的嵌入向量
        orphaned_embeddings = session.query(NewsEmbedding).filter(
            ~NewsEmbedding.news_id.in_(session.query(News.id))
        ).count()
        if orphaned_embeddings > 0:
            session.query(NewsEmbedding).filter(
                ~NewsEmbedding.news_id.in_(session.query(News.id))
            ).delete(synchronize_session=False)
            print(f"🗑️  清理孤立嵌入向量: {orphaned_embeddings} 条")
        orphaned_counts["embeddings"] = orphaned_embeddings
        
        # 2. 清理孤立的标签关系
        orphaned_tag_relations = session.query(NewsTagRelation).filter(
            ~NewsTagRelation.news_id.in_(session.query(News.id))
        ).count()
        if orphaned_tag_relations > 0:
            session.query(NewsTagRelation).filter(
                ~NewsTagRelation.news_id.in_(session.query(News.id))
            ).delete(synchronize_session=False)
            print(f"🗑️  清理孤立标签关系: {orphaned_tag_relations} 条")
        orphaned_counts["tag_relations"] = orphaned_tag_relations
        
        # 3. 清理孤立的摘要
        orphaned_summaries = session.query(NewsSummary).filter(
            ~NewsSummary.news_id.in_(session.query(News.id))
        ).count()
        if orphaned_summaries > 0:
            session.query(NewsSummary).filter(
                ~NewsSummary.news_id.in_(session.query(News.id))
            ).delete(synchronize_session=False)
            print(f"🗑️  清理孤立摘要: {orphaned_summaries} 条")
        orphaned_counts["summaries"] = orphaned_summaries
        
        # 4. 清理孤立的推送关系
        orphaned_push_relations = session.query(PushNewsRelation).filter(
            ~PushNewsRelation.news_id.in_(session.query(News.id))
        ).count()
        if orphaned_push_relations > 0:
            session.query(PushNewsRelation).filter(
                ~PushNewsRelation.news_id.in_(session.query(News.id))
            ).delete(synchronize_session=False)
            print(f"🗑️  清理孤立推送关系: {orphaned_push_relations} 条")
        orphaned_counts["push_relations"] = orphaned_push_relations
        
        session.commit()
        
        total_orphaned = sum(orphaned_counts.values())
        if total_orphaned > 0:
            print(f"✅ 孤立数据清理完成！总计删除 {total_orphaned} 条孤立记录")
        else:
            print("✅ 没有发现孤立数据")
        
        return orphaned_counts
        
    except Exception as e:
        session.rollback()
        print(f"❌ 孤立数据清理失败: {str(e)}")
        return {}
    
    finally:
        session.close()

def get_news_statistics():
    """
    获取新闻数据统计信息
    """
    session = SessionLocal()
    
    try:
        # 总新闻数量
        total_news = session.query(News).count()
        
        # 按时间范围统计
        now = datetime.now()
        one_day_ago = now - timedelta(days=1)
        one_week_ago = now - timedelta(days=7)
        one_month_ago = now - timedelta(days=30)
        
        news_last_day = session.query(News).filter(News.ctime >= one_day_ago).count()
        news_last_week = session.query(News).filter(News.ctime >= one_week_ago).count()
        news_last_month = session.query(News).filter(News.ctime >= one_month_ago).count()
        news_older_than_month = session.query(News).filter(News.ctime < one_month_ago).count()
        
        # 各种关联数据统计
        total_embeddings = session.query(NewsEmbedding).count()
        total_tag_relations = session.query(NewsTagRelation).count()
        total_summaries = session.query(NewsSummary).count()
        total_push_relations = session.query(PushNewsRelation).count()
        
        print(f"\n📊 新闻数据统计 ({now.strftime('%Y-%m-%d %H:%M:%S')})")
        print("=" * 50)
        print(f"📰 新闻总数: {total_news:,} 条")
        print(f"📅 时间分布:")
        print(f"   - 最近1天: {news_last_day:,} 条")
        print(f"   - 最近1周: {news_last_week:,} 条")
        print(f"   - 最近1月: {news_last_month:,} 条")
        print(f"   - 1月以前: {news_older_than_month:,} 条")
        print(f"🔗 关联数据:")
        print(f"   - 嵌入向量: {total_embeddings:,} 条")
        print(f"   - 标签关系: {total_tag_relations:,} 条")
        print(f"   - 新闻摘要: {total_summaries:,} 条")
        print(f"   - 推送关系: {total_push_relations:,} 条")
        
        return {
            "total_news": total_news,
            "news_last_day": news_last_day,
            "news_last_week": news_last_week,
            "news_last_month": news_last_month,
            "news_older_than_month": news_older_than_month,
            "total_embeddings": total_embeddings,
            "total_tag_relations": total_tag_relations,
            "total_summaries": total_summaries,
            "total_push_relations": total_push_relations
        }
        
    except Exception as e:
        print(f"❌ 获取统计信息失败: {str(e)}")
        return {}
    
    finally:
        session.close()

def main():
    """主函数：执行新闻数据清理任务"""
    print("🧹 新闻数据清理任务开始")
    print("=" * 50)
    
    start_time = datetime.now()
    
    # 1. 显示清理前的统计信息
    print("📊 清理前数据统计:")
    get_news_statistics()
    
    # 2. 从环境变量获取保留天数，默认30天
    days_to_keep = int(os.getenv("NEWS_RETENTION_DAYS", 30))
    print(f"\n🎯 配置: 保留最近 {days_to_keep} 天的新闻数据")
    
    # 3. 执行主要清理任务
    cleanup_result = cleanup_old_news(days_to_keep)
    
    # 4. 清理孤立数据
    orphaned_result = cleanup_orphaned_data()
    
    # 5. 显示清理后的统计信息
    print("\n📊 清理后数据统计:")
    get_news_statistics()
    
    # 6. 输出任务总结
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"\n{'=' * 50}")
    print(f"🎉 新闻数据清理任务完成")
    print(f"⏱️  总耗时: {duration:.2f} 秒")
    print(f"✅ 任务状态: {'成功' if cleanup_result['success'] else '失败'}")
    
    if not cleanup_result['success']:
        print(f"❌ 错误信息: {cleanup_result['error']}")
        return 1
    
    return 0

if __name__ == "__main__":
    """脚本入口点"""
    sys.exit(main())
