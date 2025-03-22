from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from functools import wraps
import calendar
import datetime
from .models import User, Subject, Assignment, CompletionRecord, HotTopic, HotTopicLike
from .forms import CustomUserCreationForm, CustomAuthenticationForm, AssignmentForm, BatchAssignmentForm, UpdateUsernameForm
import json
from django.db import models
from django.views.decorators.csrf import csrf_exempt
from django.db.models import F, Count, Q
from django.core.paginator import Paginator

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
            
            # 按科目名称排序
            for subject_name in sorted(subject_assignments.keys()):
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
    students_list = User.objects.filter(user_type='student').order_by('username')
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
    
    context = {
        'calendar': cal,
        'today': today,
        'tomorrow': tomorrow,
        'selected_date': selected_date,
        'current_year': current_year,
        'current_month': current_month,
        'current_month_name': current_month_name,
        'subject_assignments': subject_assignments,
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

@user_type_required(['teacher'])
def create_assignment(request):
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
        form = AssignmentForm()
        batch_form = BatchAssignmentForm()
    
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

@user_type_required(['admin'])
def delete_assignment(request):
    """API: 删除作业"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            assignment_id = data.get('assignment_id')
            
            if not assignment_id:
                return JsonResponse({'success': False, 'message': '缺少作业ID'})
                
            assignment = Assignment.objects.get(id=assignment_id)
            assignment.delete()
            
            return JsonResponse({'success': True})
        except Assignment.DoesNotExist:
            return JsonResponse({'success': False, 'message': '作业不存在'})
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
    
    return render(request, 'settings.html', {
        'all_subjects': all_subjects,
        'user_hidden_subjects': user_hidden_subjects,
        'username_form': username_form
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
    
    context = {
        'top_topics': top_topics,
        'user_liked_topics': user_liked_topics,
    }
    
    return render(request, 'hot_topics.html', context)

@user_type_required(['student', 'admin'])
def create_hot_topic(request):
    """创建热搜"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        
        if not title:
            return JsonResponse({'success': False, 'message': '标题不能为空'})
        
        # 创建热搜
        HotTopic.objects.create(
            title=title,
            content=content,
            author=request.user
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
