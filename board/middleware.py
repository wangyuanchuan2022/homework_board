from django.utils.deprecation import MiddlewareMixin
import re
from django.utils import timezone


class UserActivityMiddleware:
    """
    中间件：在用户访问通知计数API时更新其最后活动时间
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 请求处理前的代码
        response = self.get_response(request)
        # 请求处理后的代码

        # 只有已登录用户才更新活动时间
        if request.user.is_authenticated and request.path == '/api/notifications/unread-count/':
            # 更新用户的最后活动时间
            request.user.last_activity = timezone.now()
            request.user.save(update_fields=['last_activity'])

        return response
