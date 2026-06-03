import { useState } from 'react';
import { Plus, Trash2, Edit2, BookCopy, X, AlertCircle } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import { useApp } from '../../context';
import { formatDate } from '../../datetime';
import type { Course } from '../../types';

interface FormData { semester: string; name: string; classId: string; }
const emptyForm: FormData = { semester: '', name: '', classId: '' };

const SEMESTERS = ['2024春季学期', '2024秋季学期', '2025春季学期', '2025秋季学期', '2026春季学期', '2026秋季学期'];

export function CoursesPage() {
  const { currentUser, classes, courses, assignments, addCourse, updateCourse, deleteCourse } = useApp();

  const myClasses = currentUser?.role === 'admin'
    ? classes
    : classes.filter(c => c.teacherId === currentUser?.id);
  const myCourses = currentUser?.role === 'admin'
    ? courses
    : courses.filter(c => c.teacherId === currentUser?.id);

  const [editOpen, setEditOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formError, setFormError] = useState('');
  const [search, setSearch] = useState('');

  const filtered = myCourses.filter(c => {
    const q = search.toLowerCase();
    const cls = classes.find(cl => cl.id === c.classId);
    return !search || c.name.toLowerCase().includes(q) || c.semester.toLowerCase().includes(q) ||
      (cls && `${cls.grade} ${cls.major}`.toLowerCase().includes(q));
  });

  const openAdd = () => {
    setForm({ ...emptyForm, classId: myClasses[0]?.id || '' });
    setEditingId(null);
    setFormError('');
    setEditOpen(true);
  };

  const openEdit = (c: Course) => {
    setForm({ semester: c.semester, name: c.name, classId: c.classId });
    setEditingId(c.id);
    setFormError('');
    setEditOpen(true);
  };

  const handleSave = () => {
    if (!form.semester.trim()) { setFormError('请输入学期'); return; }
    if (!form.name.trim()) { setFormError('请输入课程名称'); return; }
    if (!form.classId) { setFormError('请选择关联班级'); return; }
    if (editingId) {
      const existing = courses.find(c => c.id === editingId)!;
      updateCourse({ ...existing, ...form, name: form.name.trim(), semester: form.semester.trim() });
    } else {
      addCourse({ ...form, name: form.name.trim(), semester: form.semester.trim() });
    }
    setEditOpen(false);
  };

  const getClassName = (classId: string) => {
    const c = classes.find(cl => cl.id === classId);
    return c ? `${c.grade} ${c.major}` : '未知班级';
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl text-gray-900 flex items-center gap-2">
            <BookCopy className="w-6 h-6 text-blue-600" />课程管理
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">管理您的课程信息</p>
        </div>
        <button
          onClick={openAdd}
          disabled={myClasses.length === 0}
          className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Plus className="w-4 h-4" />新建课程
        </button>
      </div>

      {myClasses.length === 0 && (
        <div className="mb-4 flex items-center gap-2 bg-amber-50 border border-amber-100 text-amber-700 rounded-lg px-4 py-3 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          请先在"班级管理"中创建班级，才能创建课程
        </div>
      )}

      <div className="mb-4">
        <input
          type="text"
          placeholder="搜索课程名称、学期或班级..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full max-w-sm px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">课程名称</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">学期</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">关联班级</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">作业数</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">创建时间</th>
              <th className="text-right px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-12">
                  <BookCopy className="w-10 h-10 text-gray-200 mx-auto mb-2" />
                  <p className="text-gray-400 text-sm">{search ? '没有找到匹配的课程' : '还没有创建课程'}</p>
                </td>
              </tr>
            ) : filtered.map(c => {
              const aCount = assignments.filter(a => a.courseId === c.id).length;
              return (
                <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-sm text-gray-800">{c.name}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full">{c.semester}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{getClassName(c.classId)}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{aCount}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{formatDate(c.createdAt)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => openEdit(c)} className="p-1.5 rounded-lg hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors">
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button onClick={() => setDeleteConfirm(c.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors">
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
          共 {filtered.length} 门课程
        </div>
      </div>

      {/* Add/Edit Dialog */}
      <Dialog.Root open={editOpen} onOpenChange={setEditOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl shadow-2xl z-50 w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-5">
              <Dialog.Title className="text-lg text-gray-900">{editingId ? '编辑课程' : '新建课程'}</Dialog.Title>
              <Dialog.Close className="p-1 rounded-lg hover:bg-gray-100 text-gray-400"><X className="w-5 h-5" /></Dialog.Close>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-700 mb-1">学期 *</label>
                <div className="flex gap-2">
                  <select
                    value={SEMESTERS.includes(form.semester) ? form.semester : ''}
                    onChange={e => setForm(f => ({ ...f, semester: e.target.value }))}
                    className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                  >
                    <option value="">选择学期</option>
                    {SEMESTERS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <input
                  type="text"
                  value={form.semester}
                  onChange={e => setForm(f => ({ ...f, semester: e.target.value }))}
                  placeholder="或手动输入学期名称"
                  className="mt-2 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">课程名称 *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="例：Web前端开发"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">关联班级 *</label>
                <select
                  value={form.classId}
                  onChange={e => setForm(f => ({ ...f, classId: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  <option value="">请选择班级</option>
                  {myClasses.map(c => (
                    <option key={c.id} value={c.id}>{c.grade} {c.major} - {c.school}</option>
                  ))}
                </select>
              </div>
              {formError && (
                <div className="flex items-center gap-2 text-red-600 bg-red-50 rounded-lg px-3 py-2 text-sm">
                  <AlertCircle className="w-4 h-4" />{formError}
                </div>
              )}
            </div>
            <div className="flex gap-3 mt-6">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">取消</Dialog.Close>
              <button onClick={handleSave} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors">
                {editingId ? '保存' : '创建'}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Delete Confirm */}
      <Dialog.Root open={!!deleteConfirm} onOpenChange={o => !o && setDeleteConfirm(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl shadow-2xl z-50 w-full max-w-sm p-6">
            <Dialog.Title className="text-lg text-gray-900 mb-2">确认删除课程</Dialog.Title>
            <p className="text-sm text-gray-500 mb-5">删除课程将同时删除该课程的所有作业和提交记录，此操作不可撤销。</p>
            <div className="flex gap-3">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">取消</Dialog.Close>
              <button
                onClick={() => { if (deleteConfirm) deleteCourse(deleteConfirm); setDeleteConfirm(null); }}
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
