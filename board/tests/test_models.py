# python manage.py test board.tests.test_models
import math
from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from board.models import Subject, HotTopic, Comment, HotTopicLike, CommentLike, Assignment, CompletionRecord

User = get_user_model()


class HotTopicModelTests(TestCase):
    """测试热搜模型的方法"""
    
    def setUp(self):
        """创建测试数据"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            user_type='student'
        )
        
        # 创建一个热搜话题
        self.topic = HotTopic.objects.create(
            title="测试热搜标题",
            content="测试热搜内容",
            author=self.user,
            is_pinned=False,
            is_anonymous=False
        )
    
    def test_likes_count(self):
        """测试热搜点赞数计算"""
        # 初始应该没有点赞
        self.assertEqual(self.topic.likes_count, 0)
        
        # 创建三个用户给热搜点赞
        for i in range(3):
            user = User.objects.create_user(
                username=f'liker{i}',
                password='password',
                user_type='student'
            )
            HotTopicLike.objects.create(topic=self.topic, user=user)
        
        # 现在应该有3个点赞
        self.assertEqual(self.topic.likes_count, 3)
    
    def test_comments_count(self):
        """测试热搜评论数计算"""
        # 初始应该没有评论
        self.assertEqual(self.topic.comments_count, 0)
        
        # 创建三条评论
        for i in range(3):
            Comment.objects.create(
                topic=self.topic,
                author=self.user,
                content=f"测试评论{i}",
                is_anonymous=False
            )
        
        # 现在应该有3条评论
        self.assertEqual(self.topic.comments_count, 3)
    
    def test_heat_score(self):
        """测试热搜热度计算"""
        # 创建一个特定时间的热搜，以便精确测试热度计算
        specific_time = timezone.now() - timedelta(days=1)  # 1天前
        topic = HotTopic.objects.create(
            title="热度测试热搜",
            content="热度测试内容",
            author=self.user
        )
        
        # 手动设置创建时间
        topic.created_at = specific_time
        topic.save()
        
        # 添加2个点赞
        for i in range(2):
            user = User.objects.create_user(
                username=f'heat_liker{i}',
                password='password',
                user_type='student'
            )
            HotTopicLike.objects.create(topic=topic, user=user)
        
        # 添加一条评论，热度为1
        comment = Comment.objects.create(
            topic=topic,
            author=self.user,
            content="热度测试评论"
        )
        comment.created_at = specific_time
        comment.save()
        
        # 计算预期热度
        # 热搜热度公式：(5 + 点赞数 + 所有评论的热度总和) * e^(k*days)
        # 其中k=-0.1，days=1
        # 基础分5分，2个点赞，评论热度约为0（因为没有点赞和回复）
        likes = 2
        comments_heat = math.exp(-0.15)  # 评论没有点赞和回复，热度约为0.9
        days = 1
        k = -0.1
        expected_heat = (5 + likes + comments_heat) * math.exp(k * days)
        
        # 允许一定的浮点数误差
        self.assertAlmostEqual(topic.heat_score, expected_heat, places=2)
    
    def test_str_representation(self):
        """测试热搜字符串表示"""
        self.assertEqual(str(self.topic), "测试热搜标题")


class HotTopicLikeModelTests(TestCase):
    """测试热搜点赞模型的方法"""
    
    def setUp(self):
        """创建测试数据"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            user_type='student'
        )
        
        # 创建一个热搜话题
        self.topic = HotTopic.objects.create(
            title="测试热搜标题",
            content="测试热搜内容",
            author=self.user
        )
        
        # 创建一个点赞
        self.like = HotTopicLike.objects.create(
            topic=self.topic,
            user=self.user
        )
    
    def test_str_representation(self):
        """测试热搜点赞的字符串表示"""
        expected_str = f"testuser 点赞了 测试热搜标题"
        self.assertEqual(str(self.like), expected_str)


