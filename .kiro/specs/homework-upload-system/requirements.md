# Requirements Document

## Introduction

本系统是一个采用前后端分离架构的现代化作业文件上传系统。系统支持管理员、教师、学生三种角色，围绕用户管理、班级管理、课程管理和作业管理展开。学生在作业截止时间前提交符合扩展名与大小限制的作业文件，文件存储于 MinIO 对象存储中；提交成功后，系统向提交学生的邮箱发送邮件通知。

本文档使用 EARS 模式描述所有功能需求，并遵循 INCOSE 质量规则，以保证需求的清晰性、可测试性与完整性。

## Glossary

- **系统（System）**：整个作业文件上传系统，含前端与后端服务。
- **认证服务（Auth_Service）**：负责用户登录、身份认证与会话令牌管理的后端组件。
- **用户管理服务（User_Service）**：负责用户账号的创建、批量创建、查询与维护的后端组件。
- **班级服务（Class_Service）**：负责班级创建、查询与维护的后端组件。
- **课程服务（Course_Service）**：负责课程创建、查询与维护的后端组件。
- **作业服务（Assignment_Service）**：负责作业创建、查询与维护的后端组件。
- **提交服务（Submission_Service）**：负责接收、校验、存储学生作业提交的后端组件。
- **文件存储服务（Storage_Service）**：基于 MinIO 的对象存储组件，用于保存作业文件。
- **邮件服务（Email_Service）**：负责向用户邮箱发送通知邮件的后端组件。
- **管理员（Admin）**：拥有最高权限的用户角色，可创建教师账号。
- **教师（Teacher）**：可创建班级、在班级内创建或批量导入学生、创建课程与作业的用户角色。
- **学生（Student）**：可登录系统、查看作业并提交作业文件的用户角色。
- **账号（Account）**：用户登录系统使用的唯一标识符。
- **学号（Student_ID）**：学生在系统内的唯一业务标识。
- **班级（Class）**：包含学校、年级、专业属性的学生集合。
- **课程（Course）**：包含学期、课程名称、关联班级的教学单元。
- **作业（Assignment）**：包含标题、说明、关联课程、允许扩展名、最大文件大小、截止时间的任务单元。
- **作业提交（Submission）**：学生针对某一作业上传的文件记录。
- **允许扩展名（Allowed_Extension）**：作业允许上传的文件扩展名集合，取值范围为 md、pdf、docx、zip、rar、7z。
- **最大文件大小（Max_File_Size）**：作业允许上传文件的大小上限，单位为 MB。
- **截止时间（Deadline）**：作业允许提交的最后时间点。
- **默认密码（Default_Password）**：批量或单个创建学生时使用的初始密码，值为 "minglog666"。

## Requirements

### Requirement 1: 用户认证与登录

**User Story:** 作为系统用户，我希望使用账号和密码登录系统，以便访问与我角色对应的功能。

#### Acceptance Criteria

1. WHEN 用户提交的账号与密码通过凭据校验，THE Auth_Service SHALL 返回包含用户角色的会话令牌，并将该会话令牌的有效期设置为自签发起 30 分钟。
2. IF 用户提交的账号在系统中不存在或提交的密码与已存储凭据不匹配，THEN THE Auth_Service SHALL 拒绝本次登录、不返回会话令牌，并返回提示账号或密码错误的登录失败错误。
3. WHEN 用户登录成功，THE System SHALL 根据用户角色（Admin、Teacher、Student）授予对应的功能访问权限。
4. IF 用户在未持有有效会话令牌（包括令牌缺失、令牌无效或令牌已超过有效期）的情况下访问受保护资源，THEN THE System SHALL 拒绝访问并返回未认证错误。
5. WHERE 待登录用户在系统中存储的密码字段为空，THE Auth_Service SHALL 拒绝该用户的密码登录请求并返回需要重置密码的提示。
6. IF 用户提交的账号字段或密码字段为空，THEN THE Auth_Service SHALL 拒绝本次登录请求、不返回会话令牌，并返回必填字段缺失错误。

### Requirement 2: 用户管理与角色

**User Story:** 作为系统，我希望以统一的数据结构管理三种角色的用户，以便区分权限与归属。

#### Acceptance Criteria

