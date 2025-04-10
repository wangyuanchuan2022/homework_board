# Generated by Django 3.2.25 on 2025-03-24 13:04

from django.db import migrations
from django.db.models import Q


def delete_orphaned_likes(apps, schema_editor):
    """删除孤立的点赞记录（没有对应用户或热搜的点赞）"""
    HotTopicLike = apps.get_model('board', 'HotTopicLike')
    User = apps.get_model('board', 'User')
    HotTopic = apps.get_model('board', 'HotTopic')
    
    # 获取所有用户和热搜ID
    user_ids = User.objects.values_list('id', flat=True)
    topic_ids = HotTopic.objects.values_list('id', flat=True)
    
    # 删除孤立的点赞记录
    HotTopicLike.objects.filter(
        Q(user_id__isnull=True) | 
        ~Q(user_id__in=user_ids) |
        Q(topic_id__isnull=True) |
        ~Q(topic_id__in=topic_ids)
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0006_hottopic_hottopiclike'),
    ]

    operations = [
        migrations.RunPython(delete_orphaned_likes, migrations.RunPython.noop),
    ]
