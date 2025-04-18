import calendar
import datetime
import json
import re
import math
from functools import wraps

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q, Avg
from django.contrib import messages
from django.urls import reverse
import markdown
import ipaddress
from user_agents import parse as user_agents_parse
import requests
import bleach

from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, AssignmentForm, BatchAssignmentForm,
    UpdateUsernameForm, ChangePasswordForm, RatingForm, UserRatingForm, RatingCommentForm,
    HotTopicForm
)
from .models import (
    User, Subject, Assignment, CompletionRecord, HotTopic, HotTopicLike, Comment, 
    CommentLike, Notification, DeviceLogin, Rating, UserRating, RatingComment, RatingCommentLike
)


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
                
                # 记录设备登录信息
                record_device_login(request, user)
                
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
            
            # 记录设备登录信息
            record_device_login(request, user)
            
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

                print(
                    f"学生 {request.user.username} 将作业 {assignment_id} 标记为: {'已完成' if record.completed else '未完成'}")

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
            
            # 如果是学生账号，检查学号
            if user_type == "student":
                student_id = data.get('student_id')
                
                if not student_id:
                    return JsonResponse({'success': False, 'message': '学生账号必须提供学号'})
                
                # 验证学号格式
                if not re.match(r'^23410\d{2}$', student_id):
                    return JsonResponse({'success': False, 'message': '学号格式不正确，应为23410xx格式'})
                
                # 检查学号是否已被使用
                if User.objects.filter(student_id=student_id).exists():
                    return JsonResponse({'success': False, 'message': '该学号已被注册'})
                
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    user_type=user_type,
                    student_id=student_id
                )
            else:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    user_type=user_type,
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


