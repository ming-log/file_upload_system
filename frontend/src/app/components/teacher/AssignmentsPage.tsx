import { useState } from 'react';
import { Plus, Trash2, Edit2, ClipboardList, X, AlertCircle, Eye, Clock, CheckCircle2, XCircle, FileText, Download } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import { useApp } from '../../context';
import { submissionsApi, ApiError } from '../../api';
import { parseDateTime, formatDateTime, toDatetimeLocalValue } from '../../datetime';
import { Tooltip, TooltipTrigger, TooltipContent } from '../ui/tooltip';
import type { Assignment } from '../../types';
import { FILE_TYPE_OPTIONS } from '../../types';

interface FormData {
  title: string;
  content: string;
  courseId: string;
  allowedFileTypes: string[];
  maxFileSizeMB: number;
  deadline: string;
}

const emptyForm: FormData = {
  title: '',
  content: '',
  courseId: '',
  allowedFileTypes: ['.pdf', '.docx'],
  maxFileSizeMB: 20,
  deadline: '',
};

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function AssignmentStatus({ deadline }: { deadline: string }) {
  const now = new Date();
  const dl = parseDateTime(deadline);
  if (!dl) return null;
  const diff = dl.getTime() - now.getTime();
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24));

  if (diff < 0) return <span className="inline-flex items-center gap-1 text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded-full whitespace-nowrap"><XCircle className="w-3 h-3" />已截止</span>;
  if (days <= 3) return <span className="inline-flex items-center gap-1 text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full whitespace-nowrap"><Clock className="w-3 h-3" />即将截止</span>;
  return <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full whitespace-nowrap"><CheckCircle2 className="w-3 h-3" />进行中</span>;
}

