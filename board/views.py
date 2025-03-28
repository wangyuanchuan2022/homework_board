import calendar
import datetime
import json
from functools import wraps

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count

from .forms import CustomUserCreationForm, CustomAuthenticationForm, AssignmentForm, BatchAssignmentForm, \
    UpdateUsernameForm, ChangePasswordForm
from .models import User, Subject, Assignment, CompletionRecord, HotTopic, HotTopicLike, Comment, CommentLike


def user_type_required(user_types):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.user_type in user_types:
                return view_func(request, *args, **kwargs)
            return redirect('login')
        return wrapper
    return decorator

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'login.html', {'form': form})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # 如果是学生用户，为其创建所有现有作业的完成记录
            if user.user_type == 'student':
                assignments = Assignment.objects.all()
                for assignment in assignments:
                    # 检查记录是否已存在
                    if not CompletionRecord.objects.filter(student=user, assignment=assignment).exists():
                        CompletionRecord.objects.create(
                            student=user,
                            assignment=assignment,
                            completed=False
                        )
            
            login(request, user)
            return redirect('dashboard')
        else:
            # 记录表单验证错误，方便调试
            print(f"表单验证错误: {form.errors}")
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@csrf_exempt
def get_today_homework(request):
    """API: 获取今天的作业（不含今天截止的作业）"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return JsonResponse({'success': False, 'message': '用户名或密码缺失'}, status=400)
            
            # 验证用户身份
            user = authenticate(username=username, password=password)
            if user is None:
                return JsonResponse({'success': False, 'message': '用户名或密码错误'}, status=401)
            
            # 确保是学生账号
            if user.user_type != 'student':
                return JsonResponse({'success': False, 'message': '只有学生账号可以使用此功能'}, status=403)
            
            # 获取今天的日期
            today = timezone.now().date()
            tomorrow = today + datetime.timedelta(days=1)
            
            # 判断今天是周几（0是周一，6是周日）
            today_weekday = today.weekday()
            
            # 如果今天是周五、六、日，计算下周一的日期
            next_monday = None
            if today_weekday == 4:  # 周五
                next_monday = today + datetime.timedelta(days=3)  # 加3天得到下周一
            elif today_weekday == 5:  # 周六
                next_monday = today + datetime.timedelta(days=2)  # 加2天得到下周一
            elif today_weekday == 6:  # 周日
                next_monday = today + datetime.timedelta(days=1)  # 加1天得到下周一
            
            # 获取学生的所有作业（通过完成记录关联），且是今天需要做的作业（开始日期<=今天，且截止日期>今天）
            student_completion_records = CompletionRecord.objects.filter(
                student=user,
                assignment__start_date__lte=today,
                assignment__end_date__gt=today
            ).select_related('assignment', 'assignment__subject', 'assignment__teacher')
            
            # 获取用户隐藏的科目ID列表
            hidden_subject_ids = list(user.hidden_subjects.values_list('id', flat=True))
            
            # 如果有隐藏科目，则过滤掉这些科目的作业
            if hidden_subject_ids:
                student_completion_records = student_completion_records.exclude(
                    assignment__subject_id__in=hidden_subject_ids
                )
            
            # 按科目分组作业
            subject_assignments = {}
            for record in student_completion_records:
                assignment = record.assignment
                subject_name = assignment.subject.name
                
                if subject_name not in subject_assignments:
                    subject_assignments[subject_name] = []
                
                # 添加特殊标记
                special_mark = ""
                if next_monday:
                    if assignment.end_date > next_monday:
                        special_mark = "周一不收"
                elif assignment.end_date != tomorrow:
                    special_mark = "明不收"
                
                subject_assignments[subject_name].append({
                    'id': assignment.id,
                    'title': assignment.title,
                    'description': assignment.description,
                    'teacher': assignment.teacher.username,
                    'end_date': assignment.end_date,
                    'completed': record.completed,
                    'special_mark': special_mark
                })
            
            # 构建返回的字符串
            result_str = ""

            # 科目的自定义排序顺序
            subject_order = {
                '其他': 0,
                '语文': 1,
                '数学': 2,
                '英语': 3,
                '物理': 4,
                '化学': 5,
                '生物': 6,
                '历史': 7,
                '地理': 8,
                '政治': 9
            }

            # 按自定义顺序排序科目
            sorted_subjects = sorted(
                subject_assignments.keys(),
                key=lambda x: subject_order.get(x, 100)  # 如果科目不在预定义列表中，放到最后
            )

            # 按照排序后的科目顺序输出
            for subject_name in sorted_subjects:
                result_str += f"{subject_name}：\n"
                
                # 对每个科目内的作业按截止日期排序
                assignments = sorted(subject_assignments[subject_name], key=lambda x: x['end_date'])
                
                # 添加每个作业
                for i, assignment in enumerate(assignments, 1):
                    title = assignment['title']
                    mark = f" ({assignment['special_mark']})" if assignment['special_mark'] else ""
                    result_str += f"{i}.{title}{mark}\n"
                result_str.strip()
            
            if not result_str:
                result_str = "今天暂时没有需要完成的作业"
            
            # 返回纯文本格式
            from django.http import HttpResponse
            return HttpResponse(result_str.strip(), content_type='text/plain; charset=utf-8')
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的请求数据'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'获取作业失败: {str(e)}'}, status=500)
    
    return JsonResponse({'success': False, 'message': '方法不允许'}, status=405)

@login_required
def dashboard(request):
    user = request.user
    
    if user.user_type == 'admin':
        return admin_dashboard(request)
    elif user.user_type == 'teacher':
        return teacher_dashboard(request)
    elif user.user_type == 'student':
        return student_dashboard(request)
    
    return redirect('login')

@user_type_required(['admin'])
def admin_dashboard(request):
    # 获取当前页码
    students_page = request.GET.get('students_page', 1)
    teachers_page = request.GET.get('teachers_page', 1)
    admins_page = request.GET.get('admins_page', 1)
    assignments_page = request.GET.get('assignments_page', 1)
    
    # 查询用户和作业数据
    students_list = User.objects.filter(user_type='student').order_by('student_id', 'username')
    teachers_list = User.objects.filter(user_type='teacher').order_by('username')
    admins_list = User.objects.filter(user_type='admin').exclude(id=request.user.id).order_by('username')
    assignments_list = Assignment.objects.all().order_by('-created_at')
    
    # 创建分页器
    students_paginator = Paginator(students_list, 10)  # 每页10条
    teachers_paginator = Paginator(teachers_list, 10)  # 每页10条
    admins_paginator = Paginator(admins_list, 10)  # 每页10条
    assignments_paginator = Paginator(assignments_list, 10)  # 每页10条
    
    # 获取当前页的数据
    try:
        students = students_paginator.page(students_page)
        teachers = teachers_paginator.page(teachers_page)
        admins = admins_paginator.page(admins_page)
        assignments = assignments_paginator.page(assignments_page)
    except:
        # 如果页码无效，返回第一页
        students = students_paginator.page(1)
        teachers = teachers_paginator.page(1)
        admins = admins_paginator.page(1)
        assignments = assignments_paginator.page(1)
    
    # 预先计算每个作业的完成情况
    for assignment in assignments:
        # 计算完成的学生数量
        completed_count = CompletionRecord.objects.filter(
            assignment=assignment,
            completed=True
        ).count()
        
        # 计算总学生数量
        total_count = CompletionRecord.objects.filter(
            assignment=assignment
        ).count()
        
        # 添加到作业对象中
        assignment.completed_count = completed_count
        assignment.total_count = total_count
        assignment.completion_percentage = 0 if total_count == 0 else int((completed_count / total_count) * 100)
    
    # 统计信息用于显示总数
    total_students = students_list.count()
    total_teachers = teachers_list.count()
    total_assignments = assignments_list.count()
    
    return render(request, 'admin_dashboard.html', {
        'students': students,
        'teachers': teachers,
        'admins': admins,
        'assignments': assignments,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_assignments': total_assignments
    })

@user_type_required(['teacher'])
def teacher_dashboard(request):
    # 获取当前教师的所有作业
    assignments = Assignment.objects.filter(teacher=request.user).order_by('-created_at')
    
    # 预先计算每个作业的完成情况
    for assignment in assignments:
        # 计算完成的学生数量
        completed_count = CompletionRecord.objects.filter(
            assignment=assignment,
            completed=True
        ).count()
        
        # 计算总学生数量
        total_count = CompletionRecord.objects.filter(
            assignment=assignment
        ).count()
        
        # 添加到作业对象中
        assignment.completed_count = completed_count
        assignment.total_count = total_count
        assignment.completion_percentage = 0 if total_count == 0 else int((completed_count / total_count) * 100)
    
    return render(request, 'teacher_dashboard.html', {'assignments': assignments})

@user_type_required(['student'])
def student_dashboard(request):
    """学生仪表盘视图，显示日历和作业"""
    # 获取当前日期或用户选择的日期
    date_param = request.GET.get('date')
    if date_param:
        try:
            year, month, day = map(int, date_param.split('-'))
            selected_date = datetime.date(year, month, day)
        except (ValueError, TypeError):
            selected_date = datetime.date.today()
    else:
        selected_date = datetime.date.today()
    
    # 获取选中的作业ID（如果有）
    selected_assignment_id = request.GET.get('assignment_id')
    selected_assignment = None
    
    # 获取今天和明天的日期
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    
    # 获取当前月份的日历
    current_year = selected_date.year
    current_month = selected_date.month
    cal = calendar.monthcalendar(current_year, current_month)
    
    # 获取月份名称
    months = {
        1: '一月', 2: '二月', 3: '三月', 4: '四月',
        5: '五月', 6: '六月', 7: '七月', 8: '八月',
        9: '九月', 10: '十月', 11: '十一月', 12: '十二月'
    }
    current_month_name = months[current_month]
    
    # 获取用户隐藏的科目ID列表
    hidden_subject_ids = list(request.user.hidden_subjects.values_list('id', flat=True))
    
    # 获取学生的所有作业（通过完成记录关联）
    student_completion_records = CompletionRecord.objects.filter(
        student=request.user
    ).select_related('assignment', 'assignment__subject')
    
    # 如果有隐藏科目，则过滤掉这些科目的作业
    if hidden_subject_ids:
        student_completion_records = student_completion_records.exclude(
            assignment__subject_id__in=hidden_subject_ids
        )
    
    # 筛选出当前日期有效的作业（开始日期<=所选日期，且截止日期>所选日期（不包含截止日期当天））
    assignments_for_selected_date = []
    for record in student_completion_records:
        assignment = record.assignment
        if assignment.start_date <= selected_date and assignment.end_date > selected_date:
            # 判断是否明天到期
            assignment.due_tomorrow = assignment.end_date == tomorrow
            # 判断是否今天到期，用于前端标记
            assignment.due_today = assignment.end_date == today
            # 添加完成状态
            assignment.completed = record.completed
            assignments_for_selected_date.append(assignment)
            
            # 如果有选中的作业ID，获取对应的作业对象
            if selected_assignment_id and str(assignment.id) == selected_assignment_id:
                selected_assignment = assignment
    
    # 按科目分组作业
    subject_assignments = {}
    for assignment in assignments_for_selected_date:
        subject_name = assignment.subject.name
        if subject_name not in subject_assignments:
            subject_assignments[subject_name] = []
        subject_assignments[subject_name].append(assignment)
    
    # 对每个科目内的作业进行排序 - 先按截止日期（近的先显示），后按创建时间（新的先显示）
    for subject, assignments in subject_assignments.items():
        subject_assignments[subject] = sorted(
            assignments, 
            key=lambda a: (a.end_date, -a.created_at.timestamp())
        )
    
    # 计算当月每天是否有作业
    days_with_assignments = set()
    for record in student_completion_records:
        assignment = record.assignment
        end_date = assignment.end_date
        if end_date.year == current_year and end_date.month == current_month:
            days_with_assignments.add(end_date.day)

    # 科目的自定义排序顺序
    subject_order = {
        '其他': 0,
        '语文': 1,
        '数学': 2,
        '英语': 3,
        '物理': 4,
        '化学': 5,
        '生物': 6,
        '历史': 7,
        '地理': 8,
        '政治': 9
    }

    # 按自定义顺序排序科目
    sorted_subject_assignments = dict(sorted(
        subject_assignments.items(),
        key=lambda x: subject_order.get(x[0], 100)  # 如果科目不在预定义列表中，放到最后
    ))
    
    context = {
        'calendar': cal,
        'today': today,
        'tomorrow': tomorrow,
        'selected_date': selected_date,
        'current_year': current_year,
        'current_month': current_month,
        'current_month_name': current_month_name,
        'subject_assignments': sorted_subject_assignments,
        'days_with_assignments': days_with_assignments,
        'selected_assignment': selected_assignment,
    }
    
    return render(request, 'student_dashboard.html', context)

def get_next_available_assignment_id():
    """查找可用的最小作业ID"""
    # 获取当前所有作业ID
    used_ids = set(Assignment.objects.values_list('id', flat=True))
    
    # 找出未使用的ID
    if not used_ids:
        return 1
    
    # 寻找中间空缺的ID
    max_id = max(used_ids)
    missing_ids = set(range(1, max_id + 1)) - used_ids
    
    if missing_ids:
        # 返回最小的未使用ID
        return min(missing_ids)
    else:
        # 如果没有空缺ID，则返回最大ID+1
        return max_id + 1


@user_type_required(['teacher', 'admin'])
def create_assignment(request):
    # 获取当前教师最近的一个作业作为默认值参考
    default_subject = None
    last_assignment = Assignment.objects.filter(teacher=request.user).order_by('-created_at').first()
    if last_assignment:
        default_subject = last_assignment.subject

    # 获取当前日期并计算默认的开始和结束日期
    today = datetime.date.today()
    default_start_date = today
    default_end_date = today + datetime.timedelta(days=1)  # 默认为第二天

    # 判断今天是周几（0是周一，6是周日）
    today_weekday = today.weekday()

    # 如果今天是周五、周六或周日，设置特殊的默认日期
    if today_weekday == 4:  # 周五
        # 默认开始日期为今天（周五），结束日期为下周一
        default_start_date = today
        default_end_date = today + datetime.timedelta(days=3)
    elif today_weekday == 5:  # 周六
        # 默认开始日期为昨天（周五），结束日期为下周一
        default_start_date = today - datetime.timedelta(days=1)  # 昨天=周五
        default_end_date = today + datetime.timedelta(days=2)
    elif today_weekday == 6:  # 周日
        # 默认开始日期为前天（周五），结束日期为下周一
        default_start_date = today - datetime.timedelta(days=2)  # 前天=周五
        default_end_date = today + datetime.timedelta(days=1)

    if request.method == 'POST':
        # 检查是否是批量提交
        if 'batch_submit' in request.POST:
            batch_form = BatchAssignmentForm(request.POST)
            form = AssignmentForm()  # 空表单作为备用
            
            if batch_form.is_valid():
                subject = batch_form.cleaned_data['subject']
                start_date = batch_form.cleaned_data['start_date']
                end_date = batch_form.cleaned_data['end_date']
                assignments_list = batch_form.cleaned_data['assignments']
                
                # 批量创建作业
                students = User.objects.filter(user_type='student')
                for assignment_data in assignments_list:
                    # 如果描述为空，设置为"暂无"
                    description = assignment_data['description'].strip() or "暂无"
                    
                    # 获取可用的最小ID
                    next_id = get_next_available_assignment_id()
                    
                    # 使用指定ID创建作业
                    assignment = Assignment(
                        id=next_id,
                        title=assignment_data['title'],
                        description=description,
                        subject=subject,
                        start_date=start_date,
                        end_date=end_date,
                        teacher=request.user
                    )
                    
                    # 使用save方法的force_insert确保使用指定ID
                    assignment.save(force_insert=True)
                    
                    # 为所有学生创建完成记录
                    for student in students:
                        CompletionRecord.objects.create(
                            student=student,
                            assignment=assignment,
                            completed=False
                        )
                
                return redirect('teacher_dashboard')
        else:
            # 单个作业提交
            form = AssignmentForm(request.POST)
            batch_form = BatchAssignmentForm()  # 空表单作为备用
            
            if form.is_valid():
                assignment = form.save(commit=False)
                assignment.teacher = request.user
                
                # 如果描述为空，设置为"暂无"
                if not assignment.description.strip():
                    assignment.description = "暂无"
                
                # 获取可用的最小ID
                next_id = get_next_available_assignment_id()
                assignment.id = next_id
                
                # 使用force_insert确保使用指定ID
                assignment.save(force_insert=True)
                
                # 为所有学生创建完成记录
                students = User.objects.filter(user_type='student')
                for student in students:
                    CompletionRecord.objects.create(
                        student=student,
                        assignment=assignment,
                        completed=False
                    )
                
                return redirect('teacher_dashboard')
    else:
        # 创建带有默认值的表单
        form = AssignmentForm(initial={
            'subject': default_subject.id if default_subject else None,
            'start_date': default_start_date,
            'end_date': default_end_date
        })
        batch_form = BatchAssignmentForm(initial={
            'subject': default_subject.id if default_subject else None,
            'start_date': default_start_date,
            'end_date': default_end_date
        })
    
    # 获取该教师过去布置的作业题目
    # 按频率排序，取最多5个最常用的作业标题
    previous_assignments = Assignment.objects.filter(
        teacher=request.user
    ).values('title').annotate(
        count=models.Count('title')
    ).order_by('-count')[:5]
    
    # 收集每个学科的常用作业题目
    subject_assignments = {}
    for subject in Subject.objects.all():
        subject_assignments[subject.id] = list(Assignment.objects.filter(
            teacher=request.user,
            subject=subject
        ).values('title').annotate(
            count=models.Count('title')
        ).order_by('-count')[:5])
    
    return render(request, 'create_assignment.html', {
        'form': form,
        'batch_form': batch_form,
        'previous_assignments': previous_assignments,
        'subject_assignments': subject_assignments
    })

@user_type_required(['teacher', 'admin'])
def edit_assignment(request, pk):
    """编辑已有作业"""
    # 管理员可以编辑任何作业，教师只能编辑自己的作业
    if request.user.user_type == 'admin':
        assignment = get_object_or_404(Assignment, pk=pk)
    else:
        assignment = get_object_or_404(Assignment, pk=pk, teacher=request.user)
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            # 保存更新后的作业
            updated_assignment = form.save(commit=False)
            
            # 如果描述为空，设置为"暂无"
            if not updated_assignment.description.strip():
                updated_assignment.description = "暂无"
                
            updated_assignment.save()
            
            return redirect('assignment_detail', pk=assignment.id)
    else:
        form = AssignmentForm(instance=assignment)
    
    return render(request, 'edit_assignment.html', {
        'form': form,
        'assignment': assignment
    })

@user_type_required(['teacher', 'admin'])
def assignment_detail(request, pk):
    # 管理员可以查看任何作业，教师只能查看自己的作业
    if request.user.user_type == 'admin':
        assignment = get_object_or_404(Assignment, pk=pk)
    else:
        assignment = get_object_or_404(Assignment, pk=pk, teacher=request.user)
    
    completion_records = CompletionRecord.objects.filter(assignment=assignment)
    
    # 计算完成情况统计
    completed_count = completion_records.filter(completed=True).count()
    total_count = completion_records.count()
    completion_percentage = 0 if total_count == 0 else int((completed_count / total_count) * 100)
    
    # 添加到作业对象
    assignment.completed_count = completed_count
    assignment.total_count = total_count
    assignment.completion_percentage = completion_percentage
    
    return render(request, 'assignment_detail.html', {
        'assignment': assignment,
        'completion_records': completion_records
    })

@login_required
def toggle_assignment_completion(request):
    """处理学生标记作业完成/未完成的请求"""
    if request.method == 'POST' and request.user.user_type == 'student':
        try:
            data = json.loads(request.body)
            assignment_id = data.get('assignment_id')
            
            if not assignment_id:
                return JsonResponse({
                    'success': False, 
                    'message': '缺少作业ID'
                }, status=400)
            
            try:
                record = CompletionRecord.objects.get(
                    student=request.user,
                    assignment_id=assignment_id
                )
                
                # 切换完成状态
                record.completed = not record.completed
                
                # 如果标记为完成，记录完成时间
                if record.completed:
                    record.completed_at = timezone.now()
                else:
                    record.completed_at = None
                
                record.save()
                
                print(f"学生 {request.user.username} 将作业 {assignment_id} 标记为: {'已完成' if record.completed else '未完成'}")
                
                return JsonResponse({
                    'success': True, 
                    'completed': record.completed,
                    'message': '状态已更新'
                })
            except CompletionRecord.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': '找不到该作业的完成记录'
                }, status=404)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': '无效的请求数据'
            }, status=400)
    
    return JsonResponse({
        'success': False,
        'message': '未授权的请求'
    }, status=403)

@user_type_required(['admin'])
def create_admin_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    user_type='admin'
                )
                return JsonResponse({'success': True})
    
    return JsonResponse({'success': False}, status=400)

def init_subjects(request):
    """初始化科目数据"""
    if Subject.objects.count() == 0:
        subjects = ['语文', '数学', '英语', '历史', '地理', '政治', '物理', '化学', '生物', '其他']
        for subject_name in subjects:
            Subject.objects.create(name=subject_name)
        return JsonResponse({'success': True, 'message': '科目初始化成功'})
    return JsonResponse({'success': False, 'message': '科目已存在'})

@user_type_required(['admin'])
def create_user(request):
    """API: 创建用户"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            user_type = data.get('user_type')
            
            if not (username and password and user_type):
                return JsonResponse({'success': False, 'message': '缺少必要参数'})
                
            if user_type not in ['admin', 'teacher', 'student']:
                return JsonResponse({'success': False, 'message': '无效的用户类型'})
            
            if User.objects.filter(username=username).exists():
                return JsonResponse({'success': False, 'message': '用户名已存在'})
                
            user = User.objects.create_user(
                username=username,
                password=password,
                user_type=user_type
            )

            # 如果创建的是学生账号，为该学生添加已有作业的完成记录
            if user_type == 'student':
                existing_assignments = Assignment.objects.all()
                for assignment in existing_assignments:
                    CompletionRecord.objects.create(
                        student=user,
                        assignment=assignment,
                        completed=False
                    )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': '方法不允许'}, status=405)

