import { useState } from 'react';
import { BookOpen, Lock, User, AlertCircle } from 'lucide-react';
import { useApp } from '../context';

export function LoginPage() {
  const { login } = useApp();
  const [account, setAccount] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!account.trim()) { setError('请输入账号'); return; }
    if (!password.trim()) { setError('请输入密码'); return; }
    setLoading(true);
    setError('');
    const ok = await login(account.trim(), password.trim());
    if (!ok) setError('账号或密码错误，请重试');
    setLoading(false);
  };

  const demoAccounts = [
    { role: '管理员', account: 'admin', password: 'admin123', color: 'bg-purple-100 text-purple-700 border-purple-200' },
    { role: '教师', account: 'teacher001', password: 'teacher123', color: 'bg-blue-100 text-blue-700 border-blue-200' },
    { role: '学生', account: '2022001', password: 'minglog666', color: 'bg-green-100 text-green-700 border-green-200' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl shadow-lg mb-4">
            <BookOpen className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl text-gray-900 mb-1">作业提交系统</h1>
          <p className="text-gray-500 text-sm">Assignment Upload & Management System</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
          <h2 className="text-xl text-gray-800 mb-6">登录账号</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-700 mb-1.5">账号</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={account}
                  onChange={e => setAccount(e.target.value)}
                  placeholder="请输入账号或学号"
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-gray-900"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm text-gray-700 mb-1.5">密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-gray-900"
                />
              </div>
            </div>
            {error && (
              <div className="flex items-center gap-2 text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-2.5 rounded-lg transition-colors mt-2 flex items-center justify-center gap-2"
            >
              {loading ? (
                <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />登录中...</>
              ) : '登 录'}
            </button>
          </form>
        </div>

        {/* Demo accounts */}
        <div className="mt-6 bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <p className="text-xs text-gray-500 mb-3">演示账号（点击快速填入）</p>
          <div className="space-y-2">
            {demoAccounts.map(d => (
              <button
                key={d.account}
                onClick={() => { setAccount(d.account); setPassword(d.password); setError(''); }}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border text-xs ${d.color} hover:opacity-80 transition-opacity text-left`}
              >
                <span className="font-medium">{d.role}</span>
                <span className="font-mono">{d.account} / {d.password}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
