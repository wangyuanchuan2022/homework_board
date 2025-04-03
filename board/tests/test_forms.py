from django.test import TestCase
from django.core.exceptions import ValidationError
from board.forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    AssignmentForm,
    BatchAssignmentForm,
    UpdateUsernameForm,
    ChangePasswordForm,
    RatingForm,
    UserRatingForm,
    RatingCommentForm
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


class RatingFormTest(TestCase):
    """测试评分表单"""
    
    def test_valid_rating_form(self):
        """测试有效的评分表单"""
        form_data = {
            'title': '测试评分标题',
            'description': '测试评分描述'
        }
        form = RatingForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_valid_rating_form_with_anonymous(self):
        """测试带匿名选项的有效评分表单"""
        form_data = {
            'title': '测试评分标题',
            'description': '测试评分描述',
            'is_anonymous': True
        }
        form = RatingForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_invalid_rating_form_no_title(self):
        """测试没有标题的无效评分表单"""
        form_data = {
            'description': '测试评分描述'
        }
        form = RatingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_invalid_rating_form_no_description(self):
        """测试没有描述的无效评分表单"""
        form_data = {
            'title': '测试评分标题'
        }
        form = RatingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('description', form.errors)
    
    def test_title_max_length(self):
        """测试标题最大长度限制"""
        # 创建一个长度超过200的标题
        long_title = 'a' * 201
        form_data = {
            'title': long_title,
            'description': '测试评分描述'
        }
        form = RatingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        self.assertIn('Ensure this value has at most 200 characters', str(form.errors['title']))


class UserRatingFormTest(TestCase):
    """测试用户评分表单"""
    
    def test_valid_user_rating_form(self):
        """测试有效的用户评分表单"""
        form_data = {
            'score': 4
        }
        form = UserRatingForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_invalid_user_rating_form_no_score(self):
        """测试没有分数的无效用户评分表单"""
        form_data = {}
        form = UserRatingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('score', form.errors)
    
    def test_invalid_user_rating_form_score_too_low(self):
        """测试分数太低的无效用户评分表单"""
        form_data = {
            'score': 0  # 最小值为1
        }
        form = UserRatingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('score', form.errors)
        self.assertIn('Ensure this value is greater than or equal to 1', str(form.errors['score']))
    
    def test_invalid_user_rating_form_score_too_high(self):
        """测试分数太高的无效用户评分表单"""
        form_data = {
            'score': 6  # 最大值为5
        }
        form = UserRatingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('score', form.errors)
        self.assertIn('Ensure this value is less than or equal to 5', str(form.errors['score']))


class RatingCommentFormTest(TestCase):
    """测试评分评论表单"""
    
    def test_valid_rating_comment_form(self):
        """测试有效的评分评论表单"""
        form_data = {
            'content': '测试评论内容'
        }
        form = RatingCommentForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_valid_rating_comment_form_with_anonymous(self):
        """测试带匿名选项的有效评分评论表单"""
        form_data = {
            'content': '测试评论内容',
            'is_anonymous': True
        }
        form = RatingCommentForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_invalid_rating_comment_form_no_content(self):
        """测试没有内容的无效评分评论表单"""
        form_data = {}
        form = RatingCommentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('content', form.errors)
    
    def test_invalid_rating_comment_form_empty_content(self):
        """测试内容为空的无效评分评论表单"""
        form_data = {
            'content': ''
        }
        form = RatingCommentForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('content', form.errors) 