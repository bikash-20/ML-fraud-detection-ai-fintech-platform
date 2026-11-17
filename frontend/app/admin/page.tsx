"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bot,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Cpu,
  Database,
  Eye,
  Filter,
  Flame,
  Layers,
  MessageSquare,
  RefreshCw,
  Search,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Users,
  UserX,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type TabKey = "overview" | "fraud" | "transactions" | "users" | "alerts" | "system";

export default function AdminDashboardPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [loading, setLoading] = useState(true);

  // Section A: Overview Data
  const [overview, setOverview] = useState<any>(null);

  // Section B: Fraud Intelligence
  const [assessments, setAssessments] = useState<any[]>([]);
  const [assessmentTotal, setAssessmentTotal] = useState(0);
  const [assessmentPage, setAssessmentPage] = useState(1);
  const [assessmentFilterRisk, setAssessmentFilterRisk] = useState<string>("");
  const [selectedAssessment, setSelectedAssessment] = useState<any>(null);
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [reviewDecision, setReviewDecision] = useState("cleared");
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);

  // Section C: Transactions
  const [transactions, setTransactions] = useState<any[]>([]);
  const [txnTotal, setTxnTotal] = useState(0);
  const [txnPage, setTxnPage] = useState(1);
  const [txnSearch, setTxnSearch] = useState("");
  const [txnStatusFilter, setTxnStatusFilter] = useState("");
  const [txnRiskFilter, setTxnRiskFilter] = useState("");
  const [selectedTxn, setSelectedTxn] = useState<any>(null);

  // Section D: Users
  const [users, setUsers] = useState<any[]>([]);
  const [userSearch, setUserSearch] = useState("");
  const [userStatusFilter, setUserStatusFilter] = useState("");
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);

  // Section E: Alerts & Audit
  const [alerts, setAlerts] = useState<any[]>([]);
  const [alertTotal, setAlertTotal] = useState(0);
  const [alertStatusFilter, setAlertStatusFilter] = useState<string>("");
  const [selectedAlert, setSelectedAlert] = useState<any>(null);
  const [alertModalOpen, setAlertModalOpen] = useState(false);
  const [newAlertStatus, setNewAlertStatus] = useState("resolved");
  const [alertNotes, setAlertNotes] = useState("");
  const [auditLogs, setAuditLogs] = useState<any[]>([]);

  // Section F: System Status
  const [systemStatus, setSystemStatus] = useState<any>(null);

  // AI Assistant Drawer
  const [aiDrawerOpen, setAiDrawerOpen] = useState(false);
  const [aiQuery, setAiQuery] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiChatHistory, setAiChatHistory] = useState<
    { sender: "admin" | "ai"; text: string; data?: any; time: string }[]
  >([
    {
      sender: "ai",
      text: "Hello Talukder! I am your live Fraud Intelligence AI Assistant. I can analyze suspicious activities, explain risk scores, inspect transaction velocities, and monitor system health directly from the MySQL/SQLite database. What would you like to investigate?",
      time: "Just now",
    },
  ]);

  // Load initial data for the current tab
  useEffect(() => {
    loadTabData(activeTab);
  }, [activeTab]);

  function loadTabData(tab: TabKey) {
    setLoading(true);
    if (tab === "overview") {
      api
        .getAdminOverview()
        .then((data) => setOverview(data))
        .catch(console.error)
        .finally(() => setLoading(false));
    } else if (tab === "fraud") {
      loadAssessments();
    } else if (tab === "transactions") {
      loadTransactions();
    } else if (tab === "users") {
      loadUsers();
    } else if (tab === "alerts") {
      loadAlerts();
      api.getAdminAuditLogs().then((res) => setAuditLogs(res.items)).catch(console.error);
    } else if (tab === "system") {
      api
        .getSystemStatus()
        .then((data) => setSystemStatus(data))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }

  function loadAssessments() {
    setLoading(true);
    api
      .getAdminFraudAssessments({
        page: assessmentPage,
        page_size: 10,
        risk_level: assessmentFilterRisk || undefined,
      })
      .then((res) => {
        setAssessments(res.items);
        setAssessmentTotal(res.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  function loadTransactions() {
    setLoading(true);
    api
      .getAdminTransactions({
        page: txnPage,
        page_size: 15,
        search: txnSearch || undefined,
        status: txnStatusFilter || undefined,
        risk_level: txnRiskFilter || undefined,
      })
      .then((res) => {
        setTransactions(res.items);
        setTxnTotal(res.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  function loadUsers() {
    setLoading(true);
    api
      .getAdminUsers({
        search: userSearch || undefined,
        status_filter: userStatusFilter || undefined,
      })
      .then((res) => {
        setUsers(res.users);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  function loadAlerts() {
    setLoading(true);
    api
      .getFraudAlerts({
        status: alertStatusFilter || undefined,
        page_size: 20,
      })
      .then((res) => {
        setAlerts(res.items);
        setAlertTotal(res.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  // Submit assessment review
  async function submitAssessmentReview() {
    if (!selectedAssessment) return;
    setReviewSubmitting(true);
    try {
      await api.reviewFraudAssessment(selectedAssessment.id, {
        decision: reviewDecision,
        notes: reviewNotes,
      });
      setReviewModalOpen(false);
      setReviewNotes("");
      loadAssessments();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setReviewSubmitting(false);
    }
  }

  // Submit alert status update
  async function submitAlertUpdate() {
    if (!selectedAlert) return;
    try {
      await api.updateFraudAlert(selectedAlert.id, {
        status: newAlertStatus,
        notes: alertNotes,
        assign_to_me: true,
      });
      setAlertModalOpen(false);
      setAlertNotes("");
      loadAlerts();
    } catch (e) {
      alert((e as Error).message);
    }
  }

  // Toggle user flag
  async function handleToggleUserFlag(userId: number) {
    setActionLoadingId(userId);
    try {
      await api.toggleUserFlag(userId, "Admin manual security update");
      loadUsers();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setActionLoadingId(null);
    }
  }

  // Toggle user freeze
  async function handleToggleUserFreeze(userId: number) {
    setActionLoadingId(userId);
    try {
      await api.toggleUserFreeze(userId, "Admin manual account action");
      loadUsers();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setActionLoadingId(null);
    }
  }

  // Ask Admin AI
  async function handleSendAiQuery(customText?: string) {
    const q = customText || aiQuery;
    if (!q.trim()) return;

    const userMessage = { sender: "admin" as const, text: q, time: new Date().toLocaleTimeString() };
    setAiChatHistory((prev) => [...prev, userMessage]);
    setAiQuery("");
    setAiLoading(true);

    try {
      const res = await api.queryAdminAI(q);
      const fullText = res.response;
      setAiLoading(false);

      // Add empty response bubble to stream word-by-word
      setAiChatHistory((prev) => [
        ...prev,
        {
          sender: "ai",
          text: "",
          data: res.data,
          time: new Date().toLocaleTimeString(),
        },
      ]);

      // Reveal words one by one for natural conversational streaming
      const words = fullText.split(" ");
      let accumulated = "";
      for (let i = 0; i < words.length; i++) {
        accumulated += (i === 0 ? "" : " ") + words[i];
        const current = accumulated;
        setAiChatHistory((prev) => {
          const next = [...prev];
          const lastIdx = next.length - 1;
          if (lastIdx >= 0 && next[lastIdx].sender === "ai") {
            next[lastIdx] = { ...next[lastIdx], text: current };
          }
          return next;
        });
        await new Promise((r) => setTimeout(r, 25));
      }
    } catch (e) {
      setAiLoading(false);
      setAiChatHistory((prev) => [
        ...prev,
        {
          sender: "ai",
          text: `Query error: ${(e as Error).message}. Please ensure the backend is active.`,
          time: new Date().toLocaleTimeString(),
        },
      ]);
    }
  }

  return (
    <div className="space-y-6">
      {/* Navigation Tabs Bar */}
      <div className="flex items-center justify-between gap-2 overflow-x-auto pb-1 border-b border-white/10 text-xs sm:text-sm">
        <div className="flex items-center gap-1.5 sm:gap-2">
          <button
            onClick={() => setActiveTab("overview")}
            className={`px-3.5 py-2 rounded-xl font-medium transition flex items-center gap-1.5 ${
              activeTab === "overview"
                ? "bg-peach-500 text-plum-950 font-semibold shadow-glow-peach"
                : "btn-ghost text-lavender hover:text-cream"
            }`}
          >
            <BarChart3 size={15} />
            <span>Overview</span>
          </button>

          <button
            onClick={() => setActiveTab("fraud")}
            className={`px-3.5 py-2 rounded-xl font-medium transition flex items-center gap-1.5 ${
              activeTab === "fraud"
                ? "bg-peach-500 text-plum-950 font-semibold shadow-glow-peach"
                : "btn-ghost text-lavender hover:text-cream"
            }`}
          >
            <ShieldAlert size={15} />
            <span>Fraud Intelligence</span>
          </button>

          <button
            onClick={() => setActiveTab("transactions")}
            className={`px-3.5 py-2 rounded-xl font-medium transition flex items-center gap-1.5 ${
              activeTab === "transactions"
                ? "bg-peach-500 text-plum-950 font-semibold shadow-glow-peach"
                : "btn-ghost text-lavender hover:text-cream"
            }`}
          >
            <Layers size={15} />
            <span>Transactions</span>
          </button>

          <button
            onClick={() => setActiveTab("users")}
            className={`px-3.5 py-2 rounded-xl font-medium transition flex items-center gap-1.5 ${
              activeTab === "users"
                ? "bg-peach-500 text-plum-950 font-semibold shadow-glow-peach"
                : "btn-ghost text-lavender hover:text-cream"
            }`}
          >
            <Users size={15} />
            <span>Users</span>
          </button>

          <button
            onClick={() => setActiveTab("alerts")}
            className={`px-3.5 py-2 rounded-xl font-medium transition flex items-center gap-1.5 ${
              activeTab === "alerts"
                ? "bg-peach-500 text-plum-950 font-semibold shadow-glow-peach"
                : "btn-ghost text-lavender hover:text-cream"
            }`}
          >
            <AlertOctagon size={15} />
            <span>Alerts & Triage</span>
          </button>

          <button
            onClick={() => setActiveTab("system")}
            className={`px-3.5 py-2 rounded-xl font-medium transition flex items-center gap-1.5 ${
              activeTab === "system"
                ? "bg-peach-500 text-plum-950 font-semibold shadow-glow-peach"
                : "btn-ghost text-lavender hover:text-cream"
            }`}
          >
            <Cpu size={15} />
            <span>System Telemetry</span>
          </button>
        </div>

        {/* AI Assistant Quick Trigger Button */}
        <button
          onClick={() => setAiDrawerOpen(true)}
          className="btn-peach px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 whitespace-nowrap shadow-glow-peach animate-pulse hover:animate-none"
        >
          <Sparkles size={14} />
          <span>Admin AI Assistant</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* SECTION A: OVERVIEW */}
      {/* ========================================================================= */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Live KPI Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
            <div className="glass rounded-2xl p-4 border border-white/5">
              <div className="text-[11px] font-medium text-secondary uppercase tracking-wider">
                Total Registered Users
              </div>
              <div className="text-2xl sm:text-3xl font-bold text-cream mt-1 font-mono">
                {overview?.kpis?.total_users ?? "—"}
              </div>
              <div className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
                <span>{overview?.kpis?.active_users ?? 0} active users</span>
              </div>
            </div>

            <div className="glass rounded-2xl p-4 border border-white/5">
              <div className="text-[11px] font-medium text-secondary uppercase tracking-wider">
                Total Processed Volume
              </div>
              <div className="text-2xl sm:text-3xl font-bold text-peach-400 mt-1 font-mono">
                ৳{(overview?.kpis?.total_volume_bdt ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 0 })}
              </div>
              <div className="text-[11px] text-lavender mt-1">
                {overview?.kpis?.completed_transactions ?? 0} completed transfers
              </div>
            </div>

            <div className="glass rounded-2xl p-4 border border-white/5 border-l-2 border-l-amber-500">
              <div className="text-[11px] font-medium text-amber-300 uppercase tracking-wider flex items-center gap-1">
                <AlertTriangle size={12} />
                Suspicious Events
              </div>
              <div className="text-2xl sm:text-3xl font-bold text-amber-400 mt-1 font-mono">
                {overview?.kpis?.suspicious_transactions ?? "0"}
              </div>
              <div className="text-[11px] text-amber-200/70 mt-1">
                {overview?.kpis?.high_risk_transactions ?? 0} critical high-risk
              </div>
            </div>

            <div className="glass rounded-2xl p-4 border border-white/5 border-l-2 border-l-rose-500">
              <div className="text-[11px] font-medium text-rose-300 uppercase tracking-wider flex items-center gap-1">
                <AlertOctagon size={12} />
                Pending Investigations
              </div>
              <div className="text-2xl sm:text-3xl font-bold text-rose-400 mt-1 font-mono">
                {overview?.kpis?.pending_investigations ?? "0"}
              </div>
              <div className="text-[11px] text-rose-200/70 mt-1">
                Requires analyst triage
              </div>
            </div>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Timeline Volume Area Chart */}
            <div className="lg:col-span-2 glass-strong rounded-3xl p-5 border border-white/10">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-cream">
                    Transaction Volume & Activity Timeline
                  </h3>
                  <p className="text-[11px] text-lavender">
                    Daily financial volume (BDT) over the past 14 days
                  </p>
                </div>
                <div className="text-xs text-secondary px-2.5 py-1 rounded-lg bg-white/5">
                  Live DB Records
                </div>
              </div>

              <div className="h-64 w-full">
                {overview?.charts?.activity_timeline ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={overview.charts.activity_timeline} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#f0a585" stopOpacity={0.6} />
                          <stop offset="100%" stopColor="#f0a585" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="date" tick={{ fill: "#b8a8b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "#b8a8b8", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `৳${v}`} width={60} />
                      <Tooltip
                        contentStyle={{
                          background: "rgba(45, 35, 48, 0.95)",
                          border: "1px solid rgba(255,255,255,0.15)",
                          borderRadius: 12,
                          color: "#f2e9e4",
                          fontSize: 12,
                        }}
                        formatter={(val: any) => [`৳${Number(val).toLocaleString("en-IN")}`, "Volume"]}
                      />
                      <Area type="monotone" dataKey="volume_bdt" stroke="#f0a585" strokeWidth={2.5} fill="url(#volGrad)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-secondary">
                    Loading telemetry…
                  </div>
                )}
              </div>
            </div>

            {/* Risk Distribution Donut Chart */}
            <div className="glass-strong rounded-3xl p-5 border border-white/10 flex flex-col justify-between">
              <div>
                <h3 className="text-sm font-semibold text-cream">
                  Fraud Risk Distribution
                </h3>
                <p className="text-[11px] text-lavender mb-2">
                  Breakdown by explainable risk classification
                </p>
              </div>

              <div className="h-48 w-full flex items-center justify-center">
                {overview?.charts?.risk_distribution ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={overview.charts.risk_distribution}
                        dataKey="count"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={48}
                        outerRadius={72}
                        paddingAngle={4}
                      >
                        {overview.charts.risk_distribution.map((entry: any, index: number) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: "rgba(45, 35, 48, 0.95)",
                          border: "1px solid rgba(255,255,255,0.15)",
                          borderRadius: 12,
                          color: "#f2e9e4",
                          fontSize: 12,
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : null}
              </div>

              <div className="space-y-1.5 pt-2 border-t border-white/10 text-xs">
                {overview?.charts?.risk_distribution?.map((item: any, i: number) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-secondary">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ background: item.color }} />
                      {item.name}
                    </span>
                    <span className="font-mono font-semibold text-cream">{item.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION B: FRAUD INTELLIGENCE */}
      {/* ========================================================================= */}
      {activeTab === "fraud" && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 glass rounded-2xl p-3.5 border border-white/5">
            <div className="flex items-center gap-2">
              <span className="text-xs text-secondary font-medium">Risk Filter:</span>
              <select
                value={assessmentFilterRisk}
                onChange={(e) => {
                  setAssessmentFilterRisk(e.target.value);
                  setAssessmentPage(1);
                }}
                className="field-select text-xs py-1.5 px-3"
              >
                <option value="">All Tiers (Low, Med, High)</option>
                <option value="high">High Risk Only (≥ 0.75)</option>
                <option value="medium">Medium Risk (0.40 - 0.74)</option>
                <option value="low">Low Risk (&lt; 0.40)</option>
              </select>
              <button
                onClick={loadAssessments}
                className="btn-ghost p-1.5 rounded-lg text-secondary hover:text-cream"
                title="Refresh feed"
              >
                <RefreshCw size={14} />
              </button>
            </div>
            <div className="text-xs text-lavender">
              Showing <span className="text-cream font-semibold">{assessments.length}</span> of {assessmentTotal} evaluated transactions
            </div>
          </div>

          {/* Assessment List */}
          <div className="space-y-3">
            {assessments.map((a) => (
              <div
                key={a.id}
                className={`glass rounded-2xl p-4 border transition hover:border-white/20 ${
                  a.risk_level === "high"
                    ? "border-l-4 border-l-rose-500"
                    : a.risk_level === "medium"
                    ? "border-l-4 border-l-amber-500"
                    : "border-l-4 border-l-emerald-500"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2.5">
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        a.risk_level === "high"
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                          : a.risk_level === "medium"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      }`}
                    >
                      {a.risk_level} Risk (Score: {a.risk_score.toFixed(2)})
                    </span>
                    <span className="text-xs text-secondary font-mono">
                      Txn #{a.txn_id ?? "Direct"}
                    </span>
                    <span className="text-xs text-cream font-medium">
                      @{a.initiator?.handle} → {a.recipient?.handle ? `@${a.recipient.handle}` : "Biller"}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold text-cream font-mono">
                      ৳{Number(a.amount_bdt).toLocaleString("en-IN")}
                    </span>
                    <button
                      onClick={() => {
                        setSelectedAssessment(a);
                        setReviewModalOpen(true);
                      }}
                      className="btn-peach px-3 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 shadow-sm"
                    >
                      <Eye size={12} />
                      Review
                    </button>
                  </div>
                </div>

                {/* Plain-Language Detection Reasons */}
                <div className="bg-black/20 rounded-xl p-3 border border-white/5 space-y-1 text-xs">
                  <div className="text-[11px] font-semibold text-secondary flex items-center gap-1.5">
                    <Shield size={12} className="text-peach-400" />
                    Explainable Behavioral Signals & Rules:
                  </div>
                  {a.reasons?.map((r: string, idx: number) => (
                    <div key={idx} className="text-cream/90 pl-4 text-[11px]">
                      • {r}
                    </div>
                  ))}
                </div>

                <div className="mt-2.5 flex items-center justify-between text-[10px] text-lavender">
                  <span>Latency: {a.latency_ms}ms • Model: rule_ml_hybrid_v1.0</span>
                  <span>{new Date(a.created_at).toLocaleString()}</span>
                </div>
              </div>
            ))}

            {assessments.length === 0 && (
              <div className="glass rounded-2xl p-8 text-center text-xs text-secondary">
                No fraud assessments match the current filters.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION C: TRANSACTION MONITORING */}
      {/* ========================================================================= */}
      {activeTab === "transactions" && (
        <div className="space-y-4">
          {/* Search & Filter Controls */}
          <div className="glass rounded-2xl p-4 border border-white/5 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2 flex-1">
              <div className="relative min-w-[200px]">
                <Search size={14} className="absolute left-3 top-2.5 text-secondary" />
                <input
                  type="text"
                  placeholder="Search Txn ID or Handle…"
                  value={txnSearch}
                  onChange={(e) => setTxnSearch(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && loadTransactions()}
                  className="field-input text-xs pl-8 pr-3 py-1.5 w-full"
                />
              </div>

              <select
                value={txnStatusFilter}
                onChange={(e) => setTxnStatusFilter(e.target.value)}
                className="field-select text-xs py-1.5 px-3"
              >
                <option value="">Status: All</option>
                <option value="completed">Completed</option>
                <option value="pending">Pending</option>
                <option value="cancelled">Cancelled</option>
              </select>

              <select
                value={txnRiskFilter}
                onChange={(e) => setTxnRiskFilter(e.target.value)}
                className="field-select text-xs py-1.5 px-3"
              >
                <option value="">Risk: All</option>
                <option value="high">High Risk</option>
                <option value="medium">Medium Risk</option>
                <option value="low">Low Risk</option>
              </select>

              <button
                onClick={loadTransactions}
                className="btn-peach px-3 py-1.5 rounded-lg text-xs font-semibold"
              >
                Apply Filter
              </button>
            </div>

            <div className="text-xs text-lavender">
              {txnTotal} total transactions in ledger
            </div>
          </div>

          {/* Transactions Table */}
          <div className="glass-strong rounded-3xl overflow-hidden border border-white/10">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-white/5 border-b border-white/10 text-secondary uppercase text-[10px] tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Txn ID</th>
                    <th className="px-4 py-3">Sender</th>
                    <th className="px-4 py-3">Recipient</th>
                    <th className="px-4 py-3">Amount (BDT)</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Fraud Risk</th>
                    <th className="px-4 py-3">Created</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {transactions.map((t) => (
                    <tr key={t.id} className="hover:bg-white/5 transition">
                      <td className="px-4 py-3 font-mono font-medium text-cream">
                        #{t.id}
                      </td>
                      <td className="px-4 py-3 text-cream font-medium">
                        @{t.sender?.handle ?? "unknown"}
                      </td>
                      <td className="px-4 py-3 text-lavender">
                        {t.recipient?.handle ? `@${t.recipient.handle}` : "External/Biller"}
                      </td>
                      <td className="px-4 py-3 font-mono font-bold text-cream">
                        ৳{Number(t.amount_bdt).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                            t.status === "completed"
                              ? "bg-emerald-500/20 text-emerald-300"
                              : t.status === "pending"
                              ? "bg-amber-500/20 text-amber-300"
                              : "bg-rose-500/20 text-rose-300"
                          }`}
                        >
                          {t.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {t.fraud_assessment ? (
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                              t.fraud_assessment.risk_level === "high"
                                ? "bg-rose-500/20 text-rose-300"
                                : t.fraud_assessment.risk_level === "medium"
                                ? "bg-amber-500/20 text-amber-300"
                                : "bg-emerald-500/20 text-emerald-300"
                            }`}
                          >
                            {t.fraud_assessment.risk_level} ({t.fraud_assessment.risk_score.toFixed(2)})
                          </span>
                        ) : (
                          <span className="text-secondary text-[10px]">Unrated</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-secondary text-[11px]">
                        {new Date(t.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setSelectedTxn(t)}
                          className="btn-ghost px-2.5 py-1 rounded-lg text-xs"
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex items-center justify-between p-3.5 border-t border-white/10 text-xs text-secondary">
              <span>Page {txnPage} of {Math.ceil(txnTotal / 15) || 1}</span>
              <div className="flex gap-2">
                <button
                  disabled={txnPage <= 1}
                  onClick={() => {
                    setTxnPage((p) => Math.max(1, p - 1));
                    loadTransactions();
                  }}
                  className="btn-ghost px-2.5 py-1 rounded-lg disabled:opacity-30"
                >
                  <ChevronLeft size={14} />
                </button>
                <button
                  disabled={txnPage >= Math.ceil(txnTotal / 15)}
                  onClick={() => {
                    setTxnPage((p) => p + 1);
                    loadTransactions();
                  }}
                  className="btn-ghost px-2.5 py-1 rounded-lg disabled:opacity-30"
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION D: USER MANAGEMENT */}
      {/* ========================================================================= */}
      {activeTab === "users" && (
        <div className="space-y-4">
          <div className="glass rounded-2xl p-4 border border-white/5 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 flex-1 max-w-sm">
              <Search size={14} className="text-secondary" />
              <input
                type="text"
                placeholder="Search by handle or display name…"
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadUsers()}
                className="field-input text-xs w-full py-1.5"
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                value={userStatusFilter}
                onChange={(e) => setUserStatusFilter(e.target.value)}
                className="field-select text-xs py-1.5 px-3"
              >
                <option value="">All Account Statuses</option>
                <option value="flagged">Flagged for Watch</option>
                <option value="frozen">Frozen Accounts</option>
              </select>
              <button onClick={loadUsers} className="btn-peach px-3 py-1.5 rounded-lg text-xs font-semibold">
                Filter
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {users.map((u) => (
              <div
                key={u.id}
                className={`glass rounded-2xl p-4 border transition ${
                  u.is_frozen
                    ? "border-rose-500/50 bg-rose-950/20"
                    : u.is_flagged
                    ? "border-amber-500/50 bg-amber-950/20"
                    : "border-white/5"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-peach-500/15 border border-peach-500/30 flex items-center justify-center font-bold text-xs text-peach-300">
                      {u.display_name.charAt(0)}
                    </div>
                    <div>
                      <div className="text-xs font-bold text-cream">
                        {u.display_name} <span className="text-secondary font-normal font-mono">@{u.handle}</span>
                      </div>
                      <div className="text-[10px] text-lavender">{u.phone}</div>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-xs font-bold font-mono text-peach-400">
                      ৳{Number(u.balance_bdt).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </div>
                    <div className="text-[10px] text-secondary">
                      {u.total_transactions} txns
                    </div>
                  </div>
                </div>

                {/* Account Badges */}
                <div className="flex flex-wrap gap-1.5 my-3 text-[10px]">
                  {u.face_enrolled ? (
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/20 flex items-center gap-1">
                      <UserCheck size={10} /> Face ID Active
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full bg-white/5 text-secondary">
                      No Face ID
                    </span>
                  )}
                  {u.fraud_alerts_count > 0 && (
                    <span className="px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/20 font-semibold">
                      {u.fraud_alerts_count} Alerts
                    </span>
                  )}
                  {u.is_flagged && (
                    <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40">
                      Security Watch
                    </span>
                  )}
                  {u.is_frozen && (
                    <span className="px-2 py-0.5 rounded-full bg-rose-600/30 text-rose-200 font-bold border border-rose-500/50">
                      ACCOUNT FROZEN
                    </span>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/10 text-xs">
                  <button
                    disabled={actionLoadingId === u.id}
                    onClick={() => handleToggleUserFlag(u.id)}
                    className={`py-1.5 px-2 rounded-xl text-[11px] font-semibold border transition ${
                      u.is_flagged
                        ? "bg-amber-500/20 text-amber-200 border-amber-500/40 hover:bg-amber-500/30"
                        : "btn-ghost text-secondary hover:text-amber-300"
                    }`}
                  >
                    {u.is_flagged ? "Remove Watch" : "Flag Watch"}
                  </button>

                  <button
                    disabled={actionLoadingId === u.id}
                    onClick={() => handleToggleUserFreeze(u.id)}
                    className={`py-1.5 px-2 rounded-xl text-[11px] font-semibold border transition ${
                      u.is_frozen
                        ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/40 hover:bg-emerald-500/30"
                        : "bg-rose-500/20 text-rose-200 border-rose-500/40 hover:bg-rose-500/30"
                    }`}
                  >
                    {u.is_frozen ? "Unfreeze" : "Freeze Account"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION E: FRAUD ALERTS & INVESTIGATION */}
      {/* ========================================================================= */}
      {activeTab === "alerts" && (
        <div className="space-y-6">
          {/* Status Tabs */}
          <div className="flex items-center justify-between gap-2 border-b border-white/10 pb-2">
            <div className="flex items-center gap-1 text-xs">
              {["", "new", "investigating", "resolved", "false_positive"].map((st) => (
                <button
                  key={st}
                  onClick={() => {
                    setAlertStatusFilter(st);
                    loadAlerts();
                  }}
                  className={`px-3 py-1.5 rounded-xl font-medium capitalize transition ${
                    alertStatusFilter === st
                      ? "bg-peach-500 text-plum-950 font-semibold"
                      : "btn-ghost text-secondary hover:text-cream"
                  }`}
                >
                  {st || "All Alerts"}
                </button>
              ))}
            </div>
            <div className="text-xs text-lavender font-mono">{alertTotal} alerts total</div>
          </div>

          {/* Alerts Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {alerts.map((al) => (
              <div
                key={al.id}
                className="glass-strong rounded-2xl p-4 border border-white/10 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                      al.severity === "critical"
                        ? "bg-rose-500/30 text-rose-200 border border-rose-500/40"
                        : al.severity === "high"
                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                        : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                    }`}
                  >
                    {al.severity} Severity
                  </span>

                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                      al.status === "new"
                        ? "bg-blue-500/20 text-blue-300"
                        : al.status === "investigating"
                        ? "bg-amber-500/20 text-amber-300"
                        : al.status === "resolved"
                        ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-purple-500/20 text-purple-300"
                    }`}
                  >
                    {al.status}
                  </span>
                </div>

                <div>
                  <div className="text-xs font-bold text-cream">{al.alert_type}</div>
                  <div className="text-[11px] text-lavender mt-0.5">
                    User: @{al.user?.handle} ({al.user?.phone})
                    {al.amount_bdt && ` • ৳${Number(al.amount_bdt).toLocaleString("en-IN")}`}
                  </div>
                </div>

                <div className="bg-black/20 rounded-xl p-2.5 border border-white/5 text-[11px] text-secondary">
                  {al.detection_reasons}
                </div>

                {al.investigation_notes && (
                  <div className="text-[10px] text-lavender/90 bg-white/5 p-2 rounded-lg">
                    <span className="font-semibold text-cream">Notes:</span> {al.investigation_notes}
                  </div>
                )}

                <div className="flex items-center justify-between pt-2 border-t border-white/10 text-xs">
                  <span className="text-[10px] text-secondary">
                    {new Date(al.created_at).toLocaleString()}
                  </span>
                  <button
                    onClick={() => {
                      setSelectedAlert(al);
                      setNewAlertStatus(al.status);
                      setAlertModalOpen(true);
                    }}
                    className="btn-peach px-3 py-1 rounded-lg text-xs font-semibold"
                  >
                    Triage & Update
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Audit Logs Section */}
          <div className="mt-8 pt-6 border-t border-white/10">
            <h3 className="text-sm font-semibold text-cream mb-3 flex items-center gap-2">
              <Clock size={15} className="text-peach-400" />
              Administrative Security Audit Trail
            </h3>
            <div className="glass rounded-2xl overflow-hidden border border-white/5">
              <table className="w-full text-left text-xs">
                <thead className="bg-white/5 text-secondary uppercase text-[10px]">
                  <tr>
                    <th className="px-4 py-2.5">Time</th>
                    <th className="px-4 py-2.5">Operator</th>
                    <th className="px-4 py-2.5">Action</th>
                    <th className="px-4 py-2.5">Target</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {auditLogs.slice(0, 8).map((log) => (
                    <tr key={log.id}>
                      <td className="px-4 py-2 font-mono text-[11px] text-secondary">
                        {new Date(log.created_at).toLocaleTimeString()}
                      </td>
                      <td className="px-4 py-2 font-semibold text-cream">{log.admin}</td>
                      <td className="px-4 py-2 text-peach-300 font-mono text-[11px]">{log.action}</td>
                      <td className="px-4 py-2 text-lavender">{log.target_type} #{log.target_id || "global"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SECTION F: SYSTEM MONITORING */}
      {/* ========================================================================= */}
      {activeTab === "system" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Database Health Card */}
            <div className="glass-strong rounded-3xl p-5 border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm font-bold text-cream">
                  <Database size={18} className="text-peach-400" /> Database Engine
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/20 text-emerald-300 font-semibold">
                  CONNECTED
                </span>
              </div>
              <div className="text-xs space-y-1.5 text-secondary">
                <div>Dialect: <span className="text-cream font-mono">SQLite (WAL Mode)</span></div>
                <div>Storage Path: <span className="text-cream font-mono text-[10px]">{systemStatus?.database?.path}</span></div>
                <div>Users Table: <span className="text-cream font-mono">{systemStatus?.database?.tables?.users} rows</span></div>
                <div>Ledger Transactions: <span className="text-cream font-mono">{systemStatus?.database?.tables?.transactions} rows</span></div>
                <div>Fraud Assessments: <span className="text-cream font-mono">{systemStatus?.database?.tables?.fraud_assessments} rows</span></div>
              </div>
            </div>

            {/* Fraud Engine Card */}
            <div className="glass-strong rounded-3xl p-5 border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm font-bold text-cream">
                  <ShieldCheck size={18} className="text-emerald-400" /> Fraud Engine
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/20 text-emerald-300 font-semibold">
                  ACTIVE
                </span>
              </div>
              <div className="text-xs space-y-1.5 text-secondary">
                <div>Version: <span className="text-cream font-mono">{systemStatus?.fraud_detection_engine?.version}</span></div>
                <div>Active Security Rules: <span className="text-cream font-mono">7 Deterministic Rules</span></div>
                <div>ML Behavioral Anomaly Scorer: <span className="text-emerald-300 font-medium">Operational</span></div>
                <div>Avg Assessment Latency: <span className="text-peach-400 font-mono font-bold">{systemStatus?.fraud_detection_engine?.average_evaluation_latency_ms ?? 0} ms</span></div>
              </div>
            </div>

            {/* AI Cascade Infrastructure */}
            <div className="glass-strong rounded-3xl p-5 border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm font-bold text-cream">
                  <Cpu size={18} className="text-peach-400" /> AI Cascade Models
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/20 text-emerald-300 font-semibold">
                  CASCADING
                </span>
              </div>
              <div className="text-xs space-y-1.5 text-secondary">
                <div>
                  Local Ollama:{" "}
                  <span className={systemStatus?.ai_cascade_infrastructure?.ollama_local?.reachable ? "text-emerald-300" : "text-rose-300"}>
                    {systemStatus?.ai_cascade_infrastructure?.ollama_local?.reachable ? "Reachable" : "Offline"}
                  </span>
                </div>
                <div>
                  Active Local Model:{" "}
                  <span className="text-cream font-mono text-[10px]">
                    {systemStatus?.ai_cascade_infrastructure?.ollama_local?.active_model?.join(", ") || "qwen2.5:7b"}
                  </span>
                </div>
                <div>Grok (xAI): <span className="text-cream">{systemStatus?.ai_cascade_infrastructure?.grok_xai?.configured ? "Configured" : "Available"}</span></div>
                <div>Deterministic Fallback: <span className="text-emerald-400 font-medium">Always Active</span></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* FLOATING ADMIN AI ASSISTANT DRAWER */}
      {/* ========================================================================= */}
      {aiDrawerOpen && (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md glass-strong border-l border-white/15 shadow-2xl flex flex-col backdrop-blur-2xl">
          {/* Header */}
          <div className="p-4 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-peach-500/20 border border-peach-500/30 flex items-center justify-center text-peach-400">
                <Bot size={18} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-cream">Admin Intelligence AI</h3>
                <p className="text-[10px] text-emerald-300">Live Database Connected • Multi-Model</p>
              </div>
            </div>
            <button
              onClick={() => setAiDrawerOpen(false)}
              className="btn-ghost p-1.5 rounded-lg text-secondary hover:text-cream"
            >
              <X size={16} />
            </button>
          </div>

          {/* Quick Query Preset Chips */}
          <div className="px-4 py-2 border-b border-white/5 flex gap-1.5 overflow-x-auto text-[11px] bg-black/20">
            <button
              onClick={() => handleSendAiQuery("How many suspicious transactions occurred today?")}
              className="px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 text-secondary hover:text-cream whitespace-nowrap transition"
            >
              ⚡ Suspicious today
            </button>
            <button
              onClick={() => handleSendAiQuery("Which transactions have the highest risk scores?")}
              className="px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 text-secondary hover:text-cream whitespace-nowrap transition"
            >
              ⚡ Highest risk txns
            </button>
            <button
              onClick={() => handleSendAiQuery("Show me the latest fraud alerts")}
              className="px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 text-secondary hover:text-cream whitespace-nowrap transition"
            >
              ⚡ Latest alerts
            </button>
            <button
              onClick={() => handleSendAiQuery("What is the current transaction volume?")}
              className="px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 text-secondary hover:text-cream whitespace-nowrap transition"
            >
              ⚡ Total volume
            </button>
          </div>

          {/* Chat History */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 text-xs">
            {aiChatHistory.map((msg, i) => (
              <div
                key={i}
                className={`flex flex-col ${
                  msg.sender === "admin" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`max-w-[88%] p-3.5 rounded-2xl leading-relaxed ${
                    msg.sender === "admin"
                      ? "bg-peach-500 text-plum-950 font-medium rounded-tr-sm"
                      : "bg-white/10 text-cream rounded-tl-sm border border-white/5"
                  }`}
                >
                  <div>{msg.text}</div>
                  {msg.data?.patterns && (
                    <div className="mt-2 pt-2 border-t border-white/10 text-[10px] space-y-1">
                      {msg.data.patterns.map((p: any, idx: number) => (
                        <div key={idx} className="flex justify-between">
                          <span>{p.rule}</span>
                          <span className="font-mono font-bold">{p.occurrences}x</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <span className="text-[10px] text-lavender/60 mt-1 px-1">
                  {msg.time}
                </span>
              </div>
            ))}
            {aiLoading && (
              <div className="flex items-center gap-2 text-xs text-peach-300 animate-pulse p-2">
                <Sparkles size={14} />
                <span>Querying live database & synthesizing response…</span>
              </div>
            )}
          </div>

          {/* Input Bar */}
          <div className="p-3 border-t border-white/10 bg-black/20 flex gap-2">
            <input
              type="text"
              placeholder="Ask anything about transactions, users, or fraud…"
              value={aiQuery}
              onChange={(e) => setAiQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendAiQuery()}
              className="field-input flex-1 text-xs py-2"
            />
            <button
              onClick={() => handleSendAiQuery()}
              disabled={aiLoading || !aiQuery.trim()}
              className="btn-peach px-3 py-2 rounded-xl text-xs font-semibold flex items-center justify-center disabled:opacity-40"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Review Assessment Modal */}
      {reviewModalOpen && selectedAssessment && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-strong rounded-3xl p-6 max-w-lg w-full border border-white/15 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <h3 className="text-sm font-bold text-cream">
                Review Assessment #{selectedAssessment.id}
              </h3>
              <button onClick={() => setReviewModalOpen(false)} className="text-secondary hover:text-cream">
                <X size={16} />
              </button>
            </div>

            <div className="text-xs space-y-2 text-lavender bg-white/5 p-3 rounded-xl">
              <div>Amount: <span className="font-bold text-cream font-mono">৳{selectedAssessment.amount_bdt}</span></div>
              <div>Risk Score: <span className="font-bold text-peach-400 font-mono">{selectedAssessment.risk_score}</span> ({selectedAssessment.risk_level})</div>
              <div>Initiator: <span className="text-cream">@{selectedAssessment.initiator?.handle}</span></div>
              <div className="pt-1 text-[11px] text-cream">
                Reasons: {selectedAssessment.reasons?.join("; ")}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-cream mb-1">
                Administrative Decision
              </label>
              <select
                value={reviewDecision}
                onChange={(e) => setReviewDecision(e.target.value)}
                className="field-select w-full text-xs"
              >
                <option value="cleared">Clear (Verified Safe / Legitimate)</option>
                <option value="confirmed_fraud">Confirm Fraud (Elevate Investigation)</option>
                <option value="investigating">Hold for Ongoing Investigation</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-cream mb-1">
                Investigation Audit Notes
              </label>
              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Enter rationale for administrative log…"
                rows={3}
                className="field-input w-full text-xs"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setReviewModalOpen(false)}
                className="btn-ghost px-4 py-2 rounded-xl text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={reviewSubmitting}
                onClick={submitAssessmentReview}
                className="btn-peach px-4 py-2 rounded-xl text-xs font-semibold"
              >
                {reviewSubmitting ? "Submitting…" : "Record Decision"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Alert Triage Modal */}
      {alertModalOpen && selectedAlert && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-strong rounded-3xl p-6 max-w-lg w-full border border-white/15 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <h3 className="text-sm font-bold text-cream">
                Triage Alert #{selectedAlert.id} ({selectedAlert.alert_type})
              </h3>
              <button onClick={() => setAlertModalOpen(false)} className="text-secondary hover:text-cream">
                <X size={16} />
              </button>
            </div>

            <div>
              <label className="block text-xs font-medium text-cream mb-1">
                Update Status
              </label>
              <select
                value={newAlertStatus}
                onChange={(e) => setNewAlertStatus(e.target.value)}
                className="field-select w-full text-xs"
              >
                <option value="investigating">Investigating</option>
                <option value="resolved">Resolved (Cleared Safe)</option>
                <option value="false_positive">Mark as False Positive</option>
                <option value="new">Keep New</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-cream mb-1">
                Investigation Notes
              </label>
              <textarea
                value={alertNotes}
                onChange={(e) => setAlertNotes(e.target.value)}
                placeholder="Describe outcome or user verification steps…"
                rows={3}
                className="field-input w-full text-xs"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setAlertModalOpen(false)}
                className="btn-ghost px-4 py-2 rounded-xl text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitAlertUpdate}
                className="btn-peach px-4 py-2 rounded-xl text-xs font-semibold"
              >
                Save Triage
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Transaction Details Modal */}
      {selectedTxn && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-strong rounded-3xl p-6 max-w-md w-full border border-white/15 space-y-3 shadow-2xl text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-white/10">
              <h3 className="text-sm font-bold text-cream font-mono">
                Transaction #{selectedTxn.id}
              </h3>
              <button onClick={() => setSelectedTxn(null)} className="text-secondary hover:text-cream">
                <X size={16} />
              </button>
            </div>
            <div className="space-y-1.5 text-lavender">
              <div>Kind: <span className="text-cream uppercase font-semibold">{selectedTxn.kind}</span></div>
              <div>Amount: <span className="text-peach-400 font-bold font-mono">৳{selectedTxn.amount_bdt}</span></div>
              <div>Status: <span className="text-cream">{selectedTxn.status}</span></div>
              <div>Sender: <span className="text-cream font-mono">@{selectedTxn.sender?.handle}</span> ({selectedTxn.sender?.phone})</div>
              <div>Recipient: <span className="text-cream font-mono">{selectedTxn.recipient?.handle ?? "N/A"}</span></div>
              <div>Created: <span className="text-cream">{new Date(selectedTxn.created_at).toLocaleString()}</span></div>
              {selectedTxn.note && <div>Note: <span className="text-cream">{selectedTxn.note}</span></div>}
            </div>
            <div className="pt-3 border-t border-white/10 flex justify-end">
              <button onClick={() => setSelectedTxn(null)} className="btn-peach px-4 py-1.5 rounded-xl text-xs font-semibold">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
