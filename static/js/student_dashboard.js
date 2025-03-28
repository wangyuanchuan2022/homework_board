document.addEventListener('DOMContentLoaded', function () {
    // 恢复滚动位置
    const savedScroll = localStorage.getItem('dashboardScroll');
    if (savedScroll) {
        window.scrollTo({
            top: parseInt(savedScroll),
            behavior: 'instant'
        });
        localStorage.removeItem('dashboardScroll');
    }

    // 日期选择
    const calendarDays = document.querySelectorAll('.calendar-day');
    calendarDays.forEach(day => {
        day.addEventListener('click', function (e) {
            e.preventDefault();
            const date = this.dataset.date;
            updateContent(date);
        });
    });

    // 今天按钮
    document.getElementById('todayBtn').addEventListener('click', function (e) {
        e.preventDefault();
        updateContent();
    });

    // 月份导航
    document.getElementById('prevMonth').addEventListener('click', function (e) {
        e.preventDefault();
        const currentDate = new Date(currentYear, currentMonth - 1, 1);
        const prevMonth = new Date(currentDate);
        prevMonth.setMonth(currentDate.getMonth() - 1);

        const date = prevMonth.getFullYear() + "-" +
            (prevMonth.getMonth() + 1) + "-1";
        updateContent(date);
    });

    document.getElementById('nextMonth').addEventListener('click', function (e) {
        e.preventDefault();
        const currentDate = new Date(currentYear, currentMonth - 1, 1);
        const nextMonth = new Date(currentDate);
        nextMonth.setMonth(currentDate.getMonth() + 1);

        const date = nextMonth.getFullYear() + "-" +
            (nextMonth.getMonth() + 1) + "-1";
        updateContent(date);
    });

    // 更新内容的函数
    function updateContent(date = null, assignmentId = null) {
        // 保存当前滚动位置
        localStorage.setItem('dashboardScroll', window.scrollY);

        // 构建请求参数
        const params = new URLSearchParams();
        if (date) {
            params.append('date', date);
        }
        if (assignmentId) {
            params.append('assignment_id', assignmentId);
        }

        // 显示加载中状态
        document.body.style.cursor = 'wait';

        // 获取新内容
        fetch(`${dashboardUrl}?${params.toString()}`)
            .then(response => response.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                // 更新日历部分
                const newCalendar = doc.querySelector('.card.mb-4');
                const oldCalendar = document.querySelector('.card.mb-4');
                if (newCalendar && oldCalendar) {
                    oldCalendar.innerHTML = newCalendar.innerHTML;
                }

                // 更新信息提示
                const newAlert = doc.querySelector('.glass-alert');
                const oldAlert = document.querySelector('.glass-alert');
                if (newAlert && oldAlert) {
                    oldAlert.innerHTML = newAlert.innerHTML;
                }

                // 更新作业列表
                const newAssignments = doc.querySelector('.row.g-4:last-child');
                const oldAssignments = document.querySelector('.row.g-4:last-child');
                if (newAssignments && oldAssignments) {
                    oldAssignments.innerHTML = newAssignments.innerHTML;
                }

                // 恢复鼠标样式
                document.body.style.cursor = 'default';

                // 重新绑定事件
                bindEvents();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('加载失败，请重试');
                document.body.style.cursor = 'default';
            });
    }

    // 移除所有已绑定的事件
    function removeAllEventListeners() {
        // 移除日期单元格的事件
        document.querySelectorAll('.calendar-day').forEach(day => {
            const newDay = day.cloneNode(true);
            day.parentNode.replaceChild(newDay, day);
        });

        // 移除导航按钮的事件
        const todayBtn = document.getElementById('todayBtn');
        if (todayBtn) {
            const newTodayBtn = todayBtn.cloneNode(true);
            todayBtn.parentNode.replaceChild(newTodayBtn, todayBtn);
        }

        const prevMonth = document.getElementById('prevMonth');
        if (prevMonth) {
            const newPrevMonth = prevMonth.cloneNode(true);
            prevMonth.parentNode.replaceChild(newPrevMonth, prevMonth);
        }

        const nextMonth = document.getElementById('nextMonth');
        if (nextMonth) {
            const newNextMonth = nextMonth.cloneNode(true);
            nextMonth.parentNode.replaceChild(newNextMonth, nextMonth);
        }

        // 移除作业链接的事件
        document.querySelectorAll('.assignment-link').forEach(link => {
            const newLink = link.cloneNode(true);
            link.parentNode.replaceChild(newLink, link);
        });

        // 移除展开/收起按钮的事件
        document.querySelectorAll('.toggle-description').forEach(button => {
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);
        });

        // 移除复选框的事件
        document.querySelectorAll('.assignment-checkbox').forEach(checkbox => {
            const newCheckbox = checkbox.cloneNode(true);
            checkbox.parentNode.replaceChild(newCheckbox, checkbox);
        });

        // 移除复制按钮的事件
        const copyBtn = document.getElementById('copyAssignmentsBtn');
        if (copyBtn) {
            const newCopyBtn = copyBtn.cloneNode(true);
            copyBtn.parentNode.replaceChild(newCopyBtn, copyBtn);
        }
    }

    // 获取当前显示日期
    function getCurrentDisplayDate() {
        // 首先尝试从URL参数中获取
        const urlParams = new URLSearchParams(window.location.search);
        const dateParam = urlParams.get('date');

        if (dateParam) {
            // 格式为YYYY-MM-DD
            const dateParts = dateParam.split('-').map(part => parseInt(part, 10));
            // 注意月份从0开始
            return new Date(dateParts[0], dateParts[1] - 1, dateParts[2]);
        }

        // 如果URL中没有日期参数，尝试从页面元素中获取
        const dateDisplay = document.querySelector('.glass-alert strong');
        if (dateDisplay) {
            // 格式为YYYY年MM月DD日
            const dateText = dateDisplay.textContent;
            const yearMatch = dateText.match(/(\d{4})年/);
            const monthMatch = dateText.match(/(\d{1,2})月/);
            const dayMatch = dateText.match(/(\d{1,2})日/);

            if (yearMatch && monthMatch && dayMatch) {
                // 注意月份从0开始
                return new Date(
                    parseInt(yearMatch[1], 10),
                    parseInt(monthMatch[1], 10) - 1,
                    parseInt(dayMatch[1], 10)
                );
            }
        }

        // 都获取不到，返回当前日期
        return new Date();
    }

    // 绑定事件的函数
    function bindEvents() {
        // 先移除所有已绑定的事件，避免重复绑定
        removeAllEventListeners();

        // 重新绑定日期选择事件
        document.querySelectorAll('.calendar-day').forEach(day => {
            day.addEventListener('click', function (e) {
                e.preventDefault();
                const date = this.dataset.date;
                updateContent(date);
            });
        });

        // 重新绑定今天按钮事件
        const todayBtn = document.getElementById('todayBtn');
        if (todayBtn) {
            todayBtn.addEventListener('click', function (e) {
                e.preventDefault();
                updateContent();
            });
        }

        // 重新绑定月份导航事件
        const prevMonth = document.getElementById('prevMonth');
        if (prevMonth) {
            prevMonth.addEventListener('click', function (e) {
                e.preventDefault();
                // 获取当前显示的日期
                const currentDate = getCurrentDisplayDate();
                // 计算上个月的日期
                const prevMonthDate = new Date(currentDate);
                prevMonthDate.setDate(1); // 设置为当月1号
                prevMonthDate.setMonth(currentDate.getMonth() - 1); // 月份减1

                const dateStr = prevMonthDate.getFullYear() + "-" +
                    (prevMonthDate.getMonth() + 1) + "-1";
                updateContent(dateStr);
            });
        }

        const nextMonth = document.getElementById('nextMonth');
        if (nextMonth) {
            nextMonth.addEventListener('click', function (e) {
                e.preventDefault();
                // 获取当前显示的日期
                const currentDate = getCurrentDisplayDate();
                // 计算下个月的日期
                const nextMonthDate = new Date(currentDate);
                nextMonthDate.setDate(1); // 设置为当月1号
                nextMonthDate.setMonth(currentDate.getMonth() + 1); // 月份加1

                const dateStr = nextMonthDate.getFullYear() + "-" +
                    (nextMonthDate.getMonth() + 1) + "-1";
                updateContent(dateStr);
            });
        }

        // 重新绑定作业链接点击事件
        document.querySelectorAll('.assignment-link').forEach(link => {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                const date = this.dataset.date;
                const assignmentId = this.dataset.assignmentId;
                updateContent(date, assignmentId);
            });
        });

        // 绑定展开/收起描述按钮事件
        document.querySelectorAll('.toggle-description').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation(); // 阻止冒泡，避免触发作业链接的点击事件
                
                const container = this.closest('.assignment-description');
                const preview = container.querySelector('.description-preview');
                const full = container.querySelector('.description-full');
                const action = this.getAttribute('data-action');
                
                if (action === 'expand') {
                    // 展开操作
                    preview.style.display = 'none';
                    full.style.display = 'inline';
                    this.innerHTML = '<i class="bi bi-arrows-collapse"></i> 收起';
                    this.setAttribute('data-action', 'collapse');
                } else {
                    // 收起操作
                    preview.style.display = 'inline';
                    full.style.display = 'none';
                    this.innerHTML = '<i class="bi bi-arrows-expand"></i> 展开';
                    this.setAttribute('data-action', 'expand');
                }
            });
        });

        // 重新绑定复选框事件
        document.querySelectorAll('.assignment-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', function (e) {
                e.stopPropagation();
                const assignmentId = this.dataset.id;
                const listItem = this.closest('.assignment-item');
                const assignmentLink = listItem.querySelector('.assignment-link');
                const isChecked = this.checked;

                // 显示临时的加载状态
                const originalCursor = document.body.style.cursor;
                document.body.style.cursor = 'wait';
                this.disabled = true;

                fetch(toggleAssignmentUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({
                        assignment_id: assignmentId
                    })
                })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('服务器响应错误: ' + response.status);
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.success) {
                            this.checked = data.completed;
                            if (data.completed) {
                                assignmentLink.classList.add('text-decoration-line-through');
                            } else {
                                assignmentLink.classList.remove('text-decoration-line-through');
                            }

                            // 显示简短的状态提示
                            const statusMsg = document.createElement('div');
                            statusMsg.className = 'alert alert-success py-1 mt-2 small status-alert';
                            statusMsg.innerHTML = `<i class="bi bi-${data.completed ? 'check' : 'x-lg'} me-1"></i> ${data.completed ? '已标记为完成' : '已标记为未完成'}`;
                            listItem.appendChild(statusMsg);

                            // 2秒后移除消息
                            setTimeout(() => {
                                if (listItem.contains(statusMsg)) {
                                    listItem.removeChild(statusMsg);
                                }
                            }, 2000);
                        } else {
                            this.checked = !isChecked;
                            alert('操作失败，请重试');
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('操作失败，请重试');
                        this.checked = !isChecked;
                    })
                    .finally(() => {
                        document.body.style.cursor = originalCursor;
                        this.disabled = false;
                    });
            });
        });

        // 重新绑定复制按钮事件
        const copyBtn = document.getElementById('copyAssignmentsBtn');
        if (copyBtn) {
            copyBtn.addEventListener('click', copyAssignmentsToClipboard);
        }
    }

    // 复制作业到剪贴板的函数
    function copyAssignmentsToClipboard() {
        // 从页面中提取作业信息
        let copyText = '';
        const subjectCards = document.querySelectorAll('.subject-card');

        subjectCards.forEach(card => {
            const subjectName = card.querySelector('.card-header h5').textContent.trim();
            const assignments = Array.from(card.querySelectorAll('.assignment-item'));

            if (assignments.length > 0) {
                copyText += subjectName + '：\n';

                assignments.forEach((assignment, index) => {
                    const titleElement = assignment.querySelector('.assignment-title');
                    // 获取作业标题但过滤掉可能包含的"明天截止"标签
                    let titleText = '';
                    if (titleElement && titleElement.childNodes.length > 0) {
                        titleText = titleElement.childNodes[0].textContent.trim();
                    } else if (titleElement) {
                        titleText = titleElement.textContent.replace(/明天截止$/g, '').trim();
                    }

                    const isDueTomorrow = assignment.classList.contains('bg-warning-subtle');

                    copyText += (index + 1) + '.' + titleText;
                    if (!isDueTomorrow) {
                        copyText += '（明不收）';
                    }
                    copyText += '\n';
                });

                copyText += '\n';
            }
        });

        // 尝试使用现代剪贴板API
        const copyToClipboard = async (text) => {
            try {
                // 首先尝试使用document.execCommand('copy')作为主要方法
                const textArea = document.createElement('textarea');
                textArea.value = text.trim();
                textArea.style.position = 'fixed';
                textArea.style.top = '0';
                textArea.style.left = '0';
                textArea.style.width = '2em';
                textArea.style.height = '2em';
                textArea.style.padding = '0';
                textArea.style.border = 'none';
                textArea.style.outline = 'none';
                textArea.style.boxShadow = 'none';
                textArea.style.background = 'transparent';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();

                const success = document.execCommand('copy');
                document.body.removeChild(textArea);

                if (success) {
                    return true;
                }

                // 如果execCommand失败，尝试使用navigator.clipboard API
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(text.trim());
                    return true;
                }

                return false;
            } catch (error) {
                console.error('复制失败:', error);
                return false;
            }
        };

        copyToClipboard(copyText)
            .then(success => {
                const btn = document.getElementById('copyAssignmentsBtn');
                if (!btn) return;

                const originalText = btn.innerHTML;

                if (success) {
                    btn.innerHTML = '<i class="bi bi-check-lg me-1"></i> 复制成功';
                    btn.classList.remove('btn-outline-primary');
                    btn.classList.add('btn-success');

                    // 显示复制内容的调试提示
                    console.log('已复制内容:', copyText);
                } else {
                    btn.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i> 复制失败';
                    btn.classList.remove('btn-outline-primary');
                    btn.classList.add('btn-danger');

                    // 创建临时的显示区域
                    const textDisplay = document.createElement('div');
                    textDisplay.className = 'mt-2 p-2 bg-light text-dark small';
                    textDisplay.style.borderRadius = '4px';
                    textDisplay.style.whiteSpace = 'pre-wrap';
                    textDisplay.style.maxHeight = '200px';
                    textDisplay.style.overflow = 'auto';
                    textDisplay.textContent = copyText.trim();

                    const alertDiv = document.querySelector('.glass-alert');
                    if (!alertDiv) return;

                    alertDiv.appendChild(textDisplay);

                    // 添加手动复制的说明
                    const helpText = document.createElement('p');
                    helpText.className = 'mt-1 small text-muted';
                    helpText.innerHTML = '请手动选择上方文本并复制（Ctrl+C 或 ⌘+C）';
                    textDisplay.after(helpText);

                    // 10秒后移除显示区域
                    setTimeout(() => {
                        if (alertDiv.contains(textDisplay)) alertDiv.removeChild(textDisplay);
                        if (alertDiv.contains(helpText)) alertDiv.removeChild(helpText);
                    }, 10000);
                }

                // 恢复按钮状态
                setTimeout(() => {
                    if (btn) {
                        btn.innerHTML = originalText;
                        btn.classList.remove('btn-success', 'btn-danger');
                        btn.classList.add('btn-outline-primary');
                    }
                }, 3000);
            });
    }

    // 在页面加载时绑定所有事件
    bindEvents();
});

// 辅助函数：获取CSRF令牌
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}