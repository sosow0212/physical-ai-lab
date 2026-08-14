import { NavLink, Route, Routes } from "react-router-dom";

import ChatPage from "./pages/Chat";
import DashboardPage from "./pages/Dashboard";
import DocumentsPage from "./pages/Documents";
import DrawingsPage from "./pages/Drawings";
import GraphPage from "./pages/Graph";
import PipelinePage from "./pages/Pipeline";

const NAV_SECTIONS = [
  {
    title: "질의",
    items: [{ to: "/chat", label: "챗봇", icon: "💬" }],
  },
  {
    title: "지식 관리",
    items: [
      { to: "/documents", label: "매뉴얼", icon: "📄" },
      { to: "/drawings", label: "설계도면", icon: "📐" },
      { to: "/graph", label: "지식그래프", icon: "🔗" },
    ],
  },
  {
    title: "모니터링",
    items: [
      { to: "/", label: "대시보드", icon: "📊" },
      { to: "/pipeline", label: "수집 작업", icon: "⚙️" },
    ],
  },
] as const;

export default function App() {
  return (
    <div className="flex h-screen bg-slate-100 text-slate-800">
      {/* 사이드바 */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-slate-900">
        <div className="flex items-center gap-3 px-5 py-5">
          <span className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 text-sm font-bold text-white shadow-lg shadow-blue-900/40">
            PA
          </span>
          <div>
            <p className="text-sm font-semibold text-white">Physical AI Lab</p>
            <p className="text-[11px] text-slate-400">공정 매뉴얼 RAG 챗봇</p>
          </div>
        </div>

        <nav className="mt-1 flex flex-1 flex-col gap-4 px-3">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title}>
              <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {section.title}
              </p>
              <div className="flex flex-col gap-1">
                {section.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                        isActive
                          ? "bg-blue-600 font-medium text-white shadow-sm"
                          : "text-slate-300 hover:bg-slate-800 hover:text-white"
                      }`
                    }
                  >
                    <span aria-hidden className="w-4 text-center text-xs">
                      {item.icon}
                    </span>
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <p className="border-t border-slate-800 px-5 py-4 text-[11px] text-slate-500">
          PAL v0.1 · 학습용 프로젝트
        </p>
      </aside>

      {/* 메인 영역 */}
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/drawings" element={<DrawingsPage />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
        </Routes>
      </main>
    </div>
  );
}
