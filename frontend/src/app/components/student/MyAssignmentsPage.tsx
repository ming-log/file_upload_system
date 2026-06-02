import { useState, useRef } from 'react';
import { FileText, Upload, CheckCircle2, Clock, XCircle, X, AlertCircle, Paperclip, Trash2, Send } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import { useApp } from '../../context';
import type { Assignment } from '../../types';

function getStatus(deadline: string, submitted: boolean) {
  const now = new Date();
  const dl = new Date(deadline);
  if (submitted) return 'submitted';
  if (dl < now) return 'overdue';
  const diff = dl.getTime() - now.getTime();
  if (diff < 3 * 24 * 60 * 60 * 1000) return 'soon';
  return 'open';
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDeadline(deadline: string) {
  return new Date(deadline).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

export function MyAssignmentsPage() {
  const { currentUser, courses, assignments, submissions, students, submitAssignment } = useApp();

  // Get the student record to find classId
  const student = students.find(s => s.id === currentUser?.id);
  const classId = student?.classId || currentUser?.classId;

  // Courses for this student's class
  const myCourses = courses.filter(c => c.classId === classId);
  // Assignments for these courses
  const myAssignments = assignments.filter(a => myCourses.some(c => c.id === a.courseId));

  const [submitOpen, setSubmitOpen] = useState(false);
  const [selectedAssignment, setSelectedAssignment] = useState<Assignment | null>(null);
  const [comment, setComment] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getMySubmission = (assignmentId: string) =>
    submissions.find(s => s.assignmentId === assignmentId && s.studentId === currentUser?.id);

  const openSubmit = (a: Assignment) => {
    setSelectedAssignment(a);
    setComment('');
    setFiles([]);
    setFileError('');
    setSuccessMsg('');
    setSubmitOpen(true);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files;
    if (!selected || !selectedAssignment) return;
    setFileError('');
    const newFiles: File[] = [];
    const errs: string[] = [];

    Array.from(selected).forEach(file => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      const allowed = selectedAssignment.allowedFileTypes;
      if (!allowed.includes('*') && !allowed.includes(ext)) {
        errs.push(`文件 "${file.name}" 类型不允许`);
        return;
      }
      const maxBytes = selectedAssignment.maxFileSizeMB * 1024 * 1024;
      if (file.size > maxBytes) {
        errs.push(`文件 "${file.name}" 超过大小限制 (${selectedAssignment.maxFileSizeMB}MB)`);
        return;
      }
      newFiles.push(file);
    });

    if (errs.length) { setFileError(errs.join('\n')); return; }
    setFiles(prev => [...prev, ...newFiles]);
    e.target.value = '';
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    if (!selectedAssignment || !currentUser) return;
    if (files.length === 0) { setFileError('请至少上传一个文件'); return; }
    setSubmitting(true);
    try {
      await submitAssignment(selectedAssignment.id, files, comment);
      setSuccessMsg('提交成功！');
    } catch (e: any) {
      setFileError(e?.message || '提交失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  // Group by course
  const courseGroups = myCourses
    .map(course => ({
      course,
      items: myAssignments.filter(a => a.courseId === course.id),
    }))
    .filter(g => g.items.length > 0);

  const statusConfig = {
    submitted: { label: '已提交', color: 'bg-green-50 text-green-700 border-green-100', icon: <CheckCircle2 className="w-4 h-4" /> },
    overdue: { label: '已截止', color: 'bg-red-50 text-red-700 border-red-100', icon: <XCircle className="w-4 h-4" /> },
    soon: { label: '即将截止', color: 'bg-amber-50 text-amber-700 border-amber-100', icon: <Clock className="w-4 h-4" /> },
    open: { label: '待提交', color: 'bg-blue-50 text-blue-700 border-blue-100', icon: <FileText className="w-4 h-4" /> },
  };

  const stats = {
    total: myAssignments.length,
    submitted: myAssignments.filter(a => !!getMySubmission(a.id)).length,
    pending: myAssignments.filter(a => !getMySubmission(a.id) && new Date(a.deadline) > new Date()).length,
    overdue: myAssignments.filter(a => !getMySubmission(a.id) && new Date(a.deadline) <= new Date()).length,
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl text-gray-900 flex items-center gap-2">
          <FileText className="w-6 h-6 text-blue-600" />我的作业
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">查看并提交您的课程作业</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {[
          { label: '全部作业', value: stats.total, color: 'text-gray-700', bg: 'bg-gray-50 border-gray-100' },
          { label: '已提交', value: stats.submitted, color: 'text-green-700', bg: 'bg-green-50 border-green-100' },
          { label: '待提交', value: stats.pending, color: 'text-blue-700', bg: 'bg-blue-50 border-blue-100' },
          { label: '已截止未交', value: stats.overdue, color: 'text-red-700', bg: 'bg-red-50 border-red-100' },
        ].map(s => (
          <div key={s.label} className={`${s.bg} border rounded-xl p-4`}>
            <p className={`text-2xl font-semibold ${s.color}`}>{s.value}</p>
            <p className="text-sm text-gray-500">{s.label}</p>
          </div>
        ))}
      </div>

      {courseGroups.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-100 border-dashed p-16 text-center">
          <FileText className="w-12 h-12 text-gray-200 mx-auto mb-3" />
          <p className="text-gray-500">暂无作业</p>
          <p className="text-sm text-gray-400 mt-1">您所在的班级还没有布置作业</p>
        </div>
      ) : (
        <div className="space-y-6">
          {courseGroups.map(({ course, items }) => (
            <div key={course.id}>
              <div className="flex items-center gap-3 mb-3">
                <h2 className="text-gray-800">{course.name}</h2>
                <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full">{course.semester}</span>
                <span className="text-sm text-gray-400">{items.length} 个作业</span>
              </div>
              <div className="grid gap-3">
                {items.map(a => {
                  const mySub = getMySubmission(a.id);
                  const status = getStatus(a.deadline, !!mySub);
                  const sc = statusConfig[status];
                  const isOverdue = status === 'overdue';
                  return (
                    <div key={a.id} className="bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <h3 className="text-gray-900 text-base">{a.title}</h3>
                            <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${sc.color}`}>
                              {sc.icon}{sc.label}
                            </span>
                          </div>
                          <p className="text-sm text-gray-500 line-clamp-2 mb-3">{a.content}</p>
                          <div className="flex flex-wrap gap-4 text-xs text-gray-400">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3.5 h-3.5" />截止：{formatDeadline(a.deadline)}
                            </span>
                            <span>
                              文件类型：{a.allowedFileTypes.join(', ')}
                            </span>
                            <span>大小限制：≤{a.maxFileSizeMB}MB</span>
                          </div>
                          {mySub && (
                            <div className="mt-3 p-2.5 bg-green-50 rounded-lg border border-green-100">
                              <p className="text-xs text-green-700 mb-1">
                                已提交于 {new Date(mySub.submittedAt).toLocaleString('zh-CN')}
                              </p>
                              <div className="flex flex-wrap gap-2">
                                {mySub.files.map((f, i) => (
                                  <span key={i} className="flex items-center gap-1 text-xs bg-white text-green-700 border border-green-200 px-2 py-0.5 rounded-full">
                                    <Paperclip className="w-3 h-3" />{f.name} ({formatFileSize(f.size)})
                                  </span>
                                ))}
                              </div>
                              {mySub.comment && <p className="text-xs text-green-600 mt-1 italic">备注：{mySub.comment}</p>}
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => openSubmit(a)}
                          disabled={isOverdue && !mySub}
                          className={`flex-shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm transition-colors ${
                            isOverdue && !mySub
                              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                              : mySub
                              ? 'border border-blue-200 text-blue-600 hover:bg-blue-50'
                              : 'bg-blue-600 text-white hover:bg-blue-700'
                          }`}
                        >
                          <Upload className="w-4 h-4" />
                          {mySub ? '重新提交' : isOverdue ? '已截止' : '提交作业'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Submit Dialog */}
      <Dialog.Root open={submitOpen} onOpenChange={o => { if (!o) { setSubmitOpen(false); setSuccessMsg(''); } }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-2xl shadow-2xl z-50 w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-5">
              <div>
                <Dialog.Title className="text-lg text-gray-900">提交作业</Dialog.Title>
                <p className="text-sm text-gray-500 mt-0.5">{selectedAssignment?.title}</p>
              </div>
              <Dialog.Close className="p-1 rounded-lg hover:bg-gray-100 text-gray-400"><X className="w-5 h-5" /></Dialog.Close>
            </div>

            {successMsg ? (
              <div className="text-center py-8">
                <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-3" />
                <p className="text-green-700 text-lg mb-2">提交成功！</p>
                <p className="text-gray-500 text-sm mb-6">您的作业已成功提交</p>
                <Dialog.Close className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors">
                  关闭
                </Dialog.Close>
              </div>
            ) : (
              <>
                {selectedAssignment && (
                  <div className="bg-blue-50 rounded-lg p-3 mb-4 text-sm text-blue-700 border border-blue-100">
                    <p className="mb-1">{selectedAssignment.content}</p>
                    <div className="flex flex-wrap gap-3 text-xs text-blue-600 mt-2">
                      <span>允许类型：{selectedAssignment.allowedFileTypes.join(', ')}</span>
                      <span>大小限制：≤{selectedAssignment.maxFileSizeMB}MB</span>
                      <span>截止：{formatDeadline(selectedAssignment.deadline)}</span>
                    </div>
                  </div>
                )}

                {/* File Upload */}
                <div className="mb-4">
                  <label className="block text-sm text-gray-700 mb-2">上传文件 *</label>
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
                  >
                    <Upload className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    <p className="text-sm text-gray-500">点击选择文件</p>
                    <p className="text-xs text-gray-400 mt-1">
                      {selectedAssignment?.allowedFileTypes.join(', ')} · 最大 {selectedAssignment?.maxFileSizeMB}MB
                    </p>
                  </div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    className="hidden"
                    onChange={handleFileSelect}
                    accept={selectedAssignment?.allowedFileTypes.includes('*') ? '*' : selectedAssignment?.allowedFileTypes.join(',')}
                  />
                  {fileError && (
                    <div className="mt-2 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 whitespace-pre-line">
                      <AlertCircle className="w-4 h-4 inline mr-1" />{fileError}
                    </div>
                  )}
                </div>

                {/* File List */}
                {files.length > 0 && (
                  <div className="mb-4 space-y-2">
                    {files.map((f, i) => (
                      <div key={i} className="flex items-center gap-3 p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                        <Paperclip className="w-4 h-4 text-blue-500 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-gray-700 truncate">{f.name}</p>
                          <p className="text-xs text-gray-400">{formatFileSize(f.size)}</p>
                        </div>
                        <button onClick={() => removeFile(i)} className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Comment */}
                <div className="mb-5">
                  <label className="block text-sm text-gray-700 mb-1">备注说明（可选）</label>
                  <textarea
                    value={comment}
                    onChange={e => setComment(e.target.value)}
                    placeholder="可以填写作业说明或补充内容..."
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  />
                </div>

                <div className="flex gap-3">
                  <Dialog.Close className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50">取消</Dialog.Close>
                  <button
                    onClick={handleSubmit}
                    disabled={submitting || files.length === 0}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {submitting ? (
                      <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />提交中...</>
                    ) : (
                      <><Send className="w-4 h-4" />确认提交</>
                    )}
                  </button>
                </div>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
