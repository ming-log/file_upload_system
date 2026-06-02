# Implementation Plan: 作业文件上传系统

## Overview

本实现计划将 design.md 中的前后端分离架构拆解为一系列增量式编码任务。后端采用 **Python + FastAPI + SQLAlchemy 2.x + Pydantic v2**，对象存储使用 MinIO，邮件使用 aiosmtplib，属性测试使用 **Hypothesis**；前端采用 **Vue 3 + Pinia + Axios + Element Plus**。

实现顺序遵循"自底向上、随用随测"的策略：先建立项目骨架与核心纯函数（validators），再实现数据模型与仓储层，随后逐个实现各业务服务并就地编写属性测试与单元测试，最后接入 API 路由/认证中间件、构建前端 SPA，并补充外部依赖的集成测试。

设计文档包含完整的 Correctness Properties 章节（共 36 条属性），因此每条属性均被转化为一个独立的属性测试子任务（使用 Hypothesis，每个测试至少运行 100 次迭代），并标注其属性编号与所验证的需求条款。带 `*` 的子任务为可选测试任务，可在快速 MVP 中跳过。

## Tasks

- [x] 1. 搭建后端项目结构与核心定义
  - [x] 1.1 初始化后端项目、依赖与测试框架
    - 创建目录结构：`app/`（`core/`、`services/`、`adapters/`、`api/`）、`tests/`（`properties/`、`unit/`、`integration/`）
    - 配置依赖（`pyproject.toml`）：fastapi、uvicorn、sqlalchemy、pydantic、python-jose（JWT）、minio、aiosmtplib、pytest、hypothesis
    - 创建 `app/main.py` 应用骨架与 pytest/Hypothesis 配置
    - _Requirements: 基础设施_
  - [x] 1.2 定义统一错误模型与校验结果类型
    - 在 `app/core/errors.py` 实现 `ErrorCode` 枚举（覆盖设计中错误码表）
    - 在 `app/core/results.py` 实现 `ValidationResult` 数据类
    - _Requirements: 设计 Error Handling 章节全部错误码_

- [x] 2. 实现核心校验纯函数（validators.py）
  - [x] 2.1 实现 validators.py 全部纯函数
    - 实现 `validate_email`、`validate_role`、`validate_required`、`validate_length`、`validate_extension`、`validate_file_size`、`validate_max_file_size_setting`、`normalize_max_file_size`、`validate_deadline`、`validate_allowed_extension_set`、`compute_token_expiry`、`is_token_valid` 及常量定义
    - _Requirements: 1.1, 1.4, 2.2, 2.5, 2.7, 5.4, 5.5, 5.6, 7.4, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11, 8.13, 9.3, 9.4, 9.5, 9.6_
  - [x]* 2.2 编写属性测试：令牌过期时间为签发后 30 分钟
    - **Property 1: 令牌过期时间为签发后 30 分钟**
    - **Validates: Requirements 1.1**
  - [x]* 2.3 编写属性测试：令牌有效性以过期时刻为界
    - **Property 2: 令牌有效性以过期时刻为界**
    - **Validates: Requirements 1.4**
  - [x]* 2.4 编写属性测试：角色取值校验
    - **Property 6: 角色取值校验**
    - **Validates: Requirements 2.2, 2.7**
  - [x]* 2.5 编写属性测试：邮箱格式校验
    - **Property 7: 邮箱格式校验**
    - **Validates: Requirements 2.5**
  - [x]* 2.6 编写属性测试：字段长度上限校验
    - **Property 13: 字段长度上限校验**
    - **Validates: Requirements 5.4, 5.5, 5.6, 7.4, 8.6, 8.7**
  - [x]* 2.7 编写属性测试：允许扩展名集合校验
    - **Property 23: 允许扩展名集合校验**
    - **Validates: Requirements 8.8, 8.9**
  - [x]* 2.8 编写属性测试：最大文件大小取值校验
    - **Property 24: 最大文件大小取值校验**
    - **Validates: Requirements 8.11**
  - [x]* 2.9 编写属性测试：最大文件大小默认值
    - **Property 25: 最大文件大小默认值**
    - **Validates: Requirements 8.10**
  - [x]* 2.10 编写属性测试：截止时间边界
    - **Property 26: 截止时间边界**
    - **Validates: Requirements 8.13, 9.6**
  - [x]* 2.11 编写属性测试：文件扩展名不区分大小写校验
    - **Property 27: 文件扩展名不区分大小写校验**
    - **Validates: Requirements 9.4**
  - [x]* 2.12 编写属性测试：文件大小校验
    - **Property 28: 文件大小校验**
    - **Validates: Requirements 9.5**
  - [x]* 2.13 编写 validators 单元测试（边界与示例）
    - 覆盖长度恰为上限/超 1、缺省大小、非法邮箱等边界示例
    - _Requirements: 2.5, 8.10_

