// Default enterprise mock data clearly labeled to prevent confusion with live production metrics.

export const MOCK_LABEL = "DEMO DATA — NOT LIVE BALANCE";

export interface AccountItem {
  id: number;
  account_identifier: string;
  account_name: string;
  email?: string | null;
  organization: string;
  owner_user_id?: number | null;
  owner_name?: string | null;
  ownership_type: "COMPANY_OWNED" | "PERSONAL";
  description?: string | null;
  status: "active" | "suspended" | "pending";
  auth_type: "oauth" | "mcp" | "api_key" | "universal_key";
  connection_status: "CONNECTED" | "DISCONNECTED" | "EXPIRED" | "AUTHORIZATION_REQUIRED" | "ERROR" | "PENDING" | "API_CONNECTED" | "NOT_CONNECTED" | "LOGIN_IN_PROGRESS" | "OTP_REQUIRED" | "AUTHENTICATED" | "LOGIN_FAILED" | "SESSION_EXPIRED" | "STANDBY" | "EXHAUSTED";
  credit_sync_status: string;
  latest_credit_balance: number;
  last_connected_at?: string | null;
  last_synced_at?: string | null;
  assigned_members_count?: number;
  has_saved_password?: boolean;
  is_mock?: boolean;
}

export const INITIAL_ACCOUNTS: AccountItem[] = [
  {
    id: 1,
    account_identifier: "EMG-PROD-01",
    account_name: "Production Core Account",
    email: "prod-core@company.org",
    organization: "Enterprise Engineering",
    owner_name: "Hub System Administrator",
    ownership_type: "COMPANY_OWNED",
    description: "Primary production pipeline cluster",
    status: "active",
    auth_type: "oauth",
    connection_status: "CONNECTED",
    credit_sync_status: "manual_only",
    latest_credit_balance: 1250.0,
    last_connected_at: "2026-11-04 09:15 UTC",
    last_synced_at: "2026-11-04 09:15 UTC",
    assigned_members_count: 3,
    is_mock: true,
  },
  {
    id: 2,
    account_identifier: "EMG-DEV-02",
    account_name: "Dev & Sandbox Account",
    email: "dev-sandbox@company.org",
    organization: "AI R&D Lab",
    owner_name: "Hub Operations Manager",
    ownership_type: "COMPANY_OWNED",
    description: "Rapid prototyping and experiment workloads",
    status: "active",
    auth_type: "mcp",
    connection_status: "CONNECTED",
    credit_sync_status: "manual_only",
    latest_credit_balance: 540.25,
    last_connected_at: "2026-11-04 08:45 UTC",
    last_synced_at: "2026-11-04 08:45 UTC",
    assigned_members_count: 2,
    is_mock: true,
  },
  {
    id: 3,
    account_identifier: "EMG-QA-03",
    account_name: "Quality Assurance Account",
    email: "qa-team@company.org",
    organization: "QA Operations",
    owner_name: "QA Lead",
    ownership_type: "COMPANY_OWNED",
    description: "End-to-end regression validation node",
    status: "active",
    auth_type: "oauth",
    connection_status: "DISCONNECTED",
    credit_sync_status: "manual_only",
    latest_credit_balance: 450.0,
    last_connected_at: "2026-11-01 12:00 UTC",
    last_synced_at: "2026-11-03 18:20 UTC",
    assigned_members_count: 1,
    is_mock: true,
  },
  {
    id: 4,
    account_identifier: "EMG-PERS-04",
    account_name: "Dr. Chen Research Node",
    email: "chen.personal@company.org",
    organization: "Advanced Research",
    owner_name: "Dr. Victor Chen",
    ownership_type: "PERSONAL",
    description: "Specialized model fine-tuning personal node",
    status: "active",
    auth_type: "oauth",
    connection_status: "PENDING",
    credit_sync_status: "manual_only",
    latest_credit_balance: 850.0,
    last_connected_at: null,
    last_synced_at: "2026-11-04 07:00 UTC",
    assigned_members_count: 1,
    is_mock: true,
  },
];

export const MOCK_DASHBOARD_METRICS = {
  total_registered: 4,
  connected_accounts: 2,
  disconnected_accounts: 2,
  total_available_credits: 3090.25,
  today_consumption: 48.25,
  monthly_consumption: 645.8,
  active_build_jobs: 3,
  failed_jobs: 0,
  is_mock: true,
};

export const MOCK_RECENT_BUILDS = [
  {
    id: 101,
    project: "Autonomous Agent Workspace",
    account: "EMG-PROD-01",
    job_type: "prompt_build",
    status: "completed",
    credits_used: 12.5,
    operator: "Hub System Administrator",
    time: "25 mins ago",
  },
  {
    id: 102,
    project: "Customer Portal Gen",
    account: "EMG-DEV-02",
    job_type: "code_gen",
    status: "running",
    credits_used: 6.0,
    operator: "Hub Operations Manager",
    time: "40 mins ago",
  },
  {
    id: 103,
    project: "Workflow Orchestrator",
    account: "EMG-PROD-01",
    job_type: "full_stack",
    status: "pending",
    credits_used: 0.0,
    operator: "Hub Team Member",
    time: "1 hour ago",
  },
];

export const MOCK_RECENT_ACTIVITIES = [
  {
    id: 1,
    user: "admin@emergent-hub.com",
    action: "account_synced",
    resource: "EMG-PROD-01",
    time: "10 mins ago",
    status: "success",
  },
  {
    id: 2,
    user: "manager@emergent-hub.com",
    action: "credit_manual_entry",
    resource: "+500 credits to EMG-DEV-02",
    time: "1 hour ago",
    status: "success",
  },
  {
    id: 3,
    user: "system_security",
    action: "mailbox_auth_check",
    resource: "auth-mailbox@internal.corp",
    time: "3 hours ago",
    status: "notice (unverified access)",
  },
];

export const MOCK_CONSUMPTION_TREND = [
  { day: "Oct 29", credits: 35.5, jobs: 4 },
  { day: "Oct 30", credits: 52.0, jobs: 7 },
  { day: "Oct 31", credits: 41.2, jobs: 5 },
  { day: "Nov 01", credits: 68.4, jobs: 9 },
  { day: "Nov 02", credits: 28.0, jobs: 3 },
  { day: "Nov 03", credits: 74.5, jobs: 11 },
  { day: "Nov 04", credits: 48.25, jobs: 6 },
];
