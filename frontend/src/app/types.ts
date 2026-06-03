export type Role = 'admin' | 'teacher' | 'student';

export interface User {
  id: string;
  role: 'admin' | 'teacher';
  account: string;
  name: string;
  email: string;
  password: string;
  createdAt: string;
}

export interface Class {
  id: string;
  school: string;
  grade: string;
  major: string;
  logo?: string;
  teacherId: string;
  createdAt: string;
}

export interface Student {
  id: string;
  studentId: string;
  name: string;
  email: string;
  password: string;
  classId: string;
}

export interface Course {
  id: string;
  semester: string;
  name: string;
  classId: string;
  teacherId: string;
  createdAt: string;
}

export interface Assignment {
  id: string;
  title: string;
  content: string;
  courseId: string;
  allowedFileTypes: string[];
  maxFileSizeMB: number;
  deadline: string;
  createdAt: string;
}

export interface SubmittedFile {
  name: string;
  size: number;
  type: string;
  storageId?: string;
}

export interface Submission {
  id: string;
  assignmentId: string;
  studentId: string;
  files: SubmittedFile[];
  submittedAt: string;
  comment: string;
}

export interface AuthUser {
  id: string;
  role: Role;
  account: string;
  name: string;
  email: string;
  avatar?: string;
  emailVerified?: boolean;
  classId?: string;
  school?: string;
}

export type Page =
  | 'login'
  | 'users'
  | 'classes'
  | 'class-detail'
  | 'courses'
  | 'assignments'
  | 'my-assignments'
  | 'profile';

export const FILE_TYPE_OPTIONS = [
  { label: 'PDF', value: '.pdf' },
  { label: 'Word (.docx)', value: '.docx' },
  { label: 'Word (.doc)', value: '.doc' },
  { label: 'Excel (.xlsx)', value: '.xlsx' },
  { label: 'PPT (.pptx)', value: '.pptx' },
  { label: '图片 (.jpg)', value: '.jpg' },
  { label: '图片 (.png)', value: '.png' },
  { label: 'ZIP压缩包 (.zip)', value: '.zip' },
  { label: 'RAR压缩包 (.rar)', value: '.rar' },
  { label: '文本文件 (.txt)', value: '.txt' },
  { label: 'Python (.py)', value: '.py' },
  { label: 'Java (.java)', value: '.java' },
  { label: 'C/C++ (.c/.cpp)', value: '.cpp' },
  { label: '所有文件 (*)', value: '*' },
];
