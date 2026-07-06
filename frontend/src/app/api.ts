// 后端 API 客户端封装。
//
// 所有请求经由 Vite dev server 的 /api 代理转发到 FastAPI（见 vite.config.ts）。
// 会话令牌（JWT）保存在 localStorage，请求时自动附加到 Authorization 头。

import type {
  AuthUser, User, Class, Student, Course, Assignment, Submission, Role,
} from './types';

const TOKEN_KEY = 'auth_token';
export const AUTH_EXPIRED_EVENT = 'app:auth-expired';
const UNAUTHENTICATED_CODE = 'UNAUTHENTICATED';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function isAuthExpiredError(error: unknown): boolean {
  return error instanceof ApiError && error.code === UNAUTHENTICATED_CODE;
}

export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

function notifyAuthExpired(error: ApiError) {
  if (!isAuthExpiredError(error) || typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT, { detail: error }));
}

function apiErrorFromData(
  res: Response,
  data: any,
  fallbackMessage: string,
): ApiError {
  const detail = data?.detail;
  const code = typeof detail === 'object' ? detail?.error_code : undefined;
  const message = typeof detail === 'object'
    ? detail?.message
    : (detail || res.statusText || fallbackMessage);
  const error = new ApiError(res.status, message || fallbackMessage, code);
  notifyAuthExpired(error);
  return error;
}

export async function apiErrorFromResponse(
  res: Response,
  fallbackMessage = '请求失败',
): Promise<ApiError> {
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  return apiErrorFromData(res, data, fallbackMessage);
}

const BASE = '/api';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers = getAuthHeaders();

  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    throw apiErrorFromData(res, data, '请求失败');
  }
  return data as T;
}

export const api = {
  get: <T>(p: string) => request<T>('GET', p),
  post: <T>(p: string, b?: unknown) => request<T>('POST', p, b),
  put: <T>(p: string, b?: unknown) => request<T>('PUT', p, b),
  del: <T>(p: string) => request<T>('DELETE', p),
};

// --------------------------------------------------------------------------- //
// 业务接口                                                                      //
// --------------------------------------------------------------------------- //

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface CaptchaResponse {
  captchaId: string;
  image: string;
}

export interface BatchResult {
  success_count: number;
  failure_count: number;
  failures: { row_id: number | string; reason: string }[];
}

export const authApi = {
  captcha: () => api.get<CaptchaResponse>('/auth/captcha'),
  schools: () => api.get<string[]>('/auth/schools'),
  loginStudent: (school: string, studentId: string, password: string, captchaId?: string, captcha?: string) =>
    api.post<LoginResponse>('/auth/login/student', { school, studentId, password, captchaId, captcha }),
  loginTeacher: (account: string, password: string) =>
    api.post<LoginResponse>('/auth/login/teacher', { account, password }),
  sendEmailCode: (email?: string) =>
    api.post<{ status: string; email: string }>(
      '/auth/email/send-code',
      email ? { email } : undefined,
    ),
  verifyEmail: (code: string, newPassword: string) =>
    api.post<{ status: string; user: AuthUser }>('/auth/email/verify', { code, newPassword }),
};

export interface MeProfile {
  id: string;
  role: Role;
  account: string;
  name: string;
  email: string;
  avatar: string;
  emailVerified: boolean;
  studentId?: string;
  classId?: string;
  school?: string;
  className?: string;
}

export const meApi = {
  get: () => api.get<MeProfile>('/me'),
  update: (data: { name?: string; email?: string; avatar?: string }) =>
    api.put<MeProfile>('/me', data),
};

export const usersApi = {
  list: () => api.get<User[]>('/users'),
  create: (u: Omit<User, 'id' | 'createdAt'>) => api.post<User>('/users', u),
  update: (id: string, u: Omit<User, 'id' | 'createdAt'>) => api.put<User>(`/users/${id}`, u),
  remove: (id: string) => api.del<{ status: string }>(`/users/${id}`),
  batch: (records: Omit<User, 'id' | 'createdAt'>[]) =>
    api.post<BatchResult>('/users/batch', { records }),
};

