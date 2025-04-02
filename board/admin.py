from django.contrib import admin
from .models import *

admin.site.register(User)
admin.site.register(Subject)
admin.site.register(Assignment)
admin.site.register(CompletionRecord)
admin.site.register(HotTopic)
admin.site.register(HotTopicLike)
admin.site.register(Comment)
admin.site.register(CommentLike)
admin.site.register(Notification)
admin.site.register(DeviceLogin)
