from django.contrib import admin
from .models import User, Subject, Assignment, CompletionRecord, HotTopic, HotTopicLike

admin.site.register(User)
admin.site.register(Subject)
admin.site.register(Assignment)
admin.site.register(CompletionRecord)
admin.site.register(HotTopic)
admin.site.register(HotTopicLike)
