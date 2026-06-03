import { useState } from 'react';
import { ChevronLeft, Plus, Trash2, Edit2, Upload, Users, X, AlertCircle, Check, UserPlus } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import { useApp } from '../../context';
import { PasswordInput } from '../ui/PasswordInput';
import type { Student } from '../../types';

interface FormData { studentId: string; name: string; email: string; password: string; }
const emptyForm: FormData = { studentId: '', name: '', email: '', password: 'minglog666' };

export function ClassDetailPage() {
  const { classes, students, selectedClassId, navigate, addStudent, updateStudent, deleteStudent, bulkAddStudents } = useApp();

  const cls = classes.find(c => c.id === selectedClassId);
  const classStudents = students.filter(s => s.classId === selectedClassId);

  const [editOpen, setEditOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formError, setFormError] = useState('');
  const [bulkText, setBulkText] = useState('');
  const [bulkError, setBulkError] = useState('');
  const [bulkSuccess, setBulkSuccess] = useState(0);
  const [search, setSearch] = useState('');

  if (!cls) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">班级不存在</p>
        <button onClick={() => navigate('classes')} className="mt-3 text-blue-600 text-sm hover:underline">返回班级列表</button>
      </div>
    );
  }

  const filtered = classStudents.filter(s => {
    const q = search.toLowerCase();
    return !search || s.studentId.includes(q) || s.name.toLowerCase().includes(q) || s.email.toLowerCase().includes(q);
  });

  const openAdd = () => { setForm(emptyForm); setEditingId(null); setFormError(''); setEditOpen(true); };
  const openEdit = (s: Student) => {
    setForm({ studentId: s.studentId, name: s.name, email: s.email, password: s.password });
    setEditingId(s.id);
    setFormError('');
    setEditOpen(true);
  };

  const handleSave = () => {
    if (!form.studentId.trim()) { setFormError('学号不能为空'); return; }
    if (!form.name.trim()) { setFormError('姓名不能为空'); return; }
    if (!form.email.trim()) { setFormError('邮箱不能为空'); return; }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) { setFormError('邮箱格式不正确'); return; }
    const dup = students.find(s => s.studentId === form.studentId.trim() && s.id !== editingId);
    if (dup) { setFormError('该学号已存在'); return; }
    if (editingId) {
      const existing = students.find(s => s.id === editingId)!;
      updateStudent({ ...existing, ...form, studentId: form.studentId.trim(), name: form.name.trim(), password: form.password || 'minglog666' });
    } else {
      addStudent({ studentId: form.studentId.trim(), name: form.name.trim(), email: form.email.trim(), password: form.password || 'minglog666', classId: selectedClassId! });
    }
    setEditOpen(false);
  };

  const handleBulkImport = () => {
    setBulkError('');
    setBulkSuccess(0);
    const lines = bulkText.trim().split('\n').filter(l => l.trim());
    if (!lines.length) { setBulkError('请输入学生数据'); return; }
    const rows: Omit<Student, 'id'>[] = [];
    const errors: string[] = [];
    const allIds = students.map(s => s.studentId);

    lines.forEach((line, i) => {
      const parts = line.split(',').map(p => p.trim());
      if (parts.length < 3) { errors.push(`第${i + 1}行格式错误（需要：学号,姓名,邮箱）`); return; }
      const [studentId, name, email = '', password = 'minglog666'] = parts;
      if (!studentId) { errors.push(`第${i + 1}行学号为空`); return; }
      if (!name) { errors.push(`第${i + 1}行姓名为空`); return; }
      if (!email) { errors.push(`第${i + 1}行邮箱为空（邮箱为必填项）`); return; }
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { errors.push(`第${i + 1}行邮箱"${email}"格式不正确`); return; }
      if (allIds.includes(studentId)) { errors.push(`第${i + 1}行学号"${studentId}"已存在`); return; }
      rows.push({ studentId, name, email, password: password || 'minglog666', classId: selectedClassId! });
      allIds.push(studentId);
    });

    if (errors.length) { setBulkError(errors.join('\n')); return; }
    bulkAddStudents(rows, selectedClassId!);
    setBulkSuccess(rows.length);
    setBulkText('');
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Breadcrumb */}
      <button
        onClick={() => navigate('classes')}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-blue-600 transition-colors mb-4"
      >
        <ChevronLeft className="w-4 h-4" />返回班级列表
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl text-gray-900">{cls.grade} {cls.major}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{cls.school} · {classStudents.length} 名学生</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setBulkText(''); setBulkError(''); setBulkSuccess(0); setBulkOpen(true); }}
            className="flex items-center gap-1.5 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <Upload className="w-4 h-4" />批量导入
          </button>
          <button
            onClick={openAdd}
            className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />添加学生
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="mb-4">
        <input
          type="text"
          placeholder="搜索学号、姓名或邮箱..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full max-w-sm px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">学号</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">姓名</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">邮箱</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">密码</th>
              <th className="text-right px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-12">
                  <Users className="w-10 h-10 text-gray-200 mx-auto mb-2" />
                  <p className="text-gray-400 text-sm">{search ? '没有找到匹配的学生' : '还没有添加学生'}</p>
                </td>
              </tr>
            ) : filtered.map(s => (
              <tr key={s.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 text-sm font-mono text-gray-800">{s.studentId}</td>
                <td className="px-4 py-3 text-sm text-gray-800">{s.name}</td>
                <td className="px-4 py-3 text-sm text-gray-500">{s.email || '—'}</td>
                <td className="px-4 py-3 text-sm font-mono text-gray-400">{'•'.repeat(Math.min(s.password.length, 10))}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => openEdit(s)} className="p-1.5 rounded-lg hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors">
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button onClick={() => setDeleteConfirm(s.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-4 py-2.5 border-t border-gray-100 bg-gray-50 text-xs text-gray-400">
          共 {filtered.length} 名学生
        </div>
      </div>

      {/* Add/Edit Dialog */}
      <Dialog.Root open={editOpen} onOpenChange={setEditOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl shadow-2xl z-50 w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-5">
              <Dialog.Title className="text-lg text-gray-900 flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-blue-600" />
                {editingId ? '编辑学生' : '添加学生'}
              </Dialog.Title>
              <Dialog.Close className="p-1 rounded-lg hover:bg-gray-100 text-gray-400"><X className="w-5 h-5" /></Dialog.Close>
            </div>
            <div className="space-y-4">
              {[
                { key: 'studentId', label: '学号', placeholder: '例：2022001', required: true },
                { key: 'name', label: '姓名', placeholder: '学生真实姓名', required: true },
                { key: 'email', label: '邮箱', placeholder: '电子邮箱（必填）', required: true },
                { key: 'password', label: '密码', placeholder: '默认：minglog666' },
              ].map(f => (
                <div key={f.key}>
                  <label className="block text-sm text-gray-700 mb-1">{f.label}{f.required ? ' *' : ''}</label>
                  {f.key === 'password' ? (
                    <PasswordInput
                      value={(form as any)[f.key]}
                      onChange={v => setForm(prev => ({ ...prev, [f.key]: v }))}
                      placeholder={f.placeholder}
                      withIcon={false}
                    />
                  ) : (
                    <input
                      type="text"
                      value={(form as any)[f.key]}
                      onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                      placeholder={f.placeholder}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  )}
                </div>
              ))}
              <p className="text-xs text-gray-400">密码为空时默认使用 minglog666</p>
              {formError && (
                <div className="flex items-center gap-2 text-red-600 bg-red-50 rounded-lg px-3 py-2 text-sm">
                  <AlertCircle className="w-4 h-4" />{formError}
                </div>
              )}
            </div>
            <div className="flex gap-3 mt-6">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">取消</Dialog.Close>
              <button onClick={handleSave} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors">
                {editingId ? '保存' : '添加'}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Bulk Import Dialog */}
      <Dialog.Root open={bulkOpen} onOpenChange={setBulkOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl shadow-2xl z-50 w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <Dialog.Title className="text-lg text-gray-900 flex items-center gap-2">
                <Upload className="w-5 h-5 text-blue-600" />批量导入学生
              </Dialog.Title>
              <Dialog.Close className="p-1 rounded-lg hover:bg-gray-100 text-gray-400"><X className="w-5 h-5" /></Dialog.Close>
            </div>
            <div className="bg-blue-50 rounded-lg p-3 text-xs text-blue-700 mb-3 font-mono">
              格式：学号,姓名,邮箱,密码(可选)<br />
              说明：邮箱为必填项；密码留空时默认为 minglog666<br />
              示例：<br />
              2022001,张三,zhangsan@email.com,minglog666<br />
              2022002,李四,lisi@email.com,<br />
              2022003,王五,wangwu@email.com
            </div>
            <textarea
              value={bulkText}
              onChange={e => { setBulkText(e.target.value); setBulkError(''); setBulkSuccess(0); }}
              placeholder="每行一名学生，按格式输入..."
              rows={8}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
            {bulkError && (
              <div className="mt-2 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 whitespace-pre-line">
                <AlertCircle className="w-4 h-4 inline mr-1" />{bulkError}
              </div>
            )}
            {bulkSuccess > 0 && (
              <div className="mt-2 text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2 flex items-center gap-2">
                <Check className="w-4 h-4" />成功导入 {bulkSuccess} 名学生
              </div>
            )}
            <div className="flex gap-3 mt-4">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">关闭</Dialog.Close>
              <button onClick={handleBulkImport} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors">
                导入
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
            <Dialog.Title className="text-lg text-gray-900 mb-2">确认删除学生</Dialog.Title>
            <p className="text-sm text-gray-500 mb-5">确定要删除该学生吗？此操作不可撤销。</p>
            <div className="flex gap-3">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">取消</Dialog.Close>
              <button
                onClick={() => { if (deleteConfirm) deleteStudent(deleteConfirm); setDeleteConfirm(null); }}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 transition-colors"
              >
                删除
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