1. THE User_Service SHALL 为每个用户存储以下字段：角色（role）、账号（account，在系统内作为唯一标识符且不可重复）、邮箱（email）、密码（password）。
2. THE User_Service SHALL 将用户角色限定为 Admin、Teacher、Student 三者之一。
3. IF 创建用户时账号在系统内已存在，THEN THE User_Service SHALL 拒绝创建、不修改已存在的用户记录，并返回账号重复错误。
4. WHERE 用户的密码字段为空，THE User_Service SHALL 允许保存该用户记录。
5. IF 创建用户时邮箱地址不符合“本地名@域名”格式（即不满足以下全部条件：包含且仅包含一个 @ 符号、@ 前的本地名非空、@ 后的域名部分非空且包含至少一个点号），THEN THE User_Service SHALL 拒绝创建并返回邮箱格式错误。
6. IF 创建用户时角色（role）或账号（account）中任一必填字段为空，THEN THE User_Service SHALL 拒绝创建并返回必填字段缺失错误。
7. IF 创建用户时提交的角色取值不属于 Admin、Teacher、Student 之一，THEN THE User_Service SHALL 拒绝创建并返回角色取值无效错误。

### Requirement 3: 批量创建用户

**User Story:** 作为管理员或教师，我希望批量创建用户，以便快速录入多个账号。

#### Acceptance Criteria

1. WHEN 提交包含 1 至 1000 条用户记录的批量创建请求，THE User_Service SHALL 为每条有效记录（账号在系统内唯一且邮箱符合标准邮箱格式）创建对应用户。
2. IF 批量创建请求中存在账号重复或邮箱格式错误的记录，THEN THE User_Service SHALL 跳过该错误记录、继续处理其余记录，并在响应中返回每条失败记录的行标识与失败原因。
3. WHEN 批量创建处理完成，THE User_Service SHALL 返回成功创建的记录数量与失败的记录数量，其中被跳过的错误记录计入失败记录数量。
4. IF 批量创建请求不包含任何用户记录，THEN THE User_Service SHALL 拒绝该请求并返回记录为空错误。
5. IF 批量创建请求包含的用户记录数量超过 1000，THEN THE User_Service SHALL 拒绝整个请求、不创建任何用户，并返回记录数量超过上限错误。

### Requirement 4: 管理员创建教师账号

**User Story:** 作为管理员，我希望创建教师账号，以便教师能够登录系统并管理教学。

#### Acceptance Criteria

1. WHERE 当前用户角色为 Admin，WHEN 管理员提交账号与邮箱字段均非空的教师账号创建请求，THE User_Service SHALL 创建角色为 Teacher 的用户账号。
2. IF 当前用户角色不是 Admin 且尝试创建教师账号，THEN THE User_Service SHALL 拒绝请求、不创建任何用户账号，并返回权限不足错误。
3. WHEN 管理员成功创建教师账号，THE User_Service SHALL 返回该教师账号的账号标识（account）。
4. IF 当前用户角色为 Admin 且提交的教师账号创建请求中账号或邮箱字段为空，THEN THE User_Service SHALL 拒绝创建、不创建任何用户账号，并返回必填字段缺失错误。

### Requirement 5: 教师创建班级

**User Story:** 作为教师，我希望创建班级，以便组织和管理学生。

#### Acceptance Criteria

1. WHERE 当前用户角色为 Teacher，THE Class_Service SHALL 允许创建班级。
2. IF 当前用户角色不是 Teacher 且尝试创建班级，THEN THE Class_Service SHALL 拒绝请求、不创建任何班级，并返回权限不足错误。
3. THE Class_Service SHALL 为每个班级存储以下字段：学校（school）、年级（grade）、专业（major）。
4. WHEN 创建班级且学校字段长度超过 20 个字符，THE Class_Service SHALL 拒绝创建并返回学校字段超长错误。
5. WHEN 创建班级且年级字段长度超过 20 个字符，THE Class_Service SHALL 拒绝创建并返回年级字段超长错误。
6. WHEN 创建班级且专业字段长度超过 20 个字符，THE Class_Service SHALL 拒绝创建并返回专业字段超长错误。
7. IF 创建班级时学校、年级或专业中的任一必填字段为空或仅包含空白字符，THEN THE Class_Service SHALL 拒绝创建并返回必填字段缺失错误。
8. WHEN 创建班级且学校、年级、专业均满足非空与长度约束，THE Class_Service SHALL 创建班级并返回新建班级的标识。

### Requirement 6: 班级内创建学生

**User Story:** 作为教师，我希望在班级页面内单个或批量导入学生，以便将学生归属到对应班级。

#### Acceptance Criteria

