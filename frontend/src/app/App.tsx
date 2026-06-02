import { AppProvider, useApp } from './context';
import { LoginPage } from './components/LoginPage';
import { Layout } from './components/Layout';
import { UsersPage } from './components/admin/UsersPage';
import { ClassesPage } from './components/teacher/ClassesPage';
import { ClassDetailPage } from './components/teacher/ClassDetailPage';
import { CoursesPage } from './components/teacher/CoursesPage';
import { AssignmentsPage } from './components/teacher/AssignmentsPage';
import { MyAssignmentsPage } from './components/student/MyAssignmentsPage';

function AppContent() {
  const { currentUser, currentPage } = useApp();

  if (!currentUser) return <LoginPage />;

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
