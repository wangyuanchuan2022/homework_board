from django.core.management.base import BaseCommand
from django.utils import timezone
from board.models import Assignment, CompletionRecord
import datetime

class Command(BaseCommand):
    help = '删除三个月前创建的作业及其相关记录'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='要删除的作业的最小天数（默认：90天）'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将要删除的作业，不实际删除'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        # 计算截止日期（当前日期减去指定天数）
        cutoff_date = timezone.now().date() - datetime.timedelta(days=days)
        
        # 获取截止日期之前的所有作业
        old_assignments = Assignment.objects.filter(created_at__date__lt=cutoff_date)
        total_count = old_assignments.count()
        
        self.stdout.write(f"找到 {total_count} 个创建于 {cutoff_date} 之前的作业")
        
        if dry_run:
            # 仅显示将要删除的作业，不实际删除
            for assignment in old_assignments:
                completion_count = CompletionRecord.objects.filter(assignment=assignment).count()
                self.stdout.write(f"将删除: {assignment.title} (ID: {assignment.id}, 完成记录: {completion_count})")
            self.stdout.write(self.style.SUCCESS(f"模拟运行完成，找到 {total_count} 个要删除的作业"))
        else:
            # 实际删除作业（Django会自动删除关联的CompletionRecord记录，因为设置了on_delete=models.CASCADE）
            old_assignments.delete()
            self.stdout.write(self.style.SUCCESS(f"成功删除了 {total_count} 个旧作业及其关联记录")) 