class CommentModelTests(TestCase):
    """测试评论模型的方法"""
    
    def setUp(self):
        """创建测试数据"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            user_type='student'
        )
        
        # 创建一个热搜话题
        self.topic = HotTopic.objects.create(
            title="测试热搜标题",
            content="测试热搜内容",
            author=self.user
        )
        
        # 创建一条评论
        self.comment = Comment.objects.create(
            topic=self.topic,
            author=self.user,
            content="测试评论内容",
            is_anonymous=False
        )
    
    def test_likes_count(self):
        """测试评论点赞数计算"""
        # 初始应该没有点赞
        self.assertEqual(self.comment.likes_count, 0)
        
        # 创建三个用户给评论点赞
        for i in range(3):
            user = User.objects.create_user(
                username=f'comment_liker{i}',
                password='password',
                user_type='student'
            )
            CommentLike.objects.create(comment=self.comment, user=user)
        
        # 现在应该有3个点赞
        self.assertEqual(self.comment.likes_count, 3)
    
    def test_replies_count(self):
        """测试评论回复数计算"""
        # 初始应该没有回复
        self.assertEqual(self.comment.replies_count, 0)
        
        # 创建三条回复
        for i in range(3):
            Comment.objects.create(
                topic=self.topic,
                author=self.user,
                content=f"测试回复{i}",
                parent=self.comment,
                is_anonymous=False
            )
        
        # 现在应该有3条回复
        self.assertEqual(self.comment.replies_count, 3)
    
    def test_heat_score(self):
        """测试评论热度计算"""
        # 创建一个特定时间的评论，以便精确测试热度计算
        specific_time = timezone.now() - timedelta(days=1)  # 1天前
        comment = Comment.objects.create(
            topic=self.topic,
            author=self.user,
            content="热度测试评论"
        )
        
        # 手动设置创建时间
        comment.created_at = specific_time
        comment.save()
        
        # 添加2个点赞
        for i in range(2):
            user = User.objects.create_user(
                username=f'comment_liker{i}',
                password='password',
                user_type='student'
            )
            CommentLike.objects.create(comment=comment, user=user)
        
        # 添加一条回复
        Comment.objects.create(
            topic=self.topic,
            author=self.user,
            content="回复测试评论",
            parent=comment
        )
        
        # 计算预期热度
        # 评论热度公式：(1 + 点赞数 + 回复数) * e^(k*days)
        # 其中k=-0.15，days=1
        k = -0.15
        days = 1
        
        # 基础分1分，2个点赞，1个回复
        expected_heat = (1 + 2 + 1) * math.exp(k * days)
        
        # 考虑到浮点数计算的误差，使用近似比较
        self.assertAlmostEqual(comment.heat_score, expected_heat, places=2)
    
    def test_str_representation(self):
        """测试评论字符串表示"""
        expected_str = f"testuser 评论了 测试热搜标题"
        self.assertEqual(str(self.comment), expected_str)


class CommentLikeModelTests(TestCase):
    """测试评论点赞模型的方法"""
    
    def setUp(self):
        """创建测试数据"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            user_type='student'
        )
        
        # 创建一个热搜话题
        self.topic = HotTopic.objects.create(
            title="测试热搜标题",
            content="测试热搜内容",
            author=self.user
        )
        
        # 创建一条评论
        self.comment = Comment.objects.create(
            topic=self.topic,
            author=self.user,
            content="测试评论内容"
        )
        
        # 创建一个评论点赞
        self.comment_like = CommentLike.objects.create(
            comment=self.comment,
            user=self.user
        )
    
    def test_str_representation(self):
        """测试评论点赞的字符串表示"""
        expected_str = f"testuser 点赞了评论 {self.comment.id}"
        self.assertEqual(str(self.comment_like), expected_str)


