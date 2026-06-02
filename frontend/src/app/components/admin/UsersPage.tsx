import { useState } from 'react';
import { Plus, Trash2, Edit2, Users, Upload, X, Check, AlertCircle, UserPlus } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import { useApp } from '../../context';
import type { User } from '../../types';

const ROLES = [
  { value: 'admin', label: '管理员', color: 'bg-purple-100 text-purple-700' },
  { value: 'teacher', label: '教师', color: 'bg-blue-100 text-blue-700' },
];

function RoleBadge({ role }: { role: string }) {
  const r = ROLES.find(x => x.value === role);
  return <span className={`text-xs px-2 py-0.5 rounded-full ${r?.color || 'bg-gray-100 text-gray-600'}`}>{r?.label || role}</span>;
}

interface UserFormData {
  role: 'admin' | 'teacher';
  account: string;
  name: string;
  email: string;
  password: string;
}

const emptyForm: UserFormData = { role: 'teacher', account: '', name: '', email: '', password: '' };

export function UsersPage() {
  const { users, addUser, updateUser, deleteUser, bulkAddUsers } = useApp();
  const [editOpen, setEditOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [form, setForm] = useState<UserFormData>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [bulkText, setBulkText] = useState('');
  const [bulkError, setBulkError] = useState('');
  const [bulkSuccess, setBulkSuccess] = useState(0);
  const [formError, setFormError] = useState('');
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');

  const filtered = users.filter(u => {
    const q = search.toLowerCase();
    const matchSearch = !search || u.account.toLowerCase().includes(q) || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q);
    const matchRole = !roleFilter || u.role === roleFilter;
    return matchSearch && matchRole;
  });

  const openAdd = () => {
    setForm(emptyForm);
    setEditingId(null);
    setFormError('');
    setEditOpen(true);
  };

  const openEdit = (u: User) => {
    setForm({ role: u.role, account: u.account, name: u.name, email: u.email, password: u.password });
    setEditingId(u.id);
    setFormError('');
    setEditOpen(true);
  };

  const handleSave = () => {
    if (!form.account.trim()) { setFormError('账号不能为空'); return; }
    if (!form.name.trim()) { setFormError('姓名不能为空'); return; }
    // Check duplicate account
    const dup = users.find(u => u.account === form.account.trim() && u.id !== editingId);
    if (dup) { setFormError('该账号已存在'); return; }
    if (editingId) {
      const existing = users.find(u => u.id === editingId)!;
      updateUser({ ...existing, ...form, account: form.account.trim(), name: form.name.trim(), email: form.email.trim() });
    } else {
      addUser({ ...form, account: form.account.trim(), name: form.name.trim(), email: form.email.trim() });
    }
    setEditOpen(false);
  };

  const handleBulkImport = () => {
    setBulkError('');
    setBulkSuccess(0);
    const lines = bulkText.trim().split('\n').filter(l => l.trim());
    if (!lines.length) { setBulkError('请输入用户数据'); return; }
    const rows: Omit<User, 'id' | 'createdAt'>[] = [];
    const errors: string[] = [];
    lines.forEach((line, i) => {
      const parts = line.split(',').map(p => p.trim());
      if (parts.length < 3) { errors.push(`第${i + 1}行格式错误`); return; }
      const [roleStr, account, name, email = '', password = ''] = parts;
      const role = roleStr === '管理员' ? 'admin' : roleStr === '教师' ? 'teacher' : null;
      if (!role) { errors.push(`第${i + 1}行角色无效（应为"管理员"或"教师"）`); return; }
      if (!account) { errors.push(`第${i + 1}行账号为空`); return; }
      if (!name) { errors.push(`第${i + 1}行姓名为空`); return; }
      if (users.find(u => u.account === account)) { errors.push(`第${i + 1}行账号"${account}"已存在`); return; }
      rows.push({ role: role as 'admin' | 'teacher', account, name, email, password });
    });
    if (errors.length) { setBulkError(errors.join('\n')); return; }
    bulkAddUsers(rows);
    setBulkSuccess(rows.length);
    setBulkText('');
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl text-gray-900 flex items-center gap-2">
            <Users className="w-6 h-6 text-blue-600" />用户管理
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">管理系统中的管理员和教师账号</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setBulkText(''); setBulkError(''); setBulkSuccess(0); setBulkOpen(true); }}
            className="flex items-center gap-1.5 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <Upload className="w-4 h-4" />批量创建
          </button>
          <button
            onClick={openAdd}
            className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />新增用户
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          placeholder="搜索账号、姓名或邮箱..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={roleFilter}
          onChange={e => setRoleFilter(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="">全部角色</option>
          <option value="admin">管理员</option>
          <option value="teacher">教师</option>
        </select>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: '全部用户', count: users.length, color: 'text-gray-700', bg: 'bg-gray-50' },
          { label: '管理员', count: users.filter(u => u.role === 'admin').length, color: 'text-purple-700', bg: 'bg-purple-50' },
          { label: '教师', count: users.filter(u => u.role === 'teacher').length, color: 'text-blue-700', bg: 'bg-blue-50' },
        ].map(s => (
          <div key={s.label} className={`${s.bg} rounded-xl p-4 border border-gray-100`}>
            <p className="text-2xl font-semibold ${s.color} text-gray-900">{s.count}</p>
            <p className="text-sm text-gray-500">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">账号</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">姓名</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">角色</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">邮箱</th>
              <th className="text-left px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">创建时间</th>
              <th className="text-right px-4 py-3 text-xs text-gray-500 uppercase tracking-wide">操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-12 text-gray-400">暂无用户数据</td></tr>
            ) : filtered.map(u => (
              <tr key={u.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 text-sm font-mono text-gray-800">{u.account}</td>
                <td className="px-4 py-3 text-sm text-gray-800">{u.name}</td>
                <td className="px-4 py-3"><RoleBadge role={u.role} /></td>
                <td className="px-4 py-3 text-sm text-gray-500">{u.email || '—'}</td>
                <td className="px-4 py-3 text-sm text-gray-500">{new Date(u.createdAt).toLocaleDateString('zh-CN')}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => openEdit(u)} className="p-1.5 rounded-lg hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors">
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button onClick={() => setDeleteConfirm(u.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-4 py-2.5 border-t border-gray-100 bg-gray-50 text-xs text-gray-400">
          共 {filtered.length} 条记录
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
                {editingId ? '编辑用户' : '新增用户'}
              </Dialog.Title>
              <Dialog.Close className="p-1 rounded-lg hover:bg-gray-100 text-gray-400">
                <X className="w-5 h-5" />
              </Dialog.Close>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-700 mb-1">角色 *</label>
                <select
                  value={form.role}
                  onChange={e => setForm(f => ({ ...f, role: e.target.value as 'admin' | 'teacher' }))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="teacher">教师</option>
                  <option value="admin">管理员</option>
                </select>
              </div>
              {[
                { key: 'account', label: '账号', placeholder: '登录账号', required: true },
                { key: 'name', label: '姓名', placeholder: '真实姓名', required: true },
                { key: 'email', label: '邮箱', placeholder: '电子邮箱（可选）' },
                { key: 'password', label: '密码', placeholder: '登录密码（留空则默认：minglog666）' },
              ].map(f => (
                <div key={f.key}>
                  <label className="block text-sm text-gray-700 mb-1">{f.label} {f.required && '*'}</label>
                  <input
                    type={f.key === 'password' ? 'password' : 'text'}
                    value={(form as any)[f.key]}
                    onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              ))}
              {formError && (
                <div className="flex items-center gap-2 text-red-600 bg-red-50 rounded-lg px-3 py-2 text-sm">
                  <AlertCircle className="w-4 h-4" />{formError}
                </div>
              )}
            </div>
            <div className="flex gap-3 mt-6">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors">
                取消
              </Dialog.Close>
              <button onClick={handleSave} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors">
                {editingId ? '保存修改' : '创建用户'}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Bulk Dialog */}
      <Dialog.Root open={bulkOpen} onOpenChange={setBulkOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl shadow-2xl z-50 w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <Dialog.Title className="text-lg text-gray-900 flex items-center gap-2">
                <Upload className="w-5 h-5 text-blue-600" />批量创建用户
              </Dialog.Title>
              <Dialog.Close className="p-1 rounded-lg hover:bg-gray-100 text-gray-400"><X className="w-5 h-5" /></Dialog.Close>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500 mb-3 font-mono">
              格式：角色,账号,姓名,邮箱(可选),密码(可选)<br />
              说明：密码留空时默认为 minglog666<br />
              示例：<br />
              教师,teacher002,李老师,li@school.edu,pass123<br />
              管理员,admin2,副管理员,,
            </div>
            <textarea
              value={bulkText}
              onChange={e => { setBulkText(e.target.value); setBulkError(''); setBulkSuccess(0); }}
              placeholder="每行一条记录，按格式输入..."
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
                <Check className="w-4 h-4" />成功创建 {bulkSuccess} 个用户
              </div>
            )}
            <div className="flex gap-3 mt-4">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors">
                关闭
              </Dialog.Close>
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
            <Dialog.Title className="text-lg text-gray-900 mb-2">确认删除</Dialog.Title>
            <p className="text-sm text-gray-500 mb-5">确定要删除该用户吗？此操作不可撤销。</p>
            <div className="flex gap-3">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">取消</Dialog.Close>
              <button
                onClick={() => { if (deleteConfirm) deleteUser(deleteConfirm); setDeleteConfirm(null); }}
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
