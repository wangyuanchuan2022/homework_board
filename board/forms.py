import re

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError

from .models import User, Assignment, Subject, Rating, UserRating, RatingComment, HotTopic


class CustomUserCreationForm(UserCreationForm):
    USER_TYPE_CHOICES = (
        ('teacher', '老师'),
        ('student', '学生'),
    )
    user_type = forms.ChoiceField(choices=USER_TYPE_CHOICES, label='账号类型')
    
    # 添加邀请码字段和学号字段
    invitation_code = forms.CharField(
        max_length=20, 
        required=False, 
        label='教师邀请码',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    student_id = forms.CharField(
        max_length=10, 
        required=False, 
        label='学号',
        help_text='格式：23410xx'
    )
    
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'user_type', 'invitation_code', 'student_id']
        labels = {
            'username': '用户名',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
    
    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        invitation_code = cleaned_data.get('invitation_code')
        student_id = cleaned_data.get('student_id')
        username = cleaned_data.get('username')
        
        # 老师需要验证邀请码
        if user_type == 'teacher':
            if not invitation_code:
                self.add_error('invitation_code', '请输入教师邀请码')
            elif invitation_code != 'rdfzteacher':
                self.add_error('invitation_code', '邀请码不正确')
        
        # 学生需要验证学号
        if user_type == 'student':
            if not student_id:
                self.add_error('student_id', '请输入学号')
            elif not re.match(r'^23410\d{2}$', student_id):
                self.add_error('student_id', '学号格式不正确，应为23410xx格式')
            # 检查学号是否唯一
            elif User.objects.filter(student_id=student_id).exists():
                self.add_error('student_id', '该学号已被注册')
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # 保存用户类型
        user.user_type = self.cleaned_data.get('user_type')
        
        # 如果是学生，保存学号；如果是教师，确保学号为空
        if user.user_type == 'student':
            user.student_id = self.cleaned_data.get('student_id')
        else:
            user.student_id = None  # 确保教师账号的学号字段为空
        
        if commit:
            user.save()
        return user

class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        self.fields['username'].label = '用户名'
        self.fields['password'].label = '密码'

class AssignmentForm(forms.ModelForm):
    subject = forms.ModelChoiceField(queryset=Subject.objects.all(), label='科目')
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='开始日期')
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='截止日期')
    description = forms.CharField(widget=forms.Textarea, label='描述', initial='暂无')
    
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'subject', 'start_date', 'end_date']
        labels = {
            'title': '标题',
            'description': '描述',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 设置日期默认值
        import datetime
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        
        self.fields['start_date'].initial = today
        self.fields['end_date'].initial = tomorrow
        
        # 设置表单样式
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError('结束日期必须晚于开始日期')
            
        return cleaned_data

class BatchAssignmentForm(forms.Form):
    subject = forms.ModelChoiceField(queryset=Subject.objects.all(), label='科目')
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='开始日期')
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='截止日期')
    assignments = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'placeholder': '每行一个作业标题和描述，格式：标题|描述'}), 
                                label='批量作业')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 设置日期默认值
        import datetime
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        
        self.fields['start_date'].initial = today
        self.fields['end_date'].initial = tomorrow
        
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
    
    def clean_assignments(self):
        assignments_text = self.cleaned_data.get('assignments')
        if not assignments_text:
            raise ValidationError('请输入至少一个作业')
        
        assignments_list = []
        for line in assignments_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            parts = line.split('|')
            if len(parts) < 2:
                raise ValidationError(f'作业格式错误: {line}，请使用"标题|描述"格式')
                
            title = parts[0].strip()
            description = '|'.join(parts[1:]).strip()
            
            if not title or not description:
                raise ValidationError(f'作业标题和描述不能为空: {line}')
                
            assignments_list.append({'title': title, 'description': description})
        
        if not assignments_list:
            raise ValidationError('请输入至少一个有效的作业')
            
        return assignments_list
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError('结束日期必须晚于开始日期')
            
        return cleaned_data

class UpdateUsernameForm(forms.Form):
    """用于更新用户名的表单"""
    username = forms.CharField(
        max_length=150,
        label='新用户名',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exclude(pk=self.user.pk).exists():
            raise ValidationError('此用户名已被使用')
        return username


class ChangePasswordForm(forms.Form):
    """用于修改密码的表单"""
    current_password = forms.CharField(
        label='当前密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password = forms.CharField(
        label='新密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='密码至少需要8个字符'
    )
    confirm_password = forms.CharField(
        label='确认新密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if not self.user.check_password(current_password):
            raise ValidationError('当前密码不正确')
        return current_password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if len(new_password) < 8:
                self.add_error('new_password', '密码至少需要8个字符')

            if new_password != confirm_password:
                self.add_error('confirm_password', '两次输入的密码不一致')

        return cleaned_data

class RatingForm(forms.ModelForm):
    """用于创建评分项目的表单"""
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 6, 'placeholder': '支持Markdown语法'}),
        label='详情描述'
    )
    is_anonymous = forms.BooleanField(
        required=False,
        label='匿名发布',
        initial=False
    )
    
    class Meta:
        model = Rating
        fields = ['title', 'description', 'is_anonymous']
        labels = {
            'title': '评分标题',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'is_anonymous':
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-check-input'})


class UserRatingForm(forms.ModelForm):
    """用户提交评分的表单"""
    score = forms.IntegerField(
        min_value=1,
        max_value=5,
        widget=forms.HiddenInput(),
        required=True
    )
    
    class Meta:
        model = UserRating
        fields = ['score']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class RatingCommentForm(forms.ModelForm):
    """评分评论表单"""
    content = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': '写下你的评论（支持Markdown语法）...'}),
        label='评论内容'
    )
    is_anonymous = forms.BooleanField(
        required=False,
        label='匿名评论',
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = RatingComment
        fields = ['content', 'is_anonymous']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].widget.attrs.update({'class': 'form-control'})

class HotTopicForm(forms.ModelForm):
    """热搜表单"""
    title = forms.CharField(
        label="标题",
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '输入热搜标题'}),
    )
    content = forms.CharField(
        label="内容",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 8,
            'placeholder': '输入热搜详细内容，支持Markdown语法和LaTeX公式',
        }),
    )
    is_anonymous = forms.BooleanField(
        label="匿名发布",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        initial=False,
    )

    class Meta:
        model = HotTopic
        fields = ['title', 'content', 'is_anonymous']
