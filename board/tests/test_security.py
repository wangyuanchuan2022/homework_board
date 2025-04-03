from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from board.models import HotTopic, Comment
from board.views import convert_markdown_to_html
import re

User = get_user_model()

class XSSSecurityTests(TestCase):
    """测试XSS防御机制"""
    
    def setUp(self):
        """创建测试数据"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            user_type='student'
        )
        
        # 创建热搜话题
        self.topic = HotTopic.objects.create(
            title="测试热搜",
            content="测试内容",
            author=self.user
        )
        
        # 创建客户端
        self.client = Client()
    
    def test_markdown_to_html_sanitization(self):
        """测试Markdown转HTML时的内容净化"""
        # 包含XSS的Markdown文本
        xss_markdown = """
# 标题

这是一个[链接](javascript:alert('XSS'))

<script>alert('XSS')</script>

<iframe src="javascript:alert('XSS')"></iframe>
"""
        # 转换为HTML
        html = convert_markdown_to_html(xss_markdown)
        
        # 检查危险内容是否被移除或转义
        self.assertNotIn('<script>', html)
        self.assertNotIn('javascript:', html)
        self.assertNotIn('<iframe', html)
    
    def test_comment_creation_xss_prevention(self):
        """测试评论创建时的XSS防御"""
        # 登录用户
        self.client.login(username='testuser', password='testpassword')
        
        # 尝试创建包含XSS的评论
        response = self.client.post(
            reverse('create_comment'),
            {
                'topic_id': self.topic.id,
                'content': '<script>alert("XSS")</script>',
                'is_anonymous': 'false'
            }
        )
        
        # 验证请求被处理（由于现在有XSS检测，可能会拒绝这种明显的XSS尝试）
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 如果请求被拒绝（XSS检测起作用）
        if not data.get('success', False):
            self.assertIn('HTML', data.get('message', ''), "XSS检测应提及不允许的HTML内容")
        # 如果请求被接受（内容被净化）
        else:
            # 验证存储的评论内容不包含危险标签
            created_comment = Comment.objects.filter(topic=self.topic).first()
            self.assertIsNotNone(created_comment)
            self.assertNotIn('<script>', created_comment.content)
    
    def test_security_headers(self):
        """测试安全HTTP头部是否被正确设置"""
        # 向任意页面发送请求
        response = self.client.get(reverse('login'))
        
        # 验证安全头部
        self.assertIn('X-Content-Type-Options', response)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        
        self.assertIn('X-Frame-Options', response)
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        
        self.assertIn('Content-Security-Policy', response)
        
        self.assertIn('X-XSS-Protection', response)
        self.assertEqual(response['X-XSS-Protection'], '1; mode=block')
    
    def test_dangerous_xss_patterns_rejected(self):
        """测试明显的XSS模式是否被拒绝"""
        # 登录用户
        self.client.login(username='testuser', password='testpassword')
        
        # 尝试提交各种XSS模式
        xss_patterns = [
            '<script>alert("XSS")</script>',
            'javascript:alert("XSS")',
            '<img src="x" onerror="alert(\'XSS\')">',
            '<iframe src="javascript:alert(\'XSS\')"></iframe>'
        ]
        
        for pattern in xss_patterns:
            # 尝试创建评论
            response = self.client.post(
                reverse('create_comment'),
                {
                    'topic_id': self.topic.id,
                    'content': pattern,
                    'is_anonymous': 'false'
                }
            )
            
            # 验证响应
            data = response.json()
            
            # 如果XSS模式被接受但内容被净化
            if data.get('success', False):
                comment = Comment.objects.filter(topic=self.topic).order_by('-created_at').first()
                if comment:
                    # 检查评论内容中是否没有危险的HTML标签或属性
                    self.assertNotIn('<script>', comment.content.lower())
                    self.assertNotIn('javascript:', comment.content.lower())
                    self.assertNotIn('onerror=', comment.content.lower())
                    self.assertNotIn('<iframe', comment.content.lower())
            # 如果XSS模式被拒绝
            else:
                self.assertIn('HTML', data.get('message', ''), "XSS检测应提及不允许的HTML内容")


class InputValidationTests(TestCase):
    """测试输入验证机制"""
    
    def setUp(self):
        """创建测试数据"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            user_type='student'
        )
        
        # 创建测试话题
        self.topic = HotTopic.objects.create(
            title="测试话题",
            content="测试内容",
            author=self.user
        )
        
        # 创建客户端
        self.client = Client()
        self.client.login(username='testuser', password='testpassword')
    
    def test_long_comment_rejected(self):
        """测试过长的评论是否被拒绝"""
        # 创建超长评论内容 - 我们用更长的内容来确保超过限制
        long_content = "很长的评论" * 2000  # 创建一个非常长的字符串
        
        # 提交评论
        response = self.client.post(
            reverse('create_comment'),
            {
                'topic_id': self.topic.id,
                'content': long_content,
                'is_anonymous': 'false'
            }
        )
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 检查是否有关于长度的响应或评论是否被截断
        if not data.get('success', True):
            # 如果请求被拒绝，应提及评论内容过长
            self.assertIn('过长', data.get('message', ''), "拒绝长评论时应提及评论过长")
        else:
            # 如果请求被接受，检查评论是否被截断
            comment = Comment.objects.filter(topic=self.topic).order_by('-created_at').first()
            self.assertIsNotNone(comment)
            self.assertLess(len(comment.content), len(long_content), "长评论应被截断")
    
    def test_invalid_ids_rejected(self):
        """测试无效的ID参数是否被拒绝"""
        # 提交带有无效话题ID的评论
        response = self.client.post(
            reverse('create_comment'),
            {
                'topic_id': 'not-a-number',
                'content': '测试评论',
                'is_anonymous': 'false'
            }
        )
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get('success', True), "无效话题ID应被拒绝")
        
        # 提交带有无效父评论ID的评论
        response = self.client.post(
            reverse('create_comment'),
            {
                'topic_id': self.topic.id,
                'parent_id': 'invalid-id',
                'content': '测试回复',
                'is_anonymous': 'false'
            }
        )
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get('success', True), "无效父评论ID应被拒绝")