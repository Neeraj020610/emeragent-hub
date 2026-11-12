"use client";

import React, { useState, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import {
  Sparkles,
  Bot,
  Play,
  Pause,
  Square,
  Zap,
  RotateCw,
  TrendingUp,
  Layers,
  ListFilter,
  PlusCircle,
  RefreshCw,
  Send,
  Paperclip,
  X,
  FileCode,
  Image as ImageIcon,
  CheckCircle2,
  ExternalLink,
  Trash2,
  Search,
  User,
  ShieldCheck,
  Server,
  Activity,
  Cpu,
  Clock,
  AlertCircle,
  Plus,
  Eye,
  Terminal,
  Film,
  Download,
  Volume2,
} from "lucide-react";

function renderInlineMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const tok = match[0];
    if (tok.startsWith("**") && tok.endsWith("**")) {
      parts.push(<strong key={key++} className="font-semibold text-slate-900">{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("`") && tok.endsWith("`")) {
      parts.push(<code key={key++} className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 font-mono text-[11px]">{tok.slice(1, -1)}</code>);
    } else if (tok.startsWith("*") && tok.endsWith("*")) {
      parts.push(<em key={key++} className="italic text-slate-700">{tok.slice(1, -1)}</em>);
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

function renderChatMarkdown(content: string): React.ReactNode {
  const lines = (content || "").split("\n");
  return (
    <div className="space-y-1.5">
      {lines.map((rawLine, idx) => {
        const line = rawLine.trimEnd();
        if (!line.trim()) {
          return <div key={idx} className="h-1" />;
        }
        if (line.startsWith("### ") || line.startsWith("#### ")) {
          const txt = line.replace(/^#{3,4}\s+/, "");
          return <div key={idx} className="font-bold text-slate-900 text-sm pt-1">{renderInlineMarkdown(txt)}</div>;
        }
        if (/^[-*]\s+/.test(line)) {
          const txt = line.replace(/^[-*]\s+(?:\[[ xX]\]\s+)?/, "");
          return (
            <div key={idx} className="flex items-start gap-2 pl-1">
              <span className="text-blue-500 font-bold mt-0.5">•</span>
              <span className="flex-1">{renderInlineMarkdown(txt)}</span>
            </div>
          );
        }
        if (/^\d+\.\s+/.test(line)) {
          const numMatch = line.match(/^(\d+\.)\s+(.*)$/);
          if (numMatch) {
            return (
              <div key={idx} className="flex items-start gap-2 pl-1">
                <span className="text-blue-600 font-semibold shrink-0">{numMatch[1]}</span>
                <span className="flex-1">{renderInlineMarkdown(numMatch[2])}</span>
              </div>
            );
          }
        }
        return <p key={idx} className="leading-relaxed">{renderInlineMarkdown(line)}</p>;
      })}
    </div>
  );
}

// --- Types ---
interface SystemState {
  status: string;
  last_command: string;
  last_command_at: string;
  command_message: string;
  active_workers_count: number;
  total_tasks_queued: number;
  total_tasks_in_progress: number;
  total_tasks_completed: number;
  total_tasks_failed: number;
  eligible_accounts_count: number;
  updated_at: string;
}

interface AccountBudget {
  id: number;
  account_id: number;
  account_name: string;
  starting_balance: string;
  verified_current_balance: string;
  credit_usage: string;
  reserved_credits: string;
  ceiling_percentage: string;
  planned_ceiling_limit: string;
  remaining_eligible_budget: string;
  balance_source: string;
  is_eligible: boolean;
  ineligibility_reason?: string;
  universal_api_usage: string;
  platform_build_usage: string;
  active_task_id?: number;
}

interface AutonomousTask {
  id: number;
  task_identifier: string;
  work_type: string;
  source: string;
  title: string;
  description: string;
  expected_result: string;
  acceptance_criteria?: string;
  assigned_account_id?: number;
  priority: string;
  estimated_credit_cost: string;
  actual_credit_cost: string;
  status: string;
  dependencies?: string;
  retry_count: number;
  max_retries: number;
  checkpoints?: string;
  result_metadata?: string;
  is_mock: boolean;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

interface AutonomousInstruction {
  id: number;
  title: string;
  work_type: string;
  objective: string;
  max_tasks: number;
  is_active: boolean;
  created_at: string;
}

interface Attachment {
  id: number;
  file_name: string;
  file_size_bytes: number;
  mime_type: string;
  file_summary?: string;
  created_at: string;
}

interface Message {
  id: number;
  conversation_id: number;
  sender_type: "USER" | "AGENT" | "SYSTEM";
  content: string;
  task_id?: number;
  action_plan_json?: string;
  execution_status?: string;
  account_id?: number;
  account_name?: string;
  is_mock: boolean;
  attachments?: Attachment[];
  created_at: string;
}

interface ConversationItem {
  id: number;
  conversation_uuid: string;
  title: string;
  is_pinned: boolean;
  current_task_id?: number;
  message_count: number;
  last_message_preview?: string;
  updated_at: string;
  created_at: string;
}

interface BuildJob {
  id: number;
  project_id: number;
  project_name?: string;
  account_name?: string;
  account_id?: number;
  title: string;
  job_type: string;
  job_status: string;
  priority: string;
  is_mock: boolean;
  credits_used: string | number;
  created_at: string;
}

interface TaskLog {
  id: number;
  task_id: number;
  worker_id?: string;
  log_level: string;
  message: string;
  step_name?: string;
  created_at: string;
}

function BuildsContent() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab") === "chat" ? "chat" : searchParams.get("tab") === "jobs" ? "jobs" : "worker";
  const [activeTab, setActiveTab] = useState<"worker" | "chat" | "jobs">(initialTab);

  // --- Worker State ---
  const [systemState, setSystemState] = useState<SystemState | null>(null);
  const [budgets, setBudgets] = useState<AccountBudget[]>([]);
  const [tasks, setTasks] = useState<AutonomousTask[]>([]);
  const [instructions, setInstructions] = useState<AutonomousInstruction[]>([]);
  
  // Modals for Worker
  const [showInstructionModal, setShowInstructionModal] = useState(false);
  const [instTitle, setInstTitle] = useState("");
  const [instWorkType, setInstWorkType] = useState("VIDEO_CREATION");
  const [instObjective, setInstObjective] = useState("");
  const [instMaxTasks, setInstMaxTasks] = useState(3);
  const [isSubmittingInst, setIsSubmittingInst] = useState(false);

  // Task Logs Modal
  const [activeLogTaskId, setActiveLogTaskId] = useState<number | null>(null);
  const [taskLogs, setTaskLogs] = useState<TaskLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);

  // Deliverables & Output Modal
  const [activeArtifactTask, setActiveArtifactTask] = useState<AutonomousTask | null>(null);

  // --- Agent Chat State ---
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeUuid, setActiveUuid] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentTask, setCurrentTask] = useState<AutonomousTask | null>(null);
  const [chatSearch, setChatSearch] = useState("");
  const [prompt, setPrompt] = useState("");
  const [stagedAttachments, setStagedAttachments] = useState<Attachment[]>([]);
  const [sending, setSending] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);

  // --- Standard Jobs State ---
  const [jobs, setJobs] = useState<BuildJob[]>([]);
  const [showJobModal, setShowJobModal] = useState(false);
  const [jobTitle, setJobTitle] = useState("");
  const [jobType, setJobType] = useState("prompt_build");
  const [jobPriority, setJobPriority] = useState("MEDIUM");
  const [jobRequirements, setJobRequirements] = useState("");
  const [jobAccountId, setJobAccountId] = useState<number>(6);
  const [jobAutoExecute, setJobAutoExecute] = useState(true);
  const [isSubmittingJob, setIsSubmittingJob] = useState(false);
  const [executingJobId, setExecutingJobId] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Fetch telemetry
  const fetchWorkerData = async () => {
    try {
      const [s, b, t, inst] = await Promise.all([
        apiFetch<SystemState>("/autonomous/status").catch(() => null),
        apiFetch<AccountBudget[]>("/autonomous/budgets").catch(() => []),
        apiFetch<AutonomousTask[]>("/autonomous/tasks?limit=50").catch(() => []),
        apiFetch<AutonomousInstruction[]>("/autonomous/instructions").catch(() => []),
      ]);
      if (s) setSystemState(s);
      if (b) setBudgets(b);
      if (t) setTasks(t);
      if (inst) setInstructions(inst);
    } catch (e) {
      console.error("Worker data error:", e);
    }
  };

  const fetchChatData = async () => {
    try {
      const convs = await apiFetch<ConversationItem[]>("/agent-chat/conversations").catch(() => []);
      if (convs && convs.length > 0) {
        setConversations(convs);
        if (!activeUuid) {
          setActiveUuid(convs[0].conversation_uuid);
        }
      } else {
        // If no conversations exist, auto-create a default chat session
        const newConv = await apiFetch<any>("/agent-chat/conversations", {
          method: "POST",
          body: JSON.stringify({ title: "Emergent Assistant" }),
        }).catch(() => null);
        if (newConv) {
          setConversations([newConv]);
          setActiveUuid(newConv.conversation_uuid);
          setMessages(newConv.messages || []);
        }
      }
    } catch (e) {
      console.error("Chat data error:", e);
    }
  };

  const fetchJobsData = async () => {
    try {
      const data = await apiFetch<any[]>("/builds").catch(() => []);
      if (data) setJobs(data);
    } catch (e) {
      console.error("Jobs error:", e);
    }
  };

  useEffect(() => {
    fetchWorkerData();
    fetchChatData();
    fetchJobsData();
    const interval = setInterval(fetchWorkerData, 6000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!activeUuid) return;
    const syncActiveConversation = () => {
      apiFetch<any>(`/agent-chat/conversations/${activeUuid}`)
        .then((data) => {
          if (data) {
            setMessages(data.messages || []);
            if (data.current_task_id) {
              apiFetch<AutonomousTask>(`/autonomous/tasks/${data.current_task_id}`).then((task) => {
                if (task) {
                  setCurrentTask(task);
                  setActiveArtifactTask((prev) => (prev && prev.id === task.id ? task : prev));
                }
              });
            } else {
              setCurrentTask(null);
            }
          }
        })
        .catch(() => {});
    };
    syncActiveConversation();
    const convInterval = setInterval(syncActiveConversation, 4000);
    return () => clearInterval(convInterval);
  }, [activeUuid]);

  // Command handlers for Autonomous Worker
  const handleWorkerCommand = async (command: "START" | "PAUSE" | "RESUME" | "STOP") => {
    try {
      const s = await apiFetch<SystemState>("/autonomous/control", {
        method: "POST",
        body: JSON.stringify({ command, message: `Builds panel command: ${command}` }),
      });
      if (s) {
        setSystemState(s);
        fetchWorkerData();
      }
    } catch (e) {
      console.error("Command error:", e);
    }
  };

  const handleDispatchStep = async () => {
    try {
      await apiFetch<any>("/autonomous/worker/step", { method: "POST" });
      await fetchWorkerData();
      if (activeUuid) fetchChatData();
    } catch (e) {
      console.error("Step error:", e);
    }
  };

  // Submit new instruction and generate tasks
  const handleCreateInstruction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!instTitle.trim() || !instObjective.trim()) return;
    setIsSubmittingInst(true);
    try {
      const inst = await apiFetch<AutonomousInstruction>("/autonomous/instructions", {
        method: "POST",
        body: JSON.stringify({
          project_id: 1, // Default project
          title: instTitle.trim(),
          work_type: instWorkType,
          objective: instObjective.trim(),
          max_tasks: Number(instMaxTasks) || 3,
        }),
      });

      if (inst && inst.id) {
        // Automatically generate bounded plan and actionable tasks
        await apiFetch<AutonomousTask[]>(`/autonomous/instructions/${inst.id}/plan`, {
          method: "POST",
        });
      }

      setShowInstructionModal(false);
      setInstTitle("");
      setInstObjective("");
      await fetchWorkerData();
    } catch (err: any) {
      alert("Error generating task plan: " + (err.message || "Failed"));
    } finally {
      setIsSubmittingInst(false);
    }
  };

  // View task execution logs
  const handleViewTaskLogs = async (taskId: number) => {
    setActiveLogTaskId(taskId);
    setLoadingLogs(true);
    try {
      const logs = await apiFetch<TaskLog[]>(`/autonomous/tasks/${taskId}/logs`);
      setTaskLogs(logs || []);
    } catch (e) {
      console.error("Logs error:", e);
    } finally {
      setLoadingLogs(false);
    }
  };

  // Create standard build job
  const handleCreateBuildJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobTitle.trim()) return;
    setIsSubmittingJob(true);
    try {
      const newJob = await apiFetch<any>("/builds", {
        method: "POST",
        body: JSON.stringify({
          project_id: 1,
          account_id: Number(jobAccountId),
          title: jobTitle.trim(),
          job_type: jobType,
          priority: jobPriority,
          requirements: jobRequirements.trim() || undefined,
          auto_start: jobAutoExecute,
        }),
      });

      if (newJob && jobAutoExecute) {
        // Execute immediately through queue engine
        try {
          await apiFetch(`/builds/${newJob.id}/execute`, { method: "POST" });
        } catch {}
      }

      setShowJobModal(false);
      setJobTitle("");
      setJobRequirements("");
      await fetchJobsData();
      await fetchWorkerData();
    } catch (err: any) {
      alert("Error creating build job: " + (err.message || "Failed"));
    } finally {
      setIsSubmittingJob(false);
    }
  };

  // Execute direct build job
  const handleExecuteBuildJob = async (jobId: number) => {
    setExecutingJobId(jobId);
    try {
      await apiFetch(`/builds/${jobId}/execute`, { method: "POST" });
      await fetchJobsData();
      await fetchWorkerData();
    } catch (err: any) {
      alert("Execution error: " + (err.message || "Failed"));
    } finally {
      setExecutingJobId(null);
    }
  };

  // Chat handlers
  const handleNewChat = async () => {
    try {
      const newConv = await apiFetch<any>("/agent-chat/conversations", {
        method: "POST",
        body: JSON.stringify({ title: "New Agent Chat" }),
      });
      if (newConv) {
        setConversations((prev) => [newConv, ...prev]);
        setActiveUuid(newConv.conversation_uuid);
        setMessages(newConv.messages || []);
        setCurrentTask(null);
      }
    } catch (e) {
      console.error("New chat error:", e);
    }
  };

  const handleSendMessage = async (customPrompt?: string) => {
    const textToSend = customPrompt !== undefined ? customPrompt : prompt;
    if ((!textToSend.trim() && stagedAttachments.length === 0) || sending || !activeUuid) return;

    const currentPrompt = textToSend.trim();
    const currentAttIds = stagedAttachments.map((a) => a.id);
    const attachedObjects = [...stagedAttachments];

    setPrompt("");
    setStagedAttachments([]);
    setSending(true);

    const optimistic: Message = {
      id: Date.now(),
      conversation_id: 0,
      sender_type: "USER",
      content: currentPrompt,
      is_mock: false,
      attachments: attachedObjects,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);

    try {
      const reply = await apiFetch<Message>(`/agent-chat/conversations/${activeUuid}/messages`, {
        method: "POST",
        body: JSON.stringify({
          prompt: currentPrompt,
          attachment_ids: currentAttIds,
          auto_execute: true,
        }),
      });
      if (reply) {
        setMessages((prev) => [...prev, reply]);
        fetchWorkerData();
        fetchChatData();
      }
    } catch (e) {
      console.error("Send error:", e);
    } finally {
      setSending(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeUuid) return;
    setUploadingFile(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const att = await apiFetch<Attachment>(`/agent-chat/conversations/${activeUuid}/upload`, {
        method: "POST",
        body: formData,
      });
      if (att) {
        setStagedAttachments((prev) => [...prev, att]);
      }
    } catch (err) {
      console.error("Upload error:", err);
    } finally {
      setUploadingFile(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <AppShell noPadding={activeTab === "chat"}>
      {/* Tab Navigation Header */}
      <div className={`border-b border-slate-200 bg-white ${activeTab === "chat" ? "px-6 pt-4 pb-0" : "mb-6 pb-0"}`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
              <Cpu className="w-6 h-6 text-blue-600" />
              Builds & Autonomous Platform
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Autonomous background task workers, interactive agent chat, and multi-account build execution.
            </p>
          </div>

          {/* Quick status pill */}
          <div className="flex items-center gap-2 shrink-0">
            <span
              className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 ${
                systemState?.status === "RUNNING"
                  ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                  : systemState?.status === "PAUSED"
                  ? "bg-amber-100 text-amber-800 border border-amber-300"
                  : "bg-rose-100 text-rose-800 border border-rose-300"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  systemState?.status === "RUNNING"
                    ? "bg-emerald-500 animate-ping"
                    : systemState?.status === "PAUSED"
                    ? "bg-amber-500"
                    : "bg-rose-500"
                }`}
              />
              Worker: {systemState?.status || "STOPPED"}
            </span>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab("worker")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
              activeTab === "worker"
                ? "border-blue-600 text-blue-600 bg-blue-50/50"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Sparkles className="w-4 h-4" />
            Autonomous Worker Platform
          </button>

          <button
            onClick={() => setActiveTab("chat")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
              activeTab === "chat"
                ? "border-blue-600 text-blue-600 bg-blue-50/50"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Bot className="w-4 h-4" />
            Personal Agent Chat
            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-blue-100 text-blue-700">
              Interactive
            </span>
          </button>

          <button
            onClick={() => setActiveTab("jobs")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
              activeTab === "jobs"
                ? "border-blue-600 text-blue-600 bg-blue-50/50"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Layers className="w-4 h-4" />
            Pipeline Jobs ({jobs.length})
          </button>
        </div>
      </div>

      {/* ========================================================= */}
      {/* TAB 1: AUTONOMOUS WORKER PLATFORM                         */}
      {/* ========================================================= */}
      {activeTab === "worker" && (
        <div className="space-y-6">
          {/* Quick Operator Controls Bar */}
          <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs">
            <div>
              <div className="text-sm font-bold text-slate-900">Background Autonomous Execution</div>
              <div className="text-xs text-slate-500 mt-0.5">
                Plans, schedules, executes, monitors, and records work with 50% credit ceiling guard.
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setShowInstructionModal(true)}
                className="px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                New Instruction
              </button>

              {systemState?.status === "RUNNING" ? (
                <button
                  onClick={() => handleWorkerCommand("PAUSE")}
                  className="px-3.5 py-2 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors"
                >
                  <Pause className="w-3.5 h-3.5" />
                  PAUSE
                </button>
              ) : (
                <button
                  onClick={() => handleWorkerCommand("START")}
                  className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors"
                >
                  <Play className="w-3.5 h-3.5 fill-white" />
                  START
                </button>
              )}

              <button
                onClick={() => handleWorkerCommand("STOP")}
                className="px-3.5 py-2 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-800 border border-rose-300 font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors"
              >
                <Square className="w-3.5 h-3.5 fill-rose-700" />
                STOP
              </button>

              <button
                onClick={handleDispatchStep}
                className="px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors"
                title="Execute next step in priority queue"
              >
                <Zap className="w-3.5 h-3.5" />
                Dispatch Step
              </button>
            </div>
          </div>

          {/* Operational Metrics Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
              <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">Queued Tasks</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">{systemState?.total_tasks_queued || 0}</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Pending execution</div>
            </div>
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
              <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">In Progress</div>
              <div className="text-2xl font-bold text-blue-600 mt-1">{systemState?.total_tasks_in_progress || 0}</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Active worker checkpoints</div>
            </div>
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
              <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">Completed</div>
              <div className="text-2xl font-bold text-emerald-600 mt-1">{systemState?.total_tasks_completed || 0}</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Verified completions</div>
            </div>
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs">
              <div className="text-xs uppercase text-slate-400 font-bold tracking-wider">Eligible Accounts</div>
              <div className="text-2xl font-bold text-teal-600 mt-1">
                {budgets.length > 0 ? budgets.filter((b) => b.is_eligible).length : (systemState?.eligible_accounts_count || 0)}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">Under 50% planned ceiling</div>
            </div>
          </div>

          {/* Multi-Account 50% Ceiling Guard & Budgets */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-teal-600" />
                  Multi-Account Rotation & 50% Budget Guard
                </h2>
                <p className="text-xs text-slate-500">
                  Strict budget guard automatically halts tasks on an account when committed usage hits 50%.
                </p>
              </div>
              <button
                onClick={fetchWorkerData}
                className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Sync
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {budgets.map((b) => {
                const startBal = parseFloat(b.starting_balance) || 0;
                const ceilingLimit = parseFloat(b.planned_ceiling_limit) || 0;
                const usage = parseFloat(b.credit_usage) || 0;
                const reserved = parseFloat(b.reserved_credits) || 0;
                const committed = usage + reserved;
                const pct = ceilingLimit > 0 ? Math.min(100, Math.round((committed / ceilingLimit) * 100)) : 0;

                return (
                  <div
                    key={b.id}
                    className={`p-4 rounded-xl border space-y-3 ${
                      b.is_eligible ? "bg-slate-50/50 border-slate-200" : "bg-rose-50/40 border-rose-200"
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="font-bold text-slate-900 truncate max-w-[170px]">{b.account_name}</div>
                        <div className="text-[11px] text-slate-500 font-mono">Src: {b.balance_source}</div>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          b.is_eligible
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            : b.ineligibility_reason === "Ceiling Reached"
                            ? "bg-rose-100 text-rose-800 border border-rose-300"
                            : "bg-amber-100 text-amber-800 border border-amber-300"
                        }`}
                      >
                        {b.is_eligible ? "Eligible" : b.ineligibility_reason || "Ineligible"}
                      </span>
                    </div>

                    <div>
                      <div className="flex justify-between text-xs text-slate-600 mb-1">
                        <span>50% Ceiling Usage</span>
                        <span className="font-bold text-slate-900">
                          ${committed.toFixed(3)} / ${ceilingLimit.toFixed(3)} ({pct}%)
                        </span>
                      </div>
                      <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all duration-500 ${
                            pct >= 100 ? "bg-rose-500" : pct > 75 ? "bg-amber-500" : "bg-blue-600"
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-slate-200/80 text-slate-600">
                      <div>
                        Start: <span className="font-mono text-slate-800">${startBal.toFixed(2)}</span>
                      </div>
                      <div>
                        Headroom:{" "}
                        <span className="font-mono text-emerald-600 font-bold">
                          ${parseFloat(b.remaining_eligible_budget).toFixed(2)}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Autonomous Tasks Execution Queue */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <ListFilter className="w-5 h-5 text-blue-600" />
                  Active Autonomous Tasks & Execution Pipeline
                </h2>
                <p className="text-xs text-slate-500">Structured tasks decomposing instructions with step-by-step verification.</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">{tasks.length} tasks registered</span>
                <button
                  onClick={() => setShowInstructionModal(true)}
                  className="px-2.5 py-1 text-xs font-semibold rounded bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 flex items-center gap-1"
                >
                  <Plus className="w-3 h-3" /> Add Task
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[10px] border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-2.5">Task ID</th>
                    <th className="px-4 py-2.5">Work Type</th>
                    <th className="px-4 py-2.5">Title & Expected Result</th>
                    <th className="px-4 py-2.5">Priority</th>
                    <th className="px-4 py-2.5">Cost ($)</th>
                    <th className="px-4 py-2.5">Status</th>
                    <th className="px-4 py-2.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {tasks.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-xs text-slate-400 italic">
                        No autonomous tasks currently queued. Click &quot;New Instruction&quot; above or prompt the Personal Agent.
                      </td>
                    </tr>
                  ) : (
                    tasks.map((t) => (
                      <tr key={t.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="px-4 py-3 font-mono text-blue-600 font-semibold">{t.task_identifier}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              t.work_type === "VIDEO_CREATION"
                                ? "bg-purple-100 text-purple-700 border border-purple-200"
                                : "bg-blue-100 text-blue-700 border border-blue-200"
                            }`}
                          >
                            {t.work_type === "VIDEO_CREATION" ? "Video" : "Web/App"}
                          </span>
                        </td>
                        <td className="px-4 py-3 max-w-xs">
                          <div className="font-semibold text-slate-900 truncate">{t.title}</div>
                          <div className="text-[11px] text-slate-500 truncate">{t.expected_result}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              t.priority === "CRITICAL"
                                ? "bg-rose-100 text-rose-800"
                                : t.priority === "HIGH"
                                ? "bg-amber-100 text-amber-800"
                                : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {t.priority}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono font-semibold">${parseFloat(t.actual_credit_cost).toFixed(3)}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              t.status === "COMPLETED"
                                ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                                : t.status === "IN_PROGRESS" || t.status === "CHECKPOINT"
                                ? "bg-blue-100 text-blue-800 border border-blue-300"
                                : "bg-slate-100 text-slate-600 border border-slate-300"
                            }`}
                          >
                            {t.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="inline-flex items-center gap-1.5">
                            <button
                              onClick={() => setActiveArtifactTask(t)}
                              className="px-2 py-1 text-[11px] font-semibold rounded bg-purple-50 hover:bg-purple-100 border border-purple-200 text-purple-700 shadow-2xs flex items-center gap-1"
                              title="View generated deliverables, script, storyboard & media outputs"
                            >
                              <Film className="w-3 h-3 text-purple-600" /> Deliverables
                            </button>
                            {t.status !== "COMPLETED" && (
                              <button
                                onClick={handleDispatchStep}
                                className="px-2 py-1 text-[11px] font-semibold rounded bg-white hover:bg-slate-50 border border-slate-200 text-blue-600 shadow-2xs flex items-center gap-1"
                                title="Execute next checkpoint"
                              >
                                <Zap className="w-3 h-3" /> Step
                              </button>
                            )}
                            <button
                              onClick={() => handleViewTaskLogs(t.id)}
                              className="px-2 py-1 text-[11px] font-semibold rounded bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 shadow-2xs flex items-center gap-1"
                              title="View execution logs"
                            >
                              <Terminal className="w-3 h-3 text-slate-500" /> Logs
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* TAB 2: PERSONAL AGENT CHAT (Interactive Agent Workspace)  */}
      {/* ========================================================= */}
      {activeTab === "chat" && (
        <div className="flex h-[calc(100vh-140px)] w-full bg-slate-50 border-t border-slate-200 overflow-hidden select-none">
          {/* Chat Sessions Drawer */}
          <aside className="w-64 border-r border-slate-200 bg-white flex flex-col shrink-0">
            <div className="p-3 border-b border-slate-200 space-y-2 bg-slate-50/50">
              <button
                onClick={handleNewChat}
                className="w-full py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow-xs transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                New Chat
              </button>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  placeholder="Search chats..."
                  value={chatSearch}
                  onChange={(e) => setChatSearch(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-lg pl-8 pr-2.5 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {conversations
                .filter((c) => c.title.toLowerCase().includes(chatSearch.toLowerCase()))
                .map((conv) => {
                  const isActive = activeUuid === conv.conversation_uuid;
                  return (
                    <div
                      key={conv.id}
                      onClick={() => setActiveUuid(conv.conversation_uuid)}
                      className={`flex items-center justify-between p-2.5 rounded-lg text-xs cursor-pointer transition-all ${
                        isActive
                          ? "bg-blue-50 text-blue-900 border border-blue-200 font-semibold shadow-xs"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                      }`}
                    >
                      <div className="truncate pr-1">
                        <div className="truncate">{conv.title}</div>
                        <div className="text-[11px] text-slate-400 truncate mt-0.5">
                          {conv.last_message_preview || "Interactive session"}
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </aside>

          {/* Chat Stream & Composer */}
          <main className="flex-1 flex flex-col min-w-0 h-full bg-white">
            {/* Stream */}
            <div className="flex-1 overflow-y-auto p-5 md:p-6 space-y-5 bg-slate-50/40">
              {messages.length <= 1 && (
                <div className="max-w-xl mx-auto my-6 p-5 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-3">
                  <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
                    <Sparkles className="w-4 h-4 text-blue-600" />
                    Quick Starters — Prompt the Emergent Agent
                  </div>
                  <p className="text-xs text-slate-500">
                    Click any recommendation below to generate an autonomous execution plan on your connected Emergent account:
                  </p>
                  <div className="space-y-2">
                    <button
                      onClick={() => handleSendMessage("Create a high-impact 3-scene video explaining Emergent multi-account session management and budget guard.")}
                      className="w-full text-left p-2.5 rounded-xl border border-slate-200 hover:border-blue-300 hover:bg-blue-50/50 transition-colors text-xs text-slate-700 flex items-center justify-between"
                    >
                      <span>🎬 <strong>Video Creation</strong>: 3-Scene Emergent Hub Explainer Video</span>
                      <Zap className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                    </button>
                    <button
                      onClick={() => handleSendMessage("Build a Next.js responsive analytics dashboard with credit telemetry and real-time session status.")}
                      className="w-full text-left p-2.5 rounded-xl border border-slate-200 hover:border-blue-300 hover:bg-blue-50/50 transition-colors text-xs text-slate-700 flex items-center justify-between"
                    >
                      <span>💻 <strong>Web App Dev</strong>: Next.js Real-time Telemetry Dashboard</span>
                      <Zap className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                    </button>
                    <button
                      onClick={() => handleSendMessage("Check account headroom for Neeraj 3 and plan high-priority build pipeline execution.")}
                      className="w-full text-left p-2.5 rounded-xl border border-slate-200 hover:border-blue-300 hover:bg-blue-50/50 transition-colors text-xs text-slate-700 flex items-center justify-between"
                    >
                      <span>⚡ <strong>Audit & Plan</strong>: Inspect 50% Headroom & Schedule Work</span>
                      <Zap className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                    </button>
                  </div>
                </div>
              )}

              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-3.5 ${msg.sender_type === "USER" ? "justify-end" : "justify-start"}`}
                >
                  {msg.sender_type !== "USER" && (
                    <div className="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-xs mt-0.5">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div className={`max-w-xl md:max-w-2xl space-y-2 ${msg.sender_type === "USER" ? "items-end" : ""}`}>
                    <div
                      className={`p-3.5 rounded-2xl text-xs md:text-sm leading-relaxed shadow-xs ${
                        msg.sender_type === "USER"
                          ? "bg-blue-600 text-white rounded-br-none whitespace-pre-wrap"
                          : "bg-white border border-slate-200 text-slate-800 rounded-bl-none"
                      }`}
                    >
                      {msg.sender_type === "USER" ? msg.content : renderChatMarkdown(msg.content)}
                    </div>

                    {/* Attachments */}
                    {msg.attachments && msg.attachments.length > 0 && (
                      <div className="flex flex-wrap gap-2 pt-0.5">
                        {msg.attachments.map((att) => (
                          <div
                            key={att.id}
                            className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg px-2.5 py-1 text-xs text-slate-700 shadow-xs"
                          >
                            {att.mime_type.startsWith("image/") ? (
                              <ImageIcon className="w-3.5 h-3.5 text-purple-600" />
                            ) : (
                              <FileCode className="w-3.5 h-3.5 text-blue-600" />
                            )}
                            <span className="font-mono truncate max-w-[140px] text-[11px]">{att.file_name}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Action Plan Card */}
                    {msg.action_plan_json && (
                      <div className="bg-white border border-slate-200 rounded-xl p-3.5 text-xs space-y-2 shadow-xs">
                        <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
                          <span className="font-bold text-slate-900 flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                            Generated Plan
                          </span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-100">
                            {msg.is_mock ? "LOCAL STUDIO ENGINE" : "REAL_PROVIDER"}
                          </span>
                        </div>
                        {(() => {
                          try {
                            const plan = JSON.parse(msg.action_plan_json);
                            return (
                              <div className="space-y-1">
                                <div className="font-semibold text-slate-800">{plan.title}</div>
                                <div className="text-slate-600 text-xs">{plan.expected_result}</div>
                              </div>
                            );
                          } catch {
                            return null;
                          }
                        })()}

                        {msg.task_id && (
                          <button
                            type="button"
                            onClick={async () => {
                              const matched = tasks.find((t) => t.id === msg.task_id);
                              if (matched) {
                                setActiveArtifactTask(matched);
                              } else {
                                const fetched = await apiFetch<AutonomousTask>(`/autonomous/tasks/${msg.task_id}`).catch(() => null);
                                if (fetched) setActiveArtifactTask(fetched);
                              }
                            }}
                            className="w-full mt-2 py-2 px-3 rounded-lg bg-purple-50 hover:bg-purple-100 border border-purple-200 text-purple-700 font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors shadow-2xs"
                          >
                            <Film className="w-3.5 h-3.5 text-purple-600" />
                            View Generated Deliverables & Script
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  {msg.sender_type === "USER" && (
                    <div className="w-7 h-7 rounded-lg bg-slate-800 text-white flex items-center justify-center shrink-0 shadow-xs mt-0.5">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
              ))}

              {sending && (
                <div className="flex gap-3.5 items-start">
                  <div className="w-7 h-7 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center shrink-0 shadow-xs">
                    <Bot className="w-4 h-4 animate-spin" />
                  </div>
                  <div className="bg-white border border-slate-200 p-3 rounded-2xl rounded-bl-none text-xs text-slate-600 flex items-center gap-2 shadow-xs">
                    <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
                    Thinking and building your response...
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Composer */}
            <div className="p-3.5 border-t border-slate-200 bg-white">
              {stagedAttachments.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {stagedAttachments.map((att) => (
                    <div
                      key={att.id}
                      className="flex items-center gap-1.5 bg-slate-100 border border-slate-200 rounded-lg px-2 py-1 text-xs text-slate-700"
                    >
                      <Paperclip className="w-3 h-3 text-blue-600" />
                      <span className="font-mono truncate max-w-[140px] text-[11px]">{att.file_name}</span>
                      <button
                        onClick={() => setStagedAttachments((prev) => prev.filter((a) => a.id !== att.id))}
                        className="hover:text-rose-600 p-0.5 text-slate-400"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="flex items-end gap-2">
                <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingFile || sending}
                  className="p-2.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 border border-slate-200 shrink-0"
                  title="Upload attachment"
                >
                  <Paperclip className="w-4 h-4" />
                </button>
                <textarea
                  rows={1}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  placeholder="Ask your Personal Agent to execute any task..."
                  className="flex-1 bg-slate-50 border border-slate-200 focus:bg-white rounded-lg px-3.5 py-2 text-xs md:text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 resize-none max-h-32"
                />
                <button
                  type="submit"
                  disabled={(!prompt.trim() && stagedAttachments.length === 0) || sending}
                  className="p-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white shrink-0 font-semibold shadow-xs disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                </button>
              </form>
            </div>
          </main>
        </div>
      )}

      {/* ========================================================= */}
      {/* TAB 3: PIPELINE BUILDS LIST                               */}
      {/* ========================================================= */}
      {activeTab === "jobs" && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Layers className="w-5 h-5 text-indigo-600" />
                Registered Build Jobs
              </h2>
              <p className="text-xs text-slate-500">Pipeline executions across registered project repositories.</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-slate-500">{jobs.length} total jobs</span>
              <button
                onClick={() => setShowJobModal(true)}
                className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center gap-1.5 shadow-xs transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                Create Build Job
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider text-[10px] border-b border-slate-200">
                <tr>
                  <th className="px-4 py-2.5">Build ID</th>
                  <th className="px-4 py-2.5">Project</th>
                  <th className="px-4 py-2.5">Title</th>
                  <th className="px-4 py-2.5">Assigned Account</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Credits</th>
                  <th className="px-4 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {jobs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-xs text-slate-400 italic">
                      No build jobs recorded yet. Click &quot;Create Build Job&quot; above to schedule your first build!
                    </td>
                  </tr>
                ) : (
                  jobs.map((j) => (
                    <tr key={j.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-4 py-3 font-mono text-blue-600 font-semibold">#BUILD-{j.id}</td>
                      <td className="px-4 py-3 font-semibold text-slate-900">{j.project_name || "General"}</td>
                      <td className="px-4 py-3 text-slate-700 truncate max-w-xs">{j.title}</td>
                      <td className="px-4 py-3 font-mono text-slate-600">{j.account_name || "Assigned Account"}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            j.job_status === "COMPLETED" || j.job_status === "completed"
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                              : j.job_status === "RUNNING" || j.job_status === "running"
                              ? "bg-blue-100 text-blue-800 border border-blue-300"
                              : "bg-slate-100 text-slate-600 border border-slate-300"
                          }`}
                        >
                          {j.job_status}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold">${Number(j.credits_used || 0).toFixed(2)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          {j.job_status !== "COMPLETED" && j.job_status !== "completed" && (
                            <button
                              onClick={() => handleExecuteBuildJob(j.id)}
                              disabled={executingJobId === j.id}
                              className="px-2 py-1 text-[11px] font-semibold rounded bg-white hover:bg-slate-50 border border-slate-200 text-emerald-700 shadow-2xs flex items-center gap-1 disabled:opacity-50"
                              title="Run build in execution engine"
                            >
                              <Play className="w-3 h-3 fill-emerald-600" />
                              {executingJobId === j.id ? "Running..." : "Run"}
                            </button>
                          )}
                          <Link
                            href={`/builds/${j.id}`}
                            className="px-2 py-1 text-[11px] font-semibold rounded bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 shadow-2xs flex items-center gap-1"
                          >
                            <Eye className="w-3 h-3 text-slate-500" /> Details
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL 1: Create Instruction & Tasks */}
      {showInstructionModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600" />
                New Autonomous Instruction & Tasks
              </h3>
              <button onClick={() => setShowInstructionModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Define a high-level goal. The Autonomous Brain will decompose it into actionable verified tasks.
            </p>

            <form onSubmit={handleCreateInstruction} className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700">Instruction Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Next.js SaaS Landing Page Architecture"
                  value={instTitle}
                  onChange={(e) => setInstTitle(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700">Work Type</label>
                <select
                  value={instWorkType}
                  onChange={(e) => setInstWorkType(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900"
                >
                  <option value="WEBSITE_APP_DEV">Website & App Development (Architecture, Code, Deploy)</option>
                  <option value="VIDEO_CREATION">Video Creation (Script, Storyboard, Render)</option>
                </select>
              </div>

              <div>
                <label className="font-semibold text-slate-700">Objective & Requirements</label>
                <textarea
                  rows={3}
                  required
                  placeholder="Detail the deliverable, tech stack, and acceptance criteria..."
                  value={instObjective}
                  onChange={(e) => setInstObjective(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700">Max Bounded Tasks</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={instMaxTasks}
                  onChange={(e) => setInstMaxTasks(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900 font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowInstructionModal(false)}
                  className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingInst}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold disabled:opacity-50"
                >
                  {isSubmittingInst ? "Generating Tasks..." : "Generate Task Plan"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Create Build Job */}
      {showJobModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-600" />
                Create Pipeline Build Job
              </h3>
              <button onClick={() => setShowJobModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateBuildJob} className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700">Build Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Production Docker Image & Next.js Bundle"
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700">Assigned Account</label>
                <select
                  value={jobAccountId}
                  onChange={(e) => setJobAccountId(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900"
                >
                  <option value={6}>Neeraj 3 (Connected - 109.65 Credits)</option>
                  <option value={4}>Neeraj (Account #4)</option>
                  <option value={5}>Neeraj2 (Account #5)</option>
                  <option value={7}>Neeraj 4 (Account #7)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-semibold text-slate-700">Job Type</label>
                  <select
                    value={jobType}
                    onChange={(e) => setJobType(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900"
                  >
                    <option value="prompt_build">Prompt Build</option>
                    <option value="code_gen">Code Generation</option>
                    <option value="full_stack">Full Stack</option>
                    <option value="deployment">Deployment</option>
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-slate-700">Priority</label>
                  <select
                    value={jobPriority}
                    onChange={(e) => setJobPriority(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900"
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="CRITICAL">Critical</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-semibold text-slate-700">Requirements / Notes</label>
                <textarea
                  rows={2}
                  placeholder="Specific requirements for this build execution..."
                  value={jobRequirements}
                  onChange={(e) => setJobRequirements(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-1 text-slate-900"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="auto-exec"
                  checked={jobAutoExecute}
                  onChange={(e) => setJobAutoExecute(e.target.checked)}
                  className="rounded text-blue-600"
                />
                <label htmlFor="auto-exec" className="text-slate-700 text-xs font-medium cursor-pointer">
                  Auto-Execute immediately through queue engine
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowJobModal(false)}
                  className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingJob}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold disabled:opacity-50"
                >
                  {isSubmittingJob ? "Creating..." : "Create Build Job"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: Task Logs View */}
      {activeLogTaskId !== null && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Terminal className="w-4 h-4 text-blue-600" />
                Execution Logs: Task #{activeLogTaskId}
              </h3>
              <button onClick={() => setActiveLogTaskId(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            {loadingLogs ? (
              <div className="p-8 text-center text-xs text-slate-500">Loading execution checkpoint logs...</div>
            ) : taskLogs.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400 italic">No execution logs recorded yet.</div>
            ) : (
              <div className="bg-slate-950 rounded-xl p-4 text-slate-200 font-mono text-[11px] max-h-80 overflow-y-auto space-y-1.5">
                {taskLogs.map((log) => (
                  <div key={log.id} className="flex items-start gap-2">
                    <span className="text-slate-500 shrink-0">
                      {new Date(log.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                    </span>
                    <span
                      className={`px-1 py-0.2 rounded text-[9px] font-bold ${
                        log.log_level === "ERROR"
                          ? "bg-rose-900 text-rose-200"
                          : log.log_level === "WARN"
                          ? "bg-amber-900 text-amber-200"
                          : "bg-emerald-900 text-emerald-200"
                      }`}
                    >
                      {log.log_level}
                    </span>
                    <span className="text-slate-300">{log.message}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <button
                onClick={() => setActiveLogTaskId(null)}
                className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 4: Deliverables & Generated Artifacts Modal */}
      {activeArtifactTask !== null && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-2xl w-full p-6 space-y-5 my-8 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between border-b border-slate-100 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    activeArtifactTask.work_type === "VIDEO_CREATION"
                      ? "bg-purple-100 text-purple-700 border border-purple-200"
                      : "bg-blue-100 text-blue-700 border border-blue-200"
                  }`}>
                    {activeArtifactTask.work_type === "VIDEO_CREATION" ? "Video Production" : "Web / App Development"}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                    {activeArtifactTask.status}
                  </span>
                </div>
                <h3 className="font-bold text-slate-900 text-lg mt-1">{activeArtifactTask.title}</h3>
                <p className="font-mono text-xs text-blue-600 mt-0.5">{activeArtifactTask.task_identifier}</p>
              </div>
              <button onClick={() => setActiveArtifactTask(null)} className="text-slate-400 hover:text-slate-600 p-1">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Checkpoint Deliverables Content */}
            {(() => {
              let checkpointsList: any[] = [];
              let resultMeta: any = {};
              try {
                if (activeArtifactTask.checkpoints) {
                  checkpointsList = JSON.parse(activeArtifactTask.checkpoints);
                }
              } catch {}
              try {
                if (activeArtifactTask.result_metadata) {
                  resultMeta = JSON.parse(activeArtifactTask.result_metadata);
                }
              } catch {}

              const scriptStep = checkpointsList.find((c: any) => c.step === "SCRIPT_GENERATION" || c.script);
              const storyboardStep = checkpointsList.find((c: any) => c.step === "STORYBOARD_PROMPTS" || c.prompts);
              const voiceoverStep = checkpointsList.find((c: any) => c.step === "VOICEOVER_SYNTHESIS" || c.voiceover);
              const renderStep = checkpointsList.find((c: any) => c.step === "VIDEO_RENDERING_ASSEMBLY" || c.render);
              const emergentUrl = resultMeta?.emergent_task_url || checkpointsList.find((c: any) => c.emergent_url)?.emergent_url;
              const isRealGenerating = !activeArtifactTask.is_mock && activeArtifactTask.status !== "COMPLETED";

              return (
                <div className="space-y-4 text-xs">
                  {/* Live Real Emergent Workspace Banner if available */}
                  {!activeArtifactTask.is_mock && (
                    <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-emerald-900">
                        <span className="px-2 py-0.5 rounded bg-emerald-600 text-white text-[10px] font-bold">
                          REAL EMERGENT STUDIO
                        </span>
                        <span className="text-xs font-medium">
                          {activeArtifactTask.status === "COMPLETED"
                            ? "Executed on authenticated Emergent browser session"
                            : "Generating live on app.emergent.sh..."}
                        </span>
                      </div>
                      {emergentUrl && (
                        <a
                          href={emergentUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="px-3 py-1 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-[11px] font-semibold flex items-center gap-1"
                        >
                          <ExternalLink className="w-3 h-3" />
                          Open in Emergent
                        </a>
                      )}
                    </div>
                  )}

                  {/* Master Render Preview */}
                  {activeArtifactTask.work_type === "VIDEO_CREATION" && (
                    <div className="bg-slate-950 rounded-xl p-4 text-white space-y-3 shadow-inner">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-xs flex items-center gap-1.5 text-purple-300">
                          <Film className="w-4 h-4 text-purple-400" />
                          {activeArtifactTask.is_mock ? "Master Render Artifact (Custom Prompt Video)" : "Emergent Video Agent Output"}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded bg-purple-900/60 border border-purple-500/40 text-[10px] font-bold text-purple-200">
                            {renderStep?.render?.resolution || "1280x720"} @ {renderStep?.render?.fps || 30}FPS
                          </span>
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-slate-300">
                            H.264 + AAC Audio
                          </span>
                        </div>
                      </div>

                      {/* Real HTML5 Video Player OR Live Emergent Progress Screenshot while rendering */}
                      {isRealGenerating ? (
                        <div className="relative aspect-video rounded-xl bg-slate-900 border border-slate-800 overflow-hidden flex flex-col justify-center items-center">
                          <img
                            src={`http://localhost:8000/api/v1/autonomous/tasks/${activeArtifactTask.id}/preview-image?t=${Date.now()}`}
                            alt="Live Emergent Video Progress"
                            className="w-full h-full object-contain"
                          />
                        </div>
                      ) : (
                        <div className="relative aspect-video rounded-xl bg-black border border-slate-800 overflow-hidden shadow-2xl flex flex-col justify-center items-center">
                          <video
                            key={`${activeArtifactTask.id}-${activeArtifactTask.task_identifier}-${activeArtifactTask.status}`}
                            controls
                            playsInline
                            preload="auto"
                            className="w-full h-full object-contain"
                            src={`http://localhost:8000/api/v1/autonomous/tasks/${activeArtifactTask.id}/video`}
                          >
                            Your browser does not support the video tag.
                          </video>
                        </div>
                      )}

                      {/* Video Actions: Direct Download */}
                      {!isRealGenerating && (
                        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-slate-800">
                          <div className="text-[11px] text-slate-400 font-mono flex items-center gap-1.5">
                            <Film className="w-3.5 h-3.5 text-purple-400" />
                            <span>{activeArtifactTask.task_identifier}.mp4</span>
                          </div>

                          <a
                            href={`http://localhost:8000/api/v1/autonomous/tasks/${activeArtifactTask.id}/video`}
                            download={`${activeArtifactTask.task_identifier}.mp4`}
                            target="_blank"
                            rel="noreferrer"
                            className="px-3.5 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-semibold text-xs flex items-center gap-1.5 shadow-md transition-colors"
                          >
                            <Download className="w-3.5 h-3.5" />
                            Download MP4 Video
                          </a>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Live Web / App Interactive Preview */}
                  {activeArtifactTask.work_type !== "VIDEO_CREATION" && (
                    <div className="bg-slate-950 rounded-xl p-4 text-white space-y-3 shadow-inner">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-xs flex items-center gap-1.5 text-blue-300">
                          <FileCode className="w-4 h-4 text-blue-400" />
                          Live Generated Website / App Preview
                        </span>
                        <span className="px-2 py-0.5 rounded bg-blue-900/60 border border-blue-500/40 text-[10px] font-bold text-blue-200">
                          Interactive Build
                        </span>
                      </div>

                      <div className="relative aspect-video rounded-xl bg-white border border-slate-800 overflow-hidden shadow-2xl">
                        <iframe
                          key={`web-${activeArtifactTask.id}`}
                          src={`http://localhost:8000/api/v1/autonomous/tasks/${activeArtifactTask.id}/webapp`}
                          className="w-full h-full border-0"
                          title={activeArtifactTask.title}
                        />
                      </div>

                      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-slate-800">
                        <div className="text-[11px] text-slate-400 font-mono">
                          {activeArtifactTask.task_identifier}-app.html
                        </div>
                        <div className="flex items-center gap-2">
                          <a
                            href={`http://localhost:8000/api/v1/autonomous/tasks/${activeArtifactTask.id}/webapp`}
                            target="_blank"
                            rel="noreferrer"
                            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs flex items-center gap-1.5 transition-colors"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            Open Full App
                          </a>
                          <a
                            href={`http://localhost:8000/api/v1/autonomous/tasks/${activeArtifactTask.id}/webapp?download=true`}
                            download={`${activeArtifactTask.task_identifier}-app.html`}
                            className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center gap-1.5 shadow-md transition-colors"
                          >
                            <Download className="w-3.5 h-3.5" />
                            Download App HTML
                          </a>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Scene Script & Storyboard */}
                  {scriptStep && scriptStep.script && (
                    <div className="space-y-2">
                      <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                        <FileCode className="w-4 h-4 text-blue-600" />
                        Scene-by-Scene Script & Narration
                      </h4>
                      <div className="space-y-2">
                        {scriptStep.script.scenes?.map((sc: any, idx: number) => {
                          const promptObj = storyboardStep?.prompts?.find((p: any) => p.scene === sc.scene_id) || storyboardStep?.prompts?.[idx];
                          return (
                            <div key={idx} className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-slate-900 text-[11px] flex items-center gap-1">
                                  Scene {sc.scene_id} ({sc.duration_sec}s)
                                </span>
                                <span className="text-[10px] text-slate-500 font-mono">Visual: {sc.visual}</span>
                              </div>
                              <div className="text-slate-700 text-xs italic bg-white p-2 rounded-lg border border-slate-100">
                                &quot;{sc.narration}&quot;
                              </div>
                              {promptObj && (
                                <div className="text-[11px] text-slate-600 flex items-start gap-1">
                                  <span className="font-semibold text-purple-700 shrink-0">🎨 Visual Prompt:</span>
                                  <span className="font-mono text-slate-600 text-[10px]">{promptObj.prompt}</span>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Voiceover Synthesis Details */}
                  {voiceoverStep && voiceoverStep.voiceover && (
                    <div className="p-3 bg-blue-50/60 rounded-xl border border-blue-200 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Volume2 className="w-4 h-4 text-blue-600" />
                        <div>
                          <div className="font-bold text-slate-900 text-xs">AI Voiceover Track Synthesized</div>
                          <div className="text-[11px] text-slate-600">
                            Model: <span className="font-mono font-semibold">{voiceoverStep.voiceover.voice_profile}</span> • Sample Rate: {voiceoverStep.voiceover.sample_rate_hz} Hz
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono font-bold text-blue-700 text-xs">{voiceoverStep.voiceover.audio_duration_sec}s</div>
                        <div className="text-[10px] text-slate-500">{voiceoverStep.voiceover.word_count} words</div>
                      </div>
                    </div>
                  )}

                  {/* Acceptance Criteria Report */}
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                    <div className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      Acceptance Criteria & Audit Validation
                    </div>
                    {(() => {
                      let crit: string[] = [];
                      try {
                        crit = JSON.parse(activeArtifactTask.acceptance_criteria || "[]");
                      } catch {}
                      return (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                          {crit.map((c, i) => (
                            <div key={i} className="flex items-center gap-1.5 text-[11px] text-slate-700">
                              <span className="w-3.5 h-3.5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-[9px] font-bold shrink-0">
                                ✓
                              </span>
                              <span>{c}</span>
                            </div>
                          ))}
                        </div>
                      );
                    })()}
                  </div>

                  {/* Ledger Provenance Card */}
                  <div className="flex items-center justify-between text-[11px] text-slate-500 bg-white p-2.5 rounded-lg border border-slate-100 font-mono">
                    <span>Artifact Provenance: Verified Storage</span>
                    <span>Actual Cost: ${parseFloat(activeArtifactTask.actual_credit_cost).toFixed(4)}</span>
                  </div>
                </div>
              );
            })()}

            <div className="flex justify-between items-center pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => {
                  const blob = new Blob([JSON.stringify(activeArtifactTask, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${activeArtifactTask.task_identifier}-deliverables.json`;
                  a.click();
                }}
                className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold text-xs flex items-center gap-1.5 shadow-2xs"
              >
                <Download className="w-3.5 h-3.5 text-slate-500" />
                Download JSON Manifest
              </button>

              <button
                onClick={() => setActiveArtifactTask(null)}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs"
              >
                Close Deliverables
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}

export default function BuildsPage() {
  return (
    <React.Suspense fallback={<div className="p-8 text-center text-slate-500">Loading Builds Workspace...</div>}>
      <BuildsContent />
    </React.Suspense>
  );
}
