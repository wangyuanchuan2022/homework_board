# 作业数据清理指南

作业板系统提供了自动清理功能，用于删除超过一定时间的旧作业，以保持数据库的大小合理，并防止主键(ID)过大。

## 手动清理

管理员可以通过管理界面手动触发清理：

1. 登录管理员账号
2. 在作业管理卡片右上角，点击"清理旧作业"按钮
3. 在弹出的对话框中输入要删除的天数（默认90天）
4. 点击"确认清理"按钮

## 命令行清理

系统提供了一个Django管理命令，可以在命令行中执行清理操作：

```bash
# 删除90天前的作业（默认）
python manage.py cleanup_old_assignments

# 删除指定天数（如180天）前的作业
python manage.py cleanup_old_assignments --days=180

# 模拟运行（不实际删除，仅查看会删除什么）
python manage.py cleanup_old_assignments --dry-run
```

## 设置定时任务

为了自动化清理过程，建议设置定时任务。以下是在Linux系统上使用crontab设置每月执行一次清理的方法：

1. 编辑crontab：

```bash
crontab -e
```

2. 添加以下内容（每月1日的凌晨3:00执行）：

```
0 3 1 * * cd /path/to/your/project && /path/to/your/python /path/to/your/project/manage.py cleanup_old_assignments >> /path/to/your/project/logs/cleanup.log 2>&1
```

将路径替换为你的实际项目路径。

## 清理策略

建议的清理策略：

- **保留期限**：默认保留90天（约3个月）的作业数据，这通常足够满足学期内的查询需求。
- **执行时间**：选择系统负载较低的时间（如凌晨）执行清理任务。
- **备份**：在执行大规模清理前，建议先备份数据库。

## 定制清理逻辑

如果需要更复杂的清理逻辑（例如，仅删除已完成的作业），可以修改`board/management/commands/cleanup_old_assignments.py`文件中的过滤条件。 