"""LLM cascade for intent parsing and phrasing.

Mirrors the pattern from ~/python/AI ENGINEERING/llm.py — empty responses
trigger fallthrough. No write access here; this module only reads via the
phraser facts passed in by the router.

Resilience: when every local Ollama slot fails AND no OpenRouter key is
configured, `parse_intent` falls through to a deterministic regex parser so
the demo never dead-ends. The phraser also has a deterministic fallback.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Iterator, Optional

import httpx

from . import config


# ---- Local Ollama slot ------------------------------------------------------
def _stream_ollama(model: str, system: str, user: str) -> Iterator[str]:
    """Stream a single chat completion from local Ollama."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "options": {"temperature": 0.0},
    }
    with httpx.stream(
        "POST",
        f"{config.OLLAMA_URL}/api/chat",
        json=payload,
        timeout=10.0,
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = (j.get("message") or {}).get("content") or ""
            if content:
                yield content
            if j.get("done"):
                break


# ---- Grok (xAI) slot --------------------------------------------------------
def _stream_grok(model: str, system: str, user: str) -> Iterator[str]:
    """Stream a chat completion via Grok (xAI API, OpenAI-compatible)."""
    api_key = (config.GROK_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("GROK_API_KEY not set")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "temperature": 0.0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.stream(
        "POST",
        f"{config.GROK_URL}/chat/completions",
        json=payload,
        headers=headers,
        timeout=30.0,
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                j = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = (j.get("choices") or [{}])[0].get("delta") or {}
            content = delta.get("content") or ""
            if content:
                yield content


# ---- OpenRouter (cloud) slot ------------------------------------------------
def _stream_openrouter(model: str, system: str, user: str) -> Iterator[str]:
    """Stream a chat completion via OpenRouter (OpenAI-compatible)."""
    api_key = (config.OPENROUTER_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "temperature": 0.0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://wallet.local",
        "X-Title": "Wallet Demo",
    }
    with httpx.stream(
        "POST",
        f"{config.OPENROUTER_URL}/chat/completions",
        json=payload,
        headers=headers,
        timeout=30.0,
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                j = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = (j.get("choices") or [{}])[0].get("delta") or {}
            content = delta.get("content") or ""
            if content:
                yield content


# ---- Cascade orchestration --------------------------------------------------
def _local_slot_iter(model: str):
    """Yield (slot_label, iterator) tuples for local cascade."""
    return ("ollama:" + model, _stream_ollama(model, system="", user=""))


def _collect_with_fallback(
    system: str,
    user: str,
    *,
    primary: list[tuple[str, callable]],
) -> Optional[str]:
    """Try `primary` cascade; if all fail, try Grok then OpenRouter if configured.
    Returns the first non-empty response, or None."""
    last_err: Optional[Exception] = None

    # 1. Local Ollama cascade
    for label, fn in primary:
        try:
            chunks = list(fn(label.split(":", 1)[1], system, user))
            text = "".join(chunks).strip()
            if text:
                return text
            sys.stderr.write(f"[llm] {label} returned empty — falling through\n")
            sys.stderr.flush()
        except Exception as e:
            last_err = e
            sys.stderr.write(f"[llm] {label} failed: {type(e).__name__}: {e}\n")
            sys.stderr.flush()

    # 2. Grok (xAI API) fallback — if configured
    if (config.GROK_API_KEY or "").strip():
        for model in config.GROK_MODELS:
            try:
                chunks = list(_stream_grok(model, system, user))
                text = "".join(chunks).strip()
                if text:
                    return text
                sys.stderr.write(f"[llm] grok:{model} empty — falling through\n")
                sys.stderr.flush()
            except Exception as e:
                last_err = e
                sys.stderr.write(f"[llm] grok:{model} failed: {type(e).__name__}: {e}\n")
                sys.stderr.flush()

    # 3. OpenRouter fallback (free models) — only if a key is configured.
    if (config.OPENROUTER_API_KEY or "").strip():
        for model in config.OPENROUTER_MODELS:
            try:
                chunks = list(_stream_openrouter(model, system, user))
                text = "".join(chunks).strip()
                if text:
                    return text
                sys.stderr.write(f"[llm] openrouter:{model} empty — falling through\n")
                sys.stderr.flush()
            except Exception as e:
                last_err = e
                sys.stderr.write(f"[llm] openrouter:{model} failed: {type(e).__name__}: {e}\n")
                sys.stderr.flush()

    if last_err is not None:
        sys.stderr.write(f"[llm] all slots failed: {last_err}\n")
    return None


def _ollama_cascade() -> list[tuple[str, callable]]:
    return [
        ("ollama:" + m, lambda model, sys_, usr, _m=m: _stream_ollama(_m, sys_, usr))
        for m in config.LLM_CASCADE
    ]


def _collect(system: str, user: str) -> str:
    """Backwards-compatible wrapper: returns empty string if cascade fails."""
    out = _collect_with_fallback(system, user, primary=_ollama_cascade())
    return out or ""


def stream_cascade(system: str, user: str) -> Iterator[str]:
    """Stream response tokens across the multi-model cascade (Ollama -> Grok -> OpenRouter)."""
    # 1. Local Ollama cascade
    for label, fn in _ollama_cascade():
        try:
            tokens = []
            for chunk in fn(label.split(":", 1)[1], system, user):
                tokens.append(chunk)
                yield chunk
            if tokens:
                return
        except Exception as e:
            sys.stderr.write(f"[llm] {label} stream failed: {e}\n")

    # 2. Grok
    if (config.GROK_API_KEY or "").strip():
        for model in config.GROK_MODELS:
            try:
                tokens = []
                for chunk in _stream_grok(model, system, user):
                    tokens.append(chunk)
                    yield chunk
                if tokens:
                    return
            except Exception as e:
                sys.stderr.write(f"[llm] grok:{model} stream failed: {e}\n")

    # 3. OpenRouter
    if (config.OPENROUTER_API_KEY or "").strip():
        for model in config.OPENROUTER_MODELS:
            try:
                tokens = []
                for chunk in _stream_openrouter(model, system, user):
                    tokens.append(chunk)
                    yield chunk
                if tokens:
                    return
            except Exception as e:
                sys.stderr.write(f"[llm] openrouter:{model} stream failed: {e}\n")


def generate_cascade(system: str, user: str) -> str:
    """Generate a response using the multi-model cascade (Ollama -> Grok -> OpenRouter)."""
    return _collect(system, user)


_stream_cascade = stream_cascade


# ---- Intent parser ----------------------------------------------------------
def parse_intent(
    text: str,
    known_handles: list[str],
    known_billers: list[str],
) -> dict:
    """Run the cascade and parse the response as JSON.

    Falls through to a regex-based parser when the LLM cascade returns
    nothing — so the demo stays alive even if every LLM slot is down.
    """
    # Fast path: if the regex fallback can classify this with high
    # confidence (greeting / thanks / bye / balance / history / pay_bill
    # with a known biller, or send/request/split with a known handle),
    # skip the 10s LLM round-trip entirely. This is what makes voice
    # replies feel instant for the common case.
    quick = _regex_intent(text, known_handles, known_billers)
    if _is_high_confidence_intent(quick, known_handles, known_billers):
        return quick

    user = (
        f"User said: {text!r}\n\n"
        f"Known handles (recipient names): {known_handles}\n"
        f"Known billers: {known_billers}\n\n"
        "Respond with ONLY the JSON object, nothing else."
    )
    raw = _collect(config.INTENT_SYSTEM_PROMPT, user)
    if raw:
        parsed = _parse_json_lenient(raw)
        if parsed.get("action") not in (None, "unknown"):
            return parsed
    # LLM gave us nothing usable — return the regex answer we already
    # computed above so we don't throw away good work.
    return quick


def _is_high_confidence_intent(
    intent: dict, known_handles: list[str], known_billers: list[str]
) -> bool:
    """Whether the regex result is good enough to skip the LLM.

    Confidence is high when the regex identified a real money action with
    a known counterparty (handle or biller), a clear live DB question, or
    small-talk intent. Anything ambiguous goes to the LLM.
    """
    action = (intent.get("action") or "").strip().lower()
    if action in {
        "greeting", "thanks", "bye", "balance", "history",
        "spending_recent", "spending_where", "latest_transaction",
        "send_vs_receive", "requests_made", "requests_received",
        "recent_splits", "spending_history", "budget_status", "account_limits",
    }:
        return True
    if action == "set_budget":
        return bool(intent.get("amount"))
    if action in {"send", "request"}:
        recipient = (intent.get("recipient") or "").strip()
        amount = intent.get("amount")
        if recipient and recipient in known_handles:
            return True
        if amount and amount > 0:
            return True
        return False
    if action == "split":
        recipients = intent.get("split_recipients") or []
        amount = intent.get("amount")
        if recipients or (amount and amount > 0):
            return True
        return False
    if action == "pay_bill":
        biller = (intent.get("biller") or "").strip()
        amount = intent.get("amount")
        if biller and amount:
            return biller in known_billers
        return False
    return False


# ---- Regex fallback ---------------------------------------------------------
_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# Match common money patterns: 500, 500 taka, ৳500, 1,200, 1k, 2.5k.
# Also handles STT noise: "500 takh" (missing a), "500 taq" (q→k),
# "500 takaa", "500 টাকা" (Bangla).
_AMOUNT_RE = re.compile(
    r"(?P<sym>৳|bdt|tk)?\s*"
    r"(?P<num>\d[\d,]*(?:\.\d+)?|\d+(?:\.\d+)?\s*[kK]?)"
    r"(?:\s*(?:taka|takaa|takah|takh|tak|takaa|taqa|tks|টাকা|টা))?",
    re.IGNORECASE,
)

_K_SUFFIX_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[kK]\b")

_GREETINGS = {
    "hi", "hello", "hey", "yo", "sup", "howdy",
    "good morning", "good evening", "good afternoon",
    "salam", "assalamu alaikum", "asalam", "adaab",
    "নমস্কার",
}

_THANKS = {"thanks", "thank you", "thx", "ty", "জাজ"}
_BYE = {"bye", "goodbye", "see you", "see ya", "আসসালামু"}

_SPENDING_RECENT_PATTERNS = [
    r"how much did i spend",
    r"how much i spent",
    r"how much spent",
    r"recent spending",
    r"spending recently",
    r"recent expense",
    r"how much have i spent",
]

_ACCOUNT_LIMITS_PATTERNS = [
    r"what is my limit",
    r"what are my limits",
    r"my limit",
    r"daily limit",
    r"transfer limit",
    r"single transaction limit",
    r"account tier",
    r"what tier am i",
    r"check my limit",
    r"how much can i send",
    r"can i send",
    r"আমার লিমিট",
    r"আমার টিয়ার",
]

_SPENDING_WHERE_PATTERNS = [
    r"where did i spend",
    r"where did my money go",
    r"where was my money spent",
    r"where i spent",
    r"what did i spend on",
    r"spending breakdown",
]

_LATEST_TXN_PATTERNS = [
    r"latest transaction",
    r"last transaction",
    r"most recent transaction",
    r"what was my latest transaction",
    r"what was my last transaction",
    r"latest transfer",
    r"last transfer",
]

_SEND_VS_RECEIVE_PATTERNS = [
    r"send or receive",
    r"sent or received",
    r"sent vs received",
    r"did i send or receive",
    r"have i sent or received",
]

_REQUESTS_MADE_PATTERNS = [
    r"requests have i made",
    r"requests i made",
    r"requests i have made",
    r"money requests have i made",
    r"money requests i made",
    r"requests i sent",
    r"requests made",
]

_REQUESTS_RECEIVED_PATTERNS = [
    r"requests have i received",
    r"requests i received",
    r"requests i have received",
    r"money requests have i received",
    r"money requests received",
    r"requests for me",
    r"requests to me",
    r"pending requests",
]

_RECENT_SPLITS_PATTERNS = [
    r"recent split",
    r"recent splits",
    r"split-money transactions",
    r"split transactions",
    r"my splits",
    r"recent split-money",
]

_SPENDING_HISTORY_PATTERNS = [
    r"spending history",
    r"current spending history",
    r"overview of my spending",
    r"my spending history",
]

_SET_BUDGET_PATTERNS = [
    r"set budget",
    r"fix budget",
    r"budget fixing",
    r"save for",
    r"savings goal",
    r"fix a budget",
    r"set a budget",
    r"budget management",
]

_BUDGET_STATUS_PATTERNS = [
    r"how is my budget",
    r"what is my budget",
    r"check budget",
    r"budget status",
    r"my budget",
    r"budget info",
]

_FINANCIAL_INSIGHTS_PATTERNS = [
    r"budget recommendation",
    r"budget recommendations",
    r"budget advice",
    r"spending habit",
    r"spending habits",
    r"financial health",
    r"financial insight",
    r"financial insights",
    r"how is my financial health",
    r"analyze my spending",
    r"spending analysis",
    r"বাজেট পরামর্শ",
    r"টাকা জমানোর পরামর্শ",
    r"আর্থিক স্বাস্থ্য",
]

_FINANCIAL_LITERACY_PATTERNS = [
    r"emergency fund",
    r"what is an emergency fund",
    r"50.?30.?20",
    r"50 30 20 rule",
    r"financial literacy",
    r"how does fraud detection work",
    r"fraud protection",
    r"scam protection",
    r"prevent fraud",
    r"double entry",
    r"ledger integrity",
    r"জরুরি ফান্ড",
    r"জরুরি তহবিল",
    r"বাজেট করার নিয়ম",
    r"প্রতারণা থেকে বাঁচার উপায়",
]

_BALANCE_TOKENS = {
    "balance", "bal", "মিউ", "money left", "how much do i have",
    "what's my balance", "what is my balance", "how much money do i have",
    "check balance", "current balance", "balance check", "আমার ব্যালেন্স",
    "কত টাকা আছে",
}

_HISTORY_TOKENS = {
    "history", "transactions", "statement", "statement list",
    "কী করেছি", "history list",
}

_RECHARGE_TRIGGERS = {
    "recharge", "mobile recharge", "flexiload", "রিচার্জ", "মোবাইল রিচার্জ", "top up", "topup", "airtime",
}

_CASHOUT_TRIGGERS = {
    "cash out", "cashout", "withdraw", "উত্তোলন", "ক্যাশ আউট", "ক্যাশআউট", "agent cashout",
}

_REQUEST_TRIGGERS = {
    "ask", "request", "demand", "collect", "ধার", "চাই",
    "need", "want from", "ask for money", "request money",
}

_SEND_TRIGGERS = {
    "send", "transfer", "pay", "give", "transfer to", "send money",
    "পাঠাও", "পাঠাই", "পাঠাচ্ছি", "দাও", "দিই", "bhechhe", "pathao", "dao",
    "parbe", "পার্বে",
}

_SPLIT_TRIGGERS = {
    "split", "divide", "share", "ভাগ", "ভাগ কর", "ভাগাও", "split money",
    "split the bill", "split bill",
}

_BILL_TRIGGERS = {
    "bill", "internet", "electricity", "wifi", "utility", "বিল",
}


def _normalize(text: str) -> str:
    s = text.strip().lower()
    s = s.translate(_BANGLA_DIGITS)
    # collapse multiple spaces
    s = re.sub(r"\s+", " ", s)
    return s


def _extract_amount(text: str) -> Optional[float]:
    """Find a money amount in the text. Handles 500, 1,200.50, 1k, ৳500."""
    t = _normalize(text)
    # Strip 11-digit phone numbers so mobile numbers like 01712345678 are not treated as money amounts
    t_clean = re.sub(r"\b(?:\+?880|0)1[3-9]\d{8}\b", " ", t)
    # k-suffix first (1k -> 1000)
    m = _K_SUFFIX_RE.search(t_clean)
    if m:
        try:
            return float(m.group(1)) * 1000
        except ValueError:
            pass
    # Strip the ৳/bdt prefix when scanning for a number.
    candidates: list[float] = []
    for m in _AMOUNT_RE.finditer(t_clean):
        num = m.group("num").replace(",", "").strip()
        if not num:
            continue
        try:
            candidates.append(float(num))
        except ValueError:
            continue
    if not candidates:
        return None
    return max(candidates)


def _extract_recipient(text: str, known: list[str]) -> Optional[str]:
    """Find a known handle, phone, or alias in the text. Tries longest-first."""
    t = _normalize(text)
    candidates = sorted(known, key=len, reverse=True)

    # 1. Alias: "agent" or "agent point" maps to registered agent handle "tahzib"
    if ("agent" in t or "এজেন্ট" in t) and "tahzib" in known:
        return "tahzib"

    # 2. Check for 11-digit phone number in text (e.g. 01712345678)
    phone_m = re.search(r"\b(?:\+?880|0)1[3-9]\d{8}\b", t)
    phone_found = phone_m.group(0) if phone_m else None

    # 3. Preposition-priority: handle directly after a recipient preposition.
    prep_re = re.compile(
        r"\b(?:to|for|towards|toward|with|by|from|কে|এ|টা)\s+(?:a\s+|an\s+|the\s+|ur\s+|u\s+)?"
        r"(?P<h>[a-z0-9_]+)",
        re.IGNORECASE,
    )
    prep_fallback = None
    stop_words = {"the", "a", "an", "my", "your", "ur", "someone", "him", "her", "me", "taka", "tk", "bdt", "account", "wallet"}
    for m in prep_re.finditer(t):
        word = m.group("h")
        if word in known:
            return word
        for h in candidates:
            if h in word or word in h:
                return h
        if not prep_fallback and word not in stop_words:
            prep_fallback = word

    # 4. Substring match anywhere in known handles.
    for h in candidates:
        if re.search(rf"\b{re.escape(h)}\b", t):
            return h
    # 5. Fuzzy: handle inside a word.
    for h in candidates:
        if h in t:
            return h

    if prep_fallback:
        return prep_fallback
    if phone_found:
        return phone_found

    return None


def _extract_budget_info(text: str) -> tuple[str, Optional[float]]:
    """Extract festival/purpose and amount for budget commands."""
    t = _normalize(text)
    amount = _extract_amount(text)
    m = re.search(r"\b(?:for|towards|goal|named)\s+([a-zA-Z]+)", t)
    festival = m.group(1).lower() if m else None
    if not festival:
        for common in ("eid", "puja", "boishakh", "vacation", "trip", "wedding", "emergency", "shopping", "gift"):
            if common in t:
                festival = common
                break
    if not festival:
        festival = "general"
    return festival, amount


def _classify_action(text: str) -> str:
    t = _normalize(text)

    # 1. Specific live database query intents (check BEFORE general tokens)
    for pat in _SPENDING_RECENT_PATTERNS:
        if re.search(pat, t):
            return "spending_recent"
    for pat in _ACCOUNT_LIMITS_PATTERNS:
        if re.search(pat, t):
            return "account_limits"
    for pat in _SPENDING_WHERE_PATTERNS:
        if re.search(pat, t):
            return "spending_where"
    for pat in _LATEST_TXN_PATTERNS:
        if re.search(pat, t):
            return "latest_transaction"
    for pat in _SEND_VS_RECEIVE_PATTERNS:
        if re.search(pat, t):
            return "send_vs_receive"
    for pat in _REQUESTS_MADE_PATTERNS:
        if re.search(pat, t):
            return "requests_made"
    for pat in _REQUESTS_RECEIVED_PATTERNS:
        if re.search(pat, t):
            return "requests_received"
    for pat in _RECENT_SPLITS_PATTERNS:
        if re.search(pat, t):
            return "recent_splits"
    for pat in _SPENDING_HISTORY_PATTERNS:
        if re.search(pat, t):
            return "spending_history"
    for pat in _SET_BUDGET_PATTERNS:
        if re.search(pat, t):
            return "set_budget"
    for pat in _BUDGET_STATUS_PATTERNS:
        if re.search(pat, t):
            return "budget_status"
    for pat in _FINANCIAL_INSIGHTS_PATTERNS:
        if re.search(pat, t):
            return "financial_insights"
    for pat in _FINANCIAL_LITERACY_PATTERNS:
        if re.search(pat, t):
            return "financial_literacy"

    # greetings (very short, no numbers)
    if len(t.split()) <= 6:
        for g in _GREETINGS:
            if t == g or t.startswith(g + " "):
                return "greeting"
    if any(re.search(rf"\b{re.escape(k)}\b", t) for k in _THANKS):
        return "thanks"
    if any(re.search(rf"\b{re.escape(k)}\b", t) for k in _BYE):
        return "bye"
    if any(k in t for k in _RECHARGE_TRIGGERS):
        return "recharge"
    if any(k in t for k in _CASHOUT_TRIGGERS):
        return "cash_out"
    if any(k in t for k in _BALANCE_TOKENS):
        return "balance"
    if any(k in t for k in _HISTORY_TOKENS):
        return "history"
    if any(k in t for k in _SPLIT_TRIGGERS):
        return "split"
    if any(k in t for k in _REQUEST_TRIGGERS):
        return "request"
    if any(k in t for k in _BILL_TRIGGERS):
        return "pay_bill"
    if any(k in t for k in _SEND_TRIGGERS):
        return "send"

    has_number = bool(re.search(r"\d", t))
    has_prep = bool(re.search(r"\b(to|for|towards|কে|এ)\b", t))
    if has_number and has_prep:
        return "send"
    return "unknown"


def _regex_intent(text: str, known_handles: list[str], known_billers: list[str]) -> dict:
    """Deterministic fallback intent parser. Used when the LLM is unreachable."""
    action = _classify_action(text)
    amount = _extract_amount(text)
    recipient = _extract_recipient(text, known_handles) if known_handles else None

    if action == "spending_recent":
        return {"action": "spending_recent", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "account_limits":
        return {"action": "account_limits", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "spending_where":
        return {"action": "spending_where", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "latest_transaction":
        return {"action": "latest_transaction", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "send_vs_receive":
        return {"action": "send_vs_receive", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "requests_made":
        return {"action": "requests_made", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "requests_received":
        return {"action": "requests_received", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "recent_splits":
        return {"action": "recent_splits", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "spending_history":
        return {"action": "spending_history", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "set_budget":
        fest, amt = _extract_budget_info(text)
        return {"action": "set_budget", "festival": fest, "amount": amt, "recipient": None, "biller": None, "split_recipients": []}
    if action == "budget_status":
        fest, _ = _extract_budget_info(text)
        return {"action": "budget_status", "festival": fest if fest != "general" else None, "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "financial_insights":
        return {"action": "financial_insights", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "financial_literacy":
        topic = None
        t = _normalize(text)
        if "emergency" in t or "fund" in t or "জরুরি" in t:
            topic = "emergency_fund"
        elif "50" in t or "rule" in t:
            topic = "50_30_20"
        elif "fraud" in t or "scam" in t or "প্রতারণা" in t or "protection" in t:
            topic = "fraud_prevention"
        elif "double" in t or "entry" in t or "ledger" in t:
            topic = "double_entry"
        elif "festival" in t or "eid" in t or "puja" in t:
            topic = "festival_savings"
        return {"action": "financial_literacy", "topic": topic, "amount": None, "recipient": None, "biller": None, "split_recipients": []}

    if action in ("send", "request", "recharge", "cash_out"):
        sub_action = "send"
        if action == "recharge":
            sub_action = "recharge"
            action = "send"
        elif action == "cash_out":
            sub_action = "cash_out"
            action = "send"
            if not recipient and "tahzib" in known_handles:
                recipient = "tahzib"

        note = "Mobile Recharge" if sub_action == "recharge" else ("Cash Out via Agent" if sub_action == "cash_out" else None)
        return {
            "action": action,
            "sub_action": sub_action,
            "amount": amount,
            "recipient": recipient,
            "biller": None,
            "split_recipients": [],
            "note": note,
        }
    if action == "split":
        t = _normalize(text)
        found = [h for h in known_handles if re.search(rf"\b{re.escape(h)}\b", t)]
        return {
            "action": "split",
            "amount": amount,
            "recipient": None,
            "biller": None,
            "split_recipients": found,
        }
    if action == "pay_bill":
        biller = None
        t = _normalize(text)
        for b in known_billers:
            if re.search(rf"\b{re.escape(b.lower())}\b", t):
                biller = b
                break
        return {
            "action": "pay_bill",
            "amount": amount,
            "recipient": None,
            "biller": biller,
            "split_recipients": [],
        }
    if action == "balance":
        return {"action": "balance", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "history":
        return {"action": "history", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "greeting":
        return {"action": "greeting", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "thanks":
        return {"action": "thanks", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    if action == "bye":
        return {"action": "bye", "amount": None, "recipient": None, "biller": None, "split_recipients": []}
    return {"action": "unknown", "amount": None, "recipient": None, "biller": None, "split_recipients": []}


def _parse_json_lenient(raw: str) -> dict:
    """Strip code fences, find the outermost {...}, parse it."""
    s = raw.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start:end + 1]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        s2 = s.replace(",}", "}").replace(",]", "]")
        try:
            return json.loads(s2)
        except json.JSONDecodeError:
            return {"action": "unknown"}


# ---- Phraser ---------------------------------------------------------------
def phrase(text_kind: str, facts: dict) -> str:
    """Turn deterministic facts into a single natural sentence.

    Financial facts NEVER go through the LLM — every factual kind in
    `_FACTUAL_PHRASE_KINDS` is short-circuited to the deterministic
    template. This keeps replies instant (no Ollama round-trip) and
    guarantees the model cannot fabricate a number that isn't in `facts`.

    The non-factual path is for casual small talk only; even there we
    cap latency by using the existing cascade (10s timeout) and falling
    back to a deterministic template if it returns empty.
    """
    if text_kind in _FACTUAL_PHRASE_KINDS:
        # Fast path: no LLM. This is what makes voice replies feel instant.
        return _deterministic_phrase(text_kind, facts)
    system = config.PHRASER_SYSTEM_PROMPT
    user = json.dumps({"kind": text_kind, **facts})
    try:
        out = _collect(system, user).strip()
        out = out.strip().strip('"').strip("`")
        if out:
            return out
    except Exception as e:
        sys.stderr.write(f"[phrase] fallback: {e!r}\n")
    return _deterministic_phrase(text_kind, facts)


# ---- Chat (conversational) -------------------------------------------------
def chat_reply(text: str, user_handle: str, user_facts: Optional[dict] = None) -> str:
    """Conversational and financial advisory reply.

    Uses the LLM cascade grounded in live database facts (balance, spending,
    goals, recommendations) if available; falls back to deterministic templates
    so the system always replies without failing.
    """
    norm = _normalize(text)
    if not user_facts and _classify_action(norm) in {"greeting", "thanks", "bye"}:
        return _deterministic_chat(text, user_handle)

    if user_facts:
        facts_str = json.dumps(user_facts, indent=2)
        system = (
            "You are Wallet Financial Assistant — an intelligent, concise, BD-grounded AI advisor. "
            "Address the user as 'Boss'. Keep replies direct, helpful, and natural (2-3 sentences max). "
            "Use the verified LIVE DATABASE FACTS below to give practical, specific, grounded financial advice. "
            "Give concrete taka amounts and actionable guidance. Do not fabricate numbers or facts.\n\n"
            f"LIVE DATABASE FACTS:\n{facts_str}"
        )
    else:
        system = (
            "You are Wallet Assistant — concise, friendly, BD-flavored. "
            "Address the user as 'Boss' when natural. Keep replies short (1-2 sentences). "
            "You can also answer simple questions about balances or transaction history. "
            "Reply with ONLY the sentence, no quotes, no markdown."
        )

    user = f"User ({user_handle}) asked: {text}"
    try:
        out = _collect(system, user).strip()
        out = out.strip().strip('"').strip("`")
        if out:
            return out
    except Exception as e:
        sys.stderr.write(f"[chat] fallback: {e!r}\n")
    return _deterministic_chat(text, user_handle)


_FACTUAL_PHRASE_KINDS = {
    "review_send",
    "review_request",
    "review_split",
    "review_bill",
    "missing_amount_send",
    "missing_recipient_send",
    "missing_details_send",
    "missing_amount_request",
    "missing_recipient_request",
    "missing_details_request",
    "missing_recipients_split",
    "missing_amount_split",
    "missing_budget_details",
    "executed_send",
    "executed_split",
    "executed_bill",
    "cancelled",
    "insufficient_funds",
    "ambiguous_recipient",
    "unknown_recipient",
    "balance",
    "history_summary",
    "request_created",
    "request_paid",
    "request_declined",
    "rephrase",
}


_GREETING_REPLIES = [
    "Hey Boss! Ready to move some money?",
    "Hi Boss — say the word and we'll send it.",
    "Hello Boss. Want to send, request, or check your balance?",
    "Hey! I'm here. Try 'send 500 to rishad' or 'what's my balance'.",
    "Salam Boss. What's the plan today?",
]

_THANKS_REPLIES = [
    "Anytime Boss.",
    "No problem. Just say the word.",
    "You're welcome, Boss.",
    "Glad to help.",
]

_BYE_REPLIES = [
    "Catch you later, Boss.",
    "Bye. I'll be here.",
    "Take care, Boss.",
]

_BALANCE_HINTS = [
    "Say 'what's my balance' and I'll pull it up.",
    "Want a balance check? Just ask.",
]


def _deterministic_chat(text: str, user_handle: str) -> str:
    t = _normalize(text)
    # Check thanks/bye/greetings BEFORE "how are you" / greetings because some
    # greeting tokens (e.g. "yo") are substrings of longer phrases ("thank you",
    # "goodbye"). Order matters: thanks/bye first, then greetings.
    if any(re.search(rf"\b{re.escape(k)}\b", t) for k in _THANKS):
        return _THANKS_REPLIES[0]
    if any(re.search(rf"\b{re.escape(k)}\b", t) for k in _BYE):
        return _BYE_REPLIES[0]
    if any(k in t for k in ("how are you", "how's it going", "how is it going", "what's up")):
        return "Doing well, Boss. I'm ready whenever you are."
    if any(g in t for g in _GREETINGS):
        return _GREETING_REPLIES[0]
    if any(k in t for k in ("who are you", "what are you", "your name", "তুমি কে")):
        return (
            "I'm Wallet Assistant — a local demo that moves money between "
            "the 6 demo accounts. Talk to me or type what you want."
        )
    if any(k in t for k in ("help", "what can you do", "commands")):
        return (
            "I can send, request, split bills, pay utilities, and check "
            "your balance and history. Try 'send 500 to rishad'."
        )
    if any(k in t for k in _BALANCE_TOKENS):
        return _BALANCE_HINTS[0]
    # Generic fallback.
    return (
        "I heard you, Boss. Try a money command like 'send 500 to rishad' "
        "or ask 'what's my balance'."
    )


def _format_bdt_amt(val: Any) -> str:
    """Format an amount as clean BDT taka text (e.g. ৳500)."""
    if val is None:
        return "the money"
    try:
        f = float(str(val).replace(",", ""))
        if f.is_integer():
            return f"৳{int(f):,}"
        return f"৳{f:,.2f}"
    except (ValueError, TypeError):
        return f"৳{val}"


def _deterministic_phrase(text_kind: str, facts: dict) -> str:
    """Deterministic natural phrasing matching the Boss persona and exact requirements."""
    if text_kind == "review_send":
        amt_str = _format_bdt_amt(facts.get("amount_bdt"))
        recipient = facts.get("recipient", "the recipient")
        sub_action = facts.get("sub_action") or "send"
        resulting = _format_bdt_amt(facts.get("resulting_balance_bdt"))

        if sub_action == "recharge":
            return (
                f"Sure Boss! Preparing to recharge {amt_str} for @{recipient}. "
                f"Your new balance will be {resulting} after deducting. "
                "Please confirm below to proceed."
            )
        elif sub_action == "cash_out":
            return (
                f"Sure Boss! Preparing to cash out {amt_str} to Agent @{recipient}. "
                f"Your new balance will be {resulting} after deducting. "
                "Please confirm below to proceed."
            )
        else:
            return (
                f"Sure Boss! Preparing to send {amt_str} to @{recipient}. "
                f"Your new balance will be {resulting} after deducting. "
                "Please confirm below to proceed."
            )

    if text_kind == "review_request":
        amt_str = _format_bdt_amt(facts.get("amount_bdt"))
        payer = facts.get("recipient") or facts.get("payer", "the user")
        curr_bal = _format_bdt_amt(facts.get("current_balance_bdt"))
        bal_clause = f" Your balance will remain {curr_bal} until approved." if curr_bal != "the money" else ""
        return (
            f"Sure Boss! Requesting {amt_str} from @{payer}.{bal_clause} "
            "Please confirm below to proceed."
        )

    if text_kind == "review_split":
        amt_str = _format_bdt_amt(facts.get("total_amount_bdt"))
        recipients_list = facts.get("recipients", [])
        recipients = ", ".join(f"@{r}" for r in recipients_list) if recipients_list else "the group"
        per_amt = _format_bdt_amt(facts.get("per_amount_bdt"))
        per_clause = f" ({per_amt} each)" if per_amt != "the money" else ""
        resulting = _format_bdt_amt(facts.get("resulting_balance_bdt"))
        return (
            f"Sure Boss! Splitting {amt_str} with {recipients}{per_clause}. "
            f"Your new balance will be {resulting} after deducting your share. "
            "Please confirm below to proceed."
        )

    if text_kind == "review_bill":
        amt_str = _format_bdt_amt(facts.get("amount_bdt"))
        biller = facts.get("biller", "the utility")
        resulting = _format_bdt_amt(facts.get("resulting_balance_bdt"))
        return (
            f"Sure Boss! Preparing to pay {amt_str} to {biller}. "
            f"Your new balance will be {resulting} after deducting. "
            "Please confirm below to proceed."
        )

    if text_kind == "missing_amount_send":
        recipient = facts.get("recipient", "the recipient")
        return f"Sure Boss, how much money would you like to send to @{recipient}?"
    if text_kind == "missing_recipient_send":
        amt_str = _format_bdt_amt(facts.get("amount_bdt"))
        return f"Sure Boss, who would you like to send {amt_str} to?"
    if text_kind == "missing_details_send":
        return "Sure Boss, how much money would you like to send and to whom?"
    if text_kind == "missing_amount_request":
        recipient = facts.get("recipient") or facts.get("payer", "the recipient")
        return f"Sure Boss, how much money would you like to request from @{recipient}?"
    if text_kind == "missing_recipient_request":
        amt_str = _format_bdt_amt(facts.get("amount_bdt"))
        return f"Sure Boss, who would you like to request {amt_str} from?"
    if text_kind == "missing_details_request":
        return "Sure Boss, how much would you like to request and from whom?"
    if text_kind == "missing_recipients_split":
        amt_str = _format_bdt_amt(facts.get("total_amount_bdt"))
        return f"Sure Boss, who would you like to split {amt_str} with?"
    if text_kind == "missing_amount_split":
        recipients = ", ".join(facts.get("recipients", []))
        return f"Sure Boss, how much would you like to split with {recipients}?"
    if text_kind == "missing_budget_details":
        return "Sure Boss, what festival or goal is this budget for, and how much would you like to set?"
    if text_kind == "executed_send":
        sub_action = facts.get("sub_action") or "send"
        if sub_action == "recharge":
            return (
                f"Done, Boss. Recharged ৳{facts.get('amount_bdt')} for "
                f"@{facts.get('recipient')}. "
                f"New balance: ৳{facts.get('new_balance_bdt')}."
            )
        elif sub_action == "cash_out":
            return (
                f"Done, Boss. Cashed out ৳{facts.get('amount_bdt')} to "
                f"Agent @{facts.get('recipient')}. "
                f"New balance: ৳{facts.get('new_balance_bdt')}."
            )
        return (
            f"Done, Boss. Sent ৳{facts.get('amount_bdt')} to "
            f"@{facts.get('recipient')}. "
            f"New balance: ৳{facts.get('new_balance_bdt')}."
        )
    if text_kind == "executed_split":
        return (
            f"Split done. ৳{facts.get('total_amount_bdt')} across "
            f"{len(facts.get('recipients', []))} people. "
            f"New balance: ৳{facts.get('new_balance_bdt')}."
        )
    if text_kind == "executed_bill":
        return (
            f"Bill paid: ৳{facts.get('amount_bdt')} to {facts.get('biller')}. "
            f"New balance: ৳{facts.get('new_balance_bdt')}."
        )
    if text_kind == "cancelled":
        return "Cancelled. No money moved."
    if text_kind == "insufficient_funds":
        return (
            f"Sorry Boss, your balance is ৳{facts.get('balance_bdt')} "
            f"— short of ৳{facts.get('amount_bdt')}."
        )
    if text_kind == "ambiguous_recipient":
        c = facts.get("candidates") or []
        return f"Did you mean one of: {', '.join(c)}?"
    if text_kind == "unknown_recipient":
        raw = facts.get("raw") or "that user"
        known_list = facts.get("known") or []
        known_str = ", ".join(f"@{h}" for h in known_list) if known_list else "@bikash, @rishad, @arman, @tahzib, @srijan, @mahdin, @rahim"
        return (
            f"Sorry Boss, we have current limitations: '{raw}' is outside our registered system. "
            f"You can send, recharge, cashout, send money, or split money with these particular users: {known_str}."
        )
    if text_kind == "balance":
        return f"Let me check, Boss — your current balance is ৳{facts.get('balance_bdt')}."
    if text_kind == "history_summary":
        n = facts.get("count", 0)
        return f"I checked your history, Boss. You have {n} recent transactions."
    if text_kind == "request_created":
        return (
            f"Request sent to {facts.get('payer')}: ৳{facts.get('amount_bdt')}. "
            f"They'll see it on their end."
        )
    if text_kind == "request_paid":
        return (
            f"Paid ৳{facts.get('amount_bdt')} to {facts.get('asker')}. "
            f"New balance: ৳{facts.get('new_balance_bdt')}."
        )
    if text_kind == "request_declined":
        return "Request declined."
    if text_kind == "rephrase":
        return "Sorry Boss, I didn't catch that. Could you rephrase?"
    return "Done."
