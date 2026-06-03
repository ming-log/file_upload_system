import { useState } from 'react';
import { MailCheck, AlertCircle, Lock, ShieldCheck, LogOut, Send } from 'lucide-react';
import { useApp } from '../../context';
import { authApi, ApiError } from '../../api';

// 学生首次登录后的强制邮箱验证 + 改密界面。
// 流程：发送验证码到邮箱 -> 输入验证码 + 新密码 -> 校验通过后进入应用。
export function EmailVerificationGate() {
  const { currentUser, onEmailVerified, logout } = useApp();
  const [codeSent, setCodeSent] = useState(false);
  const [maskedEmail, setMaskedEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [sending, setSending] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  const startCooldown = () => {
    setCooldown(60);
    const timer = setInterval(() => {
      setCooldown(c => {
        if (c <= 1) { clearInterval(timer); return 0; }
        return c - 1;
      });
    }, 1000);
  };

  const handleSendCode = async () => {
    setError('');
    setInfo('');
    setSending(true);
    try {
      const res = await authApi.sendEmailCode();
      setCodeSent(true);
      setMaskedEmail(res.email);
      setInfo(`验证码已发送至 ${res.email}，10 分钟内有效`);
      startCooldown();
    } catch (e) {
      setError(e instanceof ApiError ? (e.message || '验证码发送失败') : '验证码发送失败，请稍后重试');
    } finally {
      setSending(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!code.trim()) { setError('请输入邮箱验证码'); return; }
    if (newPassword.length < 6) { setError('新密码至少 6 位'); return; }
    if (newPassword !== confirmPassword) { setError('两次输入的密码不一致'); return; }
    setSubmitting(true);
    try {
      const res = await authApi.verifyEmail(code.trim(), newPassword);
      await onEmailVerified(res.user);
    } catch (err) {
      setError(err instanceof ApiError ? (err.message || '验证失败') : '验证失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass = 'w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-gray-900';

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl shadow-lg mb-4">
            <MailCheck className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl text-gray-900 mb-1">邮箱验证</h1>
          <p className="text-gray-500 text-sm">
            首次登录需验证邮箱并设置新密码
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
          <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3 mb-5 text-sm text-blue-700">
            您好，{currentUser?.name}！为保障账号安全，请先验证邮箱并修改初始密码。
            {currentUser?.email && <span className="block mt-1 text-blue-600">绑定邮箱：{currentUser.email}</span>}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* 验证码 + 发送 */}
            <div>
              <label className="block text-sm text-gray-700 mb-1.5">邮箱验证码</label>
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input type="text" value={code} onChange={e => setCode(e.target.value)} placeholder="请输入 6 位验证码"
                    autoComplete="off" maxLength={6} className={`${inputClass} tracking-widest`} />
                </div>
                <button type="button" onClick={handleSendCode} disabled={sending || cooldown > 0}
                  className="h-[46px] px-3 flex-shrink-0 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5 whitespace-nowrap">
                  {sending ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                  {cooldown > 0 ? `${cooldown}s` : (codeSent ? '重新发送' : '发送验证码')}
                </button>
              </div>
            </div>

            {/* 新密码 */}
            <div>
              <label className="block text-sm text-gray-700 mb-1.5">新密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="至少 6 位" className={inputClass} />
              </div>
            </div>
            <div>
              <label className="block text-sm text-gray-700 mb-1.5">确认新密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} placeholder="再次输入新密码" className={inputClass} />
              </div>
            </div>

            {info && (
              <div className="flex items-center gap-2 text-green-700 bg-green-50 border border-green-100 rounded-lg px-3 py-2 text-sm">
                <MailCheck className="w-4 h-4 flex-shrink-0" />{info}
              </div>
            )}
            {error && (
              <div className="flex items-center gap-2 text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
              </div>
            )}

            <button type="submit" disabled={submitting}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2">
              {submitting ? (<><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />验证中...</>) : '完成验证并进入'}
            </button>
          </form>
        </div>

        <button onClick={logout} className="w-full mt-4 flex items-center justify-center gap-1.5 text-sm text-gray-500 hover:text-red-600 transition-colors">
          <LogOut className="w-4 h-4" />退出登录
        </button>
      </div>
    </div>
  );
}
