import { ReactNode } from 'react';
import {
  Users, LayoutDashboard, GraduationCap, BookCopy,
  FileText, ClipboardList, LogOut, ChevronRight, Menu, X
} from 'lucide-react';
import { useState } from 'react';
import { useApp } from '../context';
import type { Page } from '../types';

interface NavItem {
  label: string;
  page: Page;
  icon: ReactNode;
}

const adminNav: NavItem[] = [
  { label: '用户管理', page: 'users', icon: <Users className="w-4 h-4" /> },
  { label: '班级管理', page: 'classes', icon: <GraduationCap className="w-4 h-4" /> },
  { label: '课程管理', page: 'courses', icon: <BookCopy className="w-4 h-4" /> },
  { label: '作业管理', page: 'assignments', icon: <ClipboardList className="w-4 h-4" /> },
];

const teacherNav: NavItem[] = [
  { label: '班级管理', page: 'classes', icon: <GraduationCap className="w-4 h-4" /> },
  { label: '课程管理', page: 'courses', icon: <BookCopy className="w-4 h-4" /> },
  { label: '作业管理', page: 'assignments', icon: <ClipboardList className="w-4 h-4" /> },
];

const studentNav: NavItem[] = [
  { label: '我的作业', page: 'my-assignments', icon: <FileText className="w-4 h-4" /> },
];

export function Layout({ children }: { children: ReactNode }) {
  const { currentUser, currentPage, navigate, logout } = useApp();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (!currentUser) return null;

  const navItems =
    currentUser.role === 'admin' ? adminNav :
    currentUser.role === 'teacher' ? teacherNav :
    studentNav;

  const roleLabel =
    currentUser.role === 'admin' ? '管理员' :
    currentUser.role === 'teacher' ? '教师' : '学生';

  const roleColor =
    currentUser.role === 'admin' ? 'bg-purple-100 text-purple-700' :
    currentUser.role === 'teacher' ? 'bg-blue-100 text-blue-700' :
    'bg-green-100 text-green-700';

  const Sidebar = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center flex-shrink-0 overflow-hidden border border-gray-100">
            <img src="/logo.png" alt="LOGO" className="w-full h-full object-contain" />
          </div>
          <div>
            <p className="text-sm text-gray-900 leading-tight">作业提交系统</p>
            <p className="text-xs text-gray-400">Assignment System</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map(item => {
          const active = currentPage === item.page ||
            (item.page === 'classes' && currentPage === 'class-detail');
          return (
            <button
              key={item.page}
              onClick={() => { navigate(item.page); setSidebarOpen(false); }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                active
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              {item.icon}
              {item.label}
              {active && <ChevronRight className="w-3.5 h-3.5 ml-auto" />}
            </button>
          );
        })}
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-gray-100">
        <button
          onClick={() => { navigate('profile'); setSidebarOpen(false); }}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg mb-2 transition-colors text-left ${
            currentPage === 'profile' ? 'bg-blue-50' : 'bg-gray-50 hover:bg-gray-100'
          }`}
          title="个人中心"
        >
          <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white text-xs flex-shrink-0 overflow-hidden">
            {currentUser.avatar ? (
              <img src={currentUser.avatar} alt="头像" className="w-full h-full object-cover" />
            ) : (
              currentUser.name.charAt(0)
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-900 truncate">{currentUser.name}</p>
            <span className={`text-xs px-1.5 py-0.5 rounded ${roleColor}`}>{roleLabel}</span>
          </div>
        </button>
        <button
          onClick={logout}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          退出登录
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-60 flex-col bg-white border-r border-gray-100 flex-shrink-0">
        <Sidebar />
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          <div className="fixed inset-0 bg-black/40" onClick={() => setSidebarOpen(false)} />
          <aside className="relative z-50 w-64 bg-white flex flex-col shadow-xl">
            <button
              onClick={() => setSidebarOpen(false)}
              className="absolute top-4 right-4 p-1 rounded-lg hover:bg-gray-100"
            >
              <X className="w-5 h-5" />
            </button>
            <Sidebar />
          </aside>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-100">
          <button onClick={() => setSidebarOpen(true)} className="p-1.5 rounded-lg hover:bg-gray-100">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="LOGO" className="w-6 h-6 object-contain" />
            <span className="text-gray-900 text-sm">作业提交系统</span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          {children}
          <footer className="py-4 text-center text-xs text-gray-400 border-t border-gray-100 mt-2">
            © {new Date().getFullYear()} 作业提交系统 · Designed &amp; Developed by minglog
          </footer>
        </main>
      </div>
    </div>
  );
}