1. WHERE 当前用户角色为 Teacher，THE User_Service SHALL 允许在指定班级内创建角色为 Student 的用户。
2. THE User_Service SHALL 为每个学生存储以下字段：学号（Student_ID）、姓名（name）、邮箱（email）、密码（password）。
3. WHERE 创建学生时未提供密码，THE User_Service SHALL 将该学生的密码设置为默认密码 "minglog666"。
4. WHEN 在班级内创建学生成功，THE User_Service SHALL 将该学生关联到当前班级。
5. WHEN 提交批量导入学生请求，THE User_Service SHALL 为每条有效记录创建学生并将其关联到当前班级，其中有效记录指学号、姓名、邮箱均非空，邮箱符合标准邮箱格式，且学号在系统内不存在并在本次导入批次内未重复出现的记录。
6. IF 批量导入学生时某条记录的学号在系统内已存在或在本次导入批次内重复出现，THEN THE User_Service SHALL 跳过该记录、继续处理其余记录，并在响应中返回该记录的学号与失败原因。
7. WHEN 创建学生且学号在系统内已存在，THE User_Service SHALL 拒绝创建该学生并返回学号重复错误。
8. IF 当前用户角色不是 Teacher 且尝试在班级内创建学生，THEN THE User_Service SHALL 拒绝请求并返回权限不足错误。
9. IF 在班级内创建学生时学号、姓名或邮箱中的任一字段为空，THEN THE User_Service SHALL 拒绝创建该学生并返回必填字段缺失错误。
10. WHEN 批量导入学生处理完成，THE User_Service SHALL 返回成功创建的记录数量与失败的记录数量，其中被跳过的记录计入失败记录数量。

### Requirement 7: 教师创建课程

**User Story:** 作为教师，我希望创建课程并关联到班级，以便围绕课程发布作业。

#### Acceptance Criteria

1. WHERE 当前用户角色为 Teacher，THE Course_Service SHALL 允许创建课程。
2. THE Course_Service SHALL 为每个课程存储以下字段：学期（semester）、课程名称（course name）、关联班级（associated class）。
3. WHEN 创建课程，THE Course_Service SHALL 通过下拉选择提供已存在的班级列表供教师选择关联班级。
4. WHEN 创建课程且课程名称长度超过 20 个字符（课程名称的有效长度为 1 至 20 个字符），THE Course_Service SHALL 拒绝创建并返回课程名称超长错误，且不创建任何课程记录。
5. IF 创建课程时所选关联班级不存在，THEN THE Course_Service SHALL 拒绝创建并返回班级不存在错误，且不创建任何课程记录。
6. IF 创建课程时学期、课程名称或关联班级中的任一必填字段为空（未提供或仅包含空白字符），THEN THE Course_Service SHALL 拒绝创建并返回必填字段缺失错误，且不创建任何课程记录。
7. WHEN 创建课程且通过全部校验（学期、课程名称、关联班级均非空，课程名称长度为 1 至 20 个字符，且所选关联班级存在），THE Course_Service SHALL 创建课程、将其关联到所选班级，并返回新建课程的标识。

### Requirement 8: 教师创建作业

**User Story:** 作为教师，我希望创建作业并设置提交约束，以便学生按要求提交文件。

#### Acceptance Criteria

1. WHERE 当前用户角色为 Teacher，THE Assignment_Service SHALL 允许创建作业。
2. IF 当前用户角色不是 Teacher 且尝试创建作业，THEN THE Assignment_Service SHALL 拒绝请求、不创建任何作业记录，并返回权限不足错误。
3. THE Assignment_Service SHALL 为每个作业存储以下字段：作业标题（title）、作业说明（content）、关联课程（associated course）、允许扩展名（Allowed_Extension）、最大文件大小（Max_File_Size）、截止时间（Deadline）。
4. WHEN 创建作业，THE Assignment_Service SHALL 通过下拉选择提供已存在的课程列表供教师选择关联课程。
5. IF 创建作业时作业标题、关联课程或截止时间中的任一必填字段为空，THEN THE Assignment_Service SHALL 拒绝创建、不创建任何作业记录，并返回必填字段缺失错误。
6. WHEN 创建作业且作业标题长度超过 20 个字符，THE Assignment_Service SHALL 拒绝创建并返回标题超长错误。
7. WHEN 创建作业且作业说明长度超过 100 个字符，THE Assignment_Service SHALL 拒绝创建并返回说明超长错误。
8. THE Assignment_Service SHALL 将允许扩展名的可选值限定为 md、pdf、docx、zip、rar、7z 的子集。
9. IF 创建作业时未选择任何允许扩展名，THEN THE Assignment_Service SHALL 拒绝创建并返回至少选择一种扩展名的错误。
10. WHERE 创建作业时未指定最大文件大小，THE Assignment_Service SHALL 将最大文件大小默认设置为 5 MB。
11. WHEN 创建作业且最大文件大小不是位于 1 至 100 MB（含）之间的正数，THE Assignment_Service SHALL 拒绝创建并返回最大文件大小取值无效错误。
12. IF 创建作业时所选关联课程不存在，THEN THE Assignment_Service SHALL 拒绝创建并返回课程不存在错误。
13. IF 创建作业时截止时间不晚于创建请求处理时的当前时间，THEN THE Assignment_Service SHALL 拒绝创建、不创建任何作业记录，并返回截止时间无效错误。

