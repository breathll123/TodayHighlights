import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { SummaryPage } from "./pages/SummaryPage";
import { StockTopicPage } from "./pages/StockTopicPage";
import { AdminSourcesPage } from "./pages/AdminSourcesPage";
import { AdminJobsPage } from "./pages/AdminJobsPage";
import { AdminHighlightsPage } from "./pages/AdminHighlightsPage";
import { AdminSettingsPage } from "./pages/AdminSettingsPage";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app">
          <nav className="nav">
            <a href="/" className="nav-brand">每日看点</a>
            <div className="nav-links">
              <a href="/">摘要</a>
              <a href="/topics/stocks">股票</a>
              <a href="/admin/sources">管理</a>
            </div>
          </nav>
          <main className="main">
            <Routes>
              <Route path="/" element={<SummaryPage />} />
              <Route path="/topics/stocks" element={<StockTopicPage />} />
              <Route path="/admin/sources" element={<AdminSourcesPage />} />
              <Route path="/admin/jobs" element={<AdminJobsPage />} />
              <Route path="/admin/highlights" element={<AdminHighlightsPage />} />
              <Route path="/admin/settings" element={<AdminSettingsPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
