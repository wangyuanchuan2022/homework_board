"""
URL configuration for homework_board project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
from django.urls import path
from django.views import static

from board import views
from homework_board import settings

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.login_view, name="login"),
    path("accounts/login/", views.login_view, name="account_login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/save-hidden-subjects/", views.save_hidden_subjects, name="save_hidden_subjects"),
    path("settings/delete-account/", views.delete_my_account, name="delete_my_account"),
    path("settings/update-username/", views.update_username, name="update_username"),
    path("settings/change-password/", views.change_password, name="change_password"),
    path("teacher/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("assignments/create/", views.create_assignment, name="create_assignment"),
    path("assignments/<int:pk>/", views.assignment_detail, name="assignment_detail"),
    path("assignments/<int:pk>/edit/", views.edit_assignment, name="edit_assignment"),
    path("hot-topics/", views.hot_topics_view, name="hot_topics"),
    path("hot-topics/<int:topic_id>/", views.hot_topic_detail_view, name="hot_topic_detail"),
    path("api/toggle-assignment/", views.toggle_assignment_completion, name="toggle_assignment"),
    path("api/create-admin/", views.create_admin_user, name="create_admin"),
    path("api/init-subjects/", views.init_subjects, name="init_subjects"),
    path("api/create-user/", views.create_user, name="create_user"),
    path("api/delete-user/", views.delete_user, name="delete_user"),
    path("api/delete-assignment/", views.delete_assignment, name="delete_assignment"),
    path("api/subject-suggestions/", views.subject_suggestions, name="subject_suggestions"),
    path("api/cleanup-old-assignments/", views.cleanup_old_assignments, name="cleanup_old_assignments"),
    path("api/get_today_homework/", views.get_today_homework, name="get_today_homework"),
    path("api/hot-topics/create/", views.create_hot_topic, name="create_hot_topic"),
    path("api/hot-topics/delete/", views.delete_hot_topic, name="delete_hot_topic"),
    path("api/hot-topics/pin/", views.pin_hot_topic, name="pin_hot_topic"),
    path("api/hot-topics/like/", views.toggle_hot_topic_like, name="toggle_hot_topic_like"),
    path("api/hot-topics/recent/", views.get_recent_topics, name="get_recent_topics"),
    path("api/comments/create/", views.create_comment, name="create_comment"),
    path("api/comments/like/", views.toggle_comment_like, name="toggle_comment_like"),
    path("api/comments/hot/", views.get_hot_comments, name="get_hot_comments"),
    path("api/comments/all/", views.get_comments, name="get_comments"),
    path("api/comments/replies/", views.get_replies, name="get_replies"),
    path("api/admin/students/", views.get_admin_students, name="get_admin_students"),
    path("api/admin/teachers/", views.get_admin_teachers, name="get_admin_teachers"),
    path("api/admin/assignments/", views.get_admin_assignments, name="get_admin_assignments"),
    url(r'^static/(?P<path>.*)$', static.serve, {'document_root': settings.STATIC_ROOT}, name='static'),
]
