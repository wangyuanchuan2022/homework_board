from django.test import TestCase
from django.core.exceptions import ValidationError
from board.forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    AssignmentForm,
    BatchAssignmentForm,
    UpdateUsernameForm,
    ChangePasswordForm
)
from board.models import User, Subject
import datetime

class CustomUserCreationFormTest(TestCase):
    def test_clean_method_teacher_valid(self):
        """测试教师账号验证与有效邀请码"""
        form_data = {
            'username': 'testteacher',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'user_type': 'teacher',
            'invitation_code': 'rdfzteacher',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_clean_method_teacher_no_code(self):
        """测试教师账号验证缺少邀请码"""
        form_data = {
            'username': 'testteacher',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'user_type': 'teacher',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('invitation_code', form.errors)
        self.assertEqual(form.errors['invitation_code'][0], '请输入教师邀请码')
    
    def test_clean_method_teacher_invalid_code(self):
        """测试教师账号验证错误的邀请码"""
        form_data = {
            'username': 'testteacher',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'user_type': 'teacher',
            'invitation_code': 'wrongcode',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('invitation_code', form.errors)
        self.assertEqual(form.errors['invitation_code'][0], '邀请码不正确')
    
    def test_clean_method_student_valid(self):
        """测试学生账号验证与有效学号"""
        form_data = {
            'username': 'teststudent',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'user_type': 'student',
            'student_id': '2341001',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_clean_method_student_no_id(self):
        """测试学生账号验证缺少学号"""
        form_data = {
            'username': 'teststudent',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'user_type': 'student',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('student_id', form.errors)
        self.assertEqual(form.errors['student_id'][0], '请输入学号')
    
    def test_clean_method_student_invalid_id_format(self):
        """测试学生账号验证错误格式的学号"""
        form_data = {
            'username': 'teststudent',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'user_type': 'student',
            'student_id': '12345678',  # 错误格式
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('student_id', form.errors)
        self.assertEqual(form.errors['student_id'][0], '学号格式不正确，应为23410xx格式')
    
    def test_clean_method_student_duplicate_id(self):
        """测试学生账号验证重复的学号"""
        # 先创建一个有学号的用户
        User.objects.create_user(
            username='existing_student',
            password='testpassword',
            user_type='student',
            student_id='2341002'
        )
        
        # 尝试使用相同学号创建新账号
        form_data = {
            'username': 'teststudent',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'user_type': 'student',
            'student_id': '2341002',  # 重复的学号
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('student_id', form.errors)
        self.assertEqual(form.errors['student_id'][0], '该学号已被注册')
    
    def test_save_method_student(self):
        """测试保存学生账号"""
        form_data = {
            'username': 'teststudent',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'user_type': 'student',
            'student_id': '2341003',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        user = form.save()
        self.assertEqual(user.user_type, 'student')
        self.assertEqual(user.student_id, '2341003')
    
    def test_save_method_teacher(self):
        """测试保存教师账号"""
        form_data = {
            'username': 'testteacher',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'user_type': 'teacher',
            'invitation_code': 'rdfzteacher',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        user = form.save()
        self.assertEqual(user.user_type, 'teacher')
        self.assertIsNone(user.student_id)  # 确保教师账号的学号字段为空


class BatchAssignmentFormTest(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='测试科目')
        self.today = datetime.date.today()
        self.tomorrow = self.today + datetime.timedelta(days=1)
    
    def test_clean_assignments_valid(self):
        """测试有效的批量作业输入"""
        form_data = {
            'subject': self.subject.id,
            'start_date': self.today,
            'end_date': self.tomorrow,
            'assignments': '作业1|这是作业1的描述\n作业2|这是作业2的描述',
        }
        form = BatchAssignmentForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        assignments_list = form.cleaned_data['assignments']
        self.assertEqual(len(assignments_list), 2)
        self.assertEqual(assignments_list[0]['title'], '作业1')
        self.assertEqual(assignments_list[0]['description'], '这是作业1的描述')
        self.assertEqual(assignments_list[1]['title'], '作业2')
        self.assertEqual(assignments_list[1]['description'], '这是作业2的描述')
    
    def test_clean_assignments_empty(self):
        """测试空的批量作业输入"""
        form_data = {
            'subject': self.subject.id,
            'start_date': self.today,
            'end_date': self.tomorrow,
            'assignments': '',
        }
        form = BatchAssignmentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('assignments', form.errors)
        self.assertIn('This field is required', str(form.errors['assignments']))
    
    def test_clean_assignments_invalid_format(self):
        """测试格式错误的批量作业输入"""
        form_data = {
            'subject': self.subject.id,
            'start_date': self.today,
            'end_date': self.tomorrow,
            'assignments': '作业1没有分隔符',
        }
        form = BatchAssignmentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('assignments', form.errors)
        self.assertIn('作业格式错误', str(form.errors['assignments']))
    
    def test_clean_assignments_empty_title_or_description(self):
        """测试标题或描述为空的批量作业输入"""
        form_data = {
            'subject': self.subject.id,
            'start_date': self.today,
            'end_date': self.tomorrow,
            'assignments': '|这是缺少标题的作业',
        }
        form = BatchAssignmentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('assignments', form.errors)
        self.assertIn('作业标题和描述不能为空', str(form.errors['assignments']))
    
    def test_clean_assignments_multiple_delimiters(self):
        """测试有多个分隔符的批量作业输入"""
        form_data = {
            'subject': self.subject.id,
            'start_date': self.today,
            'end_date': self.tomorrow,
            'assignments': '作业1|这是描述|包含多个分隔符',
        }
        form = BatchAssignmentForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        assignments_list = form.cleaned_data['assignments']
        self.assertEqual(len(assignments_list), 1)
        self.assertEqual(assignments_list[0]['title'], '作业1')
        self.assertEqual(assignments_list[0]['description'], '这是描述|包含多个分隔符')
    
    def test_clean_assignments_empty_lines(self):
        """测试包含空行的批量作业输入"""
        form_data = {
            'subject': self.subject.id,
            'start_date': self.today,
            'end_date': self.tomorrow,
            'assignments': '作业1|这是作业1的描述\n\n作业2|这是作业2的描述',
        }
        form = BatchAssignmentForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        assignments_list = form.cleaned_data['assignments']
        self.assertEqual(len(assignments_list), 2)
    
    def test_clean_date_validation(self):
        """测试日期验证"""
        # 结束日期早于开始日期
        form_data = {
            'subject': self.subject.id,
            'start_date': self.tomorrow,
            'end_date': self.today,  # 早于开始日期
            'assignments': '作业1|这是作业1的描述',
        }
        form = BatchAssignmentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertIn('结束日期必须晚于开始日期', str(form.errors['__all__'])) 