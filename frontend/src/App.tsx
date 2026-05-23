import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { PublicNavbar } from "@/components/layout/PublicNavbar";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { SummaryPage } from "./pages/SummaryPage";
import { StockTopicPage } from "./pages/StockTopicPage";
import { LoginPage } from "./pages/LoginPage";
import { AdminSourcesPage } from "./pages/AdminSourcesPage";
import { AdminJobsPage } from "./pages/AdminJobsPage";
import { AdminHighlightsPage } from "./pages/AdminHighlightsPage";
import { AdminSettingsPage } from "./pages/AdminSettingsPage";
import { AdminLayoutPage } from "./pages/AdminLayoutPage";
import { AdminTopicsPage } from "./pages/AdminTopicsPage";

const queryClient = new QueryClient();

function PublicLayout() {
  return (
    <div className="min-h-screen bg-background">
      <PublicNavbar />
      <main className="px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}

function AdminLayout() {
  return (
    <div className="min-h-screen bg-background">
      <div className="flex">
        <AdminSidebar />
        <main className="flex-1 px-8 py-8 max-w-5xl">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <AdminLayout />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public */}
            <Route element={<PublicLayout />}>
              <Route path="/" element={<SummaryPage />} />
              <Route path="/topics/stocks" element={<StockTopicPage />} />
            </Route>

            {/* Login */}
            <Route path="/login" element={<LoginPage />} />

            {/* Admin (protected) */}
            <Route element={<ProtectedRoute />}>
              <Route path="/admin/sources" element={<AdminSourcesPage />} />
              <Route path="/admin/jobs" element={<AdminJobsPage />} />
              <Route path="/admin/highlights" element={<AdminHighlightsPage />} />
              <Route path="/admin/settings" element={<AdminSettingsPage />} />
              <Route path="/admin/layout" element={<AdminLayoutPage />} />
              <Route path="/admin/topics" element={<AdminTopicsPage />} />
              <Route path="/admin" element={<Navigate to="/admin/sources" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