- [x] 3. 检查点 - 核心校验
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. 实现数据模型与仓储层
  - [x] 4.1 定义 ORM 模型（User、Class、Course、Assignment、Submission）
    - 在 `app/models.py` 定义五张表及字段、唯一约束（account、student_id、storage_id）与外键关系
    - _Requirements: 2.1, 5.3, 6.2, 7.2, 8.3, 9.9, 10.4_
  - [x] 4.2 实现 Repository 层
    - 在 `app/repository.py` 封装唯一性检查、关联查询（班级/课程/作业存在性）、事务边界
    - _Requirements: 2.3, 6.7, 7.5, 8.12, 9.1, 10.4_
  - [x]* 4.3 编写模型结构冒烟测试
    - 断言各 ORM 模型必备字段存在
    - _Requirements: 2.1, 5.3, 6.2, 7.2, 8.3_

- [x] 5. 实现认证服务
  - [x] 5.1 实现 AuthService.login 与 verify_token
    - 在 `app/services/auth_service.py` 实现账号/密码非空校验、用户查找、空密码拒绝、凭据匹配、签发含 role 与 exp 的 JWT、令牌解析与过期判定
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [x]* 5.2 编写属性测试：登录成功的令牌角色与用户角色一致
    - **Property 3: 登录成功的令牌角色与用户角色一致**
    - **Validates: Requirements 1.3**
  - [x]* 5.3 编写属性测试：凭据不匹配则登录失败且不签发令牌
    - **Property 4: 凭据不匹配则登录失败且不签发令牌**
    - **Validates: Requirements 1.2**
  - [x]* 5.4 编写属性测试：空存储密码拒绝密码登录
    - **Property 5: 空存储密码拒绝密码登录**
    - **Validates: Requirements 1.5**
  - [x]* 5.5 编写认证服务单元测试（成功/失败示例）
    - 覆盖典型登录成功、必填缺失等示例
    - _Requirements: 1.1, 1.6_

- [x] 6. 检查点 - 认证
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. 实现用户管理服务
  - [x] 7.1 实现 UserService.create_user
    - 在 `app/services/user_service.py` 实现必填(role/account)、role 取值、邮箱格式、账号唯一性校验；允许空密码保存
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_
  - [x]* 7.2 编写属性测试：账号唯一性不可破坏
    - **Property 9: 账号唯一性不可破坏**
    - **Validates: Requirements 2.3**
  - [x]* 7.3 编写属性测试：空密码用户允许保存
    - **Property 10: 空密码用户允许保存**
    - **Validates: Requirements 2.4**
  - [x] 7.4 实现 create_teacher 与 create_student
    - 在 `app/services/user_service.py` 实现教师创建（Admin 门控、必填、返回 account）与学生创建（Teacher 门控、必填、缺省密码、关联班级、学号重复拒绝）
    - _Requirements: 4.1, 4.3, 4.4, 6.1, 6.2, 6.3, 6.4, 6.7, 6.9_
  - [x]* 7.5 编写属性测试：Admin 创建教师返回教师账号
    - **Property 12: Admin 创建教师返回教师账号**
    - **Validates: Requirements 4.1, 4.3**
  - [x]* 7.6 编写属性测试：学生缺省密码赋值
    - **Property 15: 学生缺省密码赋值**
    - **Validates: Requirements 6.3**
  - [x]* 7.7 编写属性测试：学生成功创建关联至当前班级
    - **Property 16: 学生成功创建关联至当前班级**
    - **Validates: Requirements 6.4, 6.5**
  - [x]* 7.8 编写属性测试：学号重复被跳过或拒绝
    - **Property 17: 学号重复被跳过或拒绝**
    - **Validates: Requirements 6.6, 6.7**
  - [x] 7.9 实现 batch_create_users 与 batch_import_students
    - 在 `app/services/user_service.py` 实现空批次/超 1000 上限整体拒绝、逐条校验、失败收集、成功/失败计数
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 6.5, 6.6, 6.10_
  - [x]* 7.10 编写属性测试：批量创建处理全部有效记录
    - **Property 18: 批量创建处理全部有效记录**
    - **Validates: Requirements 3.1, 3.2, 6.5**
  - [x]* 7.11 编写属性测试：批量计数守恒
    - **Property 19: 批量计数守恒**
    - **Validates: Requirements 3.3, 6.10**
  - [ ]* 7.12 编写属性测试：批量超上限整体拒绝
    - **Property 20: 批量超上限整体拒绝**
    - **Validates: Requirements 3.5**
  - [x]* 7.13 编写批量处理单元测试（空批次与失败明细）
    - 覆盖空记录拒绝、单条失败行标识与原因
    - _Requirements: 3.4_

