# Generated by Django 3.2.25 on 2025-04-03 12:46

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0011_alter_devicelogin_ip_address'),
    ]

    operations = [
        migrations.CreateModel(
            name='Rating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='标题')),
                ('description', models.TextField(help_text='支持Markdown语法', verbose_name='详情描述')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否激活')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ratings', to=settings.AUTH_USER_MODEL, verbose_name='发布者')),
            ],
            options={
                'verbose_name': '评分项目',
                'verbose_name_plural': '评分项目',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RatingComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(help_text='支持Markdown语法', verbose_name='评论内容')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='评论时间')),
                ('is_anonymous', models.BooleanField(default=False, verbose_name='是否匿名')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rating_comments', to=settings.AUTH_USER_MODEL, verbose_name='评论者')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='board.ratingcomment', verbose_name='引用评论')),
                ('rating', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='board.rating', verbose_name='所属评分')),
            ],
            options={
                'verbose_name': '评分评论',
                'verbose_name_plural': '评分评论',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='UserRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.PositiveSmallIntegerField(default=0, help_text='1-5分', verbose_name='分数')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='评分时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('rating', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_ratings', to='board.rating', verbose_name='评分项目')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_ratings', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '用户评分',
                'verbose_name_plural': '用户评分',
                'unique_together': {('rating', 'user')},
            },
        ),
        migrations.CreateModel(
            name='RatingCommentLike',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='点赞时间')),
                ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='likes', to='board.ratingcomment', verbose_name='评论')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rating_comment_likes', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '评分评论点赞',
                'verbose_name_plural': '评分评论点赞',
                'unique_together': {('comment', 'user')},
            },
        ),
    ]
