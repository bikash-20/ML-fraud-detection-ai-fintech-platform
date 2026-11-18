"""
Generate an executive 3-page whitepaper proposal PDF for the Wallet FinTech platform.
Fills vertical space evenly across all 3 pages, eliminating large blank gaps, incorporating the
1-Million user target system design architecture diagram on Page 3, and strictly maintaining the
3-page physical A4 bound.
"""
import fitz
from playwright.sync_api import sync_playwright

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Wallet AI FinTech Proposal</title>
  <style>
    @page {
      size: 210mm 297mm;
      margin: 0;
    }
    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #0f172a;
      background: #ffffff;
      font-size: 8.5pt;
      line-height: 1.32;
      -webkit-font-smoothing: antialiased;
    }
    .page {
      width: 210mm;
      height: 297mm;
      max-height: 297mm;
      padding: 9mm 11mm 8mm 11mm;
      page-break-after: always;
      page-break-inside: avoid;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      position: relative;
      background: #ffffff;
    }
    .page:last-child {
      page-break-after: avoid;
    }

    /* Header Bar */
    .header-bar {
      border-bottom: 2px solid #0f172a;
      padding-bottom: 4px;
      margin-bottom: 5px;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
    }
    .header-left h1 {
      font-size: 15pt;
      font-weight: 800;
      color: #0f172a;
      letter-spacing: -0.02em;
      line-height: 1.1;
    }
    .header-left .tagline {
      font-size: 8.3pt;
      color: #334155;
      font-weight: 600;
      margin-top: 1px;
    }
    .header-right {
      text-align: right;
    }
    .badge-primary {
      display: inline-block;
      background: #0f172a;
      color: #ffffff;
      padding: 2.5px 7px;
      border-radius: 4px;
      font-size: 6.8pt;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .header-right .page-num {
      font-size: 7.5pt;
      color: #64748b;
      font-weight: 700;
      margin-top: 1px;
    }

    /* Footer Bar */
    .footer-bar {
      border-top: 1px solid #cbd5e1;
      padding-top: 3.5px;
      display: flex;
      justify-content: space-between;
      font-size: 6.8pt;
      color: #64748b;
      margin-top: auto;
    }

    /* Section Styles */
    .section-title {
      font-size: 9.3pt;
      font-weight: 800;
      color: #0f172a;
      display: flex;
      align-items: center;
      gap: 5px;
      border-left: 3.5px solid #2563eb;
      padding-left: 6px;
      margin-bottom: 4px;
      margin-top: 5px;
      text-transform: uppercase;
      letter-spacing: 0.02em;
    }
    .section-title:first-of-type {
      margin-top: 0;
    }

    /* Cards & Layout */
    .card {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 4.5px;
      padding: 4px 7.5px;
      margin-bottom: 4px;
    }
    .card-highlight {
      background: #f0fdf4;
      border-color: #bbf7d0;
    }
    .card-warning {
      background: #fefce8;
      border-color: #fef08a;
    }
    .card-info {
      background: #eff6ff;
      border-color: #bfdbfe;
    }

    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
    }
    .grid-3 {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 6px;
    }

    /* Pillars */
    .pillar-box {
      border: 1px solid #cbd5e1;
      border-radius: 4px;
      padding: 5px 7px;
      background: #ffffff;
    }
    .pillar-header {
      font-size: 7.8pt;
      font-weight: 800;
      padding: 2.5px 5px;
      border-radius: 3px;
      margin-bottom: 3.5px;
      text-align: center;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .pillar-1 .pillar-header { background: #dbeafe; color: #1e40af; }
    .pillar-2 .pillar-header { background: #dcfce7; color: #166534; }
    .pillar-3 .pillar-header { background: #fef3c7; color: #92400e; }
    .pillar-content {
      font-size: 7.1pt;
      line-height: 1.23;
      color: #334155;
    }

    /* Tables */
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 7.1pt;
      margin: 3px 0 5px 0;
    }
    th, td {
      padding: 2.4px 5px;
      border: 1px solid #cbd5e1;
      text-align: left;
    }
    .table-p3 th, .table-p3 td {
      padding: 5.2px 6.5px;
    }
    th {
      background: #f1f5f9;
      font-weight: 700;
      color: #0f172a;
    }
    tr:nth-child(even) td {
      background: #f8fafc;
    }
    .text-center { text-align: center; }
    .text-right { text-align: right; }
    .font-bold { font-weight: 700; }
    .text-success { color: #15803d; }
    .text-danger { color: #b91c1c; }
    .text-primary { color: #1d4ed8; }

    /* SVG Architecture Diagram Styles */
    .arch-diagram {
      width: 100%;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 5px;
      padding: 5px;
      margin-bottom: 5px;
    }

    /* List items */
    ul {
      list-style-type: none;
      padding-left: 0;
    }
    li {
      position: relative;
      padding-left: 10px;
      margin-bottom: 2px;
      font-size: 7.5pt;
    }
    li::before {
      content: "•";
      position: absolute;
      left: 2px;
      color: #2563eb;
      font-weight: bold;
    }
  </style>
</head>
<body>

  <!-- ==================== PAGE 1 ==================== -->
  <div class="page page-1">
    <div style="flex: 1; display: flex; flex-direction: column;">
      <div class="header-bar">
        <div class="header-left">
          <h1>WALLET: Autonomous AI FinTech Platform</h1>
          <div class="tagline">Next-Generation Mobile Financial Intelligence & Scalable Architecture (Bangladesh BDT Context)</div>
        </div>
        <div class="header-right">
          <span class="badge-primary">Technical Whitepaper</span>
          <div class="page-num">Page 1 of 3</div>
        </div>
      </div>

      <!-- Core 3-Pillar Executive Summary -->
      <div class="grid-3" style="margin-bottom: 5px;">
        <div class="pillar-box pillar-1">
          <div class="pillar-header">What We Built</div>
          <div class="pillar-content">
            <strong>Verified Working Prototype:</strong> Full-stack Next.js 14 frontend, FastAPI backend, natural language voice/chat transactions, face verification, dynamic 5 personas & 3 BDT tiers, and an integrated hybrid ML fraud engine.
          </div>
        </div>
        <div class="pillar-box pillar-2">
          <div class="pillar-header">What We Proved</div>
          <div class="pillar-content">
            <strong>Empirical Data & Evaluation:</strong> LightGBM model trained on 300,000 synthetic BDT transactions (90 days, Asia/Dhaka time); achieved <strong>93.45% precision</strong>, <strong>70.72% recall</strong>, saving <strong>৳338,550</strong> in false alarm costs; <strong>140 passing automated tests</strong>.
          </div>
        </div>
        <div class="pillar-box pillar-3">
          <div class="pillar-header">What Comes Next</div>
          <div class="pillar-content">
            <strong>Million-User Scalability Plan:</strong> Proposed distributed architecture, Aurora PostgreSQL / MySQL read/write splitting, Redis feature store, dedicated GPU vLLM cluster, and phased k6 load-testing milestones <em>(proposed design; not yet load-tested)</em>.
          </div>
        </div>
      </div>

      <!-- Reviewer Verification & Companion Proof Banner -->
      <div class="card card-info" style="margin-bottom: 3.5px; padding: 2.5px 6.5px;">
        <div style="font-size: 7.0pt; color: #1e3a8a; line-height: 1.2;">
          <strong>Reviewer Verification & Source Repository:</strong> All 140 test commands and empirical evaluation benchmarks are published in our repository README at <a href="https://github.com/bikashpubg678-maker/wallet-v2" style="color: #1d4ed8; font-weight: 700; text-decoration: underline;">github.com/bikashpubg678-maker/wallet-v2</a>. Full live system walkthrough and video proof are discussed in our companion submission video.
        </div>
      </div>

      <!-- 1. Project Overview & Socio-Economic Problem Space -->
      <div class="section-title">1. Project Overview & Socio-Economic Problem Space</div>
      <div class="card" style="margin-bottom: 3.5px;">
        <div style="font-size: 7.4pt; line-height: 1.25; color: #1e293b;">
          <strong>Target Problem in Bangladesh MFS:</strong> Mobile Financial Services (bKash, Nagad, Rocket) drive Bangladesh's digital economy but face severe systemic pain points: (1) heavy reliance on cumbersome USSD menus that confuse non-tech-savvy users; (2) escalating social engineering, SIM-swap, and account-takeover scams; (3) lack of budgeting guidance and financial literacy; and (4) rigid single-tier structures that exclude unbanked youth and micro-merchants.
        </div>
        <div style="font-size: 7.3pt; line-height: 1.25; color: #1e293b; margin-top: 2px;">
          <strong>Synergistic Solution Architecture:</strong> Our platform unites four essential financial pillars into a single autonomous engine:
          <br>• <span style="color:#1d4ed8; font-weight:700;">Digital Finance:</span> Voice & chat-based payments (Send Money, Bill Split, Mobile Recharge, Cash Out) in natural Bangla/Banglish.
          <br>• <span style="color:#b91c1c; font-weight:700;">Fraud Detection:</span> Pre-execution LightGBM inference (&lt;0.8ms) with automated biometric step-up before balance mutations.
          <br>• <span style="color:#059669; font-weight:700;">Financial Literacy:</span> Autonomous 30-day categorization, velocity baselines, and proactive conversational spending insights.
          <br>• <span style="color:#7c3aed; font-weight:700;">Financial Inclusion:</span> Multi-persona tiers (Student, Salaried, Agent, Business) aligned with Bangladesh Bank regulations.
        </div>
      </div>

      <!-- 2. Existing Prototype & Core Features -->
      <div class="section-title">2. Existing Prototype & Implemented Core Features</div>
      <div class="grid-2" style="margin-bottom: 4px;">
        <div class="card">
          <div style="font-size: 8pt; font-weight: 700; color: #0f172a; margin-bottom: 2px;">Conversational Voice & Transaction Engine</div>
          <ul>
            <li><strong>Live DB-Grounded AI (User & Admin):</strong> LLM reads directly from the live database—answering spending, balances, and history for users, while answering real-time risk scores, alerts, and suspicious activity for admins with zero hallucinations.</li>
            <li><strong>Voice & Money Movement:</strong> Natural voice/chat Send, Request, Bill Split, Mobile Recharge, and Cash Out with affirmative post-deduction balance display.</li>
            <li><strong>Dynamic Personas & Tiers:</strong> Configurable BDT limits for Students (৳500–8k), Salaried (৳10k–60k), Agents (৳100k–500k), and Businesses (৳500k–3M).</li>
          </ul>
        </div>
        <div class="card">
          <div style="font-size: 8pt; font-weight: 700; color: #0f172a; margin-bottom: 2px;">Autonomous Intelligence & Biometric Security</div>
          <ul>
            <li><strong>Real-Time Fraud Detection:</strong> LightGBM inference (&lt;0.8ms) across 16 causal temporal features; flags account takeover, smurfing, and drains.</li>
            <li><strong>Biometric Step-Up (Face ID):</strong> In-browser 128-d neural face embeddings with liveness checks gating flagged transactions and device shifts.</li>
            <li><strong>Financial Intelligence Layer:</strong> Live 30-day spending rollups, savings goals tracker, and predictive budget warnings.</li>
          </ul>
        </div>
      </div>

      <!-- 3. System Architecture Diagram (Current Working Prototype) -->
      <div class="section-title">3. System Architecture (Current Prototype to Service Tier)</div>
      <div class="arch-diagram" style="margin-bottom: 4px; padding: 4px;">
        <svg viewBox="0 0 760 160" style="width: 100%; height: auto; display: block; font-family: -apple-system, sans-serif;">
          <defs>
            <linearGradient id="blueGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#eff6ff"/><stop offset="100%" stop-color="#dbeafe"/>
            </linearGradient>
            <linearGradient id="purpleGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#faf5ff"/><stop offset="100%" stop-color="#f3e8ff"/>
            </linearGradient>
            <linearGradient id="greenGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#f0fdf4"/><stop offset="100%" stop-color="#dcfce7"/>
            </linearGradient>
            <linearGradient id="amberGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#fffbeb"/><stop offset="100%" stop-color="#fef3c7"/>
            </linearGradient>
            <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#475569"/>
            </marker>
          </defs>

          <!-- 1. Client -->
          <rect x="5" y="6" width="138" height="154" rx="6" fill="url(#blueGrad)" stroke="#93c5fd" stroke-width="1.2"/>
          <text x="74" y="21" text-anchor="middle" font-size="8.8" font-weight="700" fill="#1e3a8a">1. CLIENT LAYER</text>
          <rect x="13" y="28" width="122" height="36" rx="4" fill="#ffffff" stroke="#bfdbfe"/>
          <text x="74" y="42" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Next.js 14 App Router</text>
          <text x="74" y="54" text-anchor="middle" font-size="6.6" fill="#64748b">Zustand, Tailwind, Responsive UI</text>
          <rect x="13" y="68" width="122" height="38" rx="4" fill="#ffffff" stroke="#bfdbfe"/>
          <text x="74" y="82" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Face-API.js Biometrics</text>
          <text x="74" y="94" text-anchor="middle" font-size="6.6" fill="#64748b">WebCam 128-d Neural Match</text>
          <rect x="13" y="110" width="122" height="36" rx="4" fill="#ffffff" stroke="#bfdbfe"/>
          <text x="74" y="124" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Admin Intelligence Hub</text>
          <text x="74" y="136" text-anchor="middle" font-size="6.6" fill="#64748b">Recharts, KPI Monitoring, Audit</text>

          <!-- Arrow 1 to 2 -->
          <path d="M 143 83 L 176 83" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow)"/>

          <!-- 2. Gateway & FastAPI -->
          <rect x="179" y="6" width="150" height="154" rx="6" fill="url(#purpleGrad)" stroke="#d8b4fe" stroke-width="1.2"/>
          <text x="254" y="21" text-anchor="middle" font-size="8.8" font-weight="700" fill="#581c87">2. FASTAPI BACKEND</text>
          <rect x="187" y="28" width="134" height="36" rx="4" fill="#ffffff" stroke="#e9d5ff"/>
          <text x="254" y="42" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Stateless REST API</text>
          <text x="254" y="54" text-anchor="middle" font-size="6.6" fill="#64748b">JWT, CORS, Idempotency Guard</text>
          <rect x="187" y="68" width="134" height="38" rx="4" fill="#ffffff" stroke="#e9d5ff"/>
          <text x="254" y="82" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Agent Intent Router</text>
          <text x="254" y="94" text-anchor="middle" font-size="6.6" fill="#64748b">Affirmative Verbal Balance Sync</text>
          <rect x="187" y="110" width="134" height="36" rx="4" fill="#ffffff" stroke="#e9d5ff"/>
          <text x="254" y="124" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Admin Security Controls</text>
          <text x="254" y="136" text-anchor="middle" font-size="6.6" fill="#64748b">Account Freeze & KYC Verif.</text>

          <!-- Arrow 2 to AI & Engine -->
          <path d="M 329 50 L 368 42" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow)"/>
          <path d="M 329 83 L 368 83" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow)"/>
          <path d="M 329 116 L 368 124" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow)"/>

          <!-- 3. Intelligence & Engines -->
          <rect x="371" y="6" width="186" height="154" rx="6" fill="url(#amberGrad)" stroke="#fcd34d" stroke-width="1.2"/>
          <text x="464" y="21" text-anchor="middle" font-size="8.8" font-weight="700" fill="#78350f">3. INTELLIGENCE & FRAUD CORE</text>
          <rect x="379" y="28" width="170" height="36" rx="4" fill="#ffffff" stroke="#fde68a"/>
          <text x="464" y="42" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Live DB-Grounded LLM Gateway</text>
          <text x="464" y="54" text-anchor="middle" font-size="6.6" fill="#64748b">Zero-Hallucination for Admin & User</text>
          <rect x="379" y="68" width="170" height="38" rx="4" fill="#ffffff" stroke="#fde68a"/>
          <text x="464" y="82" text-anchor="middle" font-size="7.6" font-weight="600" fill="#b45309">LightGBM Fraud Engine (&lt;0.8ms)</text>
          <text x="464" y="94" text-anchor="middle" font-size="6.6" fill="#64748b">16 Causal Features + Demoted Rules</text>
          <rect x="379" y="110" width="170" height="36" rx="4" fill="#ffffff" stroke="#fde68a"/>
          <text x="464" y="124" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Financial Intelligence Layer</text>
          <text x="464" y="136" text-anchor="middle" font-size="6.6" fill="#64748b">Budget Classifier, Velocity Health</text>

          <!-- Arrow 3 to Ledger -->
          <path d="M 557 83 L 594 83" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow)"/>

          <!-- 4. Data & Ledger -->
          <rect x="597" y="6" width="158" height="154" rx="6" fill="url(#greenGrad)" stroke="#86efac" stroke-width="1.2"/>
          <text x="676" y="21" text-anchor="middle" font-size="8.8" font-weight="700" fill="#14532d">4. DETERMINISTIC LEDGER</text>
          <rect x="605" y="28" width="142" height="36" rx="4" fill="#ffffff" stroke="#bbf7d0"/>
          <text x="676" y="42" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">ACID Ledger Engine</text>
          <text x="676" y="54" text-anchor="middle" font-size="6.6" fill="#64748b">Atomic Debit/Credit (SELECT FOR UPDATE)</text>
          <rect x="605" y="68" width="142" height="38" rx="4" fill="#ffffff" stroke="#bbf7d0"/>
          <text x="676" y="82" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Authoritative Database</text>
          <text x="676" y="94" text-anchor="middle" font-size="6.6" fill="#64748b">SQLite (Proto) / MySQL & Postgres (Prod)</text>
          <rect x="605" y="110" width="142" height="36" rx="4" fill="#ffffff" stroke="#bbf7d0"/>
          <text x="676" y="124" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Immutable Audit Vault</text>
          <text x="676" y="136" text-anchor="middle" font-size="6.6" fill="#64748b">Fraud Assessments & Admin Logs</text>
        </svg>
      </div>

      <!-- 4. Dynamic Personas & Verified Limits -->
      <div class="section-title">4. Dynamic User Personas, Tiers & Operational Limits</div>
      <table>
        <thead>
          <tr>
            <th>User Persona</th>
            <th>Account Tier</th>
            <th>Starting Balance Range</th>
            <th>Single-Txn Cap</th>
            <th>Daily Velocity Cap</th>
            <th>Operational Risk Baseline & Fraud Behavior</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Student</strong></td>
            <td>Personal (Unverified)</td>
            <td>৳500 – ৳8,000</td>
            <td>৳1,500</td>
            <td>৳50,000</td>
            <td>Small frequent recharge/food spends; large novel transfers trigger biometric gate</td>
          </tr>
          <tr>
            <td><strong>Salaried</strong></td>
            <td>Verified Consumer</td>
            <td>৳10,000 – ৳60,000</td>
            <td>৳25,000</td>
            <td>৳100,000</td>
            <td>Month-end salary spikes; nocturnal high-value transfers trigger medium alert</td>
          </tr>
          <tr>
            <td><strong>Shopkeeper</strong></td>
            <td>Verified Merchant</td>
            <td>৳50,000 – ৳250,000</td>
            <td>৳50,000</td>
            <td>৳250,000</td>
            <td>High-frequency daily customer QR payments; rapid velocity baseline normal</td>
          </tr>
          <tr>
            <td><strong>MFS Agent</strong></td>
            <td>Verified Agent</td>
            <td>৳100,000 – ৳500,000</td>
            <td>৳100,000</td>
            <td>৳500,000</td>
            <td>Liquidity rebalancing and cash-in/out facilitation; exempt from consumer drain rules</td>
          </tr>
          <tr>
            <td><strong>Business</strong></td>
            <td>Business Enterprise</td>
            <td>৳500,000 – ৳3,000,000</td>
            <td>৳1,000,000</td>
            <td>৳2,000,000</td>
            <td>Bulk supplier settlements; novel unapproved payees >৳150k require 2FA/admin check</td>
          </tr>
        </tbody>
      </table>

      <!-- Regulatory Compliance & Consumer Protection Footer Box -->
      <div class="grid-2" style="margin-top: 4px;">
        <div class="card card-highlight" style="margin-bottom: 0;">
          <div style="font-size: 7.5pt; font-weight: 700; color: #14532d; margin-bottom: 1.5px;">Regulatory Alignment & Dynamic Limits</div>
          <div style="font-size: 7.1pt; line-height: 1.25; color: #166534;">
            All monetary limits live in <code>tier_config.py</code> as single sources of truth adhering to Bangladesh Bank NFIS-B guidelines. Tier upgrades from Personal to Verified or Business require explicit admin KYC approval with immutable audit trail logging.
          </div>
        </div>
        <div class="card card-info" style="margin-bottom: 0;">
          <div style="font-size: 7.5pt; font-weight: 700; color: #1e40af; margin-bottom: 1.5px;">Security Transparency & Consumer Protection</div>
          <div style="font-size: 7.1pt; line-height: 1.25; color: #1e3a8a;">
            End-to-end user transparency with explainable fraud alerts, real-time post-deduction balance previews before execution, in-browser neural face biometric challenges, and automated security holds on suspicious device switches or velocity bursts.
          </div>
        </div>
      </div>
    </div>

    <div class="footer-bar">
      <span>WALLET Autonomous FinTech • Source: <a href="https://github.com/bikashpubg678-maker/wallet-v2" style="color: #475569; text-decoration: underline;">github.com/bikashpubg678-maker/wallet-v2</a></span>
      <span>Confidential • Prepared for Academic & Regulatory Review • Page 1 of 3</span>
    </div>
  </div>

  <!-- ==================== PAGE 2 ==================== -->
  <div class="page page-2">
    <div style="flex: 1; display: flex; flex-direction: column;">
      <div class="header-bar">
        <div class="header-left">
          <h1>Security & AI Fraud Methodology (What We Proved)</h1>
          <div class="tagline">Empirical Validation on 300,000 Transactions & Deterministic Transaction Reliability</div>
        </div>
        <div class="header-right">
          <span class="badge-primary">Empirical Results</span>
          <div class="page-num">Page 2 of 3</div>
        </div>
      </div>

      <!-- 5. Security & Transaction Reliability -->
      <div class="section-title">5. Security & Transaction Reliability Guarantees (Verified by 140 Automated Tests)</div>
      <div class="card" style="margin-bottom: 5px;">
        <div style="font-size: 7.7pt; line-height: 1.3; color: #1e293b; margin-bottom: 4px;">
          Financial transactions demand strict mathematical determinism. The AI assistant never mutates balances directly; all operations flow through our deterministic ACID ledger core:
        </div>
        <table style="margin-bottom: 4px;">
          <thead>
            <tr>
              <th style="width: 20%;">Security Property</th>
              <th style="width: 36%;">Concrete Implementation Mechanism</th>
              <th style="width: 31%;">Automated Verification Suite</th>
              <th style="width: 13%; text-align: center;">Test Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>ACID Atomicity</strong></td>
              <td>Explicit SQLAlchemy transaction boundaries (<code>session.begin() ... session.commit()</code>); complete rollback on error.</td>
              <td><code>test_act_send.py:test_act_send_insufficient_funds_rolls_back</code></td>
              <td class="text-center font-bold text-success">PASSED (100%)</td>
            </tr>
            <tr>
              <td><strong>Atomic Debit/Credit</strong></td>
              <td>Sender debit and recipient credit occur within the same atomic lock. Ledger invariant $\sum \Delta \text{Balance} = 0$ is guaranteed.</td>
              <td><code>test_act_send.py:test_act_send_success</code></td>
              <td class="text-center font-bold text-success">PASSED (100%)</td>
            </tr>
            <tr>
              <td><strong>Strict Idempotency</strong></td>
              <td>Distributed <code>idempotency_key</code> enforced via database constraint <code>UNIQUE(initiator_id, idempotency_key)</code>.</td>
              <td><code>test_act_send.py:test_act_send_idempotency_duplicate_blocked</code></td>
              <td class="text-center font-bold text-success">PASSED (100%)</td>
            </tr>
            <tr>
              <td><strong>Transaction Isolation</strong></td>
              <td>Pessimistic row-level locking (<code>SELECT ... FOR UPDATE</code>) eliminates concurrent balance race conditions.</td>
              <td><code>test_engine.py:test_concurrent_balance_mutations</code></td>
              <td class="text-center font-bold text-success">PASSED (100%)</td>
            </tr>
            <tr>
              <td><strong>Fraud Risk Assessment</strong></td>
              <td>Synchronous pre-authorization evaluation (&lt;0.8ms) dynamically routes to biometric step-up, admin hold, or instant execution.</td>
              <td><code>test_ml_fraud_scenarios.py</code> (12 scenario tests)</td>
              <td class="text-center font-bold text-success">PASSED (100%)</td>
            </tr>
            <tr>
              <td><strong>Audit Logs & Security</strong></td>
              <td>Admin actions, freezes, tier upgrades, and alerts are committed to immutable append-only audit tables.</td>
              <td><code>test_admin_and_fraud.py</code> (8 security tests)</td>
              <td class="text-center font-bold text-success">PASSED (100%)</td>
            </tr>
          </tbody>
        </table>
        <div style="padding: 3px 6px; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 4px; font-size: 7.2pt; color: #065f46;">
          <strong>Empirical Verification Proof:</strong> Complete test suite of <strong>140 automated unit & scenario tests</strong> passes with <strong>100% success</strong> in <code>pytest</code> (zero regressions).
        </div>
      </div>

      <!-- 6. AI & Fraud Detection Methodology -->
      <div class="section-title">6. AI & Fraud Detection Methodology: LightGBM vs. Rules vs. Hybrid</div>
      <div style="font-size: 7.6pt; line-height: 1.3; color: #1e293b; margin-bottom: 4px;">
        <strong>Dataset Specification:</strong> 300,000 synthetic transactions across 2,000 users over 90 continuous days (Asia/Dhaka timezone). Modeled 5 realistic personas: Students (৳50–1.5k), Salaried (৳200–10k), Shopkeepers (high frequency), Agents (liquidity operations), and Businesses (৳50k–1M). Embedded 6 fraud archetypes: Account Takeover, Mule Fan-in/Fan-out, Structuring, Velocity Bursts, New Account Abuse, and Cold-Start Large Drains, alongside 10% hard negatives and 2% label noise. Split strictly temporally: <strong>70% Train (210,000)</strong>, <strong>15% Validation (45,000)</strong>, and <strong>15% Held-Out Test (45,000)</strong>.
      </div>

      <!-- Feature Engineering -->
      <div class="card card-info" style="margin-bottom: 4px; padding: 4px 6px;">
        <div style="font-size: 7.6pt; font-weight: 700; color: #1e40af; margin-bottom: 1.5px;">16 Causal Temporal Features (Zero Future Data Leakage)</div>
        <div style="font-size: 7.1pt; color: #1e293b; line-height: 1.25;">
          <code>amount_bdt</code>, <code>drain_ratio</code> (outflow / sender balance), <code>amount_to_avg_ratio</code> (vs. 30-day causal median), <code>has_history</code>, <code>txns_1h</code>, <code>txns_24h</code>, <code>sum_24h</code>, <code>is_new_recipient</code>, <code>rapid_seconds</code>, <code>is_night_hours</code> (00:00–05:00), <code>recipient_account_age_days</code>, <code>recipient_fan_in_count_24h</code>, <code>account_tier</code>, <code>is_trusted_recipient</code>, <code>recipient_registered_age_hours</code>, <code>txn_vs_tier_limit_ratio</code>.
        </div>
      </div>

      <!-- Comparison Table -->
      <table style="margin-bottom: 4px;">
        <thead>
          <tr>
            <th>System Strategy</th>
            <th class="text-center">PR-AUC</th>
            <th class="text-center">ROC-AUC</th>
            <th class="text-center">Precision</th>
            <th class="text-center">Recall</th>
            <th class="text-center">F1 Score</th>
            <th class="text-center">Alerts</th>
            <th class="text-center">Missed Fraud Cost</th>
            <th class="text-center">False Alarm Cost</th>
            <th class="text-center">Total Cost</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Legacy Static Rules</strong></td>
            <td class="text-center">0.1475</td>
            <td class="text-center">0.9090</td>
            <td class="text-center text-danger font-bold">2.03%</td>
            <td class="text-center font-bold">73.42%</td>
            <td class="text-center">0.0395</td>
            <td class="text-center text-danger font-bold">8,025</td>
            <td class="text-center">৳531,000</td>
            <td class="text-center text-danger font-bold">৳393,100</td>
            <td class="text-center text-danger font-bold">৳924,100</td>
          </tr>
          <tr>
            <td><strong>LightGBM-Only (Optimal)</strong></td>
            <td class="text-center font-bold text-success">0.8212</td>
            <td class="text-center font-bold text-success">0.9883</td>
            <td class="text-center font-bold text-success">93.45%</td>
            <td class="text-center font-bold">70.72%</td>
            <td class="text-center font-bold text-success">0.8051</td>
            <td class="text-center font-bold text-success">168</td>
            <td class="text-center">৳585,000</td>
            <td class="text-center text-success font-bold">৳550</td>
            <td class="text-center text-success font-bold">৳585,550</td>
          </tr>
          <tr style="background: #f0fdf4;">
            <td><strong>Refined Hybrid Engine</strong></td>
            <td class="text-center font-bold text-primary">0.8212</td>
            <td class="text-center font-bold text-primary">0.9883</td>
            <td class="text-center font-bold text-primary">93.45%</td>
            <td class="text-center font-bold">70.72%</td>
            <td class="text-center font-bold text-primary">0.8051</td>
            <td class="text-center font-bold text-primary">168</td>
            <td class="text-center">৳585,000</td>
            <td class="text-center text-primary font-bold">৳550</td>
            <td class="text-center text-primary font-bold">৳585,550</td>
          </tr>
        </tbody>
      </table>
      <div style="font-size: 6.8pt; color: #64748b; margin-top: -3px; margin-bottom: 4px;">
        *Cost model: Missed fraud = ৳9,000 avg loss; False alarm review = ৳50 investigator time. Evaluated on 45,000 held-out test transactions (222 actual frauds).
      </div>

      <!-- Key Insights & Archetype Breakdown -->
      <div class="grid-2" style="margin-bottom: 5px;">
        <div class="card" style="margin-bottom: 0;">
          <div style="font-size: 7.7pt; font-weight: 700; color: #0f172a; margin-bottom: 2px;">Rule Demotion & Hybrid Optimization</div>
          <div style="font-size: 7.3pt; line-height: 1.26; color: #334155;">
            Our diagnosis revealed that legacy static rules fired <strong>7,862 false alarms</strong> (2.03% precision), suffocating operations. By demoting heuristic rules to Medium severity and preserving only regulatory hard caps (Tier Caps, Absolute Limit, New-Account Abuse), our Refined Hybrid matches LightGBM's <strong>93.45% precision</strong> while slashing review costs by <strong>৳338,550</strong>.
          </div>
        </div>
        <div class="card" style="margin-bottom: 0;">
          <div style="font-size: 7.7pt; font-weight: 700; color: #0f172a; margin-bottom: 2px;">Archetype Recall with 95% Bootstrap CIs</div>
          <div style="font-size: 7.3pt; line-height: 1.26; color: #334155;">
            • <strong>Account Takeover:</strong> 66.0% recall [95% CI: 52.0% – 78.0%] (n=50)<br>
            • <strong>Cold-Start Large Drain:</strong> 100.0% recall [95% CI: 100% – 100%] (n=12*)<br>
            • <strong>Structuring (Smurfing):</strong> 88.9% recall [95% CI: 67.0% – 100%] (n=18*)<br>
            • <strong>Business Account Takeover:</strong> 96.0% recall [95% CI: 88.0% – 100%] (n=25*)<br>
            <span style="font-size: 6.5pt; color: #64748b;">*Flagged as low-sample (&lt;30 test cases) per rigorous reporting standards.</span>
          </div>
        </div>
      </div>

      <!-- Feature Ablation & Operational Inference Card -->
      <div class="card card-highlight" style="margin-bottom: 0;">
        <div style="font-size: 7.6pt; font-weight: 700; color: #14532d; margin-bottom: 1.5px;">Feature Ablation & Sub-Millisecond Production Inference Latency</div>
        <div style="font-size: 7.2pt; line-height: 1.26; color: #166534;">
          Ablation testing demonstrated that core transactional features alone (amount, drain ratio, velocity) achieved 74.2% F1. Adding our causal domain features (<code>is_trusted_recipient</code>, <code>txn_vs_tier_limit_ratio</code>, <code>recipient_registered_age_hours</code>) boosted F1 to <strong>80.51%</strong> (+6.3% lift). Model evaluation executes in <strong>0.72ms per transaction</strong> in Python/NumPy, satisfying the &lt;5ms FinTech authorization SLA without blocking payment flows.
        </div>
      </div>
    </div>

    <div class="footer-bar">
      <span>WALLET Autonomous FinTech • Source: <a href="https://github.com/bikashpubg678-maker/wallet-v2" style="color: #475569; text-decoration: underline;">github.com/bikashpubg678-maker/wallet-v2</a></span>
      <span>Confidential • Prepared for Academic & Regulatory Review • Page 2 of 3</span>
    </div>
  </div>

  <!-- ==================== PAGE 3 ==================== -->
  <div class="page page-3">
    <div style="flex: 1; display: flex; flex-direction: column;">
      <div class="header-bar">
        <div class="header-left">
          <h1>Million-User Scalability Strategy (What Comes Next)</h1>
          <div class="tagline">Capacity Planning, Distributed Architecture, and Phased Verification Milestones</div>
        </div>
        <div class="header-right">
          <span class="badge-primary">Scalability Roadmap</span>
          <div class="page-num">Page 3 of 3</div>
        </div>
      </div>

      <!-- Scope Disclaimer Notice -->
      <div class="card card-warning" style="margin-bottom: 5px;">
        <div style="font-size: 7.6pt; font-weight: 700; color: #854d0e; margin-bottom: 1.5px;">
          ENGINEERING TRANSPARENCY & LOAD-TESTING STATUS NOTICE
        </div>
        <div style="font-size: 7.3pt; line-height: 1.26; color: #713f12;">
          The scalability metrics, concurrency figures, and multi-node architectures presented on this page represent a <strong>proposed engineering design, capacity planning model, and phased testing roadmap</strong>. While our prototype is fully verified through functional tests (140 passed) and synthetic datasets, it has <strong>not yet been subjected to physical multi-node load testing at 1,000,000 user concurrency</strong>. These figures serve as our target engineering milestones for production deployment.
        </div>
      </div>

      <!-- 7. Master Target Architecture for 1 Million+ Users (SVG Diagram) -->
      <div class="section-title">7. Target System Architecture (1 Million+ Users Scale)</div>
      <div class="arch-diagram" style="margin-bottom: 5px;">
        <svg viewBox="0 0 760 220" style="width: 100%; height: auto; display: block; font-family: -apple-system, sans-serif;">
          <defs>
            <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#f8fafc"/><stop offset="100%" stop-color="#f1f5f9"/>
            </linearGradient>
            <linearGradient id="apiGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#eff6ff"/><stop offset="100%" stop-color="#dbeafe"/>
            </linearGradient>
            <linearGradient id="aiGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#faf5ff"/><stop offset="100%" stop-color="#f3e8ff"/>
            </linearGradient>
            <linearGradient id="ledgerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#f0fdf4"/><stop offset="100%" stop-color="#dcfce7"/>
            </linearGradient>
            <linearGradient id="dataGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#fffbeb"/><stop offset="100%" stop-color="#fef3c7"/>
            </linearGradient>
            <marker id="arrow2" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#475569"/>
            </marker>
          </defs>

          <!-- 1. Clients & Edge -->
          <rect x="4" y="6" width="128" height="206" rx="5" fill="url(#edgeGrad)" stroke="#94a3b8" stroke-width="1.2"/>
          <text x="68" y="23" text-anchor="middle" font-size="8.6" font-weight="700" fill="#0f172a">1. CLIENTS & EDGE</text>
          <rect x="11" y="31" width="114" height="38" rx="4" fill="#ffffff" stroke="#cbd5e1"/>
          <text x="68" y="47" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Next.js Web & Mobile</text>
          <text x="68" y="60" text-anchor="middle" font-size="6.5" fill="#64748b">iOS / Android / Web Client</text>
          <rect x="11" y="74" width="114" height="38" rx="4" fill="#ffffff" stroke="#cbd5e1"/>
          <text x="68" y="90" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">CloudFront Global CDN</text>
          <text x="68" y="103" text-anchor="middle" font-size="6.5" fill="#64748b">Static Edge PoPs, TLS 1.3</text>
          <rect x="11" y="117" width="114" height="38" rx="4" fill="#ffffff" stroke="#cbd5e1"/>
          <text x="68" y="133" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">AWS WAF + Shield</text>
          <text x="68" y="146" text-anchor="middle" font-size="6.5" fill="#64748b">DDoS, Rate Limit, Geo-Fence</text>
          <rect x="11" y="160" width="114" height="46" rx="4" fill="#ffffff" stroke="#cbd5e1"/>
          <text x="68" y="176" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">App Load Balancer</text>
          <text x="68" y="188" text-anchor="middle" font-size="6.5" fill="#64748b">Multi-AZ Round Robin</text>
          <text x="68" y="199" text-anchor="middle" font-size="6.3" fill="#0284c7">Health Checks & SSL Offload</text>

          <!-- Arrow 1 to 2 -->
          <path d="M 132 109 L 157 109" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow2)"/>

          <!-- 2. Stateless API Fleet -->
          <rect x="160" y="6" width="134" height="206" rx="5" fill="url(#apiGrad)" stroke="#93c5fd" stroke-width="1.2"/>
          <text x="227" y="23" text-anchor="middle" font-size="8.6" font-weight="700" fill="#1e3a8a">2. STATELESS FASTAPI</text>
          <rect x="167" y="31" width="120" height="46" rx="4" fill="#ffffff" stroke="#bfdbfe"/>
          <text x="227" y="49" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">ECS Fargate Cluster</text>
          <text x="227" y="62" text-anchor="middle" font-size="6.5" fill="#64748b">Auto-scaling 20 to 60 Pods</text>
          <text x="227" y="72" text-anchor="middle" font-size="6.3" fill="#0284c7">Elastic Compute Target</text>
          <rect x="167" y="83" width="120" height="44" rx="4" fill="#ffffff" stroke="#bfdbfe"/>
          <text x="227" y="100" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Stateless Routers</text>
          <text x="227" y="113" text-anchor="middle" font-size="6.5" fill="#64748b">Zero session state in RAM</text>
          <text x="227" y="122" text-anchor="middle" font-size="6.3" fill="#64748b">Token-bucket Rate Limiter</text>
          <rect x="167" y="133" width="120" height="73" rx="4" fill="#ffffff" stroke="#bfdbfe"/>
          <text x="227" y="151" text-anchor="middle" font-size="7.6" font-weight="600" fill="#0f172a">Workload Dispatcher</text>
          <text x="227" y="164" text-anchor="middle" font-size="6.5" fill="#64748b">AI Queries &rarr; GPU Pool</text>
          <text x="227" y="175" text-anchor="middle" font-size="6.5" fill="#64748b">Money Txns &rarr; ACID Core</text>
          <text x="227" y="187" text-anchor="middle" font-size="6.3" fill="#15803d">Strict Isolation Enforced</text>
          <text x="227" y="198" text-anchor="middle" font-size="6.1" fill="#64748b">Zero Ledger Starvation</text>

          <!-- Split arrows: API to AI & Ledger -->
          <path d="M 294 65 L 322 55" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow2)"/>
          <path d="M 294 153 L 322 163" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow2)"/>

          <!-- 3. Dedicated AI GPU Pool -->
          <rect x="325" y="6" width="144" height="98" rx="5" fill="url(#aiGrad)" stroke="#d8b4fe" stroke-width="1.2"/>
          <text x="397" y="21" text-anchor="middle" font-size="8.3" font-weight="700" fill="#581c87">3. DEDICATED GPU POOL</text>
          <rect x="331" y="29" width="132" height="32" rx="3" fill="#ffffff" stroke="#e9d5ff"/>
          <text x="397" y="43" text-anchor="middle" font-size="7.3" font-weight="600" fill="#0f172a">vLLM Inference Fleet</text>
          <text x="397" y="54" text-anchor="middle" font-size="6.3" fill="#64748b">Qwen 2.5 14B (EC2 G5/G6 GPUs)</text>
          <rect x="331" y="66" width="132" height="32" rx="3" fill="#ffffff" stroke="#e9d5ff"/>
          <text x="397" y="80" text-anchor="middle" font-size="7.3" font-weight="600" fill="#0f172a">Speech & Voice Stream</text>
          <text x="397" y="91" text-anchor="middle" font-size="6.3" fill="#64748b">Faster-Whisper STT + TTS Engine</text>

          <!-- 4. Deterministic ACID Core -->
          <rect x="325" y="110" width="144" height="102" rx="5" fill="url(#ledgerGrad)" stroke="#86efac" stroke-width="1.2"/>
          <text x="397" y="125" text-anchor="middle" font-size="8.3" font-weight="700" fill="#14532d">4. DETERMINISTIC LEDGER</text>
          <rect x="331" y="132" width="132" height="36" rx="3" fill="#ffffff" stroke="#bbf7d0"/>
          <text x="397" y="146" text-anchor="middle" font-size="7.3" font-weight="600" fill="#0f172a">ACID Engine + Idempotency</text>
          <text x="397" y="158" text-anchor="middle" font-size="6.3" fill="#64748b">Row Locks (SELECT FOR UPDATE)</text>
          <rect x="331" y="172" width="132" height="34" rx="3" fill="#ffffff" stroke="#bbf7d0"/>
          <text x="397" y="186" text-anchor="middle" font-size="7.3" font-weight="600" fill="#0f172a">LightGBM Model Guard</text>
          <text x="397" y="197" text-anchor="middle" font-size="6.3" fill="#64748b">&lt;0.8ms Pre-Authorization Check</text>

          <!-- Arrows to Data Tier -->
          <path d="M 469 160 L 497 160" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow2)"/>

          <!-- 5. State & Data Tier -->
          <rect x="500" y="6" width="138" height="206" rx="5" fill="url(#dataGrad)" stroke="#fcd34d" stroke-width="1.2"/>
          <text x="569" y="23" text-anchor="middle" font-size="8.6" font-weight="700" fill="#78350f">5. STATE & DATA TIER</text>
          <rect x="507" y="31" width="124" height="38" rx="4" fill="#ffffff" stroke="#fde68a"/>
          <text x="569" y="46" text-anchor="middle" font-size="7.5" font-weight="600" fill="#0f172a">ElastiCache Redis Cluster</text>
          <text x="569" y="58" text-anchor="middle" font-size="6.4" fill="#64748b">Feature Store & Idempotency</text>
          <rect x="507" y="75" width="124" height="38" rx="4" fill="#ffffff" stroke="#fde68a"/>
          <text x="569" y="90" text-anchor="middle" font-size="7.5" font-weight="600" fill="#0f172a">RDS Proxy Connection Pool</text>
          <text x="569" y="102" text-anchor="middle" font-size="6.4" fill="#64748b">Elastic Pool Multiplexing</text>
          <rect x="507" y="119" width="124" height="42" rx="4" fill="#ffffff" stroke="#fde68a"/>
          <text x="569" y="134" text-anchor="middle" font-size="7.5" font-weight="600" fill="#0f172a">Aurora Postgres / MySQL</text>
          <text x="569" y="146" text-anchor="middle" font-size="6.4" fill="#64748b">Primary Writer + Read Replicas</text>
          <text x="569" y="155" text-anchor="middle" font-size="6.2" fill="#0284c7">Range Partitioned on Date</text>
          <rect x="507" y="167" width="124" height="39" rx="4" fill="#ffffff" stroke="#fde68a"/>
          <text x="569" y="181" text-anchor="middle" font-size="7.5" font-weight="600" fill="#0f172a">Amazon MSK / Kafka</text>
          <text x="569" y="193" text-anchor="middle" font-size="6.4" fill="#64748b">Async Event Stream & Retrain</text>
          <text x="569" y="201" text-anchor="middle" font-size="6.1" fill="#78350f">Audit Event Pub/Sub</text>

          <!-- Arrow to Observability -->
          <path d="M 638 109 L 661 109" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow2)"/>

          <!-- 6. Observability & Vault -->
          <rect x="664" y="6" width="92" height="206" rx="5" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.2"/>
          <text x="710" y="23" text-anchor="middle" font-size="8.3" font-weight="700" fill="#0f172a">6. AUDIT & OPS</text>
          <rect x="670" y="31" width="80" height="48" rx="4" fill="#ffffff" stroke="#cbd5e1"/>
          <text x="710" y="48" text-anchor="middle" font-size="7.3" font-weight="600" fill="#0f172a">Telemetry</text>
          <text x="710" y="60" text-anchor="middle" font-size="6.3" fill="#64748b">CloudWatch</text>
          <text x="710" y="70" text-anchor="middle" font-size="6.3" fill="#64748b">Prometheus</text>
          <rect x="670" y="85" width="80" height="54" rx="4" fill="#ffffff" stroke="#cbd5e1"/>
          <text x="710" y="102" text-anchor="middle" font-size="7.3" font-weight="600" fill="#0f172a">SLI Metrics</text>
          <text x="710" y="114" text-anchor="middle" font-size="6.3" fill="#64748b">p95 Latency</text>
          <text x="710" y="124" text-anchor="middle" font-size="6.3" fill="#64748b">Error &lt; 0.05%</text>
          <text x="710" y="133" text-anchor="middle" font-size="6.1" fill="#15803d">Zero Deadlocks</text>
          <rect x="670" y="145" width="80" height="61" rx="4" fill="#ffffff" stroke="#cbd5e1"/>
          <text x="710" y="162" text-anchor="middle" font-size="7.3" font-weight="600" fill="#0f172a">Audit Vault</text>
          <text x="710" y="174" text-anchor="middle" font-size="6.3" fill="#64748b">WORM S3</text>
          <text x="710" y="184" text-anchor="middle" font-size="6.3" fill="#64748b">KMS Encrypted</text>
          <text x="710" y="195" text-anchor="middle" font-size="6.1" fill="#78350f">Immutable Logs</text>
        </svg>
      </div>

      <!-- 8. Capacity Planning Matrix -->
      <div class="section-title">8. Capacity Planning & Infrastructure Sizing (1M Registered / 100K DAU)</div>
      <table class="table-p3" style="margin-bottom: 5px;">
        <thead>
          <tr>
            <th>Scale Dimension</th>
            <th>Target Load</th>
            <th>Required Infrastructure</th>
            <th>Capacity Provisioning & SLA Target</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Registered Users</strong></td>
            <td>1,000,000</td>
            <td>Amazon Aurora PostgreSQL / MySQL Multi-AZ</td>
            <td>~250 GB storage, declarative monthly table partitioning</td>
          </tr>
          <tr>
            <td><strong>Daily Active Users (DAU)</strong></td>
            <td>100,000</td>
            <td>ElastiCache Redis Cluster (Multi-Shard)</td>
            <td>In-memory sliding feature store, session caching, TTL eviction</td>
          </tr>
          <tr>
            <td><strong>Peak Concurrency (CCU)</strong></td>
            <td>10,000</td>
            <td>AWS ECS Fargate Cluster (20–60 auto-scaling tasks)</td>
            <td>Application Load Balancer, horizontal pod autoscaling</td>
          </tr>
          <tr>
            <td><strong>Transaction Throughput</strong></td>
            <td>1,000–2,500 RPS</td>
            <td>ACID Ledger Fleet + RDS Proxy (Pool: 500)</td>
            <td>p95 API latency &lt; 250ms, zero deadlocks via row locks</td>
          </tr>
          <tr>
            <td><strong>Real-Time Voice & AI</strong></td>
            <td>150–300 CCU</td>
            <td>Auto-scaling GPU Fleet (AWS G5 / G6 NVIDIA L4)</td>
            <td>vLLM continuous batching (Qwen 2.5 14B), TTFT &lt; 100ms</td>
          </tr>
        </tbody>
      </table>

      <!-- 9. Phased Verification Milestones -->
      <div class="section-title">9. Phased Load-Testing & Production Verification Roadmap</div>
      <table class="table-p3" style="margin-bottom: 5px;">
        <thead>
          <tr>
            <th>Milestone / Tier</th>
            <th>Simulated Concurrency</th>
            <th>Target Throughput</th>
            <th>Testing Tool & Scenario</th>
            <th>Acceptance SLA Gate</th>
            <th>Current Status</th>
          </tr>
        </thead>
        <tbody>
          <tr style="background: #f0fdf4;">
            <td><strong>Milestone 0: Prototype</strong></td>
            <td>1–10 sessions</td>
            <td>Single-instance</td>
            <td><code>pytest</code> (140 tests) + Next.js build</td>
            <td>100% pass; &lt;0.8ms fraud score</td>
            <td><strong class="text-success">ACHIEVED & VERIFIED</strong></td>
          </tr>
          <tr>
            <td><strong>Milestone 1: Containerized</strong></td>
            <td>250 virtual users</td>
            <td>100 RPS</td>
            <td>k6: Synthetic send_money + balance check</td>
            <td>p95 &lt; 150ms; 0% double-spends</td>
            <td><strong>Proposed Milestone</strong></td>
          </tr>
          <tr>
            <td><strong>Milestone 2: ECS + Redis</strong></td>
            <td>1,500 virtual users</td>
            <td>500 RPS</td>
            <td>k6 + Locust: Voice intent + ACID debit</td>
            <td>p95 &lt; 250ms; error rate &lt; 0.05%</td>
            <td><strong>Proposed Milestone</strong></td>
          </tr>
          <tr>
            <td><strong>Milestone 3: Hyper-Scale</strong></td>
            <td>10,000 virtual users</td>
            <td>2,500 RPS</td>
            <td>Distributed k6: Peak Eid festival surge</td>
            <td>p99 ledger &lt; 50ms; TTFT &lt; 120ms</td>
            <td><strong>Proposed Target Goal</strong></td>
          </tr>
        </tbody>
      </table>

      <!-- 10. Conclusion, Governance & Disaster Recovery Framework -->
      <div class="section-title">10. Conclusion, Governance & Disaster Recovery Framework</div>
      <div class="grid-2">
        <div class="card card-highlight" style="margin-bottom: 0; padding: 7px 10px;">
          <div style="font-size: 7.6pt; font-weight: 700; color: #14532d; margin-bottom: 2.5px;">Disaster Recovery & High Availability SLAs</div>
          <div style="font-size: 7.2pt; line-height: 1.32; color: #166534;">
            • <strong>RPO &lt; 1 minute:</strong> Automated WAL streaming, multi-AZ binary replication, and point-in-time recovery.<br>
            • <strong>RTO &lt; 15 minutes:</strong> Infrastructure as Code (Terraform) enabling automated 1-click cloud reconstruction.<br>
            • <strong>Workload Isolation:</strong> Dedicated RDS Proxy pool ensures conversational AI spikes never starve financial ledger writes.<br>
            • <strong>Automated Multi-AZ Failover:</strong> Amazon Aurora multi-AZ auto-failover in &lt;15s with zero committed transaction loss.<br>
            • <strong>Enterprise Durability:</strong> 99.999999999% (11 9s) S3 object locking for immutable append-only financial audit trails.
          </div>
        </div>
        <div class="card card-info" style="margin-bottom: 0; padding: 7px 10px;">
          <div style="font-size: 7.6pt; font-weight: 700; color: #1e40af; margin-bottom: 2.5px;">Governance & Pre-Rollout Testing Gate</div>
          <div style="font-size: 7.2pt; line-height: 1.32; color: #1e3a8a;">
            • <strong>Regulatory Auditability:</strong> Immutable WORM S3 audit logging with AWS KMS envelope encryption for all ledger transactions.<br>
            • <strong>Pre-Rollout Gate:</strong> Mandatory pass of Milestone 1 & 2 k6 stress suites before commercial production rollout.<br>
            • <strong>NFIS-B Alignment:</strong> Architected to comply strictly with Bangladesh Bank Mobile Financial Services (MFS) guidelines.<br>
            • <strong>Continuous AML Monitoring:</strong> Real-time automated alert triage for smurfing, velocity bursts, and fan-out structures.<br>
            • <strong>Explainable AI & Safety:</strong> LightGBM tree SHAP values and human-in-the-loop admin overrides for medium-risk transactions.
          </div>
        </div>
      </div>
    </div>

    <div class="footer-bar">
      <span>WALLET Autonomous FinTech • Source: <a href="https://github.com/bikashpubg678-maker/wallet-v2" style="color: #475569; text-decoration: underline;">github.com/bikashpubg678-maker/wallet-v2</a></span>
      <span>Confidential • Prepared for Academic & Regulatory Review • Page 3 of 3</span>
    </div>
  </div>

