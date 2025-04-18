# 作业管理系统API文档

本文档详细介绍了作业管理系统提供的API接口，可用于开发第三方客户端或进行系统集成。

## 目录

1. [获取今日作业](#获取今日作业)
2. [切换作业完成状态](#切换作业完成状态)
3. [创建用户](#创建用户)
4. [删除用户](#删除用户)
5. [删除作业](#删除作业)
6. [获取学科作业建议](#获取学科作业建议)
7. [清理旧作业](#清理旧作业)

---

## 获取今日作业

获取今天需要完成的作业列表，不包含今天截止的作业。以文本格式返回按科目分组的作业列表。

### 请求

- **URL:** `/api/get_today_homework/`
- **方法:** `POST`
- **内容类型:** `application/json`

### 请求参数

| 参数名 | 类型 | 必须 | 描述 |
|--------|------|------|------|
| username | string | 是 | 学生用户名 |
| password | string | 是 | 学生密码 |

### 请求示例

```json
{
  "username": "student1",
  "password": "studentpass123"
}
```

### 响应

#### 成功响应

- **状态码:** `200 OK`
- **内容类型:** `text/plain; charset=utf-8`

返回纯文本格式的作业列表，按科目分组，并加入特殊标记：
- 明天截止的作业标记为"明不收"（"Not collected tomorrow"）
- 当今天是周五时，周一截止的作业标记为"周一不收"（"Not collected on Monday"）

#### 成功响应示例

```
语文：
1.课文朗读
2.阅读理解作业

数学：
1.习题集第三章
2.期中复习题 (明不收)

英语：
1.单词默写
2.阅读训练 (周一不收)
```

#### 错误响应

| 状态码 | 错误信息 | 描述 |
|--------|----------|------|
| 400 | 用户名或密码缺失 | 请求缺少必要的用户名或密码 |
| 400 | 无效的请求数据 | 无法解析请求体JSON数据 |
| 401 | 用户名或密码错误 | 提供的认证信息无效 |
| 403 | 只有学生账号可以使用此功能 | 使用非学生账号访问此API |
| 405 | 方法不允许 | 使用了非POST方法请求 |
| 500 | 获取作业失败 | 服务器内部错误 |

### 业务规则说明

1. 此API仅获取当前日期应该完成的作业，且符合以下条件：
   - 作业的开始日期小于等于今天
   - 作业的截止日期严格大于今天（不包括今天截止的作业）
   
2. 结果会过滤掉用户在设置中隐藏的科目的作业

3. 返回的作业列表按科目名称排序，科目内部按截止日期排序

4. 作业标题后面添加以下特殊标记：
   - 明天截止的作业：(明不收)
   - 如果今天是周五，周一截止的作业：(周一不收)

### 代码示例

#### Python

```python
import requests

url = "http://your-server.com/api/get_today_homework/"
data = {
    "username": "student1",
    "password": "studentpass123"
}

response = requests.post(url, json=data)
if response.status_code == 200:
    homework_text = response.text
    print("Today's homework:")
    print(homework_text)
else:
    print(f"Failed to get homework: Status code {response.status_code}")
    print(response.text)
```

---

## 切换作业完成状态

切换学生的作业完成状态（已完成/未完成）。

### 请求

- **URL:** `/api/toggle-assignment/`
- **方法:** `POST`
- **内容类型:** `application/json`
- **认证:** 需要用户登录

### 请求参数

| 参数名 | 类型 | 必须 | 描述 |
|--------|------|------|------|
| assignment_id | integer | 是 | 作业ID |

### 响应

略（已有实现）

---

## 其他API接口

本文档的其他API接口部分待补充。每个接口将包含URL、方法、参数、响应格式和示例等详细信息。 