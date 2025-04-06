from django.utils.deprecation import MiddlewareMixin
import re
from django.utils import timezone


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    添加安全相关的HTTP头部到所有响应
    """

    def process_response(self, request, response):
        # 内容安全策略 (CSP) - 限制页面可以加载的资源
        # 对于生产环境，这些策略应该更严格
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://latex.codecogs.com https://*.unsplash.com; "
            "font-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self';"
        )

        # X-XSS-Protection - 为不支持CSP的旧浏览器提供XSS保护
        response['X-XSS-Protection'] = '1; mode=block'

        # X-Content-Type-Options - 防止MIME类型嗅探
        response['X-Content-Type-Options'] = 'nosniff'

        # X-Frame-Options - 防止点击劫持
        response['X-Frame-Options'] = 'DENY'

        # Referrer-Policy - 控制Referer头的发送
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions-Policy - 限制浏览器特性
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        return response


class XSSProtectionMiddleware(MiddlewareMixin):
    """
    检查POST请求中的XSS攻击
    """

    def process_request(self, request):
        if request.method == 'POST':
            # 定义可能的XSS模式
            xss_patterns = [
                r'<script', r'javascript:', r'on\w+\s*=', r'vbscript:',
                r'data:\s*text/html', r'<iframe', r'<object', r'<embed'
            ]

            # 获取POST数据
            post_data = request.POST.copy()

            # 检查所有字段
            for key, value in post_data.items():
                if isinstance(value, str):
                    for pattern in xss_patterns:
                        if re.search(pattern, value, re.IGNORECASE):
                            # 可能的XSS攻击，记录但继续处理
                            # 让视图级别的验证处理它，或者在这里阻止它
                            print(f"可能的XSS攻击: {key}={value}")

        return None


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