export function AssignmentsPage() {
  const { currentUser, classes, courses, assignments, submissions, students, addAssignment, updateAssignment, deleteAssignment } = useApp();

  const myCourses = currentUser?.role === 'admin'
    ? courses
    : courses.filter(c => c.teacherId === currentUser?.id);
  const myAssignments = assignments.filter(a => myCourses.some(c => c.id === a.courseId));

  const [editOpen, setEditOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [viewSubmissions, setViewSubmissions] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formError, setFormError] = useState('');
  const [search, setSearch] = useState('');
  const [exportingId, setExportingId] = useState<string | null>(null);

  // 下载单个提交文件（带鉴权头，故用 fetch 取 Blob 再触发下载）。
  const downloadFile = async (submissionId: string, storageId: string, name: string) => {
    try {
      const headers: Record<string, string> = {};
      const token = localStorage.getItem('auth_token');
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(submissionsApi.fileUrl(submissionId, storageId), { headers });
      if (!res.ok) throw new ApiError(res.status, '下载失败');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      // eslint-disable-next-line no-alert
      alert(e instanceof ApiError ? (e.message || '下载失败') : '下载失败，请稍后重试');
    }
  };

  // 一键导出指定作业的全部提交（ZIP：文件 + 提交状态表）。
  const handleExportAssignment = async (assignmentId: string) => {
    setExportingId(assignmentId);
    try {
      const { blob, filename } = await submissionsApi.exportAssignment(assignmentId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      // eslint-disable-next-line no-alert
      alert(e instanceof ApiError ? (e.message || '导出失败') : '导出失败，请稍后重试');
    } finally {
      setExportingId(null);
    }
  };

  const filtered = myAssignments.filter(a => {
    const q = search.toLowerCase();
    const course = courses.find(c => c.id === a.courseId);
    return !search || a.title.toLowerCase().includes(q) || (course && course.name.toLowerCase().includes(q));
  });

  const openAdd = () => {
    setForm({ ...emptyForm, courseId: myCourses[0]?.id || '' });
    setEditingId(null);
    setFormError('');
    setEditOpen(true);
  };

  const openEdit = (a: Assignment) => {
    setForm({
      title: a.title,
      content: a.content,
      courseId: a.courseId,
      allowedFileTypes: a.allowedFileTypes,
      maxFileSizeMB: a.maxFileSizeMB,
      deadline: toDatetimeLocalValue(a.deadline),
    });
    setEditingId(a.id);
    setFormError('');
    setEditOpen(true);
  };

  const toggleFileType = (type: string) => {
    setForm(f => ({
      ...f,
      allowedFileTypes: f.allowedFileTypes.includes(type)
        ? f.allowedFileTypes.filter(t => t !== type)
        : [...f.allowedFileTypes, type],
    }));
  };

  const handleSave = () => {
    if (!form.title.trim()) { setFormError('请输入作业标题'); return; }
    if (!form.content.trim()) { setFormError('请输入作业内容'); return; }
    if (!form.courseId) { setFormError('请选择关联课程'); return; }
    if (form.allowedFileTypes.length === 0) { setFormError('请至少选择一种文件类型'); return; }
    if (!form.deadline) { setFormError('请设置截止时间'); return; }
    if (editingId) {
      const existing = assignments.find(a => a.id === editingId)!;
      updateAssignment({ ...existing, ...form, title: form.title.trim(), content: form.content.trim() });
    } else {
      addAssignment({ ...form, title: form.title.trim(), content: form.content.trim() });
    }
    setEditOpen(false);
  };

  const getCourseName = (courseId: string) => courses.find(c => c.id === courseId)?.name || '未知课程';

  const getSubmissionsForAssignment = (assignmentId: string) => submissions.filter(s => s.assignmentId === assignmentId);

  const selectedAssignment = viewSubmissions ? assignments.find(a => a.id === viewSubmissions) : null;
  const assignmentSubmissions = viewSubmissions ? getSubmissionsForAssignment(viewSubmissions) : [];

  // Get all students in the class of the course of this assignment
  const getAssignmentStudents = (assignmentId: string) => {
    const assignment = assignments.find(a => a.id === assignmentId);
    if (!assignment) return [];
    const course = courses.find(c => c.id === assignment.courseId);
    if (!course) return [];
    return students.filter(s => s.classId === course.classId);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl text-gray-900 flex items-center gap-2">
            <ClipboardList className="w-6 h-6 text-blue-600" />作业管理
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">创建和管理作业，查看学生提交情况</p>
        </div>
        <button
          onClick={openAdd}
          disabled={myCourses.length === 0}
          className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Plus className="w-4 h-4" />新建作业
        </button>
      </div>

      {myCourses.length === 0 && (
        <div className="mb-4 flex items-center gap-2 bg-amber-50 border border-amber-100 text-amber-700 rounded-lg px-4 py-3 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          请先在"课程管理"中创建课程，才能创建作业
        </div>
      )}

      <div className="mb-4">
        <input
          type="text"
          placeholder="搜索作业标题或课程..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full max-w-sm px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full table-fixed">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide w-[22%]">作业标题</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide w-[12%]">关联课程</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide w-[13%]">文件限制</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide w-[16%] whitespace-nowrap">截止时间</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide w-[9%] whitespace-nowrap">状态</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide w-[8%] whitespace-nowrap">提交</th>
              <th className="text-right px-4 py-3 text-xs text-gray-500 uppercase tracking-wide whitespace-nowrap">操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-12">
                  <ClipboardList className="w-10 h-10 text-gray-200 mx-auto mb-2" />
                  <p className="text-gray-400 text-sm">{search ? '没有找到匹配的作业' : '还没有创建作业'}</p>
                </td>
              </tr>
            ) : filtered.map(a => {
              const subs = getSubmissionsForAssignment(a.id);
              const totalStudents = getAssignmentStudents(a.id).length;
              return (
                <tr key={a.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <p className="text-sm text-gray-800 font-medium truncate">{a.title}</p>
                    {a.content ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <p className="text-xs text-gray-400 mt-0.5 line-clamp-1 cursor-help">{a.content}</p>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-sm whitespace-pre-wrap text-left">
                          {a.content}
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      <p className="text-xs text-gray-300 mt-0.5">无说明</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 truncate">{getCourseName(a.courseId)}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    <div className="flex flex-wrap gap-1">
                      {a.allowedFileTypes.slice(0, 3).map(t => (
                        <span key={t} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{t}</span>
                      ))}
                      {a.allowedFileTypes.length > 3 && (
                        <span className="text-xs text-gray-400">+{a.allowedFileTypes.length - 3}</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">≤ {a.maxFileSizeMB}MB</p>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                    {formatDateTime(a.deadline)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap"><AssignmentStatus deadline={a.deadline} /></td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <button
                      onClick={() => setViewSubmissions(a.id)}
                      className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 transition-colors"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      {subs.length}/{totalStudents}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => handleExportAssignment(a.id)}
                        disabled={exportingId === a.id || subs.length === 0}
                        title={subs.length === 0 ? '暂无提交可下载' : '下载该作业全部提交文件与提交状态表'}
                        className="p-1.5 rounded-lg hover:bg-green-50 text-gray-400 hover:text-green-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                      >
                        {exportingId === a.id ? (
                          <div className="w-4 h-4 border-2 border-green-500/30 border-t-green-600 rounded-full animate-spin" />
                        ) : (
                          <Download className="w-4 h-4" />
                        )}
                      </button>
                      <button onClick={() => openEdit(a)} className="p-1.5 rounded-lg hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors">
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button onClick={() => setDeleteConfirm(a.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="px-4 py-2.5 border-t border-gray-100 bg-gray-50 text-xs text-gray-400">
          共 {filtered.length} 个作业
        </div>
      </div>

      {/* Add/Edit Dialog */}
      <Dialog.Root open={editOpen} onOpenChange={setEditOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl shadow-2xl z-50 w-full max-w-xl max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-5 sticky top-0 bg-white pb-3 border-b border-gray-100">
              <Dialog.Title className="text-lg text-gray-900">{editingId ? '编辑作业' : '新建作业'}</Dialog.Title>
              <Dialog.Close className="p-1 rounded-lg hover:bg-gray-100 text-gray-400"><X className="w-5 h-5" /></Dialog.Close>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-700 mb-1">作业标题 *</label>
                <input
                  type="text"
                  value={form.title}
                  onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="例：第一次实验报告"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">作业内容说明 *</label>
                <textarea
                  value={form.content}
                  onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
                  placeholder="详细描述作业要求..."
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">关联课程 *</label>
                <select
                  value={form.courseId}
                  onChange={e => setForm(f => ({ ...f, courseId: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  <option value="">请选择课程</option>
                  {myCourses.map(c => {
                    const cls = classes.find(cl => cl.id === c.classId);
                    return <option key={c.id} value={c.id}>{c.name} - {cls ? `${cls.grade} ${cls.major}` : ''}</option>;
                  })}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-2">允许的文件类型 *</label>
                <div className="grid grid-cols-2 gap-2">
                  {FILE_TYPE_OPTIONS.map(opt => (
                    <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.allowedFileTypes.includes(opt.value)}
                        onChange={() => toggleFileType(opt.value)}
                        className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700">{opt.label}</span>
                    </label>
                  ))}
                </div>
                {form.allowedFileTypes.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {form.allowedFileTypes.map(t => (
                      <span key={t} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">{t}</span>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">文件大小限制（MB）*</label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={1}
                    max={500}
                    value={form.maxFileSizeMB}
                    onChange={e => setForm(f => ({ ...f, maxFileSizeMB: Number(e.target.value) }))}
                    className="flex-1"
                  />
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      min={1}
                      max={500}
                      value={form.maxFileSizeMB}
                      onChange={e => setForm(f => ({ ...f, maxFileSizeMB: Number(e.target.value) }))}
                      className="w-16 px-2 py-1 border border-gray-200 rounded-lg text-sm text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-500">MB</span>
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">提交截止时间 *</label>
                <input
                  type="datetime-local"
                  value={form.deadline}
                  onChange={e => setForm(f => ({ ...f, deadline: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              {formError && (
                <div className="flex items-center gap-2 text-red-600 bg-red-50 rounded-lg px-3 py-2 text-sm">
                  <AlertCircle className="w-4 h-4" />{formError}
                </div>
              )}
            </div>
            <div className="flex gap-3 mt-6 sticky bottom-0 bg-white pt-3 border-t border-gray-100">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">取消</Dialog.Close>
              <button onClick={handleSave} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors">
                {editingId ? '保存修改' : '创建作业'}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* View Submissions Dialog */}
      <Dialog.Root open={!!viewSubmissions} onOpenChange={o => !o && setViewSubmissions(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/45 backdrop-blur-sm z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-3xl shadow-2xl z-50 w-[calc(100vw-2rem)] max-w-5xl max-h-[86vh] overflow-hidden flex flex-col border border-white/80">
            <div className="flex items-center justify-between gap-4 px-6 py-5 border-b border-gray-100 bg-gradient-to-r from-blue-50 via-white to-emerald-50">
              <div>
                <Dialog.Title className="text-xl font-semibold text-gray-900">{selectedAssignment?.title}</Dialog.Title>
                <p className="mt-1 text-sm text-gray-500">提交记录 - {assignmentSubmissions.length} / {viewSubmissions ? getAssignmentStudents(viewSubmissions).length : 0} 人已提交</p>
              </div>
              <div className="flex items-center gap-2">
                {selectedAssignment && (
                  <button
                    onClick={() => handleExportAssignment(selectedAssignment.id)}
                    disabled={exportingId === selectedAssignment.id}
                    title="下载该作业全部提交文件与提交状态表（ZIP）"
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-60 transition-colors"
                  >
                    {exportingId === selectedAssignment.id ? (
                      <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />导出中...</>
                    ) : (
                      <><Download className="w-4 h-4" />下载全部提交</>
                    )}
                  </button>
                )}
                <Dialog.Close className="p-1 rounded-lg hover:bg-gray-100 text-gray-400"><X className="w-5 h-5" /></Dialog.Close>
              </div>
            </div>
            <div className="overflow-auto flex-1 bg-slate-50/60 p-4">
              {viewSubmissions && (() => {
                const assignStudents = getAssignmentStudents(viewSubmissions);
                return assignStudents.length === 0 ? (
                  <div className="text-center py-12 text-gray-400">该课程暂无学生</div>
                ) : (
                  <div className="overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-sm">
                    <table className="w-full table-fixed">
                    <thead className="sticky top-0 bg-slate-100/95 backdrop-blur border-b border-gray-200 z-10">
                      <tr>
                        <th className="w-32 text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">学号</th>
                        <th className="w-32 text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">姓名</th>
                        <th className="w-36 text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">状态</th>
                        <th className="w-44 text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">提交时间</th>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">文件</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {assignStudents.map(s => {
                        const sub = assignmentSubmissions.find(sb => sb.studentId === s.id);
                        const isLate = sub && selectedAssignment && (() => {
                          const sa = parseDateTime(sub.submittedAt);
                          const dl = parseDateTime(selectedAssignment.deadline);
                          return !!(sa && dl && sa > dl);
                        })();
                        return (
                          <tr key={s.id} className="hover:bg-blue-50/40 transition-colors">
                            <td className="px-4 py-4 text-sm font-mono text-gray-700 whitespace-nowrap">{s.studentId}</td>
                            <td className="px-4 py-4 text-sm font-medium text-gray-900 whitespace-nowrap">{s.name}</td>
                            <td className="px-4 py-4 whitespace-nowrap">
                              {sub ? (
                                <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ${isLate ? 'bg-amber-50 text-amber-700 ring-1 ring-amber-100' : 'bg-green-50 text-green-700 ring-1 ring-green-100'}`}>
                                  <CheckCircle2 className="w-3 h-3" />{isLate ? '已提交(迟交)' : '已提交'}
                                </span>
                              ) : (
                                <span className="inline-flex items-center whitespace-nowrap rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-500 ring-1 ring-gray-200">未提交</span>
                              )}
                            </td>
                            <td className="px-4 py-4 text-sm text-gray-500 whitespace-nowrap">
                              {sub ? formatDateTime(sub.submittedAt) : '—'}
                            </td>
                            <td className="px-4 py-4 min-w-0">
                              {sub ? (
                                <div className="space-y-1">
                                  {sub.files.map((f, i) => (
                                    <button
                                      key={i}
                                      onClick={() => f.storageId && downloadFile(sub.id, f.storageId, f.name)}
                                      disabled={!f.storageId}
                                      title={f.storageId ? '点击下载' : '无法下载'}
                                      className="flex max-w-full items-center gap-1.5 text-xs text-gray-600 hover:text-blue-600 disabled:hover:text-gray-600 disabled:cursor-not-allowed transition-colors"
                                    >
                                      <FileText className="w-3 h-3 text-blue-500" />
                                      <span className="truncate underline-offset-2 hover:underline">{f.name}</span>
                                      <span className="text-gray-400">({formatFileSize(f.size)})</span>
                                      {f.storageId && <Download className="w-3 h-3 text-gray-300" />}
                                    </button>
                                  ))}
                                  {sub.comment && <p className="text-xs text-gray-400 italic">"{sub.comment}"</p>}
                                </div>
                              ) : '—'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  </div>
                );
              })()}
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Delete Confirm */}
      <Dialog.Root open={!!deleteConfirm} onOpenChange={o => !o && setDeleteConfirm(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl shadow-2xl z-50 w-full max-w-sm p-6">
            <Dialog.Title className="text-lg text-gray-900 mb-2">确认删除作业</Dialog.Title>
            <p className="text-sm text-gray-500 mb-5">删除作业将同时删除所有提交记录，此操作不可撤销。</p>
            <div className="flex gap-3">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">取消</Dialog.Close>
              <button
                onClick={() => { if (deleteConfirm) deleteAssignment(deleteConfirm); setDeleteConfirm(null); }}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 transition-colors"
              >
                确认删除
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
