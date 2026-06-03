import { useState } from 'react';
import { Plus, Trash2, Edit2, GraduationCap, Users, ChevronRight, X, AlertCircle, Upload } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import { useApp } from '../../context';
import type { Class } from '../../types';

interface FormData { school: string; grade: string; major: string; logo?: string; }
const emptyForm: FormData = { school: '', grade: '', major: '', logo: undefined };

export function ClassesPage() {
  const { currentUser, classes, students, courses, addClass, updateClass, deleteClass, navigate } = useApp();
  // 管理员可管理所有班级；教师仅管理自己创建的班级。
  const myClasses = currentUser?.role === 'admin'
    ? classes
    : classes.filter(c => c.teacherId === currentUser?.id);

  const [editOpen, setEditOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formError, setFormError] = useState('');

  const openAdd = () => { setForm(emptyForm); setEditingId(null); setFormError(''); setEditOpen(true); };
  const openEdit = (c: Class) => { setForm({ school: c.school, grade: c.grade, major: c.major, logo: c.logo }); setEditingId(c.id); setFormError(''); setEditOpen(true); };

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) { setFormError('请选择图片文件'); return; }
    if (file.size > 2 * 1024 * 1024) { setFormError('图片大小不能超过2MB'); return; }
    const reader = new FileReader();
    reader.onload = () => {
      setForm(prev => ({ ...prev, logo: reader.result as string }));
      setFormError('');
    };
    reader.readAsDataURL(file);
  };

  const handleSave = () => {
    if (!form.school.trim()) { setFormError('请输入学校名称'); return; }
    if (!form.grade.trim()) { setFormError('请输入年级'); return; }
    if (!form.major.trim()) { setFormError('请输入专业'); return; }
    if (editingId) {
      const existing = classes.find(c => c.id === editingId)!;
      updateClass({ ...existing, ...form });
    } else {
      addClass(form);
    }
    setEditOpen(false);
  };

  const getClassName = (c: Class) => `${c.school} ${c.grade} ${c.major}`;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl text-gray-900 flex items-center gap-2">
            <GraduationCap className="w-6 h-6 text-blue-600" />班级管理
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">管理您的班级及学生</p>
        </div>
        <button
          onClick={openAdd}
          className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />新建班级
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: '班级数', value: myClasses.length, icon: <GraduationCap className="w-5 h-5 text-blue-600" />, bg: 'bg-blue-50' },
          { label: '学生总数', value: students.filter(s => myClasses.some(c => c.id === s.classId)).length, icon: <Users className="w-5 h-5 text-green-600" />, bg: 'bg-green-50' },
          { label: '课程总数', value: courses.filter(c => myClasses.some(cl => cl.id === c.classId)).length, icon: <GraduationCap className="w-5 h-5 text-purple-600" />, bg: 'bg-purple-50' },
        ].map(s => (
          <div key={s.label} className={`${s.bg} rounded-xl p-4 border border-gray-100 flex items-center gap-3`}>
            {s.icon}
            <div>
              <p className="text-2xl font-semibold text-gray-900">{s.value}</p>
              <p className="text-sm text-gray-500">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {myClasses.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-100 border-dashed p-16 text-center">
          <GraduationCap className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 mb-4">还没有班级，点击新建班级开始</p>
          <button onClick={openAdd} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors">
            新建第一个班级
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {myClasses.map(c => {
            const studentCount = students.filter(s => s.classId === c.id).length;
            const courseCount = courses.filter(cs => cs.classId === c.id).length;
            return (
              <div key={c.id} className="bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
                <div className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center overflow-hidden">
                      {c.logo ? (
                        <img src={c.logo} alt="班级LOGO" className="w-full h-full object-cover" />
                      ) : (
                        <GraduationCap className="w-5 h-5 text-blue-600" />
                      )}
                    </div>
                    <div className="flex gap-1">
                      <button onClick={() => openEdit(c)} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-blue-600 transition-colors">
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button onClick={() => setDeleteConfirm(c.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <h3 className="text-gray-900 mb-0.5">{c.grade} {c.major}</h3>
                  <p className="text-sm text-gray-500 mb-3">{c.school}</p>
                  <div className="flex gap-4 text-sm text-gray-500">
                    <span className="flex items-center gap-1"><Users className="w-3.5 h-3.5" />{studentCount} 名学生</span>
                    <span>{courseCount} 门课程</span>
                  </div>
                </div>
                <div className="px-5 py-3 border-t border-gray-50">
                  <button
                    onClick={() => navigate('class-detail', { classId: c.id })}
                    className="w-full flex items-center justify-between text-sm text-blue-600 hover:text-blue-700 transition-colors"
                  >
                    管理学生 <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add/Edit Dialog */}
      <Dialog.Root open={editOpen} onOpenChange={setEditOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl shadow-2xl z-50 w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-5">
              <Dialog.Title className="text-lg text-gray-900">{editingId ? '编辑班级' : '新建班级'}</Dialog.Title>
              <Dialog.Close className="p-1 rounded-lg hover:bg-gray-100 text-gray-400"><X className="w-5 h-5" /></Dialog.Close>
            </div>
            <div className="space-y-4">
              {[
                { key: 'school', label: '学校', placeholder: '例：清华大学' },
                { key: 'grade', label: '年级', placeholder: '例：2022级' },
                { key: 'major', label: '专业', placeholder: '例：软件工程' },
              ].map(f => (
                <div key={f.key}>
                  <label className="block text-sm text-gray-700 mb-1">{f.label} *</label>
                  <input
                    type="text"
                    value={(form as any)[f.key]}
                    onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              ))}
              <div>
                <label className="block text-sm text-gray-700 mb-1">班级LOGO（可选）</label>
                <div className="flex items-center gap-3">
                  <div className="w-16 h-16 bg-gray-100 rounded-xl flex items-center justify-center overflow-hidden border border-gray-200">
                    {form.logo ? (
                      <img src={form.logo} alt="预览" className="w-full h-full object-cover" />
                    ) : (
                      <GraduationCap className="w-6 h-6 text-gray-400" />
                    )}
                  </div>
                  <div className="flex-1">
                    <label className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 cursor-pointer transition-colors">
                      <Upload className="w-4 h-4" />
                      {form.logo ? '更换图片' : '上传图片'}
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleLogoUpload}
                        className="hidden"
                      />
                    </label>
                    {form.logo && (
                      <button
                        onClick={() => setForm(prev => ({ ...prev, logo: undefined }))}
                        className="text-xs text-red-600 hover:underline mt-1"
                      >
                        移除图片
                      </button>
                    )}
                    <p className="text-xs text-gray-400 mt-1">支持JPG、PNG格式，不超过2MB</p>
                  </div>
                </div>
              </div>
              {formError && (
                <div className="flex items-center gap-2 text-red-600 bg-red-50 rounded-lg px-3 py-2 text-sm">
                  <AlertCircle className="w-4 h-4" />{formError}
                </div>
              )}
            </div>
            <div className="flex gap-3 mt-6">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50">取消</Dialog.Close>
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
            <Dialog.Title className="text-lg text-gray-900 mb-2">确认删除班级</Dialog.Title>
            <p className="text-sm text-gray-500 mb-5">删除班级将同时删除该班级的所有学生、课程和作业，此操作不可撤销。</p>
            <div className="flex gap-3">
              <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">取消</Dialog.Close>
              <button
                onClick={() => { if (deleteConfirm) deleteClass(deleteConfirm); setDeleteConfirm(null); }}
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
