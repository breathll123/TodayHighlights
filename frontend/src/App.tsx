import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from "react-router-dom";
import { MotionConfig, motion } from "framer-motion";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { PublicNavbar } from "@/components/layout/PublicNavbar";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { SummaryPage } from "./pages/SummaryPage";
import { TopicPage } from "./pages/TopicPage";
import { LoginPage } from "./pages/LoginPage";
import { AdminSourcesPage } from "./pages/AdminSourcesPage";
import { AdminJobsPage } from "./pages/AdminJobsPage";
import { AdminSettingsPage } from "./pages/AdminSettingsPage";
import { AdminLayoutPage } from "./pages/AdminLayoutPage";
import { AdminTopicsPage } from "./pages/AdminTopicsPage";
import { AdminAIOpsPage } from "./pages/AdminAIOpsPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { AdminPromptTemplatesPage } from "./pages/AdminPromptTemplatesPage";

const queryClient = new QueryClient();

function PublicLayout() {
  return (
    <div className="min-h-screen bg-background">
      <PublicNavbar />
      <main id="main-content" className="mx-auto max-w-[1680px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
}

function AdminLayout() {
  const location = useLocation();
  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-screen bg-background">
        <div className="flex">
          <AdminSidebar />
          <main id="main-content" className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            >
              <Outlet />
            </motion.div>
          </main>
        </div>
      </div>
    </MotionConfig>
  );
}

function ProtectedRoute() {
  const { isAuthenticated, isAdmin } = useAuth();
  const location = useLocation();
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!isAdmin) return <Navigate to="/" replace />;
  return <AdminLayout />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            {/* Public */}
            <Route element={<PublicLayout />}>
              <Route path="/" element={<SummaryPage />} />
              <Route path="/topics/:slug" element={<TopicPage />} />
            </Route>

            {/* Login */}
            <Route path="/login" element={<LoginPage />} />

            {/* Admin (protected) */}
            <Route element={<ProtectedRoute />}>
              <Route path="/admin/sources" element={<AdminSourcesPage />} />
              <Route path="/admin/jobs" element={<AdminJobsPage />} />
              <Route path="/admin/settings" element={<AdminSettingsPage />} />
              <Route path="/admin/layout" element={<AdminLayoutPage />} />
              <Route path="/admin/topics" element={<AdminTopicsPage />} />
              <Route path="/admin/users" element={<AdminUsersPage />} />
              <Route path="/admin/ai-ops" element={<AdminAIOpsPage />} />
              <Route path="/admin/ai-prompts" element={<AdminPromptTemplatesPage />} />
              <Route path="/admin" element={<Navigate to="/admin/sources" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