</body>
</html>
"""

def generate_pdf():
    html_path = "docs/proposal.html"
    pdf_path = "docs/WALLET_AI_FINTECH_PROPOSAL.pdf"
    root_pdf_path = "WALLET_AI_FINTECH_PROPOSAL.pdf"
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)
    print(f"Wrote HTML to {html_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(HTML_CONTENT, wait_until="networkidle")
        pdf_bytes = page.pdf(
            path=pdf_path,
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"}
        )
        browser.close()
    
    # Copy to root
    with open(root_pdf_path, "wb") as f:
        f.write(pdf_bytes)
    
    print(f"Generated PDF at {pdf_path} and {root_pdf_path} ({len(pdf_bytes)} bytes)")

    # Check page count with PyMuPDF
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    print(f"Total Page Count: {page_count}")
    for i in range(page_count):
        p = doc[i]
        blocks = p.get_text('blocks')
        last_content = [b for b in blocks if "WALLET Autonomous" not in b[4]]
        max_content_y = max(b[3] for b in last_content) if last_content else 0
        footer_b = [b for b in blocks if "WALLET Autonomous" in b[4]]
        footer_y = footer_b[0][1] if footer_b else 0
        gap = footer_y - max_content_y if footer_y and max_content_y else 0
        print(f"Page {i+1}: {len(blocks)} blocks | Content max y: {max_content_y:.1f} | Footer y: {footer_y:.1f} | Gap: {gap:.1f} pt")
    doc.close()
    
    return page_count

if __name__ == "__main__":
    generate_pdf()
