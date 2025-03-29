from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from django.db import connection
from board.models import Assignment, CompletionRecord, User, Subject
import datetime

class CleanupOldAssignmentsCommandTest(TestCase):
    def setUp(self):
        # 创建测试数据
        self.teacher = User.objects.create_user(
            username='testteacher',
            password='testpassword',
            user_type='teacher'
        )
        
        self.subject = Subject.objects.create(name='测试科目')
        
        # 创建一个较旧的作业
        old_date = timezone.now() - datetime.timedelta(days=100)
        self.old_assignment = Assignment.objects.create(
            title='旧作业',
            description='这是一个旧作业',
            subject=self.subject,
            teacher=self.teacher,
            start_date=old_date.date(),
            end_date=(old_date + datetime.timedelta(days=7)).date()
        )
        # 使用SQL更新创建时间
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE board_assignment SET created_at = %s WHERE id = %s",
                [old_date, self.old_assignment.id]
            )
        
        # 创建一个新的作业
        new_date = timezone.now() - datetime.timedelta(days=10)
        self.new_assignment = Assignment.objects.create(
            title='新作业',
            description='这是一个新作业',
            subject=self.subject,
            teacher=self.teacher,
            start_date=new_date.date(),
            end_date=(new_date + datetime.timedelta(days=7)).date()
        )
        # 使用SQL更新创建时间
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE board_assignment SET created_at = %s WHERE id = %s",
                [new_date, self.new_assignment.id]
            )

    def test_cleanup_command_dry_run(self):
        """测试dry-run模式下的清理命令"""
        # 刷新对象缓存
        self.old_assignment.refresh_from_db()
        self.new_assignment.refresh_from_db()
        
        # 重定向stdout以便我们可以检查输出
        out = StringIO()
        call_command('cleanup_old_assignments', days=90, dry_run=True, stdout=out)
        output = out.getvalue()
        
        # 检查输出中是否包含预期的信息
        self.assertIn('找到 1 个创建于', output)
        self.assertIn('将删除: 旧作业', output)
        self.assertIn('模拟运行完成', output)
        
        # 确保没有实际删除任何作业
        self.assertEqual(Assignment.objects.count(), 2)

    def test_cleanup_command_actual_run(self):
        """测试实际运行清理命令"""
        # 刷新对象缓存
        self.old_assignment.refresh_from_db()
        self.new_assignment.refresh_from_db()
        
        # 确认初始状态有两个作业
        self.assertEqual(Assignment.objects.count(), 2)
        
        # 执行清理命令
        out = StringIO()
        call_command('cleanup_old_assignments', days=90, stdout=out)
        output = out.getvalue()
        
        # 检查输出和实际效果
        self.assertIn('成功删除了 1 个旧作业', output)
        
        # 确认只有新作业仍然存在
        self.assertEqual(Assignment.objects.count(), 1)
        remaining_assignment = Assignment.objects.first()
        self.assertEqual(remaining_assignment.title, '新作业')

    def test_cleanup_command_with_completion_records(self):
        """测试带有完成记录的作业清理"""
        # 刷新对象缓存
        self.old_assignment.refresh_from_db()
        self.new_assignment.refresh_from_db()
        
        # 创建一个学生用户和完成记录
        student = User.objects.create_user(
            username='teststudent',
            password='testpassword',
            user_type='student',
            student_id='2341001'
        )
        
        # 为旧作业创建完成记录
        CompletionRecord.objects.create(
            student=student,
            assignment=self.old_assignment,
            completed=True,
            completed_at=timezone.now() - datetime.timedelta(days=95)
        )
        
        # 确认初始状态
        self.assertEqual(CompletionRecord.objects.count(), 1)
        
        # 执行清理命令
        out = StringIO()
        call_command('cleanup_old_assignments', days=90, stdout=out)
        
        # 验证作业和相关的完成记录都被删除了
        self.assertEqual(Assignment.objects.count(), 1)
        self.assertEqual(CompletionRecord.objects.count(), 0)

    def test_cleanup_command_custom_days(self):
        """测试自定义天数参数"""
        # 刷新对象缓存
        self.old_assignment.refresh_from_db()
        self.new_assignment.refresh_from_db()
        
        # 执行使用5天参数的清理命令（应该删除两个作业）
        out = StringIO()
        call_command('cleanup_old_assignments', days=5, stdout=out)
        output = out.getvalue()
        
        # 验证两个作业都被删除了
        self.assertEqual(Assignment.objects.count(), 0)
        self.assertIn('成功删除了 2 个旧作业', output) 
        