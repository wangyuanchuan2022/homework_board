import math
from datetime import datetime

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.utils import timezone


class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('admin', '管理员'),
        ('teacher', '老师'),
        ('student', '学生'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='student')
    avatar = models.URLField(blank=True, null=True)
    student_id = models.CharField(max_length=10, blank=True, null=True, verbose_name='学号')
    hidden_subjects = models.ManyToManyField('Subject', blank=True, related_name='hidden_by_users')

    def __str__(self):
        if self.user_type == 'student' and self.student_id:
            return f"{self.username} ({self.student_id})"
        return f"{self.username} ({self.get_user_type_display()})"


class Subject(models.Model):
    name = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.subject.name}"

    class Meta:
        ordering = ['end_date']


class CompletionRecord(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='completion_records')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='completion_records')
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['student', 'assignment']

    def __str__(self):
        status = "已完成" if self.completed else "未完成"
        student_info = self.student.username
        if self.student.student_id:
            student_info += f" (学号: {self.student.student_id})"
        return f"{student_info} - {self.assignment.title} ({status})"


@receiver(post_migrate)
def create_subjects(sender, **kwargs):
    """确保科目数据在应用迁移后存在"""
    if sender.name == 'board':
        from board.models import Subject

        # 默认科目列表
        default_subjects = ['语文', '数学', '英语', '历史', '地理', '政治', '物理', '化学', '生物', '其他']

        # 创建不存在的科目
        for subject_name in default_subjects:
            Subject.objects.get_or_create(name=subject_name)


class HotTopic(models.Model):
    """热搜模型，记录热搜信息"""
    title = models.CharField(max_length=200, verbose_name="标题")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hot_topics', verbose_name="发布者")
    content = models.TextField(verbose_name="内容", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    is_pinned = models.BooleanField(default=False, verbose_name="是否置顶")
    is_anonymous = models.BooleanField(default=False, verbose_name="是否匿名")

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = "热搜"
        verbose_name_plural = "热搜"

    def __str__(self):
        return self.title

    @property
    def likes_count(self):
        return self.likes.count()
    
    @property
    def comments_count(self):
        return self.comments.count()

    @property
    def heat_score(self):
        """计算热度分数：(5 + 点赞数 + 所有评论的热度总和*2) * e^(-k*(t-t0))
        其中t为现在时间，t0为发布时间，按天计算
        """
        # 获取点赞数
        likes = self.likes_count
        
        # 获取所有评论的热度总和
        comments_heat = sum(comment.heat_score for comment in self.comments.all())
        
        # 计算发布至今的天数
        time_diff = timezone.now() - self.created_at
        days = time_diff.days + time_diff.seconds / 86400  # 精确到秒的天数
        
        # 衰减因子k，可以根据需要调整
        k = -0.1  # 负值表示随时间衰减
        
        # 计算热度：(5 + 点赞数 + 所有评论的热度总和) * e^(k*(t-t0))
        heat = (5 + likes + comments_heat) * math.exp(k * days)
        return heat


class HotTopicLike(models.Model):
    """热搜点赞记录"""
    topic = models.ForeignKey(HotTopic, on_delete=models.CASCADE, related_name='likes', verbose_name="热搜")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='topic_likes', verbose_name="用户")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="点赞时间")

    class Meta:
        unique_together = ['topic', 'user']
        verbose_name = "热搜点赞"
        verbose_name_plural = "热搜点赞"

    def __str__(self):
        return f"{self.user.username} 点赞了 {self.topic.title}"


class Comment(models.Model):
    """热搜评论模型"""
    topic = models.ForeignKey(HotTopic, on_delete=models.CASCADE, related_name='comments', verbose_name="所属热搜")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments', verbose_name="评论者")
    content = models.TextField(verbose_name="评论内容")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name="引用评论")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="评论时间")
    is_anonymous = models.BooleanField(default=False, verbose_name="是否匿名")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "评论"
        verbose_name_plural = "评论"

    def __str__(self):
        return f"{self.author.username} 评论了 {self.topic.title}"
    
    @property
    def likes_count(self):
        """获取评论点赞数"""
        return self.likes.count()
    
    @property
    def replies_count(self):
        """获取回复数"""
        return self.replies.count()
    
    @property
    def heat_score(self):
        """计算评论热度分数：(点赞数 + 回复数*2) * e^(-k*(t-t0))
        其中t为现在时间，t0为发布时间，按天计算
        """
        # 获取点赞数和回复数
        likes = self.likes_count
        replies = self.replies_count
        
        # 计算发布至今的天数
        time_diff = timezone.now() - self.created_at
        days = time_diff.days + time_diff.seconds / 86400  # 精确到秒的天数
        
        # 衰减因子k，可以根据需要调整
        k = -0.15  # 负值表示随时间衰减，评论的衰减可以比热搜快一些
        
        # 计算热度：(点赞数 + 回复数) * e^(k*(t-t0))
        heat = (1 + likes + replies) * math.exp(k * days)
        return heat


class CommentLike(models.Model):
    """评论点赞记录"""
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='likes', verbose_name="评论")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_likes', verbose_name="用户")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="点赞时间")

    class Meta:
        unique_together = ['comment', 'user']
        verbose_name = "评论点赞"
        verbose_name_plural = "评论点赞"

    def __str__(self):
        return f"{self.user.username} 点赞了评论 {self.comment.id}"


