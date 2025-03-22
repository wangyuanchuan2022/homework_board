from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from .models import Assignment, Subject, CompletionRecord
from .forms import AssignmentForm

def is_teacher(user):
    return user.is_authenticated and user.role == 'teacher'

@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    assignments = Assignment.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'teacher_dashboard.html', {'assignments': assignments})

