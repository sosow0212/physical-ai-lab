import { NavLink, Route, Routes } from "react-router-dom";

import ChatPage from "./pages/Chat";
import DocumentsPage from "./pages/Documents";
import { Placeholder } from "./pages/Placeholder";

const NAV_ITEMS = [
  { to: "/", label: "대시보드", icon: "▦", phase: "Phase 6" },
  { to: "/chat", label: "챗봇", icon: "💬", phase: "Phase 3" },
  { to: "/documents", label: "매뉴얼 관리", icon: "📄", phase: "Phase 2" },
  { to: "/drawings", label: "도면 관리", icon: "📐", phase: "Phase 5" },
  { to: "/graph", label: "지식그래프", icon: "🕸", phase: "Phase 4" },
  { to: "/pipeline", label: "수집 작업", icon: "⚙", phase: "Phase 2" },
] as const;

export default function App() {
  return (
    <div className="flex h-screen bg-slate-100 text-slate-800">
      {/* 사이드바 */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-slate-900 text-slate-300">
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
            PA
          </span>
          <div>
            <p className="text-sm font-semibold text-white">Physical AI Lab</p>
            <p className="text-xs text-slate-400">공정 매뉴얼 RAG 챗봇</p>
          </div>
        </div>
        <nav className="mt-2 flex flex-1 flex-col gap-1 px-3">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "bg-blue-600 font-medium text-white"
                    : "hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              <span aria-hidden>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <p className="px-5 py-4 text-xs text-slate-500">PAL v0.1 · 학습용 프로젝트</p>
      </aside>

      {/* 메인 영역 */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Placeholder title="대시보드" phase="Phase 6" />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/drawings" element={<Placeholder title="도면 관리" phase="Phase 5" />} />
          <Route path="/graph" element={<Placeholder title="지식그래프" phase="Phase 4" />} />
          <Route path="/pipeline" element={<Placeholder title="수집 작업" phase="Phase 6" />} />
        </Routes>
      </main>
    </div>
  );
}
