import { useState, useEffect, useCallback } from 'react';
import { User, AlertCircle, ShieldCheck, RefreshCw, GraduationCap, School } from 'lucide-react';
import { useApp } from '../context';
import { authApi, ApiError } from '../api';
import { PasswordInput } from './ui/PasswordInput';

type LoginMode = 'student' | 'teacher';

export function LoginPage() {
  const { loginStudent, loginTeacher } = useApp();
  const [mode, setMode] = useState<LoginMode>('student');

  // 共用
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // 学生
  const [schools, setSchools] = useState<string[]>([]);
  const [school, setSchool] = useState('');
  const [studentId, setStudentId] = useState('');
  const [captcha, setCaptcha] = useState('');
  const [captchaId, setCaptchaId] = useState('');
  const [captchaImage, setCaptchaImage] = useState('');
  const [captchaLoading, setCaptchaLoading] = useState(false);

  // 教师
  const [account, setAccount] = useState('');

  const refreshCaptcha = useCallback(async () => {
    setCaptchaLoading(true);
    setCaptcha('');
    try {
      const res = await authApi.captcha();
      setCaptchaId(res.captchaId);
      setCaptchaImage(res.image);
    } catch {
      setCaptchaImage('');
    } finally {
      setCaptchaLoading(false);
    }
  }, []);

  useEffect(() => {
    authApi.schools().then(setSchools).catch(() => setSchools([]));
    refreshCaptcha();
  }, [refreshCaptcha]);

  const switchMode = (m: LoginMode) => {
    setMode(m);
    setError('');
    setPassword('');
    if (m === 'student') refreshCaptcha();
  };

  const handleStudentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!school) { setError('请选择学校'); return; }
    if (!studentId.trim()) { setError('请输入学号'); return; }
    if (!password.trim()) { setError('请输入密码'); return; }
    if (!captcha.trim()) { setError('请输入验证码'); return; }
    setLoading(true);
    setError('');
    try {
      await loginStudent(school, studentId.trim(), password.trim(), captchaId, captcha.trim());
    } catch (err) {
      handleLoginError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleTeacherSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!account.trim()) { setError('请输入账号'); return; }
    if (!password.trim()) { setError('请输入密码'); return; }
    setLoading(true);
    setError('');
    try {
      await loginTeacher(account.trim(), password.trim());
    } catch (err) {
      handleLoginError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleLoginError = (err: unknown) => {
    if (err instanceof ApiError) {
      if (err.code === 'INVALID_CAPTCHA') {
        setError('验证码错误或已过期，请重试');
        refreshCaptcha();
      } else if (err.code === 'INVALID_CREDENTIALS' || err.status === 401) {
        setError(mode === 'student' ? '学校、学号或密码错误，请重试' : '账号或密码错误，请重试');
        if (mode === 'student') refreshCaptcha();
      } else if (err.code === 'PASSWORD_RESET_REQUIRED') {
        setError('该账号需要重置密码，请联系老师');
        if (mode === 'student') refreshCaptcha();
      } else {
        setError(err.message || '登录失败，请重试');
        if (mode === 'student') refreshCaptcha();
      }
    } else {
      setError('登录失败，请重试');
      if (mode === 'student') refreshCaptcha();
    }
  };

  const inputClass = 'w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-gray-900';
  const pwInputClass = 'w-full pl-10 pr-10 py-2.5 border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-gray-900';

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-white rounded-2xl shadow-lg mb-4 overflow-hidden">
              <img src="/logo.png" alt="LOGO" className="w-full h-full object-contain" />
            </div>
            <h1 className="text-3xl text-gray-900 mb-1">作业提交系统</h1>
            <p className="text-gray-500 text-sm">Assignment Upload & Management System</p>
          </div>

          {/* Card */}
          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
            {/* Tabs */}
            <div className="flex gap-1 p-1 bg-gray-100 rounded-lg mb-6">
              <button
                onClick={() => switchMode('student')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-sm transition-all ${
                  mode === 'student' ? 'bg-white text-blue-700 shadow-sm font-medium' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <GraduationCap className="w-4 h-4" />学生登录
              </button>
              <button
                onClick={() => switchMode('teacher')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-sm transition-all ${
                  mode === 'teacher' ? 'bg-white text-blue-700 shadow-sm font-medium' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <User className="w-4 h-4" />教师登录
              </button>
            </div>

            {mode === 'student' ? (
              <form onSubmit={handleStudentSubmit} className="space-y-4 min-h-[372px]">
                <div>
                  <label className="block text-sm text-gray-700 mb-1.5">学校</label>
                  <div className="relative">
                    <School className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 z-10" />
                    <select
                      value={school}
                      onChange={e => setSchool(e.target.value)}
                      className={`${inputClass} appearance-none`}
                    >
                      <option value="">请选择学校</option>
                      {schools.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  {schools.length === 0 && (
                    <p className="text-xs text-amber-600 mt-1">暂无可选学校，请联系老师创建班级</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm text-gray-700 mb-1.5">学号</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input type="text" value={studentId} onChange={e => setStudentId(e.target.value)} placeholder="请输入学号" className={inputClass} />
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-gray-700 mb-1.5">密码</label>
                  <PasswordInput value={password} onChange={setPassword} placeholder="请输入密码" className={pwInputClass} />
                </div>
                {/* 验证码 */}
                <div>
                  <label className="block text-sm text-gray-700 mb-1.5">验证码</label>
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input type="text" value={captcha} onChange={e => setCaptcha(e.target.value)} placeholder="请输入图中字符" autoComplete="off" maxLength={8}
                        className={`${inputClass} uppercase tracking-widest`} />
                    </div>
                    <button type="button" onClick={refreshCaptcha} title="点击刷新验证码"
                      className="relative h-[46px] w-[120px] flex-shrink-0 rounded-lg border border-gray-200 bg-gray-50 overflow-hidden flex items-center justify-center hover:border-blue-400 transition-colors">
                      {captchaLoading || !captchaImage ? (
                        <RefreshCw className={`w-5 h-5 text-gray-400 ${captchaLoading ? 'animate-spin' : ''}`} />
                      ) : (
                        <img src={captchaImage} alt="验证码" className="h-full w-full object-cover" />
                      )}
                    </button>
                  </div>
                </div>
                {error && (
                  <div className="flex items-center gap-2 text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2 text-sm">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
                  </div>
                )}
                <button type="submit" disabled={loading}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-2.5 rounded-lg transition-colors mt-2 flex items-center justify-center gap-2">
                  {loading ? (<><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />登录中...</>) : '登 录'}
                </button>
              </form>
            ) : (
              <form onSubmit={handleTeacherSubmit} className="space-y-4 min-h-[372px]">
                <div>
                  <label className="block text-sm text-gray-700 mb-1.5">账号</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input type="text" value={account} onChange={e => setAccount(e.target.value)} placeholder="请输入教师/管理员账号" className={inputClass} />
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-gray-700 mb-1.5">密码</label>
                  <PasswordInput value={password} onChange={setPassword} placeholder="请输入密码" className={pwInputClass} />
                </div>
                {error && (
                  <div className="flex items-center gap-2 text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2 text-sm">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
                  </div>
                )}
                <button type="submit" disabled={loading}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-2.5 rounded-lg transition-colors mt-2 flex items-center justify-center gap-2">
                  {loading ? (<><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />登录中...</>) : '登 录'}
                </button>
              </form>
            )}
          </div>

          <p className="text-center text-xs text-gray-400 mt-6">
            {mode === 'student' ? '学生使用「学校 + 学号 + 密码」登录，首次登录需完成邮箱验证' : '教师与管理员使用账号密码登录'}
          </p>
          <p className="text-center text-xs text-gray-400 mt-2">
            © {new Date().getFullYear()} 作业提交系统 · Designed &amp; Developed by minglog
          </p>
        </div>
    </div>
  );
}