@user_type_required(['admin'])
def delete_user(request):
    """API: 删除用户"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            
            if not user_id:
                return JsonResponse({'success': False, 'message': '缺少用户ID'})
            
            # 不能删除自己
            if int(user_id) == request.user.id:
                return JsonResponse({'success': False, 'message': '不能删除当前登录的账号'})
                
            user = User.objects.get(id=user_id)
            user.delete()
            
            return JsonResponse({'success': True})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': '用户不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': '方法不允许'}, status=405)


@user_type_required(['admin', 'teacher'])
def delete_assignment(request):
    """API: 删除作业"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            assignment_id = data.get('assignment_id')
            
            if not assignment_id:
                return JsonResponse({'success': False, 'message': '缺少作业ID'})

            # 管理员可以删除任何作业，教师只能删除自己的作业
            if request.user.user_type == 'admin':
                assignment = Assignment.objects.get(id=assignment_id)
            else:
                assignment = Assignment.objects.get(id=assignment_id, teacher=request.user)
                
            assignment.delete()
            
            return JsonResponse({'success': True})
        except Assignment.DoesNotExist:
            return JsonResponse({'success': False, 'message': '作业不存在或无权删除'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': '方法不允许'}, status=405)

@login_required
def subject_suggestions(request):
    """获取特定学科的常用作业标题建议"""
    if request.user.user_type != 'teacher':
        return JsonResponse({'success': False, 'message': '只有教师可以使用此功能'})
    
    subject_id = request.GET.get('subject_id')
    if not subject_id:
        return JsonResponse({'success': False, 'message': '缺少学科ID'})
    
    try:
        subject = Subject.objects.get(id=subject_id)
        
        # 获取该教师在此学科布置过的作业题目
        suggestions = Assignment.objects.filter(
            teacher=request.user,
            subject=subject
        ).values('title').annotate(
            count=models.Count('title')
        ).order_by('-count')[:10]
        
        return JsonResponse({
            'success': True,
            'suggestions': list(suggestions)
        })
    except Subject.DoesNotExist:
        return JsonResponse({'success': False, 'message': '学科不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@user_type_required(['admin'])
def cleanup_old_assignments(request):
    """API: 清理旧作业"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            days = data.get('days', 90)  # 默认90天
            
            # 验证days是否为正整数
            try:
                days = int(days)
                if days <= 0:
                    return JsonResponse({'success': False, 'message': '天数必须为正整数'})
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': '无效的天数'})
            
            # 计算截止日期
            cutoff_date = timezone.now().date() - datetime.timedelta(days=days)
            
            # 获取要删除的作业
            old_assignments = Assignment.objects.filter(created_at__date__lt=cutoff_date)
            total_count = old_assignments.count()
            
            # 删除作业（级联删除相关记录）
            old_assignments.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'成功删除了 {total_count} 个创建于 {cutoff_date} 之前的作业'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'清理旧作业时出错: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': '方法不允许'}, status=405)

@login_required
def settings_view(request):
    """用户设置页面"""
    # 获取所有科目
    all_subjects = Subject.objects.all()
    
    # 获取用户已隐藏的科目ID列表
    user_hidden_subjects = list(request.user.hidden_subjects.values_list('id', flat=True))
    
    # 初始化用户名更新表单
    username_form = UpdateUsernameForm(user=request.user, initial={'username': request.user.username})

    # 初始化密码修改表单
    password_form = ChangePasswordForm(user=request.user)
    
    return render(request, 'settings.html', {
        'all_subjects': all_subjects,
        'user_hidden_subjects': user_hidden_subjects,
        'username_form': username_form,
        'password_form': password_form
    })

@login_required
def update_username(request):
    """更新用户名"""
    if request.method == 'POST':
        from .forms import UpdateUsernameForm
        form = UpdateUsernameForm(user=request.user, data=request.POST)
        if form.is_valid():
            new_username = form.cleaned_data['username']
            request.user.username = new_username
            request.user.save()
            
            from django.contrib import messages
            messages.success(request, '用户名已成功更新')
        else:
            for error in form.errors.get('username', []):
                from django.contrib import messages
                messages.error(request, error)
    
    return redirect('settings')

@login_required
def save_hidden_subjects(request):
    """保存学生隐藏的科目设置"""
    if request.method == 'POST' and request.user.user_type == 'student':
        # 获取选中的科目ID列表
        hidden_subject_ids = request.POST.getlist('hidden_subjects')
        
        # 清除现有的隐藏科目
        request.user.hidden_subjects.clear()
        
        # 添加新的隐藏科目
        if hidden_subject_ids:
            subjects = Subject.objects.filter(id__in=hidden_subject_ids)
            request.user.hidden_subjects.add(*subjects)
        
        # 添加成功消息
        from django.contrib import messages
        messages.success(request, '科目设置已保存')
    
    return redirect('settings')

@login_required
def delete_my_account(request):
    """删除当前用户自己的账号"""
    if request.method == 'POST':
        password = request.POST.get('password')
        user = request.user
        
        # 验证密码
        if user.check_password(password):
            # 注销用户
            logout(request)
            
            # 删除用户
            user.delete()
            
            # 重定向到登录页面
            from django.contrib import messages
            messages.success(request, '您的账号已成功删除')
            return redirect('login')
        else:
            # 密码错误
            from django.contrib import messages
            messages.error(request, '密码错误，无法删除账号')
    
    return redirect('settings')

@user_type_required(['student', 'admin'])
def hot_topics_view(request):
    """热搜页面视图"""
    # 获取所有热搜
    topics = HotTopic.objects.all()
    
    # 计算每个热搜的热度分数并按热度排序
    topics_with_score = [(topic, topic.heat_score) for topic in topics]
    
    # 排序：置顶的在最前面，然后按热度分数降序排序
    sorted_topics = sorted(
        topics_with_score, 
        key=lambda x: (-x[0].is_pinned, -x[1])
    )
    
    # 取前10条热搜
    top_topics = sorted_topics[:10]
    
    # 获取用户已点赞的热搜ID列表
    if request.user.is_authenticated:
        user_liked_topics = list(HotTopicLike.objects.filter(
            user=request.user
        ).values_list('topic_id', flat=True))
    else:
        user_liked_topics = []

    # 获取最近热搜（按创建时间降序排序）
    recent_topics_list = HotTopic.objects.all().order_by('-created_at')

    # 创建分页器，每页显示10条最近热搜
    page = request.GET.get('page', 1)
    paginator = Paginator(recent_topics_list, 10)

    try:
        recent_topics = paginator.page(page)
    except:
        # 如果页码无效，返回第一页
        recent_topics = paginator.page(1)
    
    context = {
        'top_topics': top_topics,
        'user_liked_topics': user_liked_topics,
        'recent_topics': recent_topics,
    }
    
    return render(request, 'hot_topics.html', context)

@user_type_required(['student', 'admin'])
def create_hot_topic(request):
    """创建热搜"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        is_anonymous = request.POST.get('is_anonymous') == 'true'
        
        if not title:
            return JsonResponse({'success': False, 'message': '标题不能为空'})
        
        # 创建热搜
        HotTopic.objects.create(
            title=title,
            content=content,
            author=request.user,
            is_anonymous=is_anonymous
        )
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})

@user_type_required(['student', 'admin'])
def delete_hot_topic(request):
    """删除热搜"""
    if request.method == 'POST':
        topic_id = request.POST.get('topic_id')
        
        try:
            topic = HotTopic.objects.get(id=topic_id)
            
            # 检查权限：只有作者和管理员可以删除
            if request.user == topic.author or request.user.user_type == 'admin':
                topic.delete()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'message': '您没有权限删除此热搜'})
        except HotTopic.DoesNotExist:
            return JsonResponse({'success': False, 'message': '热搜不存在'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})

