import { useState, useEffect, useCallback } from 'react';
import {
  UserCircle, Mail, Camera, Save, AlertCircle, Check, ShieldCheck, Send, KeyRound,
} from 'lucide-react';
import { useApp } from '../context';
import { meApi, authApi, ApiError, type MeProfile } from '../api';
import { PasswordInput } from './ui/PasswordInput';

export function ProfilePage() {
  const { currentUser, setCurrentUser } = useApp();

  const [profile, setProfile] = useState<MeProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // 基本信息表单
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [avatar, setAvatar] = useState('');
  const [savingInfo, setSavingInfo] = useState(false);
  const [infoError, setInfoError] = useState('');
  const [infoSuccess, setInfoSuccess] = useState('');

  // 改密（邮箱验证）
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [sending, setSending] = useState(false);
  const [changing, setChanging] = useState(false);
  const [pwError, setPwError] = useState('');
  const [pwSuccess, setPwSuccess] = useState('');
  const [pwInfo, setPwInfo] = useState('');
  const [cooldown, setCooldown] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = await meApi.get();
      setProfile(p);
      setName(p.name);
      setEmail(p.email);
      setAvatar(p.avatar || '');
    } catch (e) {
      setInfoError(e instanceof ApiError ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const isStudent = profile?.role === 'student';

  const handleAvatarSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setInfoError('');
    if (!file.type.startsWith('image/')) { setInfoError('请选择图片文件'); return; }
    if (file.size > 1024 * 1024) { setInfoError('头像不能超过 1MB'); return; }
    const reader = new FileReader();
    reader.onload = () => setAvatar(reader.result as string);
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  const handleSaveInfo = async () => {
    setInfoError('');
    setInfoSuccess('');
    if (!email.trim()) { setInfoError('邮箱不能为空'); return; }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) { setInfoError('邮箱格式不正确'); return; }
    setSavingInfo(true);
    try {
      const updated = await meApi.update({
        name: isStudent ? undefined : name.trim(),
        email: email.trim(),
        avatar,
      });
      setProfile(updated);
      setInfoSuccess('基本信息已保存');
      // 同步会话用户（头像、姓名、邮箱、验证状态）。
      if (currentUser) {
        setCurrentUser({
          ...currentUser,
          name: updated.name,
          email: updated.email,
          avatar: updated.avatar,
          emailVerified: updated.emailVerified,
        });
      }
    } catch (e) {
      setInfoError(e instanceof ApiError ? (e.message || '保存失败') : '保存失败，请重试');
    } finally {
      setSavingInfo(false);
    }
  };

  const startCooldown = () => {
    setCooldown(60);
    const timer = setInterval(() => {
      setCooldown(c => { if (c <= 1) { clearInterval(timer); return 0; } return c - 1; });
    }, 1000);
  };

  const handleSendCode = async () => {
    setPwError('');
    setPwInfo('');
    setSending(true);
    try {
      const res = await authApi.sendEmailCode();
      setPwInfo(`验证码已发送至 ${res.email}，10 分钟内有效`);
      startCooldown();
    } catch (e) {
      setPwError(e instanceof ApiError ? (e.message || '验证码发送失败') : '验证码发送失败，请稍后重试');
    } finally {
      setSending(false);
    }
  };

  const handleChangePassword = async () => {
    setPwError('');
    setPwSuccess('');
    if (!code.trim()) { setPwError('请输入邮箱验证码'); return; }
    if (newPassword.length < 6) { setPwError('新密码至少 6 位'); return; }
    if (newPassword !== confirmPassword) { setPwError('两次输入的密码不一致'); return; }
    setChanging(true);
    try {
      const res = await authApi.verifyEmail(code.trim(), newPassword);
      setPwSuccess('密码修改成功');
      setCode(''); setNewPassword(''); setConfirmPassword('');
      if (currentUser) setCurrentUser({ ...currentUser, emailVerified: res.user.emailVerified });
    } catch (e) {
      setPwError(e instanceof ApiError ? (e.message || '修改失败') : '修改失败，请重试');
    } finally {
      setChanging(false);
    }
  };

  const inputClass = 'w-full px-3 py-2.5 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900';
  const readonlyClass = 'w-full px-3 py-2.5 border border-gray-100 rounded-lg bg-gray-50 text-gray-500 cursor-not-allowed';

  if (loading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="flex items-center justify-center py-20 text-gray-400">
          <div className="w-6 h-6 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl text-gray-900 flex items-center gap-2">
          <UserCircle className="w-6 h-6 text-blue-600" />个人中心
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">管理您的头像、基本信息与登录密码</p>
      </div>

      {/* 基本信息 */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mb-6">
        <h2 className="text-base text-gray-800 mb-5">基本信息</h2>

        {/* 头像 */}
        <div className="flex items-center gap-5 mb-6">
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-blue-100 overflow-hidden flex items-center justify-center">
              {avatar ? (
                <img src={avatar} alt="头像" className="w-full h-full object-cover" />
              ) : (
                <span className="text-2xl text-blue-600">{(profile?.name || profile?.account || '?').charAt(0)}</span>
              )}
            </div>
            <label className="absolute -bottom-1 -right-1 w-7 h-7 bg-blue-600 rounded-full flex items-center justify-center cursor-pointer hover:bg-blue-700 transition-colors shadow">
              <Camera className="w-3.5 h-3.5 text-white" />
              <input type="file" accept="image/*" className="hidden" onChange={handleAvatarSelect} />
            </label>
          </div>
          <div className="text-sm text-gray-500">
            <p>点击相机图标更换头像</p>
            <p className="text-xs text-gray-400 mt-0.5">支持 JPG/PNG，不超过 1MB</p>
            {avatar && (
              <button onClick={() => setAvatar('')} className="text-xs text-red-600 hover:underline mt-1">移除头像</button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 账号（只读） */}
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">{isStudent ? '学号' : '账号'}</label>
            <input type="text" value={isStudent ? (profile?.studentId || '') : (profile?.account || '')} readOnly className={readonlyClass} />
          </div>

          {/* 姓名：学生只读，教师/管理员可改 */}
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">姓名</label>
            {isStudent ? (
              <input type="text" value={profile?.name || ''} readOnly className={readonlyClass} />
            ) : (
              <input type="text" value={name} onChange={e => setName(e.target.value)} className={inputClass} placeholder="请输入姓名" />
            )}
          </div>

          {/* 学生：学校 + 班级（只读） */}
          {isStudent && (
            <>
              <div>
                <label className="block text-sm text-gray-700 mb-1.5">学校</label>
                <input type="text" value={profile?.school || ''} readOnly className={readonlyClass} />
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1.5">班级</label>
                <input type="text" value={profile?.className || ''} readOnly className={readonlyClass} />
              </div>
            </>
          )}

          {/* 邮箱：可改 */}
          <div className="md:col-span-2">
            <label className="block text-sm text-gray-700 mb-1.5 flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-gray-400" />电子邮箱
              {profile?.emailVerified ? (
                <span className="text-xs text-green-600 bg-green-50 px-1.5 py-0.5 rounded-full flex items-center gap-0.5"><Check className="w-3 h-3" />已验证</span>
              ) : (
                <span className="text-xs text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full">未验证</span>
              )}
            </label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} className={inputClass} placeholder="请输入电子邮箱" />
            <p className="text-xs text-gray-400 mt-1">修改邮箱后需重新通过邮箱验证</p>
          </div>
        </div>

        {infoError && (
          <div className="mt-4 flex items-center gap-2 text-red-600 bg-red-50 rounded-lg px-3 py-2 text-sm">
            <AlertCircle className="w-4 h-4" />{infoError}
          </div>
        )}
        {infoSuccess && (
          <div className="mt-4 flex items-center gap-2 text-green-700 bg-green-50 rounded-lg px-3 py-2 text-sm">
            <Check className="w-4 h-4" />{infoSuccess}
          </div>
        )}

        <div className="mt-5">
          <button onClick={handleSaveInfo} disabled={savingInfo}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-60 transition-colors">
            {savingInfo ? (<><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />保存中...</>) : (<><Save className="w-4 h-4" />保存基本信息</>)}
          </button>
        </div>
      </div>

      {/* 修改密码（邮箱验证） */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-base text-gray-800 mb-1 flex items-center gap-2"><KeyRound className="w-4 h-4 text-blue-600" />修改密码</h2>
        <p className="text-sm text-gray-500 mb-5">为保障安全，修改密码需通过当前邮箱验证</p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">邮箱验证码</label>
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input type="text" value={code} onChange={e => setCode(e.target.value)} placeholder="请输入 6 位验证码" maxLength={6} autoComplete="off"
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 tracking-widest" />
              </div>
              <button type="button" onClick={handleSendCode} disabled={sending || cooldown > 0}
                className="h-[46px] px-3 flex-shrink-0 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5 whitespace-nowrap">
                {sending ? (<div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />) : (<Send className="w-4 h-4" />)}
                {cooldown > 0 ? `${cooldown}s` : '发送验证码'}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">新密码</label>
            <PasswordInput value={newPassword} onChange={setNewPassword} placeholder="至少 6 位"
              className="w-full pl-10 pr-10 py-2.5 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">确认新密码</label>
            <PasswordInput value={confirmPassword} onChange={setConfirmPassword} placeholder="再次输入新密码"
              className="w-full pl-10 pr-10 py-2.5 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>

          {pwInfo && (
            <div className="flex items-center gap-2 text-blue-700 bg-blue-50 rounded-lg px-3 py-2 text-sm">
              <Mail className="w-4 h-4" />{pwInfo}
            </div>
          )}
          {pwError && (
            <div className="flex items-center gap-2 text-red-600 bg-red-50 rounded-lg px-3 py-2 text-sm">
              <AlertCircle className="w-4 h-4" />{pwError}
            </div>
          )}
          {pwSuccess && (
            <div className="flex items-center gap-2 text-green-700 bg-green-50 rounded-lg px-3 py-2 text-sm">
              <Check className="w-4 h-4" />{pwSuccess}
            </div>
          )}

          <button onClick={handleChangePassword} disabled={changing}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-60 transition-colors">
            {changing ? (<><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />提交中...</>) : (<><KeyRound className="w-4 h-4" />确认修改密码</>)}
          </button>
        </div>
      </div>
    </div>
  );
}
