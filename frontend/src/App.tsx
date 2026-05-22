import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Navbar } from "@/components/layout/Navbar";
import { SummaryPage } from "./pages/SummaryPage";
import { StockTopicPage } from "./pages/StockTopicPage";
import { AdminSourcesPage } from "./pages/AdminSourcesPage";
import { AdminJobsPage } from "./pages/AdminJobsPage";
import { AdminHighlightsPage } from "./pages/AdminHighlightsPage";
import { AdminSettingsPage } from "./pages/AdminSettingsPage";
import { AdminLayoutPage } from "./pages/AdminLayoutPage";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-background">
          <Navbar />
          <main className="max-w-6xl mx-auto px-6 py-8">
            <Routes>
              <Route path="/" element={<SummaryPage />} />
              <Route path="/topics/stocks" element={<StockTopicPage />} />
              <Route path="/admin/sources" element={<AdminSourcesPage />} />
              <Route path="/admin/jobs" element={<AdminJobsPage />} />
              <Route path="/admin/highlights" element={<AdminHighlightsPage />} />
              <Route path="/admin/settings" element={<AdminSettingsPage />} />
              <Route path="/admin/layout" element={<AdminLayoutPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