class Notification(models.Model):
    """用户通知模型"""
    TYPE_CHOICES = (
        ('like', '点赞'),
        ('reply', '回复'),
        ('system', '系统'),
    )
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="接收者")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True, verbose_name="发送者")
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name="通知类型")
    content = models.TextField(verbose_name="通知内容")
    topic = models.ForeignKey(HotTopic, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications', verbose_name="相关热搜")
    comment = models.ForeignKey(Comment, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications', verbose_name="相关评论")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    is_read = models.BooleanField(default=False, verbose_name="是否已读")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "通知"
        verbose_name_plural = "通知"

    def __str__(self):
        return f"{self.get_type_display()} 通知给 {self.recipient.username}"


class DeviceLogin(models.Model):
    """设备登录记录模型"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_logins', verbose_name="用户")
    device_name = models.CharField(max_length=100, verbose_name="设备名称")
    ip_address = models.GenericIPAddressField(verbose_name="IP地址", null=True, blank=True, unpack_ipv4=True)
    user_agent = models.TextField(verbose_name="用户代理")
    location = models.CharField(max_length=100, blank=True, null=True, verbose_name="登录地点")
    login_time = models.DateTimeField(auto_now_add=True, verbose_name="登录时间")
    
    class Meta:
        ordering = ['-login_time']
        verbose_name = "设备登录"
        verbose_name_plural = "设备登录"

    def __str__(self):
        return f"{self.user.username} 在 {self.login_time} 通过 {self.device_name} 登录"


class Rating(models.Model):
    """评分模型，记录发布的评分项目"""
    title = models.CharField(max_length=200, verbose_name="标题")
    description = models.TextField(verbose_name="详情描述", help_text="支持Markdown语法")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings', verbose_name="发布者")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    is_anonymous = models.BooleanField(default=False, verbose_name="匿名发布")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "评分项目"
        verbose_name_plural = "评分项目"

    def __str__(self):
        return self.title
    
    @property
    def average_score(self):
        """计算平均分数"""
        scores = self.user_ratings.filter(score__gt=0)
        if not scores.exists():
            return 0
        return round(sum(score.score for score in scores) / scores.count(), 1)
    
    @property
    def ratings_count(self):
        """获取评分数量"""
        return self.user_ratings.count()
    
    @property
    def hot_comments(self):
        """获取热门评论，按照评论热度排序"""
        # 获取所有评论
        comments = list(self.comments.all())
        # 使用Python排序，按照heat_score属性降序排序
        comments.sort(key=lambda x: x.heat_score, reverse=True)
        # 返回前3个评论
        return comments[:3]
    
    @property
    def heat_score(self):
        """计算评分热度分数，考虑评分数量、评论数量和时间因素
        热度 = (10 + 评分数量 + 评论数量*2) * e^(-k*(t-t0))
        其中t为现在时间，t0为发布时间，k为衰减因子
        """
        # 获取评分数量和评论数量
        ratings_count = self.ratings_count
        comments_count = self.comments.count()
        
        # 计算发布至今的天数
        time_diff = timezone.now() - self.created_at
        days = time_diff.days + time_diff.seconds / 86400  # 精确到秒的天数
        
        # 衰减因子k，可以根据需要调整
        k = -0.05  # 负值表示随时间衰减，评分的衰减可以比热搜更慢一些
        
        # 计算热度
        heat = (10 + ratings_count + comments_count * 2) * math.exp(k * days)
        return heat


class UserRating(models.Model):
    """用户评分记录"""
    rating = models.ForeignKey(Rating, on_delete=models.CASCADE, related_name='user_ratings', verbose_name="评分项目")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_ratings', verbose_name="用户")
    score = models.PositiveSmallIntegerField(verbose_name="分数", default=0, help_text="1-5分")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="评分时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        unique_together = ['rating', 'user']
        verbose_name = "用户评分"
        verbose_name_plural = "用户评分"

    def __str__(self):
        return f"{self.user.username} 对 {self.rating.title} 评分 {self.score}星"


class RatingComment(models.Model):
    """评分评论模型"""
    rating = models.ForeignKey(Rating, on_delete=models.CASCADE, related_name='comments', verbose_name="所属评分")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rating_comments', verbose_name="评论者")
    content = models.TextField(verbose_name="评论内容", help_text="支持Markdown语法")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name="引用评论")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="评论时间")
    is_anonymous = models.BooleanField(default=False, verbose_name="是否匿名")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "评分评论"
        verbose_name_plural = "评分评论"

    def __str__(self):
        return f"{self.author.username} 评论了 {self.rating.title}"
    
    @property
    def likes_count(self):
        """获取评论点赞数"""
        return self.likes.count()
    
    @property
    def replies_count(self):
        """获取回复数"""
        return self.replies.count()
    
    @property
    def heat_score(self):
        """计算评论热度分数"""
        # 获取点赞数和回复数
        likes = self.likes_count
        replies = self.replies_count
        
        # 计算发布至今的天数
        time_diff = timezone.now() - self.created_at
        days = time_diff.days + time_diff.seconds / 86400  # 精确到秒的天数
        
        # 衰减因子
        k = -0.15
        
        # 计算热度
        heat = (1 + likes + replies) * math.exp(k * days)
        return heat


class RatingCommentLike(models.Model):
    """评分评论点赞记录"""
    comment = models.ForeignKey(RatingComment, on_delete=models.CASCADE, related_name='likes', verbose_name="评论")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rating_comment_likes', verbose_name="用户")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="点赞时间")

    class Meta:
        unique_together = ['comment', 'user']
        verbose_name = "评分评论点赞"
        verbose_name_plural = "评分评论点赞"

    def __str__(self):
        return f"{self.user.username} 点赞了评分评论 {self.comment.id}"