@user_type_required(['admin'])
def pin_hot_topic(request):
    """置顶/取消置顶热搜"""
    if request.method == 'POST':
        topic_id = request.POST.get('topic_id')
        
        try:
            topic = HotTopic.objects.get(id=topic_id)
            topic.is_pinned = not topic.is_pinned
            topic.save()
            print(topic.is_pinned)
            
            action = '置顶' if topic.is_pinned else '取消置顶'
            return JsonResponse({'success': True, 'is_pinned': topic.is_pinned, 'message': f'已{action}热搜'})
        except HotTopic.DoesNotExist:
            return JsonResponse({'success': False, 'message': '热搜不存在'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})

@user_type_required(['student', 'admin'])
def toggle_hot_topic_like(request):
    """点赞/取消点赞热搜"""
    if request.method == 'POST':
        topic_id = request.POST.get('topic_id')
        
        try:
            topic = HotTopic.objects.get(id=topic_id)
            
            # 检查用户是否已点赞
            like_exists = HotTopicLike.objects.filter(topic=topic, user=request.user).exists()
            
            if like_exists:
                # 如果已点赞，则取消点赞
                HotTopicLike.objects.filter(topic=topic, user=request.user).delete()
                action = 'unliked'
                message = '已取消点赞'
            else:
                # 如果未点赞，则添加点赞
                HotTopicLike.objects.create(topic=topic, user=request.user)
                action = 'liked'
                message = '已点赞'
            
            # 获取最新点赞数
            likes_count = topic.likes_count
            
            return JsonResponse({
                'success': True, 
                'action': action, 
                'likes_count': likes_count,
                'message': message
            })
        except HotTopic.DoesNotExist:
            return JsonResponse({'success': False, 'message': '热搜不存在'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@user_type_required(['student', 'admin'])
def get_recent_topics(request):
    """AJAX获取最近热搜数据"""
    try:
        # 获取页码参数
        page = request.GET.get('page', 1)

        # 获取最近热搜（按创建时间降序排序）
        recent_topics_list = HotTopic.objects.all().order_by('-created_at')

        # 创建分页器
        paginator = Paginator(recent_topics_list, 10)  # 每页10条

        try:
            recent_topics = paginator.page(page)
        except:
            # 如果页码无效，返回第一页
            recent_topics = paginator.page(1)

        # 获取用户已点赞的热搜ID列表
        if request.user.is_authenticated:
            user_liked_topics = list(HotTopicLike.objects.filter(
                user=request.user
            ).values_list('topic_id', flat=True))
        else:
            user_liked_topics = []

        # 渲染部分模板
        html_content = render(request, 'partials/recent_topics.html', {
            'recent_topics': recent_topics,
            'user_liked_topics': user_liked_topics
        }).content.decode('utf-8')

        return JsonResponse({
            'success': True,
            'html': html_content,
            'has_previous': recent_topics.has_previous(),
            'has_next': recent_topics.has_next(),
            'current_page': recent_topics.number,
            'total_pages': paginator.num_pages,
            'page_range': list(paginator.page_range)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def change_password(request):
    """修改用户密码"""
    if request.method == 'POST':
        form = ChangePasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            # 修改密码
            new_password = form.cleaned_data['new_password']
            request.user.set_password(new_password)
            request.user.save()

            # 重新登录用户，因为修改密码会使当前会话失效
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)

            from django.contrib import messages
            messages.success(request, '密码已成功修改')
        else:
            # 显示表单错误信息
            for field, errors in form.errors.items():
                for error in errors:
                    from django.contrib import messages
                    messages.error(request, error)

    return redirect('settings')


@user_type_required(['admin'])
def get_admin_students(request):
    """AJAX获取学生列表数据"""
    try:
        # 获取页码参数
        page = request.GET.get('page', 1)

        # 获取学生列表数据
        students_list = User.objects.filter(user_type='student').order_by('student_id', 'username')

        # 创建分页器
        paginator = Paginator(students_list, 10)  # 每页10条

        try:
            students = paginator.page(page)
        except:
            # 如果页码无效，返回第一页
            students = paginator.page(1)

        # 渲染部分模板
        html_content = render(request, 'partials/admin_students.html', {
            'students': students,
            'total_students': students_list.count()
        }).content.decode('utf-8')

        return JsonResponse({
            'success': True,
            'html': html_content,
            'has_previous': students.has_previous(),
            'has_next': students.has_next(),
            'current_page': students.number,
            'total_pages': paginator.num_pages,
            'page_range': list(paginator.page_range)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@user_type_required(['admin'])
def get_admin_teachers(request):
    """AJAX获取教师列表数据"""
    try:
        # 获取页码参数
        page = request.GET.get('page', 1)

        # 获取教师列表数据
        teachers_list = User.objects.filter(user_type='teacher').order_by('username')

        # 创建分页器
        paginator = Paginator(teachers_list, 10)  # 每页10条

        try:
            teachers = paginator.page(page)
        except:
            # 如果页码无效，返回第一页
            teachers = paginator.page(1)

        # 渲染部分模板
        html_content = render(request, 'partials/admin_teachers.html', {
            'teachers': teachers,
            'total_teachers': teachers_list.count()
        }).content.decode('utf-8')

        return JsonResponse({
            'success': True,
            'html': html_content,
            'has_previous': teachers.has_previous(),
            'has_next': teachers.has_next(),
            'current_page': teachers.number,
            'total_pages': paginator.num_pages,
            'page_range': list(paginator.page_range)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@user_type_required(['admin'])
def get_admin_assignments(request):
    """AJAX获取作业列表数据"""
    try:
        # 获取页码参数
        page = request.GET.get('page', 1)

        # 获取作业列表数据
        assignments_list = Assignment.objects.all().order_by('-created_at')

        # 创建分页器
        paginator = Paginator(assignments_list, 10)  # 每页10条

        try:
            assignments = paginator.page(page)
        except:
            # 如果页码无效，返回第一页
            assignments = paginator.page(1)

        # 预先计算每个作业的完成情况
        for assignment in assignments:
            # 计算完成的学生数量
            completed_count = CompletionRecord.objects.filter(
                assignment=assignment,
                completed=True
            ).count()

            # 计算总学生数量
            total_count = CompletionRecord.objects.filter(
                assignment=assignment
            ).count()

            # 添加到作业对象中
            assignment.completed_count = completed_count
            assignment.total_count = total_count
            assignment.completion_percentage = 0 if total_count == 0 else int((completed_count / total_count) * 100)

        # 渲染部分模板
        html_content = render(request, 'partials/admin_assignments.html', {
            'assignments': assignments,
            'total_assignments': assignments_list.count()
        }).content.decode('utf-8')

        return JsonResponse({
            'success': True,
            'html': html_content,
            'has_previous': assignments.has_previous(),
            'has_next': assignments.has_next(),
            'current_page': assignments.number,
            'total_pages': paginator.num_pages,
            'page_range': list(paginator.page_range)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@user_type_required(['student', 'admin'])
def hot_topic_detail_view(request, topic_id):
    """热搜详情页面视图"""
    try:
        topic = HotTopic.objects.get(id=topic_id)
    except HotTopic.DoesNotExist:
        messages.error(request, '热搜不存在')
        return redirect('hot_topics')
    
    # 获取热搜热度
    heat_score = topic.heat_score
    
    # 获取用户已点赞的热搜ID列表
    if request.user.is_authenticated:
        user_liked_topics = list(HotTopicLike.objects.filter(
            user=request.user
        ).values_list('topic_id', flat=True))
        
        # 获取用户已点赞的评论ID列表
        user_liked_comments = list(CommentLike.objects.filter(
            user=request.user
        ).values_list('comment_id', flat=True))
    else:
        user_liked_topics = []
        user_liked_comments = []
    
    context = {
        'topic': topic,
        'heat_score': heat_score,
        'user_liked_topics': user_liked_topics,
        'user_liked_comments': user_liked_comments,
    }
    
    return render(request, 'hot_topic_detail.html', context)


@user_type_required(['student', 'admin'])
def create_comment(request):
    """创建评论"""
    if request.method == 'POST':
        topic_id = request.POST.get('topic_id')
        parent_id = request.POST.get('parent_id')  # 可能为空，表示这是顶级评论
        content = request.POST.get('content', '').strip()
        is_anonymous = request.POST.get('is_anonymous') == 'true'
        
        if not content:
            return JsonResponse({'success': False, 'message': '评论内容不能为空'})
        
        try:
            topic = HotTopic.objects.get(id=topic_id)
            
            # 检查是否是回复
            parent = None
            if parent_id:
                try:
                    parent = Comment.objects.get(id=parent_id)
                except Comment.DoesNotExist:
                    return JsonResponse({'success': False, 'message': '回复的评论不存在'})
            
            # 创建评论
            Comment.objects.create(
                topic=topic,
                author=request.user,
                content=content,
                parent=parent,
                is_anonymous=is_anonymous
            )
            
            return JsonResponse({'success': True})
        except HotTopic.DoesNotExist:
            return JsonResponse({'success': False, 'message': '热搜不存在'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@user_type_required(['student', 'admin'])
def toggle_comment_like(request):
    """点赞/取消点赞评论"""
    if request.method == 'POST':
        comment_id = request.POST.get('comment_id')
        
        try:
            comment = Comment.objects.get(id=comment_id)
            
            # 检查用户是否已点赞
            like_exists = CommentLike.objects.filter(comment=comment, user=request.user).exists()
            
            if like_exists:
                # 如果已点赞，则取消点赞
                CommentLike.objects.filter(comment=comment, user=request.user).delete()
                action = 'unliked'
                message = '已取消点赞'
            else:
                # 如果未点赞，则添加点赞
                CommentLike.objects.create(comment=comment, user=request.user)
                action = 'liked'
                message = '已点赞'
            
            # 获取最新点赞数
            likes_count = comment.likes_count
            
            return JsonResponse({
                'success': True, 
                'action': action, 
                'likes_count': likes_count,
                'message': message
            })
        except Comment.DoesNotExist:
            return JsonResponse({'success': False, 'message': '评论不存在'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@user_type_required(['student', 'admin'])
def get_hot_comments(request):
    """获取热门评论（按热度排序的前5条）"""
    topic_id = request.GET.get('topic_id')
    
    try:
        topic = HotTopic.objects.get(id=topic_id)
        
        # 只获取顶级评论（非回复）
        comments = Comment.objects.filter(
            topic=topic, 
            parent__isnull=True
        )
        
        # 计算每个评论的热度分数并按热度排序
        comments_with_score = [(comment, comment.heat_score) for comment in comments]
        
        # 按热度分数降序排序
        sorted_comments = sorted(comments_with_score, key=lambda x: -x[1])
        
        # 取前5条热门评论
        hot_comments = [comment for comment, _ in sorted_comments[:5]]
        
        # 获取用户已点赞的评论ID列表
        if request.user.is_authenticated:
            user_liked_comments = list(CommentLike.objects.filter(
                user=request.user
            ).values_list('comment_id', flat=True))
        else:
            user_liked_comments = []
        
        # 渲染部分模板
        html_content = render(request, 'partials/hot_comments.html', {
            'hot_comments': hot_comments,
            'user_liked_comments': user_liked_comments,
            'topic': topic
        }).content.decode('utf-8')
        
        return JsonResponse({
            'success': True,
            'html': html_content
        })
    except HotTopic.DoesNotExist:
        return JsonResponse({'success': False, 'message': '热搜不存在'})


@user_type_required(['student', 'admin'])
def get_comments(request):
    """分页获取所有评论"""
    topic_id = request.GET.get('topic_id')
    page = request.GET.get('page', 1)
    
    try:
        topic = HotTopic.objects.get(id=topic_id)
        
        # 获取顶级评论（非回复）
        comments_list = Comment.objects.filter(
            topic=topic,
            parent__isnull=True
        ).order_by('-created_at')
        
        # 创建分页器
        paginator = Paginator(comments_list, 10)  # 每页10条评论
        
        try:
            comments = paginator.page(page)
        except:
            # 如果页码无效，返回第一页
            comments = paginator.page(1)
        
        # 获取用户已点赞的评论ID列表
        if request.user.is_authenticated:
            user_liked_comments = list(CommentLike.objects.filter(
                user=request.user
            ).values_list('comment_id', flat=True))
        else:
            user_liked_comments = []
        
        # 渲染部分模板
        html_content = render(request, 'partials/comments.html', {
            'comments': comments,
            'user_liked_comments': user_liked_comments,
            'topic': topic
        }).content.decode('utf-8')
        
        return JsonResponse({
            'success': True,
            'html': html_content,
            'has_previous': comments.has_previous(),
            'has_next': comments.has_next(),
            'current_page': comments.number,
            'total_pages': paginator.num_pages,
            'page_range': list(paginator.page_range)
        })
    except HotTopic.DoesNotExist:
        return JsonResponse({'success': False, 'message': '热搜不存在'})


@user_type_required(['student', 'admin'])
def get_replies(request):
    """获取评论的回复"""
    comment_id = request.GET.get('comment_id')
    
    try:
        comment = Comment.objects.get(id=comment_id)
        
        # 获取所有回复，按创建时间排序
        replies = Comment.objects.filter(parent=comment).order_by('created_at')
        
        # 获取用户已点赞的评论ID列表
        if request.user.is_authenticated:
            user_liked_comments = list(CommentLike.objects.filter(
                user=request.user
            ).values_list('comment_id', flat=True))
        else:
            user_liked_comments = []
        
        # 渲染部分模板
        html_content = render(request, 'partials/replies.html', {
            'replies': replies,
            'parent_comment': comment,
            'user_liked_comments': user_liked_comments,
            'topic': comment.topic
        }).content.decode('utf-8')
        
        return JsonResponse({
            'success': True,
            'html': html_content
        })
    except Comment.DoesNotExist:
        return JsonResponse({'success': False, 'message': '评论不存在'})