### Requirement 9: 学生提交作业文件

**User Story:** 作为学生，我希望上传作业文件，以便完成作业提交。

#### Acceptance Criteria

1. WHERE 当前用户角色为 Student，THE Submission_Service SHALL 允许针对已存在的指定作业上传作业文件。
2. IF 当前用户角色不是 Student 且尝试上传作业文件，THEN THE Submission_Service SHALL 拒绝请求、不创建作业提交记录，并返回权限不足错误。
3. IF 学生提交请求未包含文件或所提交文件为 0 字节，THEN THE Submission_Service SHALL 拒绝提交、不创建作业提交记录，并返回文件为空错误。
4. WHEN 学生上传文件且文件扩展名（不区分大小写）不在该作业的允许扩展名集合内，THE Submission_Service SHALL 拒绝提交、不创建作业提交记录，并返回扩展名不被允许错误。
5. WHEN 学生上传文件且文件大小超过该作业的最大文件大小（单位 MB），THE Submission_Service SHALL 拒绝提交、不创建作业提交记录，并返回文件超过大小限制错误。
6. IF 学生在作业截止时间之后提交文件，THEN THE Submission_Service SHALL 拒绝提交、不创建作业提交记录，并返回已超过截止时间错误。
7. WHEN 文件通过扩展名、大小与截止时间校验，THE Submission_Service SHALL 将文件保存到 Storage_Service。
8. WHEN 文件成功保存到 Storage_Service，THE Submission_Service SHALL 创建作业提交记录。
9. WHEN 作业提交记录创建成功，THE Submission_Service SHALL 记录提交学生、关联作业与提交时间。

### Requirement 10: 文件存储（MinIO）

**User Story:** 作为系统，我希望将作业文件存储在 MinIO 中，以便集中、可靠地保存提交文件。

#### Acceptance Criteria

1. WHEN Submission_Service 请求保存作业文件，THE Storage_Service SHALL 将文件对象存入 MinIO 并返回该对象在系统内唯一的存储标识。
2. IF Storage_Service 在收到保存请求后 30 秒内未完成保存，THEN THE Storage_Service SHALL 终止本次保存操作并返回存储超时错误。
3. IF Storage_Service 在保存文件时发生存储错误或返回存储超时错误，THEN THE Submission_Service SHALL 立即取消本次提交、对存储操作执行 0 次重试、不创建作业提交记录，并返回文件保存失败错误。
4. WHEN 提交记录创建成功，THE Storage_Service SHALL 将 MinIO 中的对象存储标识与该提交记录关联，且每个存储标识仅关联一条提交记录。

### Requirement 11: 提交成功邮件通知

**User Story:** 作为学生，我希望在提交作业后收到邮件通知，以便确认作业已成功提交。

#### Acceptance Criteria

1. WHEN 作业提交记录创建成功且提交学生的邮箱字段非空，THE Email_Service SHALL 在提交记录创建成功后 60 秒内发起向该邮箱发送提交成功通知邮件。
2. WHEN Email_Service 发送提交成功通知邮件，THE Email_Service SHALL 在邮件中包含作业标题、精确到年月日时分秒的提交时间与提交文件名。
3. IF 提交学生的邮箱字段为空，THEN THE Email_Service SHALL 跳过发送邮件并记录包含提交记录标识与“邮箱缺失”原因的日志。
4. IF Email_Service 在单次发送尝试发起后 30 秒内未收到成功响应，THEN THE Email_Service SHALL 将本次发送判定为发送失败。
5. WHILE 提交学生的邮箱字段非空且发送被判定为失败，THE Email_Service SHALL 以 10 秒间隔最多重试 2 次（累计发送尝试不超过 3 次）。
6. IF 提交学生的邮箱字段非空且累计 3 次发送尝试均失败，THEN THE Email_Service SHALL 记录包含提交记录标识与失败原因的发送失败日志，并保持已创建的作业提交记录有效。
