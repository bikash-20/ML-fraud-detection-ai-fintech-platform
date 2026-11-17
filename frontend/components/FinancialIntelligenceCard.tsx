"use client";

import { useEffect, useState } from "react";
import {
  CategorySpendBreakdown,
  FinancialIntelligence,
  FinancialLiteracyTopic,
  FinancialRecommendation,
  api,
} from "@/lib/api";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Lightbulb,
  PieChart,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

interface Props {
  userId: number;
  onAskAI?: (prompt: string) => void;
}

export function FinancialIntelligenceCard({ userId, onAskAI }: Props) {
  const [data, setData] = useState<FinancialIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "recommendations" | "literacy">("overview");
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [literacyData, setLiteracyData] = useState<{
    topics?: FinancialLiteracyTopic[];
    topic?: string;
    title?: string;
    summary?: string;
    details?: string;
    bangla_summary?: string;
    key_takeaways?: string[];
  } | null>(null);

  const fetchInsights = async () => {
    try {
      setLoading(true);
      const res = await api.getFinancialIntelligence(userId);
      setData(res);
    } catch (e) {
      console.error("Failed to load financial intelligence:", e);
    } finally {
      setLoading(false);
    }
  };

  const loadLiteracy = async (topicSlug?: string) => {
    try {
      const res = await api.getFinancialLiteracy(userId, topicSlug);
      setLiteracyData(res);
      if (topicSlug) setSelectedTopic(topicSlug);
    } catch (e) {
      console.error("Failed to load financial literacy:", e);
    }
  };

  useEffect(() => {
    fetchInsights();
    loadLiteracy();
  }, [userId]);

  if (loading && !data) {
    return (
      <div className="glass-panel rounded-2xl p-6 border border-white/10 animate-pulse space-y-4">
        <div className="h-5 w-48 bg-white/10 rounded"></div>
        <div className="h-20 bg-white/5 rounded-xl"></div>
      </div>
    );
  }

  const score = data?.health_score ?? 70;
  const rating = data?.health_rating ?? "Good";
  const velocity = data?.weekly_velocity_pct ?? 0;

  return (
    <div className="glass-panel rounded-2xl p-6 border border-white/10 shadow-xl relative overflow-hidden backdrop-blur-md">
      {/* Background ambient glow */}
      <div className="absolute -top-16 -right-16 w-44 h-44 bg-peach-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/10 mb-5">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-peach-500/20 to-purple-500/20 border border-peach-500/30 flex items-center justify-center text-peach-300">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold tracking-wide text-white uppercase flex items-center gap-2">
              Financial Intelligence Layer
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono font-medium lowercase">
                live
              </span>
            </h3>
            <p className="text-xs text-white/50">
              Autonomous budget insights, risk scoring & financial literacy
            </p>
          </div>
        </div>

        <button
          onClick={fetchInsights}
          title="Refresh intelligence"
          className="p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="flex gap-2 p-1 bg-black/20 rounded-xl mb-5 text-xs font-medium border border-white/5">
        <button
          onClick={() => setActiveTab("overview")}
          className={`flex-1 py-1.5 px-3 rounded-lg transition-all flex items-center justify-center gap-1.5 ${
            activeTab === "overview"
              ? "bg-gradient-to-r from-peach-500/20 to-purple-500/30 text-white border border-peach-500/30 shadow"
              : "text-white/60 hover:text-white"
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          Health & Spending
        </button>
        <button
          onClick={() => setActiveTab("recommendations")}
          className={`flex-1 py-1.5 px-3 rounded-lg transition-all flex items-center justify-center gap-1.5 ${
            activeTab === "recommendations"
              ? "bg-gradient-to-r from-peach-500/20 to-purple-500/30 text-white border border-peach-500/30 shadow"
              : "text-white/60 hover:text-white"
          }`}
        >
          <Lightbulb className="w-3.5 h-3.5" />
          Recommendations
          {data?.recommendations?.length ? (
            <span className="w-4 h-4 rounded-full bg-peach-500/30 text-[10px] text-peach-200 flex items-center justify-center font-bold">
              {data.recommendations.length}
            </span>
          ) : null}
        </button>
        <button
          onClick={() => {
            setActiveTab("literacy");
            if (!selectedTopic) loadLiteracy("emergency_fund");
          }}
          className={`flex-1 py-1.5 px-3 rounded-lg transition-all flex items-center justify-center gap-1.5 ${
            activeTab === "literacy"
              ? "bg-gradient-to-r from-peach-500/20 to-purple-500/30 text-white border border-peach-500/30 shadow"
              : "text-white/60 hover:text-white"
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          Literacy Assistant
        </button>
      </div>

      {/* TAB 1: OVERVIEW & HEALTH SCORE */}
      {activeTab === "overview" && (
        <div className="space-y-4">
          {/* Health Score Banner */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Score Ring */}
            <div className="p-4 rounded-xl bg-white/5 border border-white/10 flex items-center gap-4">
              <div className="relative w-16 h-16 flex items-center justify-center">
                <svg className="w-16 h-16 transform -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-white/10"
                    strokeWidth="3.5"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    className={
                      score >= 80
                        ? "text-emerald-400"
                        : score >= 60
                        ? "text-peach-400"
                        : "text-rose-400"
                    }
                    strokeDasharray={`${score}, 100`}
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
                <span className="absolute font-mono font-bold text-base text-white">
                  {score}
                </span>
              </div>
              <div>
                <div className="text-[10px] text-white/50 uppercase tracking-wider font-semibold">
                  Budget Health
                </div>
                <div className="text-sm font-semibold text-white">{rating}</div>
                <div className="text-[11px] text-white/40">Scale of 0–100</div>
              </div>
            </div>

            {/* 30-Day Spending */}
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <div className="text-[10px] text-white/50 uppercase tracking-wider font-semibold">
                30-Day Spending
              </div>
              <div className="text-lg font-bold font-mono text-white mt-0.5">
                ৳{data?.total_spent_30d_bdt ?? "0.00"}
              </div>
              <div className="text-[11px] text-white/40 mt-1">
                {data?.count_30d ?? 0} total debits recorded
              </div>
            </div>

            {/* 7-Day Velocity */}
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <div className="text-[10px] text-white/50 uppercase tracking-wider font-semibold flex items-center justify-between">
                <span>7-Day Velocity</span>
                {velocity > 15 ? (
                  <span className="text-rose-400 flex items-center gap-0.5 text-[10px]">
                    <TrendingUp className="w-3 h-3" /> +{Math.round(velocity)}%
                  </span>
                ) : velocity < -10 ? (
                  <span className="text-emerald-400 flex items-center gap-0.5 text-[10px]">
                    <TrendingDown className="w-3 h-3" /> {Math.round(velocity)}%
                  </span>
                ) : (
                  <span className="text-white/60 text-[10px]">Steady</span>
                )}
              </div>
              <div className="text-lg font-bold font-mono text-white mt-0.5">
                ৳{data?.total_spent_7d_bdt ?? "0.00"}
              </div>
              <div className="text-[11px] text-white/40 mt-1">
                {velocity > 20
                  ? "Elevated pace vs 30d baseline"
                  : velocity < -15
                  ? "Prudent saving pace"
                  : "Within normal limits"}
              </div>
            </div>
          </div>

          {/* Category Spend Distribution */}
          <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-white/80 flex items-center gap-1.5">
                <PieChart className="w-3.5 h-3.5 text-peach-300" />
                Spending by Category (30 Days)
              </span>
              <span className="text-[11px] text-white/40 font-mono">
                {data?.category_breakdown?.length ?? 0} active tags
              </span>
            </div>

            {data?.category_breakdown && data.category_breakdown.length > 0 ? (
              <div className="space-y-2">
                {/* Composite bar */}
                <div className="h-2 w-full rounded-full bg-white/10 overflow-hidden flex">
                  {data.category_breakdown.map((cat, idx) => {
                    const colors = [
                      "bg-peach-400",
                      "bg-purple-400",
                      "bg-emerald-400",
                      "bg-amber-400",
                      "bg-rose-400",
                      "bg-indigo-400",
                    ];
                    return (
                      <div
                        key={cat.category}
                        style={{ width: `${Math.max(4, cat.percentage)}%` }}
                        className={`${colors[idx % colors.length]} transition-all`}
                        title={`${cat.category}: ${cat.percentage}% (৳${cat.amount_bdt})`}
                      />
                    );
                  })}
                </div>

                {/* Legend list */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1">
                  {data.category_breakdown.map((cat, idx) => {
                    const colors = [
                      "text-peach-300",
                      "text-purple-300",
                      "text-emerald-300",
                      "text-amber-300",
                      "text-rose-300",
                      "text-indigo-300",
                    ];
                    return (
                      <div
                        key={cat.category}
                        className="text-[11px] p-2 rounded-lg bg-black/20 border border-white/5 flex items-center justify-between"
                      >
                        <span className={`font-medium capitalize ${colors[idx % colors.length]}`}>
                          {cat.category}
                        </span>
                        <span className="font-mono text-white/70">
                          ৳{cat.amount_bdt}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <p className="text-xs text-white/40 italic py-2">
                No categorized spending recorded in the last 30 days.
              </p>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: PERSONALIZED BUDGET RECOMMENDATIONS */}
      {activeTab === "recommendations" && (
        <div className="space-y-3">
          {data?.recommendations && data.recommendations.length > 0 ? (
            data.recommendations.map((rec) => (
              <div
                key={rec.id}
                className="p-3.5 rounded-xl bg-white/5 border border-white/10 hover:border-peach-500/30 transition-all space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                        rec.priority === "high"
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                          : rec.priority === "medium"
                          ? "bg-peach-500/20 text-peach-300 border border-peach-500/30"
                          : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      }`}
                    >
                      {rec.priority} priority
                    </span>
                    <h4 className="text-xs font-semibold text-white">{rec.title}</h4>
                  </div>
                  <span className="text-[10px] text-white/40 capitalize font-mono">
                    {rec.category}
                  </span>
                </div>

                <p className="text-xs text-white/70 leading-relaxed">
                  {rec.description}
                </p>

                {onAskAI && (
                  <div className="pt-1 flex justify-end">
                    <button
                      onClick={() => onAskAI(`How can I ${rec.title.toLowerCase()}?`)}
                      className="text-[11px] px-2.5 py-1 rounded-lg bg-peach-500/10 hover:bg-peach-500/20 text-peach-300 border border-peach-500/20 flex items-center gap-1 transition-colors"
                    >
                      <Sparkles className="w-3 h-3" />
                      Ask AI Guide
                    </button>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="p-6 text-center text-xs text-white/50">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2 opacity-80" />
              Your finances look balanced! No urgent budget interventions needed.
            </div>
          )}
        </div>
      )}

      {/* TAB 3: FINANCIAL LITERACY ASSISTANT */}
      {activeTab === "literacy" && (
        <div className="space-y-4">
          {/* Topic Pills */}
          <div className="flex flex-wrap gap-1.5">
            {[
              { id: "emergency_fund", label: "Emergency Fund" },
              { id: "50_30_20", label: "50/30/20 Rule" },
              { id: "fraud_prevention", label: "Fraud Security" },
              { id: "double_entry", label: "Double-Entry Ledger" },
              { id: "festival_savings", label: "Festival Planning" },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => loadLiteracy(t.id)}
                className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all ${
                  selectedTopic === t.id
                    ? "bg-peach-500/20 text-peach-200 border-peach-500/40 font-semibold"
                    : "bg-white/5 text-white/60 border-white/10 hover:text-white"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Detailed Topic Card */}
          {literacyData && (
            <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
              <div>
                <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-peach-300" />
                  {literacyData.title ?? "Financial Literacy Guide"}
                </h4>
                <p className="text-xs text-white/50 mt-1">
                  {literacyData.summary}
                </p>
              </div>

              {literacyData.bangla_summary && (
                <div className="p-2.5 rounded-lg bg-black/20 border border-white/5 text-xs text-peach-200/90 leading-relaxed font-sans">
                  💡 {literacyData.bangla_summary}
                </div>
              )}

              {literacyData.details && (
                <div className="text-xs text-white/70 leading-relaxed whitespace-pre-line border-t border-white/5 pt-2">
                  {literacyData.details}
                </div>
              )}

              {literacyData.key_takeaways && (
                <div className="space-y-1.5 pt-1">
                  <div className="text-[10px] font-semibold text-white/50 uppercase tracking-wider">
                    Key Principles
                  </div>
                  <ul className="space-y-1 text-xs text-white/70 list-disc list-inside">
                    {literacyData.key_takeaways.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {onAskAI && (
                <div className="pt-2 flex justify-end">
                  <button
                    onClick={() =>
                      onAskAI(
                        `Explain ${literacyData.title || selectedTopic} and how I should apply it to my wallet`
                      )
                    }
                    className="text-xs px-3 py-1.5 rounded-lg bg-gradient-to-r from-peach-500/20 to-purple-500/20 hover:from-peach-500/30 hover:to-purple-500/30 text-white border border-peach-500/30 flex items-center gap-1.5 font-medium transition-all"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-peach-300" />
                    Discuss with Financial Assistant
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
