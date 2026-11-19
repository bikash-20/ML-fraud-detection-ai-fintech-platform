"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { api, maskPhone } from "@/lib/api";
import { speakText } from "@/lib/speech";
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
  Loader2,
  MessageSquare,
  Mic,
  MicOff,
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
  Volume2,
  VolumeX,
  X,
} from "lucide-react";

const AdminVolumeChart = dynamic(
  () => import("@/components/AdminCharts").then((m) => m.AdminVolumeChart),
  {
    ssr: false,
    loading: () => (
      <div className="h-full flex items-center justify-center text-xs text-secondary animate-pulse">
        Loading telemetry…
      </div>
    ),
  }
);

const AdminRiskPieChart = dynamic(
  () => import("@/components/AdminCharts").then((m) => m.AdminRiskPieChart),
  {
    ssr: false,
    loading: () => (
      <div className="h-full flex items-center justify-center text-xs text-secondary animate-pulse">
        Loading risk distribution…
      </div>
    ),
  }
);

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
  const [selectedUserDetail, setSelectedUserDetail] = useState<any | null>(null);
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [tierModalOpen, setTierModalOpen] = useState(false);
  const [newTier, setNewTier] = useState<string>("verified");
  const [tierReasonCode, setTierReasonCode] = useState<string>("kyc_documents_verified");
  const [tierNotes, setTierNotes] = useState<string>("");
  const [userActionWorking, setUserActionWorking] = useState<boolean>(false);

  // Section E: Alerts & Audit
  const [alerts, setAlerts] = useState<any[]>([]);
  const [alertTotal, setAlertTotal] = useState(0);
  const [alertStatusFilter, setAlertStatusFilter] = useState<string>("");
  const [selectedAlert, setSelectedAlert] = useState<any>(null);
  const [alertModalOpen, setAlertModalOpen] = useState(false);
  const [newAlertStatus, setNewAlertStatus] = useState("resolved");
  const [alertReasonCode, setAlertReasonCode] = useState("verified_legitimate");
  const [alertNotes, setAlertNotes] = useState("");
  const [auditLogs, setAuditLogs] = useState<any[]>([]);

  // Section F: System Status
  const [systemStatus, setSystemStatus] = useState<any>(null);

  // AI Assistant Drawer & Voice Control
  const [aiDrawerOpen, setAiDrawerOpen] = useState(false);
  const [aiQuery, setAiQuery] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [isVoiceMuted, setIsVoiceMuted] = useState(false);
  const [isRecordingVoice, setIsRecordingVoice] = useState(false);
  const [isTranscribingVoice, setIsTranscribingVoice] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const [aiChatHistory, setAiChatHistory] = useState<
    { sender: "admin" | "ai"; text: string; data?: any; time: string }[]
  >([
    {
      sender: "ai",
      text: "Hello Boss! I am your live Fraud Intelligence AI Assistant. I can analyze suspicious activities, check recent system activity, explain risk scores, and monitor health directly from the live database. What would you like to investigate?",
      time: "Just now",
    },
  ]);

  // Audio stream cleanup on unmount
  useEffect(() => {
    return () => {
      try {
        mediaRecorderRef.current?.stop();
      } catch {}
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

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
        reason_code: alertReasonCode,
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

  // Open User Detail & Management Drawer
  async function openUserDetail(userId: number) {
    try {
      const data = await api.getAdminUser(userId);
      setSelectedUserDetail(data);
      setNewTier(data.account_tier || "personal");
      setUserModalOpen(true);
    } catch (e: any) {
      alert(`Failed to load user details: ${e.message}`);
    }
  }

  // Admin action: Verify or Unverify KYC (audit logged)
  async function handleAdminVerifyKyc(userId: number, kycStatus: "verified" | "unverified") {
    setUserActionWorking(true);
    try {
      await api.adminVerifyKYC(userId, {
        kyc_status: kycStatus,
        notes: `Administrator manual KYC action: set to ${kycStatus}`,
        activate_requested_tier: true,
      });
      loadUsers();
      const updated = await api.getAdminUser(userId);
      setSelectedUserDetail(updated);
    } catch (e: any) {
      alert(`Failed to update KYC status: ${e.message}`);
    } finally {
      setUserActionWorking(false);
    }
  }

  // Admin action: Change Account Tier with mandatory reason code (audit logged)
  async function handleAdminChangeTierSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedUserDetail) return;
    if (!tierReasonCode) {
      alert("Mandatory reason code is required for tier changes.");
      return;
    }
    setUserActionWorking(true);
    try {
      await api.adminChangeTier(selectedUserDetail.id, {
        account_tier: newTier,
        reason_code: tierReasonCode,
        notes: tierNotes,
      });
      setTierModalOpen(false);
      loadUsers();
      const updated = await api.getAdminUser(selectedUserDetail.id);
      setSelectedUserDetail(updated);
    } catch (e: any) {
      alert(`Failed to update account tier: ${e.message}`);
    } finally {
      setUserActionWorking(false);
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

  // Admin Voice Input Handlers
  async function startVoiceRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      mediaStreamRef.current = stream;
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find(
        (candidate) => MediaRecorder.isTypeSupported(candidate)
      );
      const mr = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      audioChunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        mediaStreamRef.current = null;
        const blob = new Blob(audioChunksRef.current, {
          type: mr.mimeType || "audio/webm",
        });
        if (blob.size === 0) return;
        setIsTranscribingVoice(true);
        try {
          const text = await api.transcribe(blob);
          if (text && text.trim()) {
            // Immediate verbal acknowledgment when voice command received
            if (!isVoiceMuted) {
              speakText("Let me check, Boss...");
            }
            await handleSendAiQuery(text.trim(), true);
          }
        } catch (e) {
          console.error("Voice transcription failed:", e);
        } finally {
          setIsTranscribingVoice(false);
        }
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setIsRecordingVoice(true);
    } catch (e) {
      alert(`Microphone access unavailable: ${(e as Error).message}`);
    }
  }

  function stopVoiceRecording() {
    const mr = mediaRecorderRef.current;
    if (mr && mr.state !== "inactive") {
      mr.stop();
    }
    setIsRecordingVoice(false);
  }

  // Ask Admin AI with multi-turn history & word-by-word streaming
  async function handleSendAiQuery(customText?: string, fromVoice = false) {
    const q = customText || aiQuery;
    if (!q.trim()) return;

    const userMessage = { sender: "admin" as const, text: q, time: new Date().toLocaleTimeString() };
    setAiChatHistory((prev) => [...prev, userMessage]);
    setAiQuery("");
    setAiLoading(true);

    try {
      // Build conversation history payload from previous turns
      const historyPayload = aiChatHistory
        .filter((m) => m.text && (m.sender === "admin" || m.sender === "ai"))
        .slice(-8)
        .map((m) => ({ sender: m.sender, text: m.text }));

      const res = await api.queryAdminAI(q, historyPayload);
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

      // If voice enabled, speak the full synthesized response aloud via TTS
      if (!isVoiceMuted) {
        speakText(fullText);
      }

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
        await new Promise((r) => setTimeout(r, 20));
      }
    } catch (e) {
      setAiLoading(false);
      const errText = `Query error: ${(e as Error).message}. Please ensure the backend is active.`;
      setAiChatHistory((prev) => [
        ...prev,
        {
          sender: "ai",
          text: errText,
          time: new Date().toLocaleTimeString(),
        },
      ]);
      if (!isVoiceMuted) {
        speakText("Sorry Boss, an error occurred while connecting to the database.");
      }
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
              <div className="text-xs font-semibold text-secondary uppercase tracking-wider">
                Total Registered Users
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-cream mt-1 font-mono">
                {overview?.kpis?.total_users ?? "—"}
              </div>
              <div className="text-xs font-medium text-emerald-400 mt-1 flex items-center gap-1">
                <span>{overview?.kpis?.active_users ?? 0} active users</span>
              </div>
            </div>

            <div className="glass rounded-2xl p-4 border border-white/5">
              <div className="text-xs font-semibold text-secondary uppercase tracking-wider">
                Total Processed Volume
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-peach-400 mt-1 font-mono">
                ৳{(overview?.kpis?.total_volume_bdt ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 0 })}
              </div>
              <div className="text-xs font-medium text-lavender mt-1">
                {overview?.kpis?.completed_transactions ?? 0} completed transfers
              </div>
            </div>

            <div className="glass rounded-2xl p-4 border border-white/5 border-l-2 border-l-amber-500">
              <div className="text-xs font-semibold text-amber-300 uppercase tracking-wider flex items-center gap-1">
                <AlertTriangle size={14} />
                Suspicious Events
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-amber-400 mt-1 font-mono">
                {overview?.kpis?.suspicious_transactions ?? "0"}
              </div>
              <div className="text-xs font-medium text-amber-200/80 mt-1">
                {overview?.kpis?.high_risk_transactions ?? 0} critical high-risk
              </div>
            </div>

            <div className="glass rounded-2xl p-4 border border-white/5 border-l-2 border-l-rose-500">
              <div className="text-xs font-semibold text-rose-300 uppercase tracking-wider flex items-center gap-1">
                <AlertOctagon size={14} />
                Pending Investigations
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-rose-400 mt-1 font-mono">
                {overview?.kpis?.pending_investigations ?? "0"}
              </div>
              <div className="text-xs font-medium text-rose-200/80 mt-1">
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
                  <h3 className="text-base font-bold text-cream">
                    Transaction Volume & Activity Timeline
                  </h3>
                  <p className="text-xs text-lavender">
                    Daily financial volume (BDT) over the past 14 days
                  </p>
                </div>
                <div className="text-xs font-semibold text-secondary px-2.5 py-1 rounded-lg bg-white/5">
                  Live DB Records
                </div>
              </div>

              <div className="h-64 w-full">
                {overview?.charts?.activity_timeline ? (
                  <AdminVolumeChart data={overview.charts.activity_timeline} />
                ) : (
                  <div className="h-full flex items-center justify-center text-sm text-secondary">
                    Loading telemetry…
                  </div>
                )}
              </div>
            </div>

            {/* Risk Distribution Donut Chart */}
            <div className="glass-strong rounded-3xl p-5 border border-white/10 flex flex-col justify-between">
              <div>
                <h3 className="text-base font-bold text-cream">
                  Fraud Risk Distribution
                </h3>
                <p className="text-xs text-lavender mb-2">
                  Breakdown by explainable risk classification
                </p>
              </div>

              <div className="h-48 w-full flex items-center justify-center">
                {overview?.charts?.risk_distribution ? (
                  <AdminRiskPieChart data={overview.charts.risk_distribution} />
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
                      className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                        a.risk_level === "high"
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                          : a.risk_level === "medium"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      }`}
                    >
                      {a.risk_level} Risk (Score: {a.risk_score.toFixed(2)})
                    </span>
                    <span className="text-xs font-semibold text-secondary font-mono">
                      Txn #{a.txn_id ?? "Direct"}
                    </span>
                    <span className="text-sm text-cream font-semibold">
                      @{a.initiator?.handle} → {a.recipient?.handle ? `@${a.recipient.handle}` : "Biller"}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="text-base font-bold text-cream font-mono">
                      ৳{Number(a.amount_bdt).toLocaleString("en-IN")}
                    </span>
                    <button
                      onClick={() => {
                        setSelectedAssessment(a);
                        setReviewModalOpen(true);
                      }}
                      className="btn-peach px-3.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-sm"
                    >
                      <Eye size={14} />
                      Review
                    </button>
                  </div>
                </div>

                {/* Plain-Language Detection Reasons */}
                <div className="bg-black/20 rounded-xl p-3 border border-white/5 space-y-1.5 text-xs">
                  <div className="text-xs font-bold text-secondary flex items-center gap-1.5">
                    <Shield size={14} className="text-peach-400" />
                    Explainable Behavioral Signals & Rules:
                  </div>
                  {a.reasons?.map((r: string, idx: number) => (
                    <div key={idx} className="text-cream/90 pl-4 text-xs font-medium">
                      • {r}
                    </div>
                  ))}
                </div>

                <div className="mt-2.5 flex items-center justify-between text-xs text-lavender font-medium">
                  <span>Latency: {a.latency_ms}ms • Model: rule_ml_hybrid_v1.0</span>
                  <span>{new Date(a.created_at).toLocaleString()}</span>
                </div>
              </div>
            ))}

            {assessments.length === 0 && (
              <div className="glass rounded-2xl p-8 text-center text-sm text-secondary">
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
              <table className="w-full text-left text-sm">
                <thead className="bg-white/5 border-b border-white/10 text-secondary uppercase text-xs tracking-wider font-bold">
                  <tr>
                    <th className="px-4 py-3.5">Txn ID</th>
                    <th className="px-4 py-3.5">Sender</th>
                    <th className="px-4 py-3.5">Recipient</th>
                    <th className="px-4 py-3.5">Amount (BDT)</th>
                    <th className="px-4 py-3.5">Status</th>
                    <th className="px-4 py-3.5">Fraud Risk</th>
                    <th className="px-4 py-3.5">Created</th>
                    <th className="px-4 py-3.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {transactions.map((t) => (
                    <tr key={t.id} className="hover:bg-white/5 transition">
                      <td className="px-4 py-3.5 font-mono font-bold text-cream text-sm">
                        #{t.id}
                      </td>
                      <td className="px-4 py-3.5 text-cream font-bold text-sm">
                        {t.kind === "cash_in" ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold text-xs whitespace-nowrap">
                            <span>🏦</span> Cash-In / Deposit
                          </span>
                        ) : (
                          `@${t.sender?.handle ?? "unknown"}`
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-lavender font-medium text-sm">
                        {t.kind === "cash_out" ? (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-amber-300 font-semibold text-xs whitespace-nowrap">
                            <span>🏧</span> MFS Agent Cash-Out
                          </span>
                        ) : t.recipient?.handle ? (
                          `@${t.recipient.handle}`
                        ) : (
                          "External/Biller"
                        )}
                      </td>
                      <td className="px-4 py-3.5 font-mono font-bold text-cream text-base">
                        <div>
                          <span>৳{Number(t.amount_bdt).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
                          {(t as any).is_legacy_test_data && (
                            <span
                              className="ml-2 inline-block px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30"
                              title={(t as any).legacy_explanation || "Legacy Test Data"}
                            >
                              Legacy Test Data
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span
                          className={`px-2.5 py-1 rounded text-xs font-bold uppercase ${
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
                      <td className="px-4 py-3.5">
                        {t.fraud_assessment ? (
                          <span
                            className={`px-2.5 py-1 rounded text-xs font-bold uppercase ${
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
                          <span className="text-secondary text-xs font-medium">Unrated</span>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-secondary text-xs font-medium">
                        {new Date(t.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <button
                          onClick={() => setSelectedTxn(t)}
                          className="btn-ghost px-3 py-1.5 rounded-lg text-xs font-medium hover:text-cream"
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
            {users.map((u) => {
              const isVerifiedKyc = u.kyc_status === "verified";
              const isRestricted = u.account_tier !== u.effective_tier;

              return (
                <div
                  key={u.id}
                  className={`glass rounded-2xl p-4 border transition flex flex-col justify-between ${
                    u.is_frozen
                      ? "border-rose-500/50 bg-rose-950/20"
                      : u.is_flagged
                      ? "border-amber-500/50 bg-amber-950/20"
                      : "border-white/5"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className="w-9 h-9 rounded-full bg-peach-500/15 border border-peach-500/30 flex items-center justify-center font-bold text-sm text-peach-300">
                          {u.display_name.charAt(0)}
                        </div>
                        <div>
                          <div className="text-sm font-bold text-cream flex items-center gap-1.5">
                            <span>{u.display_name}</span>
                            <span className="text-secondary font-normal font-mono text-xs">@{u.handle}</span>
                          </div>
                          <div className="text-xs text-lavender font-mono">{u.masked_phone || maskPhone(u.phone)}</div>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-sm font-bold font-mono text-peach-400">
                          ৳{Number(u.balance_bdt).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </div>
                        <div className="text-xs text-secondary font-medium">
                          {u.total_transactions} txns
                        </div>
                      </div>
                    </div>

                    {u.business_name && (
                      <div className="text-xs text-peach-300 font-semibold truncate mb-2">
                        🏢 {u.business_name}
                      </div>
                    )}

                    {/* Account Type, Tier & KYC Badges */}
                    <div className="flex flex-wrap gap-1.5 my-2.5 text-xs">
                      <span className="px-2.5 py-0.5 rounded-full bg-white/5 text-cream border border-white/10 uppercase tracking-wide font-medium">
                        {u.user_type || "student"}
                      </span>

                      <span className="px-2.5 py-0.5 rounded-full bg-peach-500/15 text-peach-300 border border-peach-500/25 uppercase font-bold">
                        {u.account_tier || "personal"} tier
                      </span>

                      {isVerifiedKyc ? (
                        <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold flex items-center gap-1">
                          <CheckCircle2 size={12} /> KYC Verified
                        </span>
                      ) : (
                        <span className="px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 font-semibold flex items-center gap-1">
                          <AlertTriangle size={12} /> KYC Pending
                        </span>
                      )}

                      {u.fraud_alerts_count > 0 && (
                        <span className="px-2.5 py-0.5 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/20 font-bold">
                          {u.fraud_alerts_count} Alerts
                        </span>
                      )}

                      {u.is_flagged && (
                        <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40">
                          Security Watch
                        </span>
                      )}

                      {u.is_frozen && (
                        <span className="px-2.5 py-0.5 rounded-full bg-rose-600/30 text-rose-200 font-bold border border-rose-500/50">
                          FROZEN
                        </span>
                      )}
                    </div>

                    {/* 30-Day Median Baseline Info */}
                    <div className="p-2.5 rounded-xl bg-white/5 mb-3 flex items-center justify-between text-xs font-mono">
                      <span className="text-secondary">30d Spending Median:</span>
                      <span className="font-bold text-emerald-400">
                        ৳{Number(u.baseline_median_30d || 1000).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </span>
                    </div>

                    {/* Pending Upgrade Alert if user requested */}
                    {u.requested_upgrade_tier && (
                      <div className="mb-3 p-2.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-xs text-cyan-200 flex items-center justify-between">
                        <span>Requested upgrade to <strong className="uppercase">{u.requested_upgrade_tier}</strong></span>
                        <span className="font-semibold text-cyan-300">Needs Review</span>
                      </div>
                    )}
                  </div>

                  {/* Action Buttons */}
                  <div className="space-y-2 pt-2 border-t border-white/10 text-xs">
                    <button
                      onClick={() => openUserDetail(u.id)}
                      className="btn-peach w-full py-2 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 shadow-glow-peach"
                    >
                      <Eye size={14} />
                      <span>Inspect & Manage</span>
                    </button>

                    <div className="grid grid-cols-2 gap-2">
                      <button
                        disabled={actionLoadingId === u.id}
                        onClick={() => handleToggleUserFlag(u.id)}
                        className={`py-2 px-2.5 rounded-xl text-xs font-semibold border transition ${
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
                        className={`py-2 px-2.5 rounded-xl text-xs font-semibold border transition ${
                          u.is_frozen
                            ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/40 hover:bg-emerald-500/30"
                            : "bg-rose-500/20 text-rose-200 border-rose-500/40 hover:bg-rose-500/30"
                        }`}
                      >
                        {u.is_frozen ? "Unfreeze" : "Freeze Account"}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* User Detail & Tier Management Modal */}
          {userModalOpen && selectedUserDetail && (
            <div className="fixed inset-0 z-50 bg-plum-950/80 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="glass rounded-3xl p-6 sm:p-8 max-w-2xl w-full border border-white/10 shadow-2xl max-h-[90vh] overflow-y-auto space-y-5 animate-in fade-in zoom-in-95">
                <div className="flex items-center justify-between border-b border-white/10 pb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-2xl bg-peach-500/20 text-peach-300 flex items-center justify-center font-bold text-lg">
                      {selectedUserDetail.display_name?.charAt(0)}
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-cream flex items-center gap-2">
                        <span>{selectedUserDetail.display_name}</span>
                        <span className="text-secondary font-mono text-xs">@{selectedUserDetail.handle}</span>
                      </h3>
                      <div className="text-xs text-lavender font-mono">
                        {selectedUserDetail.masked_phone || maskPhone(selectedUserDetail.phone)}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => setUserModalOpen(false)}
                    className="text-secondary hover:text-cream text-lg"
                  >
                    ✕
                  </button>
                </div>

                {/* Identity, Role & Regulatory Limits Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                  <div className="p-3.5 rounded-xl bg-white/5">
                    <span className="text-xs uppercase text-secondary font-bold">User Type</span>
                    <div className="font-extrabold text-cream uppercase mt-1">{selectedUserDetail.user_type}</div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-white/5">
                    <span className="text-xs uppercase text-secondary font-bold">Account Tier</span>
                    <div className="font-extrabold text-peach-300 uppercase mt-1">{selectedUserDetail.account_tier}</div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-white/5">
                    <span className="text-xs uppercase text-secondary font-bold">KYC Status</span>
                    <div className="font-extrabold mt-1">
                      {selectedUserDetail.kyc_status === "verified" ? (
                        <span className="text-emerald-400">Verified</span>
                      ) : (
                        <span className="text-amber-400">Unverified</span>
                      )}
                    </div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-white/5">
                    <span className="text-xs uppercase text-secondary font-bold">Current Balance</span>
                    <div className="font-extrabold text-peach-400 font-mono mt-1 text-base">
                      ৳{Number(selectedUserDetail.balance_bdt).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </div>
                  </div>
                </div>

                {selectedUserDetail.business_name && (
                  <div className="p-3 rounded-xl bg-white/5 text-xs text-lavender">
                    <span className="text-secondary">Commercial Entity: </span>
                    <strong className="text-cream">{selectedUserDetail.business_name}</strong>
                  </div>
                )}

                {/* Pending Upgrade Alert Banner */}
                {selectedUserDetail.requested_upgrade_tier && (
                  <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-xs text-cyan-200 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <span className="font-bold">Pending Upgrade Request: </span>
                      User requested upgrade to <strong className="uppercase text-cream">{selectedUserDetail.requested_upgrade_tier} Tier</strong>.
                    </div>
                    <button
                      disabled={userActionWorking}
                      onClick={() => handleAdminVerifyKyc(selectedUserDetail.id, "verified")}
                      className="btn-peach px-3 py-1.5 rounded-lg text-xs font-semibold shadow-glow-peach"
                    >
                      {userActionWorking ? "Approving…" : "Approve & Verify KYC"}
                    </button>
                  </div>
                )}

                {/* Administrative Controls */}
                <div className="p-4 rounded-2xl bg-white/5 border border-white/5 space-y-3">
                  <h4 className="text-xs uppercase font-bold tracking-wider text-secondary">
                    Administrative Actions & Security Overrides
                  </h4>

                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    {/* KYC Verification Toggle */}
                    {selectedUserDetail.kyc_status === "verified" ? (
                      <button
                        disabled={userActionWorking}
                        onClick={() => handleAdminVerifyKyc(selectedUserDetail.id, "unverified")}
                        className="btn-ghost px-3 py-2 rounded-xl text-xs font-semibold text-amber-300 hover:text-amber-200"
                      >
                        Revoke KYC Verification
                      </button>
                    ) : (
                      <button
                        disabled={userActionWorking}
                        onClick={() => handleAdminVerifyKyc(selectedUserDetail.id, "verified")}
                        className="btn-peach px-3.5 py-2 rounded-xl text-xs font-semibold shadow-glow-peach"
                      >
                        Verify Customer KYC
                      </button>
                    )}

                    {/* Change Tier Button */}
                    <button
                      onClick={() => {
                        setNewTier(selectedUserDetail.account_tier || "personal");
                        setTierReasonCode("kyc_documents_verified");
                        setTierNotes("");
                        setTierModalOpen(true);
                      }}
                      className="btn-ghost px-3.5 py-2 rounded-xl text-xs font-semibold border border-peach-500/40 text-peach-300 hover:bg-peach-500/10"
                    >
                      Change Account Tier…
                    </button>

                    {/* Security Watch Button */}
                    <button
                      disabled={userActionWorking}
                      onClick={async () => {
                        await handleToggleUserFlag(selectedUserDetail.id);
                        const updated = await api.getAdminUser(selectedUserDetail.id);
                        setSelectedUserDetail(updated);
                      }}
                      className={`px-3 py-2 rounded-xl text-xs font-semibold border transition ${
                        selectedUserDetail.is_flagged
                          ? "bg-amber-500/20 text-amber-200 border-amber-500/40"
                          : "btn-ghost text-secondary hover:text-amber-300"
                      }`}
                    >
                      {selectedUserDetail.is_flagged ? "Remove Watch" : "Flag Watch"}
                    </button>

                    {/* Freeze Account Button */}
                    <button
                      disabled={userActionWorking}
                      onClick={async () => {
                        await handleToggleUserFreeze(selectedUserDetail.id);
                        const updated = await api.getAdminUser(selectedUserDetail.id);
                        setSelectedUserDetail(updated);
                      }}
                      className={`px-3 py-2 rounded-xl text-xs font-semibold border transition ${
                        selectedUserDetail.is_frozen
                          ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/40"
                          : "bg-rose-500/20 text-rose-200 border-rose-500/40 hover:bg-rose-500/30"
                      }`}
                    >
                      {selectedUserDetail.is_frozen ? "Unfreeze Account" : "Freeze Account"}
                    </button>
                  </div>
                </div>

                {/* Recent Transactions List */}
                <div className="space-y-2">
                  <h4 className="text-xs uppercase font-bold tracking-wider text-secondary">
                    Recent Account Transactions
                  </h4>
                  {selectedUserDetail.recent_transactions?.length > 0 ? (
                    <div className="divide-y divide-white/5 rounded-xl bg-white/5 overflow-hidden text-xs font-mono">
                      {selectedUserDetail.recent_transactions.map((t: any) => (
                        <div key={t.id} className="p-3 flex items-center justify-between">
                          <div>
                            <span className="text-cream font-bold text-sm">#{t.id}</span> •{" "}
                            <span className="text-lavender uppercase text-xs font-semibold">{t.kind}</span>
                            {t.is_legacy_test_data && (
                              <span className="ml-2 px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                Legacy Test Data
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-peach-400 font-bold text-sm">৳{Number(t.amount_bdt).toLocaleString("en-IN")}</span>
                            <span className="text-xs px-2.5 py-0.5 rounded-full bg-white/10 text-secondary uppercase font-semibold">
                              {t.status}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 rounded-xl bg-white/5 text-center text-sm text-secondary">
                      No recent transactions recorded.
                    </div>
                  )}
                </div>

                {/* Recent Alerts List in User Modal */}
                {selectedUserDetail.recent_alerts?.length > 0 && (
                  <div className="space-y-2 pt-2 border-t border-white/5">
                    <h4 className="text-xs uppercase font-bold tracking-wider text-secondary">
                      Recent Account Alerts
                    </h4>
                    <div className="space-y-2">
                      {selectedUserDetail.recent_alerts.map((al: any) => (
                        <div key={al.id} className="p-3 rounded-xl bg-white/5 border border-white/5 text-xs space-y-1.5">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-cream text-sm">Alert #{al.id}: {al.alert_type}</span>
                            <div className="flex items-center gap-2">
                              {al.is_legacy_test_data && (
                                <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                  Legacy Test Data
                                </span>
                              )}
                              <span className="px-2.5 py-0.5 rounded text-xs uppercase font-bold bg-white/10 text-lavender">
                                {al.status}
                              </span>
                            </div>
                          </div>
                          {al.is_legacy_test_data && (
                            <p className="text-xs text-amber-300/90 italic">
                              Pre-migration test simulation before student tier calibration.
                            </p>
                          )}
                          <p className="text-xs text-secondary leading-relaxed">{al.detection_reasons}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Change Account Tier Modal (Requires Mandatory Reason Code) */}
          {tierModalOpen && (
            <div className="fixed inset-0 z-50 bg-plum-950/90 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="glass rounded-3xl p-6 sm:p-8 max-w-md w-full border border-white/10 shadow-2xl space-y-4 animate-in fade-in zoom-in-95">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold text-cream flex items-center gap-2">
                    <Sparkles size={16} className="text-peach-400" />
                    <span>Change Tier & Regulatory Limits</span>
                  </h3>
                  <button onClick={() => setTierModalOpen(false)} className="text-secondary hover:text-cream text-lg">
                    ✕
                  </button>
                </div>

                <p className="text-xs text-lavender">
                  Administrative action: Setting an account tier updates platform limits. A
                  mandatory reason code is required for the immutable security audit log.
                </p>

                <form onSubmit={handleAdminChangeTierSubmit} className="space-y-4 pt-1">
                  <div>
                    <label className="block text-xs uppercase tracking-wider text-secondary mb-1">
                      Target Account Tier
                    </label>
                    <select
                      value={newTier}
                      onChange={(e) => setNewTier(e.target.value)}
                      className="field-select w-full text-xs"
                    >
                      <option value="personal">Personal Tier (৳50k single / ৳100k daily)</option>
                      <option value="verified">Verified Tier (৳100k single / ৳250k daily)</option>
                      <option value="business">Business Enterprise (৳1M single / ৳5M daily)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs uppercase tracking-wider text-secondary mb-1">
                      Mandatory Reason Code *
                    </label>
                    <select
                      value={tierReasonCode}
                      onChange={(e) => setTierReasonCode(e.target.value)}
                      required
                      className="field-select w-full text-xs"
                    >
                      <option value="kyc_documents_verified">kyc_documents_verified (NID/Smart Card Verified)</option>
                      <option value="trade_license_approved">trade_license_approved (Municipal Trade License Validated)</option>
                      <option value="tin_bin_validated">tin_bin_validated (TIN & BIN Form Validated)</option>
                      <option value="corporate_onboarding">corporate_onboarding (Corporate Account Formal Onboarding)</option>
                      <option value="risk_downgrade">risk_downgrade (Administrative Risk Mitigation Downgrade)</option>
                      <option value="compliance_review">compliance_review (Periodic Regulatory Compliance Review)</option>
                      <option value="manual_override">manual_override (Executive Manual Authorization)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs uppercase tracking-wider text-secondary mb-1">
                      Audit Notes / Documentation Reference
                    </label>
                    <textarea
                      rows={2}
                      value={tierNotes}
                      onChange={(e) => setTierNotes(e.target.value)}
                      placeholder="e.g. Verified trade license certificate #TL-2026-9921 from Dhaka North City Corp"
                      className="field-input w-full text-xs resize-none"
                    />
                  </div>

                  <div className="flex items-center justify-end gap-2.5 pt-2">
                    <button
                      type="button"
                      onClick={() => setTierModalOpen(false)}
                      className="btn-ghost px-4 py-2 rounded-xl text-xs font-semibold"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={userActionWorking}
                      className="btn-peach px-5 py-2 rounded-xl text-xs font-semibold shadow-glow-peach disabled:opacity-50"
                    >
                      {userActionWorking ? "Saving…" : "Confirm Tier Change"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
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
                    className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                      al.severity === "critical"
                        ? "bg-rose-500/30 text-rose-200 border border-rose-500/40"
                        : al.severity === "high"
                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                        : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                    }`}
                  >
                    {al.severity} Severity
                  </span>

                  <div className="flex items-center gap-1.5">
                    {al.is_legacy_test_data && (
                      <span
                        className="px-2.5 py-1 rounded text-xs font-bold uppercase bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        title={al.legacy_explanation}
                      >
                        Legacy Test Data
                      </span>
                    )}
                    <span
                      className={`px-2.5 py-1 rounded text-xs font-bold uppercase ${
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
                </div>

                <div>
                  <div className="text-sm font-bold text-cream">{al.alert_type}</div>
                  <div className="text-xs text-lavender mt-0.5">
                    User: @{al.user?.handle} ({maskPhone(al.user?.phone)})
                    {al.amount_bdt && ` • ৳${Number(al.amount_bdt).toLocaleString("en-IN")}`}
                  </div>
                </div>

                <div className="bg-black/20 rounded-xl p-3 border border-white/5 text-xs text-secondary leading-relaxed">
                  {al.detection_reasons}
                </div>

                {al.is_legacy_test_data && (
                  <div className="text-xs text-amber-300/90 bg-amber-500/10 border border-amber-500/20 p-2.5 rounded-lg">
                    <span className="font-bold text-amber-300">Legacy Notice:</span> {al.legacy_explanation || "Pre-migration simulation data before student profile calibration."}
                  </div>
                )}

                {al.investigation_notes && (
                  <div className="text-xs text-lavender/90 bg-white/5 p-2.5 rounded-lg">
                    <span className="font-semibold text-cream">Notes:</span> {al.investigation_notes}
                  </div>
                )}

                <div className="flex items-center justify-between pt-2 border-t border-white/10 text-xs">
                  <span className="text-xs text-secondary">
                    {new Date(al.created_at).toLocaleString()}
                  </span>
                  <button
                    onClick={() => {
                      setSelectedAlert(al);
                      setNewAlertStatus(al.status);
                      setAlertModalOpen(true);
                    }}
                    className="btn-peach px-3.5 py-1.5 rounded-lg text-xs font-bold"
                  >
                    Triage & Update
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Audit Logs Section */}
          <div className="mt-8 pt-6 border-t border-white/10">
            <h3 className="text-base font-bold text-cream mb-3 flex items-center gap-2">
              <Clock size={16} className="text-peach-400" />
              Administrative Security Audit Trail
            </h3>
            <div className="glass rounded-2xl overflow-hidden border border-white/5">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/5 text-secondary uppercase text-xs font-bold tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Time</th>
                    <th className="px-4 py-3">Operator</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Target</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {auditLogs.slice(0, 8).map((log) => (
                    <tr key={log.id}>
                      <td className="px-4 py-2.5 font-mono text-xs text-secondary">
                        {new Date(log.created_at).toLocaleTimeString()}
                      </td>
                      <td className="px-4 py-2.5 font-bold text-cream text-sm">{log.admin}</td>
                      <td className="px-4 py-2.5 text-peach-300 font-mono text-xs font-semibold">{log.action}</td>
                      <td className="px-4 py-2.5 text-lavender font-medium text-xs">{log.target_type} #{log.target_id || "global"}</td>
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
                <span className="flex items-center gap-2 text-base font-bold text-cream">
                  <Database size={20} className="text-peach-400" /> Database Engine
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-xs bg-emerald-500/20 text-emerald-300 font-bold">
                  CONNECTED
                </span>
              </div>
              <div className="text-xs space-y-1.5 text-secondary">
                <div>Dialect: <span className="text-cream font-mono">SQLite (WAL Mode)</span></div>
                <div>Storage Path: <span className="text-cream font-mono text-xs">{systemStatus?.database?.path}</span></div>
                <div>Users Table: <span className="text-cream font-mono">{systemStatus?.database?.tables?.users} rows</span></div>
                <div>Ledger Transactions: <span className="text-cream font-mono">{systemStatus?.database?.tables?.transactions} rows</span></div>
                <div>Fraud Assessments: <span className="text-cream font-mono">{systemStatus?.database?.tables?.fraud_assessments} rows</span></div>
              </div>
            </div>

            {/* Fraud Engine Card */}
            <div className="glass-strong rounded-3xl p-5 border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-base font-bold text-cream">
                  <ShieldCheck size={20} className="text-emerald-400" /> Fraud Engine
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-xs bg-emerald-500/20 text-emerald-300 font-bold">
                  ACTIVE
                </span>
              </div>
              <div className="text-xs space-y-1.5 text-secondary">
                <div>Version: <span className="text-cream font-mono">{systemStatus?.fraud_detection_engine?.version}</span></div>
                <div>Active Security Rules: <span className="text-cream font-mono">7 Deterministic Rules</span></div>
                <div>ML Behavioral Anomaly Scorer: <span className="text-emerald-300 font-semibold">Operational</span></div>
                <div>Avg Assessment Latency: <span className="text-peach-400 font-mono font-bold">{systemStatus?.fraud_detection_engine?.average_evaluation_latency_ms ?? 0} ms</span></div>
              </div>
            </div>

            {/* AI Cascade Infrastructure */}
            <div className="glass-strong rounded-3xl p-5 border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-base font-bold text-cream">
                  <Cpu size={20} className="text-peach-400" /> AI Cascade Models
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-xs bg-emerald-500/20 text-emerald-300 font-bold">
                  CASCADING
                </span>
              </div>
              <div className="text-xs space-y-1.5 text-secondary">
                <div>
                  Local Ollama:{" "}
                  <span className={systemStatus?.ai_cascade_infrastructure?.ollama_local?.reachable ? "text-emerald-300 font-semibold" : "text-rose-300 font-semibold"}>
                    {systemStatus?.ai_cascade_infrastructure?.ollama_local?.reachable ? "Reachable" : "Offline"}
                  </span>
                </div>
                <div>
                  Active Local Model:{" "}
                  <span className="text-cream font-mono text-xs">
                    {systemStatus?.ai_cascade_infrastructure?.ollama_local?.active_model?.join(", ") || "qwen2.5:7b"}
                  </span>
                </div>
                <div>Grok (xAI): <span className="text-cream font-medium">{systemStatus?.ai_cascade_infrastructure?.grok_xai?.configured ? "Configured" : "Available"}</span></div>
                <div>Deterministic Fallback: <span className="text-emerald-400 font-semibold">Always Active</span></div>
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
              <div className="w-9 h-9 rounded-xl bg-peach-500/20 border border-peach-500/30 flex items-center justify-center text-peach-400">
                <Bot size={20} />
              </div>
              <div>
                <h3 className="text-base font-bold text-cream">Admin Intelligence AI</h3>
                <p className="text-xs text-emerald-300 font-medium">Live Database Connected • Multi-Turn Voice AI</p>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setIsVoiceMuted(!isVoiceMuted)}
                className={`p-1.5 rounded-lg transition ${
                  isVoiceMuted
                    ? "text-lavender/40 hover:text-lavender bg-white/5"
                    : "text-peach-400 bg-peach-500/10 hover:bg-peach-500/20"
                }`}
                title={isVoiceMuted ? "Enable TTS Voice Audio" : "Mute TTS Voice Audio"}
              >
                {isVoiceMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
              </button>
              <button
                type="button"
                onClick={() => setAiDrawerOpen(false)}
                className="btn-ghost p-1.5 rounded-lg text-secondary hover:text-cream"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Quick Query Preset Chips */}
          <div className="px-4 py-2.5 border-b border-white/5 flex gap-2 overflow-x-auto text-xs bg-black/20">
            <button
              onClick={() => handleSendAiQuery("check the recent activity in my system")}
              className="px-3 py-1.5 rounded-full bg-peach-500/20 text-peach-300 hover:bg-peach-500/30 whitespace-nowrap transition border border-peach-500/30 font-semibold"
            >
              ⚡ Recent system activity
            </button>
            <button
              onClick={() => handleSendAiQuery("How many suspicious transactions occurred today?")}
              className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-secondary hover:text-cream whitespace-nowrap transition font-medium"
            >
              ⚡ Suspicious today
            </button>
            <button
              onClick={() => handleSendAiQuery("Which transactions have the highest risk scores?")}
              className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-secondary hover:text-cream whitespace-nowrap transition font-medium"
            >
              ⚡ Highest risk txns
            </button>
            <button
              onClick={() => handleSendAiQuery("Show me the latest fraud alerts")}
              className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-secondary hover:text-cream whitespace-nowrap transition font-medium"
            >
              ⚡ Latest alerts
            </button>
            <button
              onClick={() => handleSendAiQuery("What is the current transaction volume?")}
              className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-secondary hover:text-cream whitespace-nowrap transition font-medium"
            >
              ⚡ Total volume
            </button>
          </div>

          {/* Chat History */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 text-sm">
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
                      ? "bg-peach-500 text-plum-950 font-semibold rounded-tr-sm"
                      : "bg-white/10 text-cream rounded-tl-sm border border-white/5 font-medium"
                  }`}
                >
                  <div>{msg.text}</div>
                  {/* Visual Live Recent Completed Transactions inside bubble */}
                  {msg.data?.recent_completed_transactions && msg.data.recent_completed_transactions.length > 0 && (
                    <div className="mt-2.5 pt-2 border-t border-white/10 space-y-2 text-xs">
                      <div className="text-xs uppercase font-extrabold text-peach-300 tracking-wider">
                        Live Completed Activity ({msg.data.recent_completed_transactions.length} txns · ৳{msg.data.recent_volume_bdt?.toLocaleString()} vol)
                      </div>
                      <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                        {msg.data.recent_completed_transactions.map((tx: any) => (
                          <div key={tx.id} className="flex items-center justify-between bg-black/25 px-2.5 py-1.5 rounded-lg border border-white/5 text-xs">
                            <div className="flex items-center gap-1.5 truncate">
                              <span className="text-peach-400 font-mono font-bold">#{tx.id}</span>
                              <span className="text-cream truncate font-medium">@{tx.sender} → @{tx.recipient}</span>
                              {tx.note && <span className="text-lavender/70 truncate">({tx.note})</span>}
                            </div>
                            <div className="font-mono font-bold text-peach-300 shrink-0 ml-2">
                              ৳{tx.amount_bdt.toLocaleString()}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {msg.data?.patterns && (
                    <div className="mt-2 pt-2 border-t border-white/10 text-xs space-y-1">
                      {msg.data.patterns.map((p: any, idx: number) => (
                        <div key={idx} className="flex justify-between">
                          <span>{p.rule}</span>
                          <span className="font-mono font-bold">{p.occurrences}x</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <span className="text-xs text-lavender/70 mt-1 px-1 font-medium">
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

          {/* Voice status indicator banner */}
          {isRecordingVoice && (
            <div className="px-3 py-1.5 bg-peach-500/20 border-t border-peach-500/30 text-xs text-peach-300 flex items-center justify-between animate-pulse">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-peach-500 animate-ping" />
                Listening to your voice command, Boss...
              </span>
              <span className="font-semibold text-peach-400">Tap mic to finish</span>
            </div>
          )}
          {isTranscribingVoice && (
            <div className="px-3 py-1.5 bg-white/5 border-t border-white/10 text-xs text-lavender flex items-center gap-2">
              <Loader2 size={14} className="animate-spin text-peach-400" />
              <span>Transcribing voice with Whisper STT...</span>
            </div>
          )}

          {/* Input Bar with Voice Control */}
          <div className="p-3 border-t border-white/10 bg-black/20 flex items-center gap-2">
            <input
              type="text"
              placeholder={isRecordingVoice ? "Listening to your voice..." : "Ask anything or talk to AI by voice…"}
              value={aiQuery}
              onChange={(e) => setAiQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendAiQuery()}
              disabled={isRecordingVoice || isTranscribingVoice}
              className="field-input flex-1 text-sm py-2 px-3"
            />
            {/* Voice Control Mic Button */}
            <button
              type="button"
              onClick={() => (isRecordingVoice ? stopVoiceRecording() : startVoiceRecording())}
              disabled={aiLoading || isTranscribingVoice}
              title={isRecordingVoice ? "Tap to stop listening" : "Tap to speak to AI (Voice Control)"}
              className={`p-2.5 rounded-xl text-xs font-semibold flex items-center justify-center transition-all ${
                isRecordingVoice
                  ? "bg-peach-500 text-plum-950 animate-pulse shadow-lg shadow-peach-500/40 scale-105"
                  : isTranscribingVoice
                  ? "bg-white/10 text-cream/40"
                  : "bg-white/10 hover:bg-white/15 text-peach-400 border border-peach-500/20"
              }`}
            >
              {isTranscribingVoice ? (
                <Loader2 size={16} className="animate-spin text-peach-300" />
              ) : isRecordingVoice ? (
                <MicOff size={16} />
              ) : (
                <Mic size={16} />
              )}
            </button>
            <button
              onClick={() => handleSendAiQuery()}
              disabled={aiLoading || isRecordingVoice || isTranscribingVoice || !aiQuery.trim()}
              className="btn-peach px-3.5 py-2 rounded-xl text-xs font-bold flex items-center justify-center disabled:opacity-40"
              title="Send text query"
            >
              <Send size={15} />
            </button>
          </div>
        </div>
      )}

      {/* Review Assessment Modal */}
      {reviewModalOpen && selectedAssessment && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-strong rounded-3xl p-6 max-w-lg w-full border border-white/15 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <h3 className="text-base font-bold text-cream">
                Review Assessment #{selectedAssessment.id}
              </h3>
              <button onClick={() => setReviewModalOpen(false)} className="text-secondary hover:text-cream">
                <X size={18} />
              </button>
            </div>

            <div className="text-xs space-y-2 text-lavender bg-white/5 p-3.5 rounded-xl">
              <div>Amount: <span className="font-bold text-cream font-mono text-sm">৳{selectedAssessment.amount_bdt}</span></div>
              <div>Risk Score: <span className="font-bold text-peach-400 font-mono text-sm">{selectedAssessment.risk_score}</span> ({selectedAssessment.risk_level})</div>
              <div>Initiator: <span className="text-cream font-semibold">@{selectedAssessment.initiator?.handle}</span></div>
              <div className="pt-1 text-xs text-cream leading-relaxed">
                Reasons: {selectedAssessment.reasons?.join("; ")}
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-cream mb-1.5">
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
                Triage Decision Status
              </label>
              <select
                value={newAlertStatus}
                onChange={(e) => setNewAlertStatus(e.target.value)}
                className="field-select w-full text-xs font-medium"
              >
                <option value="investigating">Under Investigation</option>
                <option value="confirmed_fraud">Confirmed Fraud (Unauthorized / Stolen)</option>
                <option value="not_fraud">Not Fraud (Verified Legitimate Customer)</option>
                <option value="inconclusive">Inconclusive (Insufficient Telemetry)</option>
                <option value="false_positive">False Positive</option>
                <option value="new">Keep New / Unassigned</option>
              </select>
            </div>

            {["confirmed_fraud", "not_fraud", "inconclusive", "false_positive", "resolved"].includes(newAlertStatus) && (
              <div>
                <label className="block text-xs font-medium text-cream mb-1">
                  Mandatory Resolution Reason Code <span className="text-peach-400">*</span>
                </label>
                <select
                  value={alertReasonCode}
                  onChange={(e) => setAlertReasonCode(e.target.value)}
                  className="field-select w-full text-xs"
                >
                  <option value="verified_legitimate">Verified Legitimate Customer Behavior</option>
                  <option value="stolen_credentials">Stolen Credentials / Phishing Confirmed</option>
                  <option value="phishing_mule">Identified Mule Funnel Account</option>
                  <option value="friendly_fraud">Friendly Fraud / Disputed Family Use</option>
                  <option value="unauthorized_device">Unauthorized Device / Sim Swap</option>
                  <option value="inconclusive_evidence">Inconclusive / Customer Unreachable</option>
                </select>
              </div>
            )}

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
              <div>
                Sender:{" "}
                <span className="text-cream font-mono font-semibold">
                  {selectedTxn.kind === "cash_in"
                    ? "🏦 Cash-In / Opening Deposit"
                    : `@${selectedTxn.sender?.handle ?? "unknown"}`}
                </span>{" "}
                {selectedTxn.kind !== "cash_in" && selectedTxn.sender?.phone && (
                  <span>({maskPhone(selectedTxn.sender.phone)})</span>
                )}
              </div>
              <div>
                Recipient:{" "}
                <span className="text-cream font-mono font-semibold">
                  {selectedTxn.kind === "cash_out"
                    ? "🏧 MFS Agent Cash-Out"
                    : selectedTxn.recipient?.handle
                    ? `@${selectedTxn.recipient.handle}`
                    : "N/A"}
                </span>
              </div>
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