- [x] 8. 实现班级服务
  - [x] 8.1 实现 ClassService.create_class
    - 在 `app/services/class_service.py` 实现 Teacher 门控、必填(school/grade/major)、各字段长度上限、成功返回班级标识
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_
  - [x]* 8.2 编写属性测试：班级合法输入创建成功
    - **Property 14: 班级合法输入创建成功**
    - **Validates: Requirements 5.8**

- [x] 9. 实现课程服务
  - [x] 9.1 实现 CourseService.list_classes 与 create_course
    - 在 `app/services/course_service.py` 实现下拉班级列表、Teacher 门控、必填、课程名长度、班级存在性校验、成功返回课程标识
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  - [x]* 9.2 编写属性测试：课程合法输入创建成功并正确关联
    - **Property 22: 课程合法输入创建成功并正确关联**
    - **Validates: Requirements 7.7**
  - [x]* 9.3 编写课程服务单元测试（下拉数据来源）
    - 断言 `list_classes` 返回现存班级集合
    - _Requirements: 7.3_

- [x] 10. 实现作业服务
  - [x] 10.1 实现 AssignmentService.list_courses 与 create_assignment
    - 在 `app/services/assignment_service.py` 实现下拉课程列表、Teacher 门控、必填、标题/说明长度、扩展名集合、最大大小默认/校验、课程存在性、截止时间校验
    - _Requirements: 8.1, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11, 8.12, 8.13_
  - [x]* 10.2 编写属性测试：关联实体不存在则拒绝
    - **Property 21: 关联实体不存在则拒绝**
    - **Validates: Requirements 7.5, 8.12**
  - [x]* 10.3 编写作业服务单元测试（下拉来源与默认大小）
    - 断言 `list_courses` 返回现存课程；未指定时最大大小默认 5MB
    - _Requirements: 8.4, 8.10_

- [x] 11. 检查点 - 核心领域服务
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. 实现存储服务适配器（MinIO）
  - [x] 12.1 实现 StorageService（30s 超时、唯一 storage_id）与测试用 fake
    - 在 `app/adapters/storage_service.py` 定义 Protocol 与 MinIO 实现，保存成功返回唯一标识，超时/错误返回对应结果；提供内存 fake 供测试注入
    - _Requirements: 10.1, 10.2, 10.4_
  - [ ]* 12.2 编写属性测试：存储标识与提交记录一一对应
    - **Property 32: 存储标识与提交记录一一对应**
    - **Validates: Requirements 10.4**

- [x] 13. 实现作业提交服务
  - [x] 13.1 实现 SubmissionService.submit
    - 在 `app/services/submission_service.py` 实现 Student 门控、作业存在性、空文件、扩展名、大小、截止时间校验，调用存储（0 重试）、创建提交记录、触发异步邮件
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 10.3_
  - [ ]* 13.2 编写属性测试：空文件拒绝
    - **Property 29: 空文件拒绝**
    - **Validates: Requirements 9.3**
  - [ ]* 13.3 编写属性测试：成功提交不变量
    - **Property 30: 成功提交不变量**
    - **Validates: Requirements 9.7, 9.8, 9.9**
  - [ ]* 13.4 编写属性测试：存储失败零重试零记录
    - **Property 31: 存储失败零重试零记录**
    - **Validates: Requirements 10.3**

- [ ] 14. 实现跨切面授权与必填字段属性测试
  - [ ]* 14.1 编写属性测试：角色权限门控
    - **Property 11: 角色权限门控**
    - **Validates: Requirements 4.2, 5.1, 5.2, 6.1, 6.8, 7.1, 8.1, 8.2, 9.1, 9.2**
  - [ ]* 14.2 编写属性测试：必填字段缺失统一拒绝
    - **Property 8: 必填字段缺失统一拒绝**
    - **Validates: Requirements 1.6, 2.6, 4.4, 5.7, 6.9, 7.6, 8.5**

- [x] 15. 实现邮件通知服务
  - [x] 15.1 实现 EmailService.build_email_body 与 next_attempt_schedule
    - 在 `app/adapters/email_service.py` 实现邮件正文构造（含作业标题、精确到秒的提交时间、文件名）与重试调度纯函数
    - _Requirements: 11.2, 11.5_
  - [x]* 15.2 编写属性测试：邮件正文包含必备信息
    - **Property 33: 邮件正文包含必备信息**
    - **Validates: Requirements 11.2**
  - [x]* 15.3 编写属性测试：邮件重试调度
    - **Property 35: 邮件重试调度**
    - **Validates: Requirements 11.5**
  - [x] 15.4 实现 EmailService.notify_submission 异步发送/跳过/重试
    - 在 `app/adapters/email_service.py` 实现空邮箱跳过并记日志、60s 内发起、单次 30s 超时判失败、10s 间隔最多重试 2 次、最终失败记日志且不回滚提交
    - _Requirements: 11.1, 11.3, 11.4, 11.6_
  - [x]* 15.5 编写属性测试：空邮箱跳过发送并记录日志
    - **Property 34: 空邮箱跳过发送并记录日志**
    - **Validates: Requirements 11.3**
  - [x]* 15.6 编写属性测试：邮件最终失败不影响提交记录
    - **Property 36: 邮件最终失败不影响提交记录**
    - **Validates: Requirements 11.6**

