import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { SummaryPage } from "./pages/SummaryPage";
import { StockTopicPage } from "./pages/StockTopicPage";

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
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
