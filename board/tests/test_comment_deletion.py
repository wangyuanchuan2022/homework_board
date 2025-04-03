from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from board.models import HotTopic, Comment

User = get_user_model()

class HotTopicCommentDeletionTests(TestCase):
    """专门测试热搜评论删除功能"""
    
    def setUp(self):
        """创建测试数据"""
        # 创建测试用户
        self.student_user = User.objects.create_user(
            username='teststudent',
            password='testpassword',
            user_type='student'
        )
        
        self.admin_user = User.objects.create_user(
            username='testadmin',
            password='testpassword',
            user_type='admin'
        )
        
        self.another_student = User.objects.create_user(
            username='anotherstudent',
            password='testpassword',
            user_type='student'
        )
        
        # 创建热搜话题
        self.topic = HotTopic.objects.create(
            title="测试热搜标题",
            content="测试热搜内容",
            author=self.student_user
        )
        
        # 创建评论
        self.comment = Comment.objects.create(
            topic=self.topic,
            author=self.student_user,
            content="测试评论内容"
        )
        
        # 创建回复
        self.reply = Comment.objects.create(
            topic=self.topic,
            author=self.another_student,
            content="测试回复内容",
            parent=self.comment
        )
        
        # 创建客户端
        self.client = Client()
    
    def test_delete_comment_with_invalid_method(self):
        """测试使用GET方法删除评论"""
        # 登录用户
        self.client.login(username='teststudent', password='testpassword')
        
        # 使用GET方法（应该失败）
        response = self.client.get('/api/comments/delete/')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            str(response.content, encoding='utf8'),
            {'success': False, 'message': '请求方法错误'}
        )
    
    def test_delete_nonexistent_comment(self):
        """测试删除不存在的评论"""
        # 登录用户
        self.client.login(username='teststudent', password='testpassword')
        
        # 尝试删除不存在的评论
        response = self.client.post(
            '/api/comments/delete/',
            {'comment_id': 999999}  # 不存在的ID
        )
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            str(response.content, encoding='utf8'),
            {'success': False, 'message': '评论不存在'}
        )
    
    def test_delete_comment_as_author(self):
        """测试作者删除自己的评论"""
        # 登录用户
        self.client.login(username='teststudent', password='testpassword')
        
        # 删除评论
        response = self.client.post(
            '/api/comments/delete/',
            {'comment_id': self.comment.id}
        )
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            str(response.content, encoding='utf8'),
            {'success': True, 'message': '评论已删除'}
        )
        
        # 验证评论已删除
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())
        
        # 验证子回复也被删除
        self.assertFalse(Comment.objects.filter(id=self.reply.id).exists())
    
    def test_delete_comment_as_admin(self):
        """测试管理员删除他人的评论"""
        # 登录管理员
        self.client.login(username='testadmin', password='testpassword')
        
        # 删除评论
        response = self.client.post(
            '/api/comments/delete/',
            {'comment_id': self.comment.id}
        )
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            str(response.content, encoding='utf8'),
            {'success': True, 'message': '评论已删除'}
        )
        
        # 验证评论已删除
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())
    
    def test_delete_comment_unauthorized(self):
        """测试未授权用户删除评论"""
        # 登录其他学生
        self.client.login(username='anotherstudent', password='testpassword')
        
        # 尝试删除别人的评论
        response = self.client.post(
            '/api/comments/delete/',
            {'comment_id': self.comment.id}
        )
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            str(response.content, encoding='utf8'),
            {'success': False, 'message': '您没有权限删除此评论'}
        )
        
        # 验证评论未删除
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())
    
    def test_delete_reply_only(self):
        """测试只删除回复评论"""
        # 登录回复作者
        self.client.login(username='anotherstudent', password='testpassword')
        
        # 删除回复
        response = self.client.post(
            '/api/comments/delete/',
            {'comment_id': self.reply.id}
        )
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            str(response.content, encoding='utf8'),
            {'success': True, 'message': '评论已删除'}
        )
        
        # 验证回复已删除
        self.assertFalse(Comment.objects.filter(id=self.reply.id).exists())
        
        # 验证原评论未删除
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists()) 