- [ ] 16. 接入 API 路由层与认证中间件
  - [x] 16.1 实现认证中间件与依赖注入
    - 在 `app/api/deps.py`、`app/api/middleware.py` 实现令牌校验、`current_user` 注入、无效令牌返回 401
    - _Requirements: 1.3, 1.4_
  - [ ] 16.2 实现 FastAPI 路由与错误码到 HTTP 的映射
    - 在 `app/api/routes/` 实现 auth、users、classes、courses、assignments、submissions 路由；在 `app/api/errors.py` 实现 `ErrorCode` → HTTP 状态码统一映射
    - _Requirements: 设计 Error Handling 章节全部错误码映射_
  - [ ]* 16.3 编写集成测试：MinIO 保存返回 storage_id 与 30s 超时
    - 对受控 MinIO/mock 验证保存返回唯一标识与超时行为
    - _Requirements: 10.1, 10.2_
  - [ ]* 16.4 编写集成测试：邮件 60s 内发起与单次 30s 超时
    - 以 mock SMTP 与可控时钟验证发起时机与超时判定
    - _Requirements: 11.1, 11.4_

- [x] 17. 构建前端 Vue 3 SPA
  - [x] 17.1 初始化前端项目（Vue 3 + Pinia + Axios + 路由守卫）
    - 搭建工程、状态管理、HTTP 客户端、基于令牌的路由守卫
    - _Requirements: 1.3, 1.4_
  - [x] 17.2 实现登录页与基于角色的视图分发
    - 登录表单、令牌存储、Admin/Teacher/Student 视图入口
    - _Requirements: 1.1, 1.3, 4.1_
  - [x] 17.3 实现班级/课程/作业管理表单（含下拉选择）
    - 表单校验提示、班级与课程下拉数据接入
    - _Requirements: 5.8, 7.3, 7.7, 8.4_
  - [x] 17.4 实现学生作业提交上传视图
    - 文件选择、客户端扩展名/大小提示、提交结果反馈
    - _Requirements: 9.1_
  - [x]* 17.5 编写前端单元测试（表单校验与 API 集成）
    - 覆盖表单校验与请求/响应处理
    - _Requirements: 5.8, 8.5, 9.1_

- [ ] 18. 最终检查点
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- 标记 `*` 的子任务为可选测试任务，可在快速 MVP 中跳过；顶层任务不带 `*`。
- 每条属性（Property 1–36）对应一个独立属性测试子任务，使用 Hypothesis 实现，每个测试至少运行 100 次迭代，并就近放置以尽早发现错误。
- 属性测试中 `Storage_Service`、`Email_Service` 与时钟均以 mock/fake 注入，使纯业务逻辑可在内存中以低成本运行。
- 基础设施与外部时序相关需求（10.1、10.2、11.1、11.4）以集成测试覆盖；模型字段存在性以结构冒烟测试覆盖。
- 每个任务标注其验证的具体需求条款，确保可追溯性；检查点用于增量验证。

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "17.1"] },
    { "id": 2, "tasks": ["2.1", "4.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "2.8", "2.9", "2.10", "2.11", "2.12", "2.13", "4.2", "4.3"] },
    { "id": 4, "tasks": ["5.1", "7.1", "8.1", "9.1", "10.1", "12.1", "15.1", "17.2", "17.3", "17.4"] },
    { "id": 5, "tasks": ["5.2", "5.3", "5.4", "5.5", "7.2", "7.3", "7.4", "8.2", "9.2", "9.3", "10.2", "10.3", "15.2", "15.3", "16.1", "17.5"] },
    { "id": 6, "tasks": ["7.5", "7.6", "7.7", "7.8", "7.9", "15.4"] },
    { "id": 7, "tasks": ["7.10", "7.11", "7.12", "7.13", "13.1", "15.5", "15.6"] },
    { "id": 8, "tasks": ["13.2", "13.3", "13.4", "12.2", "14.1", "14.2", "16.2"] },
    { "id": 9, "tasks": ["16.3", "16.4"] }
  ]
}
```