export const classesApi = {
  list: () => api.get<Class[]>('/classes'),
  create: (c: { school: string; grade: string; major: string; logo?: string }) =>
    api.post<Class>('/classes', c),
  update: (id: string, c: { school: string; grade: string; major: string; logo?: string }) =>
    api.put<Class>(`/classes/${id}`, c),
  remove: (id: string) => api.del<{ status: string }>(`/classes/${id}`),
  listStudents: (classId: string) => api.get<Student[]>(`/classes/${classId}/students`),
  createStudent: (classId: string, s: Omit<Student, 'id' | 'classId'>) =>
    api.post<Student>(`/classes/${classId}/students`, s),
  batchStudents: (classId: string, records: Omit<Student, 'id' | 'classId'>[]) =>
    api.post<BatchResult>(`/classes/${classId}/students/batch`, { records }),
};

export const studentsApi = {
  listAll: () => api.get<Student[]>('/students'),
  update: (id: string, s: Omit<Student, 'id' | 'classId'>) => api.put<Student>(`/students/${id}`, s),
  remove: (id: string) => api.del<{ status: string }>(`/students/${id}`),
};

export const coursesApi = {
  list: () => api.get<Course[]>('/courses'),
  create: (c: { semester: string; name: string; classId: string }) =>
    api.post<Course>('/courses', c),
  update: (id: string, c: { semester: string; name: string; classId: string }) =>
    api.put<Course>(`/courses/${id}`, c),
  remove: (id: string) => api.del<{ status: string }>(`/courses/${id}`),
};

export interface AssignmentInput {
  title: string;
  content: string;
  courseId: string;
  allowedFileTypes: string[];
  maxFileSizeMB: number;
  deadline: string;
}

export const assignmentsApi = {
  list: () => api.get<Assignment[]>('/assignments'),
  create: (a: AssignmentInput) => api.post<Assignment>('/assignments', a),
  update: (id: string, a: AssignmentInput) => api.put<Assignment>(`/assignments/${id}`, a),
  remove: (id: string) => api.del<{ status: string }>(`/assignments/${id}`),
};

export const submissionsApi = {
  list: () => api.get<Submission[]>('/submissions'),
  submit: (assignmentId: string, files: File[], comment: string) => {
    const fd = new FormData();
    files.forEach(f => fd.append('files', f));
    fd.append('comment', comment);
    return api.post<Submission>(`/assignments/${assignmentId}/submissions`, fd);
  },
  // 下载单个提交文件。storageId 为含 "/" 的分层对象键，必须经查询参数传递（编码后）。
  fileUrl: (submissionId: string, storageId: string) =>
    `${BASE}/submissions/${submissionId}/file?storageId=${encodeURIComponent(storageId)}`,
  // 导出某课程全部提交（ZIP：文件 + 提交状态表）。返回 Blob 以便浏览器下载。
  exportCourse: (courseId: string) => downloadZip(`${BASE}/courses/${courseId}/submissions/export`),
  // 导出某作业全部提交（ZIP：文件 + 提交状态表）。
  exportAssignment: (assignmentId: string) =>
    downloadZip(`${BASE}/assignments/${assignmentId}/submissions/export`),
};

// 通用：带鉴权头请求一个会返回文件流的端点，解析文件名并返回 Blob。
async function downloadZip(url: string): Promise<{ blob: Blob; filename: string }> {
  const headers = getAuthHeaders();
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw await apiErrorFromResponse(res, '导出失败');
  }
  let filename = '提交汇总.zip';
  const cd = res.headers.get('Content-Disposition') || '';
  const star = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  const plain = /filename="?([^";]+)"?/i.exec(cd);
  if (star) filename = decodeURIComponent(star[1]);
  else if (plain) filename = plain[1];
  const blob = await res.blob();
  return { blob, filename };
}
