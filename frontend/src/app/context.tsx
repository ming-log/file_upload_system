import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type {
  AuthUser, User, Class, Student, Course, Assignment, Submission, Page,
} from './types';
import {
  ApiError, setToken, getToken,
  authApi, usersApi, classesApi, studentsApi, coursesApi, assignmentsApi, submissionsApi,
} from './api';

const CURRENT_USER_KEY = 'currentUser';

function loadCurrentUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(CURRENT_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function initialPageFor(user: AuthUser | null): Page {
  if (!user) return 'login';
  if (user.role === 'admin') return 'users';
  if (user.role === 'teacher') return 'classes';
  return 'my-assignments';
}

interface AppContextType {
  currentUser: AuthUser | null;
  users: User[];
  classes: Class[];
  students: Student[];
  courses: Course[];
  assignments: Assignment[];
  submissions: Submission[];
  currentPage: Page;
  selectedClassId: string | null;
  selectedAssignmentId: string | null;
  loading: boolean;
  login: (account: string, password: string, captchaId?: string, captcha?: string) => Promise<boolean>;
  logout: () => void;
  navigate: (page: Page, opts?: { classId?: string; assignmentId?: string }) => void;
  // Users
  addUser: (u: Omit<User, 'id' | 'createdAt'>) => Promise<void>;
  updateUser: (u: User) => Promise<void>;
  deleteUser: (id: string) => Promise<void>;
  bulkAddUsers: (rows: Omit<User, 'id' | 'createdAt'>[]) => Promise<void>;
  // Classes
  addClass: (c: Omit<Class, 'id' | 'createdAt' | 'teacherId'>) => Promise<void>;
  updateClass: (c: Class) => Promise<void>;
  deleteClass: (id: string) => Promise<void>;
  // Students
  addStudent: (s: Omit<Student, 'id'>) => Promise<void>;
  updateStudent: (s: Student) => Promise<void>;
  deleteStudent: (id: string) => Promise<void>;
  bulkAddStudents: (rows: Omit<Student, 'id'>[], classId: string) => Promise<void>;
  // Courses
  addCourse: (c: Omit<Course, 'id' | 'createdAt' | 'teacherId'>) => Promise<void>;
  updateCourse: (c: Course) => Promise<void>;
  deleteCourse: (id: string) => Promise<void>;
  // Assignments
  addAssignment: (a: Omit<Assignment, 'id' | 'createdAt'>) => Promise<void>;
  updateAssignment: (a: Assignment) => Promise<void>;
  deleteAssignment: (id: string) => Promise<void>;
  // Submissions
  submitAssignment: (assignmentId: string, files: File[], comment: string) => Promise<void>;
}

const AppContext = createContext<AppContextType | null>(null);

function reportError(e: unknown) {
  if (e instanceof ApiError) {
    // eslint-disable-next-line no-alert
    alert(e.message || '操作失败');
  } else {
    console.error(e);
    // eslint-disable-next-line no-alert
    alert('网络错误，请稍后重试');
  }
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(loadCurrentUser);
  const [users, setUsers] = useState<User[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [currentPage, setCurrentPage] = useState<Page>(() => initialPageFor(loadCurrentUser()));
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // 按角色加载可访问的数据集合（容错：单个失败不影响其它）。
  const loadAll = useCallback(async (user: AuthUser) => {
    setLoading(true);
    const safe = async <T,>(p: Promise<T>, setter: (v: T) => void) => {
      try { setter(await p); } catch (e) { console.warn('加载失败', e); }
    };
    const tasks: Promise<void>[] = [];
    if (user.role === 'admin') {
      tasks.push(safe(usersApi.list(), setUsers));
    }
    if (user.role === 'admin' || user.role === 'teacher') {
      tasks.push(safe(classesApi.list(), setClasses));
      tasks.push(safe(studentsApi.listAll(), setStudents));
    }
    tasks.push(safe(coursesApi.list(), setCourses));
    tasks.push(safe(assignmentsApi.list(), setAssignments));
    tasks.push(safe(submissionsApi.list(), setSubmissions));
    await Promise.all(tasks);
    setLoading(false);
  }, []);

  // 初始挂载：若已有持久化会话则加载数据。
  useEffect(() => {
    const token = getToken();
    if (currentUser && token) {
      loadAll(currentUser);
    } else if (currentUser && !token) {
      // 令牌丢失：清理会话。
      setCurrentUser(null);
      setCurrentPage('login');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (currentUser) localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(currentUser));
    else localStorage.removeItem(CURRENT_USER_KEY);
  }, [currentUser]);

  const refresh = useCallback(async () => {
    if (currentUser) await loadAll(currentUser);
  }, [currentUser, loadAll]);

  const login = useCallback(async (account: string, password: string, captchaId?: string, captcha?: string): Promise<boolean> => {
    try {
      const res = await authApi.login(account, password, captchaId, captcha);
      setToken(res.access_token);
      setCurrentUser(res.user);
      setCurrentPage(initialPageFor(res.user));
      await loadAll(res.user);
      return true;
    } catch (e) {
      if (e instanceof ApiError) throw e;
      console.error(e);
      throw new ApiError(0, '网络错误，请稍后重试');
    }
  }, [loadAll]);

  const logout = useCallback(() => {
    setToken(null);
    setCurrentUser(null);
    setCurrentPage('login');
    setSelectedClassId(null);
    setSelectedAssignmentId(null);
    setUsers([]); setClasses([]); setStudents([]);
    setCourses([]); setAssignments([]); setSubmissions([]);
  }, []);

  const navigate = useCallback((page: Page, opts?: { classId?: string; assignmentId?: string }) => {
    setCurrentPage(page);
    if (opts?.classId !== undefined) setSelectedClassId(opts.classId);
    if (opts?.assignmentId !== undefined) setSelectedAssignmentId(opts.assignmentId);
  }, []);

  // ---- Users ----
  const addUser = useCallback(async (u: Omit<User, 'id' | 'createdAt'>) => {
    try { await usersApi.create(u); await refresh(); } catch (e) { reportError(e); }
  }, [refresh]);

  const updateUser = useCallback(async (u: User) => {
    try {
      await usersApi.update(u.id, { role: u.role, account: u.account, name: u.name, email: u.email, password: u.password });
      await refresh();
    } catch (e) { reportError(e); }
  }, [refresh]);

  const deleteUser = useCallback(async (id: string) => {
    try { await usersApi.remove(id); await refresh(); } catch (e) { reportError(e); }
  }, [refresh]);

  const bulkAddUsers = useCallback(async (rows: Omit<User, 'id' | 'createdAt'>[]) => {
    try { await usersApi.batch(rows); await refresh(); } catch (e) { reportError(e); }
  }, [refresh]);

  // ---- Classes ----
  const addClass = useCallback(async (c: Omit<Class, 'id' | 'createdAt' | 'teacherId'>) => {
    try {
      await classesApi.create({ school: c.school, grade: c.grade, major: c.major, logo: c.logo });
      await refresh();
    } catch (e) { reportError(e); }
  }, [refresh]);

  const updateClass = useCallback(async (c: Class) => {
    try {
      await classesApi.update(c.id, { school: c.school, grade: c.grade, major: c.major, logo: c.logo });
      await refresh();
    } catch (e) { reportError(e); }
  }, [refresh]);

  const deleteClass = useCallback(async (id: string) => {
    try { await classesApi.remove(id); await refresh(); } catch (e) { reportError(e); }
  }, [refresh]);

  // ---- Students ----
  const addStudent = useCallback(async (s: Omit<Student, 'id'>) => {
    try {
      await classesApi.createStudent(s.classId, { studentId: s.studentId, name: s.name, email: s.email, password: s.password });
      await refresh();
    } catch (e) { reportError(e); }
  }, [refresh]);

  const updateStudent = useCallback(async (s: Student) => {
    try {
      await studentsApi.update(s.id, { studentId: s.studentId, name: s.name, email: s.email, password: s.password });
      await refresh();
    } catch (e) { reportError(e); }
  }, [refresh]);

  const deleteStudent = useCallback(async (id: string) => {
    try { await studentsApi.remove(id); await refresh(); } catch (e) { reportError(e); }
  }, [refresh]);

  const bulkAddStudents = useCallback(async (rows: Omit<Student, 'id'>[], classId: string) => {
    try {
      await classesApi.batchStudents(classId, rows.map(r => ({ studentId: r.studentId, name: r.name, email: r.email, password: r.password })));
      await refresh();
    } catch (e) { reportError(e); }
  }, [refresh]);

  // ---- Courses ----
  const addCourse = useCallback(async (c: Omit<Course, 'id' | 'createdAt' | 'teacherId'>) => {
    try { await coursesApi.create({ semester: c.semester, name: c.name, classId: c.classId }); await refresh(); } catch (e) { reportError(e); }
  }, [refresh]);

  const updateCourse = useCallback(async (c: Course) => {
    try { await coursesApi.update(c.id, { semester: c.semester, name: c.name, classId: c.classId }); await refresh(); } catch (e) { reportError(e); }
  }, [refresh]);

  const deleteCourse = useCallback(async (id: string) => {
    try { await coursesApi.remove(id); await refresh(); } catch (e) { reportError(e); }
  }, [refresh]);

  // ---- Assignments ----
  const addAssignment = useCallback(async (a: Omit<Assignment, 'id' | 'createdAt'>) => {
    try {
      await assignmentsApi.create({
        title: a.title, content: a.content, courseId: a.courseId,
        allowedFileTypes: a.allowedFileTypes, maxFileSizeMB: a.maxFileSizeMB, deadline: a.deadline,
      });
      await refresh();
    } catch (e) { reportError(e); }
  }, [refresh]);

  const updateAssignment = useCallback(async (a: Assignment) => {
    try {
      await assignmentsApi.update(a.id, {
        title: a.title, content: a.content, courseId: a.courseId,
        allowedFileTypes: a.allowedFileTypes, maxFileSizeMB: a.maxFileSizeMB, deadline: a.deadline,
      });
      await refresh();
    } catch (e) { reportError(e); }
  }, [refresh]);

  const deleteAssignment = useCallback(async (id: string) => {
    try { await assignmentsApi.remove(id); await refresh(); } catch (e) { reportError(e); }
  }, [refresh]);

  // ---- Submissions ----
  const submitAssignment = useCallback(async (assignmentId: string, files: File[], comment: string) => {
    await submissionsApi.submit(assignmentId, files, comment);
    await refresh();
  }, [refresh]);

  return (
    <AppContext.Provider value={{
      currentUser, users, classes, students, courses, assignments, submissions,
      currentPage, selectedClassId, selectedAssignmentId, loading,
      login, logout, navigate,
      addUser, updateUser, deleteUser, bulkAddUsers,
      addClass, updateClass, deleteClass,
      addStudent, updateStudent, deleteStudent, bulkAddStudents,
      addCourse, updateCourse, deleteCourse,
      addAssignment, updateAssignment, deleteAssignment,
      submitAssignment,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
