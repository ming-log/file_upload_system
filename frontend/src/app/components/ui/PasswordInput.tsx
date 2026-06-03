import { useState } from 'react';
import { Lock, Eye, EyeOff } from 'lucide-react';

interface PasswordInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  /** 是否显示左侧锁图标（默认 true） */
  withIcon?: boolean;
  autoComplete?: string;
  disabled?: boolean;
}

// 统一的密码输入框：左侧锁图标（可选），右侧「显示/隐藏明文」切换按钮。
export function PasswordInput({
  value,
  onChange,
  placeholder = '请输入密码',
  className = '',
  withIcon = true,
  autoComplete = 'off',
  disabled = false,
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const base = withIcon
    ? 'w-full pl-10 pr-10 py-2.5 border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-gray-900'
    : 'w-full px-3 pr-10 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500';
  return (
    <div className="relative">
      {withIcon && (
        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
      )}
      <input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        disabled={disabled}
        className={className || base}
      />
      <button
        type="button"
        onClick={() => setVisible(v => !v)}
        tabIndex={-1}
        title={visible ? '隐藏密码' : '显示密码'}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 transition-colors"
      >
        {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  );
}