class AssignmentModelTests(TestCase):
    """测试作业模型的方法"""
    
    def setUp(self):
        """创建测试数据"""
        # 创建测试教师用户
        self.teacher = User.objects.create_user(
            username='teacher',
            password='password',
            user_type='teacher'
        )
        
        # 创建科目
        self.subject = Subject.objects.create(name='数学')
        
        # 创建作业
        self.assignment = Assignment.objects.create(
            title="测试作业",
            description="这是一个测试作业描述",
            teacher=self.teacher,
            subject=self.subject,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7)
        )
    
    def test_str_representation(self):
        """测试作业字符串表示"""
        expected_str = f"测试作业 - 数学"
        self.assertEqual(str(self.assignment), expected_str)
    
    def test_ordering(self):
        """测试作业排序"""
        # 创建两个不同截止日期的作业
        assignment1 = Assignment.objects.create(
            title="作业1",
            description="描述1",
            teacher=self.teacher,
            subject=self.subject,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=5)  # 5天后截止
        )
        
        assignment2 = Assignment.objects.create(
            title="作业2",
            description="描述2",
            teacher=self.teacher,
            subject=self.subject,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3)  # 3天后截止
        )
        
        # 按截止日期早的排在前面
        assignments = list(Assignment.objects.all())
        self.assertEqual(assignments[0], assignment2)  # 3天后截止
        self.assertEqual(assignments[1], assignment1)  # 5天后截止
        self.assertEqual(assignments[2], self.assignment)  # 7天后截止


class CompletionRecordModelTests(TestCase):
    """测试完成记录模型的方法"""
    
    def setUp(self):
        """创建测试数据"""
        # 创建测试用户
        self.teacher = User.objects.create_user(
            username='teacher',
            password='password',
            user_type='teacher'
        )
        
        self.student = User.objects.create_user(
            username='student',
            password='password',
            user_type='student',
            student_id='12345'
        )
        
        # 创建科目
        self.subject = Subject.objects.create(name='数学')
        
        # 创建作业
        self.assignment = Assignment.objects.create(
            title="测试作业",
            description="这是一个测试作业描述",
            teacher=self.teacher,
            subject=self.subject,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7)
        )
        
        # 创建完成记录
        self.record = CompletionRecord.objects.create(
            student=self.student,
            assignment=self.assignment,
            completed=False
        )
    
    def test_str_representation_not_completed(self):
        """测试未完成的完成记录字符串表示"""
        # 预期格式："{student_info} - {assignment.title} (未完成)"
        expected_str = f"student (学号: 12345) - 测试作业 (未完成)"
        self.assertEqual(str(self.record), expected_str)
    
    def test_str_representation_completed(self):
        """测试已完成的完成记录字符串表示"""
        # 设置为已完成
        self.record.completed = True
        self.record.completed_at = timezone.now()
        self.record.save()
        
        # 预期格式："{student_info} - {assignment.title} (已完成)"
        expected_str = f"student (学号: 12345) - 测试作业 (已完成)"
        self.assertEqual(str(self.record), expected_str)
    
    def test_unique_together_constraint(self):
        """测试学生和作业的唯一约束"""
        # 尝试为同一个学生和同一个作业创建另一条完成记录，应该抛出异常
        with self.assertRaises(Exception):
            CompletionRecord.objects.create(
                student=self.student,
                assignment=self.assignment,
                completed=True
            )


class UserModelTests(TestCase):
    """测试用户模型的方法"""
    
    def test_str_representation_with_student_id(self):
        """测试带学号的学生用户字符串表示"""
        user = User.objects.create_user(
            username='student1',
            password='password',
            user_type='student',
            student_id='12345'
        )
        self.assertEqual(str(user), "student1 (12345)")
    
    def test_str_representation_without_student_id(self):
        """测试不带学号的用户字符串表示"""
        user = User.objects.create_user(
            username='teacher1',
            password='password',
            user_type='teacher'
        )
        self.assertEqual(str(user), "teacher1 (老师)")


class SubjectModelTests(TestCase):
    """测试科目模型的方法"""
    
    def test_str_representation(self):
        """测试科目字符串表示"""
        subject = Subject.objects.create(name='数学')
        self.assertEqual(str(subject), '数学') 