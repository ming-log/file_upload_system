import { AppProvider, useApp } from './context';
import { LoginPage } from './components/LoginPage';
import { Layout } from './components/Layout';
import { UsersPage } from './components/admin/UsersPage';
import { ClassesPage } from './components/teacher/ClassesPage';
import { ClassDetailPage } from './components/teacher/ClassDetailPage';
import { CoursesPage } from './components/teacher/CoursesPage';
import { AssignmentsPage } from './components/teacher/AssignmentsPage';
import { MyAssignmentsPage } from './components/student/MyAssignmentsPage';
import { EmailVerificationGate } from './components/student/EmailVerificationGate';

function AppContent() {
  const { currentUser, currentPage } = useApp();

  if (!currentUser) return <LoginPage />;

  // 学生首次登录未完成邮箱验证：强制进入验证 + 改密流程。
  if (currentUser.role === 'student' && currentUser.emailVerified === false) {
    return <EmailVerificationGate />;
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'users': return <UsersPage />;
      case 'classes': return <ClassesPage />;
      case 'class-detail': return <ClassDetailPage />;
      case 'courses': return <CoursesPage />;
      case 'assignments': return <AssignmentsPage />;
      case 'my-assignments': return <MyAssignmentsPage />;
      default:
        if (currentUser.role === 'admin') return <UsersPage />;
        if (currentUser.role === 'teacher') return <ClassesPage />;
        return <MyAssignmentsPage />;
    }
  };

  return (
    <Layout>
      {/* MARKER-MAKE-KIT-INVOKED */}
      {renderPage()}
    </Layout>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}