def strip_markdown(text):
    """将Markdown文本转换为纯文本（去除Markdown语法标记）"""
    if not text:
        return ""
        
    # 去除行间公式标记$$...$$，保留内部内容
    text = re.sub(r"\$\$(.*?)\$\$", r"[\1]", text, flags=re.S)
    
    # 去除行内公式标记$...$，保留内部内容
    text = re.sub(r"\$(.*?)\$", r"[\1]", text, flags=re.S)
    
    # 去除标题标记
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)
    
    # 去除粗体和斜体
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    
    # 去除行内代码和代码块
    text = re.sub(r"`{1,3}(.*?)`{1,3}", r"\1", text, flags=re.S)

    # 去除图片标记，用[图片]替代
    text = re.sub(r"!\[.*?\]\(.*?\)", "[图片]", text)
    
    # 去除链接，保留链接文本
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    
    # 去除引用标记
    text = re.sub(r"^>\s+", "", text, flags=re.M)
    
    # 去除分割线
    text = re.sub(r"^-{3,}$", "", text, flags=re.M)
    text = re.sub(r"^={3,}$", "", text, flags=re.M)
    text = re.sub(r"^\*{3,}$", "", text, flags=re.M)
    
    # 去除列表标记
    text = re.sub(r"^[\*\-+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.M)
    
    return text.strip()


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

    # 为每个热搜获取热度最高的评论
    top_topics_with_top_comment = []
    for topic, score in top_topics:
        # 处理内容为纯文本
        if topic.content:
            topic.plain_content = strip_markdown(topic.content)
            
        comments = Comment.objects.filter(topic=topic, parent__isnull=True)
        top_comment = None
        if comments.exists():
            # 计算每个评论的热度分数并按热度排序
            comments_with_score = [(comment, comment.heat_score) for comment in comments]
            sorted_comments = sorted(comments_with_score, key=lambda x: -x[1])
            if sorted_comments:
                top_comment = sorted_comments[0][0]
                # 处理评论内容为纯文本
                if top_comment.content:
                    top_comment.plain_content = strip_markdown(top_comment.content)

        top_topics_with_top_comment.append((topic, score, top_comment, topic.comments_count))

    # 为最近热搜获取热度最高的评论
    recent_topics_with_comment = []
    for topic in recent_topics:
        # 处理内容为纯文本
        if topic.content:
            topic.plain_content = strip_markdown(topic.content)
            
        comments = Comment.objects.filter(topic=topic, parent__isnull=True)
        top_comment = None
        if comments.exists():
            # 计算每个评论的热度分数并按热度排序
            comments_with_score = [(comment, comment.heat_score) for comment in comments]
            sorted_comments = sorted(comments_with_score, key=lambda x: -x[1])
            if sorted_comments:
                top_comment = sorted_comments[0][0]
                # 处理评论内容为纯文本
                if top_comment.content:
                    top_comment.plain_content = strip_markdown(top_comment.content)

        recent_topics_with_comment.append({
            'topic': topic,
            'top_comment': top_comment,
            'comments_count': topic.comments_count
        })

    context = {
        'top_topics': top_topics_with_top_comment,
        'user_liked_topics': user_liked_topics,
        'recent_topics_with_comment': recent_topics_with_comment,
        'recent_topics': recent_topics,
    }

    return render(request, 'hot_topics.html', context)


@user_type_required(['student', 'admin'])
def create_hot_topic(request):
    """创建热搜"""
    if request.method == 'POST':
        form = HotTopicForm(request.POST)
        if form.is_valid():
            hot_topic = form.save(commit=False)
            hot_topic.author = request.user
            hot_topic.save()
            return redirect('hot_topics')
        # 如果是AJAX请求的旧版表单提交
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
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
    else:
        form = HotTopicForm()

    return render(request, 'create_hot_topic.html', {'form': form})


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
                
                # 创建点赞通知（排除给自己的点赞，但包括匿名热搜）
                if topic.author != request.user:
                    sender_name = "匿名用户" if request.user.is_anonymous or (hasattr(request, 'is_anonymous_view') and request.is_anonymous_view) else request.user.username
                    notification_content = f"{sender_name} 点赞了你的热搜《{topic.title}》"
                    
                    Notification.objects.create(
                        recipient=topic.author,
                        sender=request.user if not request.user.is_anonymous else None,
                        type='like',
                        content=notification_content,
                        topic=topic
                    )

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

        # 为每个热搜获取热度最高的评论
        recent_topics_with_comment = []
        for topic in recent_topics:
            # 处理内容为纯文本
            if topic.content:
                topic.plain_content = strip_markdown(topic.content)
                
            comments = Comment.objects.filter(topic=topic, parent__isnull=True)
            top_comment = None
            if comments.exists():
                # 计算每个评论的热度分数并按热度排序
                comments_with_score = [(comment, comment.heat_score) for comment in comments]
                sorted_comments = sorted(comments_with_score, key=lambda x: -x[1])
                if sorted_comments:
                    top_comment = sorted_comments[0][0]
                    # 处理评论内容为纯文本
                    if top_comment.content:
                        top_comment.plain_content = strip_markdown(top_comment.content)

            recent_topics_with_comment.append({
                'topic': topic,
                'top_comment': top_comment,
                'comments_count': topic.comments_count
            })

        # 渲染部分模板
        html_content = render(request, 'partials/recent_topics.html', {
            'recent_topics': recent_topics,
            'recent_topics_with_comment': recent_topics_with_comment,
            'user_liked_topics': user_liked_topics
        }).content.decode('utf-8')

        return JsonResponse({
            'success': True,
            'html': html_content,
            'has_next': recent_topics.has_next(),
            'has_previous': recent_topics.has_previous(),
            'total_pages': paginator.num_pages,
            'current_page': recent_topics.number
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
    
    # 将热搜内容转换为Markdown (如果有内容)
    if topic.content:
        topic.html_content = convert_markdown_to_html(topic.content)
    else:
        topic.html_content = ""

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
        
        # 增强输入验证
        if not content:
            return JsonResponse({'success': False, 'message': '评论内容不能为空'})
        
        # 限制评论长度
        MAX_COMMENT_LENGTH = 5000
        if len(content) > MAX_COMMENT_LENGTH:
            return JsonResponse({'success': False, 'message': f'评论内容过长，最多允许{MAX_COMMENT_LENGTH}个字符'})
        
        # 基本XSS检测
        xss_patterns = [
            r'<script', r'javascript:', r'on\w+\s*=', r'vbscript:', r'data:',
            r'<iframe', r'<object', r'<embed'
        ]
        for pattern in xss_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return JsonResponse({'success': False, 'message': '评论内容包含不允许的HTML标签或属性'})
        
        # 使用bleach净化输入内容
        try:
            import bleach
            allowed_tags = []  # 不允许任何HTML标签
            content = bleach.clean(content, tags=allowed_tags, strip=True)
        except ImportError:
            # 如果bleach不可用，使用Django自带的escape功能
            from django.utils.html import escape
            content = escape(content)

        # 验证topic_id是否为有效整数
        try:
            topic_id = int(topic_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': '无效的话题ID'})
            
        # 验证parent_id是否为有效整数（如果提供）
        if parent_id:
            try:
                parent_id = int(parent_id)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': '无效的父评论ID'})

        try:
            topic = HotTopic.objects.get(id=topic_id)

            # 检查是否是回复
            parent = None
            if parent_id:
                try:
                    parent = Comment.objects.get(id=parent_id)
                    # 验证父评论是否属于同一话题
                    if parent.topic.id != topic.id:
                        return JsonResponse({'success': False, 'message': '回复的评论不属于当前话题'})
                except Comment.DoesNotExist:
                    return JsonResponse({'success': False, 'message': '回复的评论不存在'})

            # 创建评论
            comment = Comment.objects.create(
                topic=topic,
                author=request.user,
                content=content,
                parent=parent,
                is_anonymous=is_anonymous
            )
            
            # 获取发送者名称
            sender_name = "匿名用户" if is_anonymous else request.user.username
            
            # 净化通知内容
            safe_content = content[:100] + ('...' if len(content) > 100 else '')
            safe_title = topic.title
            
            # 如果是回复评论，创建回复通知（排除回复自己，但包括匿名评论）
            if parent and parent.author != request.user:
                notification_content = f"{sender_name} 回复了你的评论: {safe_content}"
                
                Notification.objects.create(
                    recipient=parent.author,
                    sender=request.user if not is_anonymous else None,
                    type='reply',
                    content=notification_content,
                    topic=topic,
                    comment=comment
                )
            # 如果是评论热搜，可以给热搜作者发通知
            elif not parent and topic.author != request.user:
                notification_content = f"{sender_name} 评论了你的热搜《{safe_title}》: {safe_content[:50]}" + ('...' if len(safe_content) > 50 else '')
                
                Notification.objects.create(
                    recipient=topic.author,
                    sender=request.user if not is_anonymous else None,
                    type='reply',
                    content=notification_content,
                    topic=topic,
                    comment=comment
                )

            return JsonResponse({'success': True})
        except HotTopic.DoesNotExist:
            return JsonResponse({'success': False, 'message': '热搜不存在'})
        except Exception as e:
            # 记录错误，但不向用户展示详细错误信息
            print(f"创建评论错误: {str(e)}")
            return JsonResponse({'success': False, 'message': '创建评论失败，请稍后再试'})

    return JsonResponse({'success': False, 'message': '请求方法错误'})


@user_type_required(['student', 'admin'])
def toggle_comment_like(request):
    """点赞/取消点赞热搜评论"""
    if request.method == 'POST':
        comment_id = request.POST.get('comment_id')

        try:
            comment = Comment.objects.get(id=comment_id)
            content = comment.content

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
                
                # 创建点赞通知（排除给自己的点赞，但包括匿名评论）
                if comment.author != request.user:
                    sender_name = "匿名用户" if request.user.is_anonymous or (hasattr(request, 'is_anonymous_view') and request.is_anonymous_view) else request.user.username
                    safe_content = content[:50] + '...' if len(content) > 50 else content
                    notification_content = f"{sender_name}点赞了你的评论\"{safe_content}\""
                    
                    Notification.objects.create(
                        recipient=comment.author,
                        sender=request.user if not request.user.is_anonymous else None,
                        type='like',
                        content=notification_content,
                        topic=comment.topic,
                        comment=comment
                    )

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
        
        # 为每个评论添加HTML内容（Markdown渲染）
        for comment in hot_comments:
            comment.html_content = convert_markdown_to_html(comment.content)

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
            
        # 为每个评论添加HTML内容（Markdown渲染）
        for comment in comments:
            comment.html_content = convert_markdown_to_html(comment.content)

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
        
        # 为每个回复添加HTML内容（Markdown渲染）
        for reply in replies:
            reply.html_content = convert_markdown_to_html(reply.content)

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


@user_type_required(['student', 'admin'])
def delete_hot_topic_comment(request):
    """删除评论或回复"""
    if request.method == 'POST':
        comment_id = request.POST.get('comment_id')

        try:
            comment = Comment.objects.get(id=comment_id)

            # 检查权限：只有评论作者和管理员可以删除
            if request.user == comment.author or request.user.user_type == 'admin':
                # 删除评论
                comment.delete()
                return JsonResponse({'success': True, 'message': '评论已删除'})
            else:
                return JsonResponse({'success': False, 'message': '您没有权限删除此评论'})

        except Comment.DoesNotExist:
            return JsonResponse({'success': False, 'message': '评论不存在'})

    return JsonResponse({'success': False, 'message': '请求方法错误'})


def convert_markdown_to_html(text):
    """将Markdown文本转换为HTML，包括数学公式支持和HTML净化"""
    if not text:
        return ""
    
    # 文本过长可能导致内存问题，添加长度限制
    MAX_TEXT_LENGTH = 50000  # 设置一个合理的最大长度
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "\n\n**内容过长，已截断显示**"
        
    try:
        # 定义允许的HTML标签和属性
        allowed_tags = [
            'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'div', 'em', 
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'i', 'img', 'li', 'ol', 'p', 
            'pre', 'span', 'strong', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul'
        ]
        
        allowed_attrs = {
            'a': ['href', 'title', 'class', 'rel'],
            'abbr': ['title'],
            'acronym': ['title'],
            'div': ['class', 'id', 'style'],
            'h1': ['id', 'class'],
            'h2': ['id', 'class'],
            'h3': ['id', 'class'],
            'h4': ['id', 'class'],
            'h5': ['id', 'class'],
            'h6': ['id', 'class'],
            'img': ['src', 'alt', 'title', 'class', 'align'],
            'li': ['class'],
            'ol': ['class'],
            'p': ['class'],
            'pre': ['class'],
            'span': ['class', 'style'],
            'table': ['class', 'border'],
            'td': ['class', 'colspan', 'rowspan'],
            'th': ['class', 'colspan', 'rowspan', 'scope'],
            'ul': ['class']
        }
        
        # 定义安全的URL协议
        allowed_protocols = ['http', 'https', 'mailto', 'tel']
        
        # 使用markdown库转换基本markdown语法
        md = markdown.Markdown(extensions=[
            'markdown.extensions.extra',
            'markdown.extensions.codehilite',
            'markdown.extensions.toc',
        ])
        
        # 先转换为HTML
        html = md.convert(text)
        
        # 检测是否启用简单模式（当检测到服务器内存压力大时使用）
        USE_SIMPLE_MODE = False
        
        # 安全替换函数，处理可能过长的公式
        def safe_formula_replace(match):
            formula = match.group(1).strip()
            # 限制公式长度
            if len(formula) > 500:
                return '<div class="alert alert-warning">公式过长，无法显示</div>'
                
            if USE_SIMPLE_MODE:
                # 简单模式：直接显示代码格式的公式
                return f'<div class="math-block"><code>$${formula}$$</code></div>'
                
            try:
                # 对公式进行URL编码，确保特殊字符能正确传递
                import urllib.parse
                encoded_formula = urllib.parse.quote(formula)
                return f'<div><img align="center" src="https://latex.codecogs.com/svg.latex?{encoded_formula}" class="math-formula"></div>'
            except Exception:
                return f'<div class="math-block"><code>$${formula}$$</code></div>'
        
        def safe_inline_formula_replace(match):
            formula = match.group(1).strip()
            # 限制公式长度
            if len(formula) > 300:
                return '<span class="text-warning">公式过长</span>'
                
            if USE_SIMPLE_MODE:
                # 简单模式：直接显示代码格式的公式
                return f'<code>${formula}$</code>'
                
            try:
                # 对公式进行URL编码，确保特殊字符能正确传递
                import urllib.parse
                encoded_formula = urllib.parse.quote(formula)
                return f'<img align="center" alt="${formula}$" src="https://latex.codecogs.com/svg.latex?{encoded_formula}" class="math-formula inline">'
            except Exception:
                return f'<code>${formula}$</code>'
        
        # 使用正则表达式一次性替换所有公式，避免多次字符串替换操作
        # 处理行间公式：$$...$$（限制最多处理10个公式，避免内存问题）
        html = re.sub(
            r"\$\$(.*?)\$\$", 
            safe_formula_replace, 
            html, 
            count=20,  # 限制替换次数
            flags=re.S
        )
        
        # 处理行内公式：$...$（限制最多处理20个公式，避免内存问题）
        html = re.sub(
            r"\$(.*?)\$", 
            safe_inline_formula_replace, 
            html, 
            count=40,  # 限制替换次数
            flags=re.S
        )
        
        # 使用bleach库净化HTML内容
        cleaned_html = bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attrs,
            protocols=allowed_protocols,
            strip=True
        )
        
        return cleaned_html
    except MemoryError:
        # 捕获内存错误，返回简化版本
        return f"<p>内容过于复杂，无法渲染。原文：</p><pre>{text[:200]}...</pre>"
    except Exception as e:
        # 捕获其他错误
        return f"<p>渲染失败：{str(e)}</p><pre>{text[:200]}...</pre>"


@login_required
def user_notifications(request):
    """用户通知页面"""
    # 获取用户的所有通知
    notifications = Notification.objects.filter(recipient=request.user)
    
    # 按类型分类通知
    likes = notifications.filter(type='like').order_by('-created_at')
    replies = notifications.filter(type='reply').order_by('-created_at')
    system = notifications.filter(type='system').order_by('-created_at')
    
    # 分页处理
    paginator_likes = Paginator(likes, 10)
    paginator_replies = Paginator(replies, 10)
    paginator_system = Paginator(system, 10)
    
    page = request.GET.get('page', 1)
    
    try:
        likes_page = paginator_likes.page(page)
        replies_page = paginator_replies.page(page)
        system_page = paginator_system.page(page)
    except PageNotAnInteger:
        likes_page = paginator_likes.page(1)
        replies_page = paginator_replies.page(1)
        system_page = paginator_system.page(1)
    except EmptyPage:
        likes_page = paginator_likes.page(paginator_likes.num_pages)
        replies_page = paginator_replies.page(paginator_replies.num_pages)
        system_page = paginator_system.page(paginator_system.num_pages)
    
    context = {
        'likes': likes_page,
        'replies': replies_page,
        'system': system_page,
        'unread_count': notifications.filter(is_read=False).count()
    }
    
    return render(request, 'notifications.html', context)


@login_required
def mark_notifications_read(request, notification_type=None):
    """标记通知为已读"""
    if request.method == 'POST':
        if notification_type:
            # 标记特定类型的通知为已读
            Notification.objects.filter(
                recipient=request.user, 
                type=notification_type, 
                is_read=False
            ).update(is_read=True)
        else:
            # 标记所有通知为已读
            Notification.objects.filter(
                recipient=request.user, 
                is_read=False
            ).update(is_read=True)
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error', 'message': '仅支持POST请求'})


@login_required
def unread_notifications_count(request):
    """获取未读通知数量"""
    if request.user.user_type not in ['student', 'admin']:
        return JsonResponse({'count': 0})
    
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})


def record_device_login(request, user):
    """记录设备登录信息并创建系统通知"""
    if not request:
        print("请求对象为空，无法记录设备信息")
        return
    
    try:
        # 获取IP地址
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')  # 默认为本地IP
        
        # 确保IP地址有效
        try:
            # 验证IP地址格式
            ipaddress.ip_address(ip)
        except ValueError:
            print(f"IP地址格式无效: {ip}，使用默认IP")
            ip = '127.0.0.1'
        
        # 解析User-Agent
        user_agent_string = request.META.get('HTTP_USER_AGENT', '')
        print(f"收到的User-Agent: {user_agent_string}")
        
        try:
            if user_agent_string:
                user_agent = user_agents_parse(user_agent_string)
                browser = user_agent.browser.family
                os_family = user_agent.os.family
                device_name = f"{browser} on {os_family}"
                
                if user_agent.is_mobile:
                    device_type = "移动设备"
                elif user_agent.is_tablet:
                    device_type = "平板设备"
                elif user_agent.is_pc:
                    device_type = "电脑"
                else:
                    device_type = "其他设备"
            else:
                device_name = "未知浏览器"
                device_type = "未知设备"
        except Exception as ua_error:
            print(f"解析User-Agent失败: {ua_error}")
            device_name = "未识别设备"
            device_type = "未知类型"
        
        # 获取位置信息
        location = get_location_from_ip(ip)
        print(f"IP地址 {ip} 的位置: {location}")
        
        # 创建设备登录记录
        print(f"准备创建设备登录记录: 用户={user.username}, 设备={device_name}, IP={ip}, 位置={location}")
        
        device_login = DeviceLogin.objects.create(
            user=user,
            device_name=device_name,
            ip_address=ip,
            user_agent=user_agent_string[:500] if user_agent_string else "无设备信息",  # 限制长度
            location=location
        )
        
        # 创建系统通知
        login_time = device_login.login_time.strftime('%Y-%m-%d %H:%M:%S')
        location_info = f"，位置: {location}" if location and location != "未知位置" else ""
        notification_content = f"您的账号于 {login_time} 通过 {device_type}（{device_name}）登录。IP地址: {ip}{location_info}"
        
        Notification.objects.create(
            recipient=user,
            type='system',
            content=notification_content
        )
        
        print(f"设备登录记录和通知创建成功: {device_name}, {ip}, {location}")
        return True
    
    except Exception as e:
        # 记录详细错误但不影响登录流程
        print(f"设备登录记录失败，错误详情: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


@login_required
def test_device_detection(request):
    """测试设备检测功能"""
    user = request.user
    
    # 获取IP地址用于显示
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    # 获取位置信息用于显示
    location = get_location_from_ip(ip)
    
    # 尝试直接记录设备信息
    result = record_device_login(request, user)
    
    # 收集设备信息用于调试
    debug_info = {
        "IP信息": {
            "X_Forwarded_For": request.META.get('HTTP_X_FORWARDED_FOR', '无'),
            "REMOTE_ADDR": request.META.get('REMOTE_ADDR', '无'),
        },
        "User_Agent": request.META.get('HTTP_USER_AGENT', '无'),
        "设备记录结果": "成功" if result else "失败",
        "当前IP": ip,
        "当前位置": location,
        "最近设备记录": []
    }
    
    # 获取最近的设备登录记录
    recent_logins = DeviceLogin.objects.filter(user=user).order_by('-login_time')[:5]
    for login in recent_logins:
        debug_info["最近设备记录"].append({
            "设备名称": login.device_name,
            "IP地址": login.ip_address,
            "位置信息": login.location,
            "登录时间": login.login_time.strftime('%Y-%m-%d %H:%M:%S'),
        })
    
    return render(request, 'debug_device.html', {'debug_info': debug_info})


def get_location_from_ip(ip):
    """
    通过IP地址获取地理位置信息
    使用免费的IP-API服务
    """
    if not ip or ip == '127.0.0.1' or ip.startswith('192.168.') or ip.startswith('10.'):
        return "本地网络"
    
    try:
        # 使用IP-API的免费服务，不需要API密钥
        response = requests.get(f'http://ip-api.com/json/{ip}?lang=zh-CN', timeout=5)
        data = response.json()
        
        if data['status'] == 'success':
            # 返回城市和国家/地区
            city = data.get('city', '')
            country = data.get('country', '')
            region = data.get('regionName', '')
            
            location_parts = []
            if country:
                location_parts.append(country)
            if region and region != city:  # 避免重复显示相同的城市和地区名
                location_parts.append(region)
            if city:
                location_parts.append(city)
                
            location = ' '.join(location_parts)
            return location or "未知位置"
        else:
            print(f"IP位置查询失败: {data.get('message', '未知错误')}")
            return "未知位置"
    except Exception as e:
        print(f"IP位置查询异常: {str(e)}")
        return "未知位置"


@user_type_required(['student', 'admin'])
def ratings_list(request):
    """评分系统列表页面"""
    # 获取所有激活状态的评分
    ratings = Rating.objects.filter(is_active=True)
    
    # 获取搜索关键词
    query = request.GET.get('q', '')
    if query:
        ratings = ratings.filter(title__icontains=query)
    
    # 获取排序方式
    sort_by = request.GET.get('sort_by', 'newest')
    
    # 根据排序方式进行排序
    if sort_by == 'newest':
        ratings = ratings.order_by('-created_at')
    elif sort_by == 'rating':
        # 按平均评分排序，需要用到自定义的 average_score 方法
        ratings = sorted(ratings, key=lambda x: x.average_score, reverse=True)
    elif sort_by == 'popular':
        # 按评价人数排序
        ratings = sorted(ratings, key=lambda x: x.ratings_count, reverse=True)
    elif sort_by == 'hot':
        # 按热度排序
        ratings = sorted(ratings, key=lambda x: x.heat_score, reverse=True)
    
    # 分页处理
    paginator = Paginator(ratings, 9)  # 每页显示9条评分
    page = request.GET.get('page')
    try:
        ratings = paginator.page(page)
    except PageNotAnInteger:
        ratings = paginator.page(1)
    except EmptyPage:
        ratings = paginator.page(paginator.num_pages)
    
    context = {
        'ratings': ratings,
        'query': query,
        'sort_by': sort_by
    }
    
    return render(request, 'ratings.html', context)


@user_type_required(['student', 'admin'])
def rating_detail(request, rating_id):
    """评分详情页面"""
    rating = get_object_or_404(Rating, id=rating_id, is_active=True)
    
    # 获取当前用户的评分记录
    user_rating = None
    if request.user.is_authenticated:
        user_rating = UserRating.objects.filter(rating=rating, user=request.user).first()
    
    # 获取该评分项目的所有评论，按热度排序
    comments = RatingComment.objects.filter(rating=rating, parent=None).order_by('-created_at')
    
    # 为每条评论转换Markdown格式
    for comment in comments:
        comment.html_content = convert_markdown_to_html(comment.content)

    # 转换评分详情的Markdown
    rating.html_description = convert_markdown_to_html(rating.description)
    
    # 分页
    paginator = Paginator(comments, 10)  # 每页10条评论
    page = request.GET.get('page')
    
    try:
        comments = paginator.page(page)
    except PageNotAnInteger:
        comments = paginator.page(1)
    except EmptyPage:
        comments = paginator.page(paginator.num_pages)
    
    # 计算评分分布
    score_distribution = []
    total_ratings = rating.user_ratings.count()
    
    if total_ratings > 0:
        for score in range(1, 6):
            count = rating.user_ratings.filter(score=score).count()
            percentage = round((count / total_ratings) * 100) if total_ratings > 0 else 0
            score_distribution.append({
                'score': score,
                'count': count,
                'percentage': percentage
            })
    else:
        for score in range(1, 6):
            score_distribution.append({
                'score': score,
                'count': 0,
                'percentage': 0
            })
    
    # 获取最近的用户评分
    recent_ratings = UserRating.objects.filter(rating=rating).order_by('-created_at')[:5]
    
    context = {
        'rating': rating,
        'user_rating': user_rating,
        'user_rating_form': UserRatingForm(instance=user_rating),
        'comment_form': RatingCommentForm(),
        'comments': comments,
        'score_distribution': score_distribution,
        'recent_ratings': recent_ratings,
    }
    
    return render(request, 'rating_detail.html', context)


@user_type_required(['student', 'admin'])
def create_rating(request):
    """创建评分项目"""
    if request.method == 'POST':
        form = RatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.author = request.user
            # 保存匿名设置
            rating.is_anonymous = form.cleaned_data.get('is_anonymous', False)
            rating.save()
            
            messages.success(request, '评分项目创建成功！')
            return redirect('rating_detail', rating_id=rating.id)
    else:
        form = RatingForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'create_rating.html', context)


@user_type_required(['student', 'admin'])
def rate_rating(request, rating_id):
    """为评分项目评分"""
    rating = get_object_or_404(Rating, id=rating_id, is_active=True)
    
    if request.method == 'POST':
        # 获取或创建用户评分记录
        user_rating, created = UserRating.objects.get_or_create(
            rating=rating,
            user=request.user,
            defaults={'score': 0}
        )
        
        # 获取用户提交的评分
        form = UserRatingForm(request.POST, instance=user_rating)
        if form.is_valid():
            user_rating = form.save()
            
            if created or user_rating.score > 0:  # 确保只在新评分或修改评分时发通知
                # 发送通知给评分作者（如果评分者不是作者自己）
                if rating.author != request.user:
                    notification_content = f"{request.user.username} 给你的评分 {rating.title} 打了 {user_rating.score} 星"
                    
                    Notification.objects.create(
                        recipient=rating.author,
                        sender=request.user,
                        type='reply',  # 使用reply类型表示评分
                        content=notification_content
                    )
            
            messages.success(request, '评分成功！')
        else:
            messages.error(request, '评分失败，请确保评分为1-5之间的整数！')
    
    return redirect('rating_detail', rating_id=rating.id)


@user_type_required(['student', 'admin'])
def comment_rating(request, rating_id):
    """评论评分"""
    rating = get_object_or_404(Rating, id=rating_id, is_active=True)
    
    if request.method == 'POST':
        form = RatingCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.rating = rating
            comment.author = request.user
            comment.save()
            
            # 发送通知给评分作者（如果评论者不是作者自己）
            if rating.author != request.user:
                sender_name = "匿名用户" if comment.is_anonymous else request.user.username
                safe_content = comment.content[:50] + "..." if len(comment.content) > 50 else comment.content
                notification_content = f"{sender_name} 评论了你的评分 {rating.title}：\"{safe_content}\""
                
                Notification.objects.create(
                    recipient=rating.author,
                    sender=request.user,
                    type='reply',  # 使用reply类型表示评论
                    content=notification_content
                )
            
            messages.success(request, '评论发表成功！')
            return redirect('rating_detail', rating_id=rating.id)
        else:
            messages.error(request, '评论发表失败，请重试！')
    
    return redirect('rating_detail', rating_id=rating.id)


@user_type_required(['student', 'admin'])
def reply_comment(request, comment_id):
    """回复评论"""
    parent_comment = get_object_or_404(RatingComment, id=comment_id)
    rating = parent_comment.rating
    
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        is_anonymous = request.POST.get('is_anonymous') == 'on'
        
        if content:
            comment = RatingComment(
                rating=rating,
                author=request.user,
                content=content,
                parent=parent_comment,
                is_anonymous=is_anonymous
            )
            comment.save()
            
            # 创建通知，通知原评论作者有人回复了评论
            if parent_comment.author != request.user:
                sender_name = "匿名用户" if is_anonymous else request.user.username
                safe_content = content[:50] + "..." if len(content) > 50 else content
                notification_content = f"{sender_name} 回复了你的评论：\"{safe_content}\""
                
                Notification.objects.create(
                    recipient=parent_comment.author,
                    sender=request.user,
                    type='reply',
                    content=notification_content
                )
            
            messages.success(request, '回复发表成功！')
    
    return redirect('rating_detail', rating_id=rating.id)


@user_type_required(['student', 'admin'])
def like_comment(request, comment_id):
    """点赞/取消点赞评论"""
    if request.method == 'POST':
        comment = get_object_or_404(RatingComment, id=comment_id)
        
        # 查找是否已经点赞
        like, created = RatingCommentLike.objects.get_or_create(
            comment=comment,
            user=request.user
        )
        
        # 如果已经点赞，则取消点赞
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
            
            # 创建通知（如果不是给自己点赞）
            if comment.author != request.user:
                sender_name = "匿名用户" if comment.is_anonymous else request.user.username
                safe_content = comment.content[:50] + "..." if len(comment.content) > 50 else comment.content
                notification_content = f"{sender_name} 点赞了你的评论：\"{safe_content}\""
                
                Notification.objects.create(
                    recipient=comment.author,
                    sender=request.user,
                    type='like',
                    content=notification_content
                )
        
        return JsonResponse({
            'success': True,
            'liked': liked,
            'likes_count': comment.likes_count
        })
    
    return JsonResponse({'success': False, 'error': '请求方法不允许'})


@user_type_required(['student', 'admin'])
def delete_comment(request, comment_id):
    """删除评论"""
    if request.method == 'POST':
        comment = get_object_or_404(RatingComment, id=comment_id)
        
        # 只有评论作者或管理员可以删除评论
        if request.user == comment.author or request.user.user_type == 'admin':
            comment.delete()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': '您没有权限删除此评论'})
    
    return JsonResponse({'success': False, 'error': '请求方法不允许'})


@user_type_required(['student', 'admin'])
def delete_rating(request, rating_id):
    """删除评分项目"""
    rating = get_object_or_404(Rating, id=rating_id)
    
    # 检查权限：只有评分作者或管理员可以删除
    if request.user == rating.author or request.user.user_type == 'admin':
        # 标记为不活跃而不是直接删除，保留历史数据
        rating.delete()
        messages.success(request, '评分项目已删除')
        return redirect('ratings')
    else:
        messages.error(request, '您没有权限删除此评分项目')
        return redirect('rating_detail', rating_id=rating.id)


@login_required
def get_notifications_ajax(request):
    """AJAX获取通知数据"""
    notification_type = request.GET.get('type', 'like')
    page = request.GET.get('page', 1)
    
    # 获取用户的通知
    notifications = Notification.objects.filter(recipient=request.user, type=notification_type).order_by('-created_at')
    
    # 分页处理
    paginator = Paginator(notifications, 10)  # 每页10条
    
    try:
        notifications_page = paginator.page(page)
    except PageNotAnInteger:
        notifications_page = paginator.page(1)
    except EmptyPage:
        notifications_page = paginator.page(paginator.num_pages)
    
    # 准备返回的数据
    notifications_data = []
    for notification in notifications_page:
        notification_data = {
            'id': notification.id,
            'content': notification.content,
            'is_read': notification.is_read,
            'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M'),
            'sender_username': notification.sender.username if notification.sender else '系统',
            'comment_id': notification.comment.id if notification.comment else None,
            'topic_id': notification.topic.id if notification.topic else None,
        }
        notifications_data.append(notification_data)
    
    return JsonResponse({
        'notifications': notifications_data,
        'has_next': notifications_page.has_next(),
        'has_previous': notifications_page.has_previous(),
        'current_page': notifications_page.number,
        'total_pages': paginator.num_pages,
    })
