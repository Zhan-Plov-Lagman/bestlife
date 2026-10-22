export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
let csrf = "";
let sessionExpires = 0;
export async function getSession(): Promise<string> {
  const response = await fetch(`${API}/api/session`);
  if (!response.ok) throw new Error("Backend unavailable");
  const session = await response.json();
  csrf = session.csrf;
  sessionExpires = Date.now() + (session.expires_in ?? 900) * 1000;
  return csrf;
}
export async function api<T>(path: string, body?: unknown, method = "POST"): Promise<T> {
  if (body && (!csrf || Date.now() >= sessionExpires - 5000)) await getSession();
  const response = await fetch(`${API}/api/${path}`, body ? { method, headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify(body) } : undefined);
  if (!response.ok) { const error = await response.json(); throw new Error(typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail)); }
  return response.json() as Promise<T>;
}
export function money(value: string | number | null | undefined): string {
  return value == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(Number(value));
}
export type Signal = { strategy: string; action: string; score: number; reason_codes: string[] };
export type Decision = { decision_id: string; event_time: string; symbol: string; action: string; strategy: string; reason_codes: string[]; signals: Signal[]; regime: { regime: string; score: number }; risk: { status: string; checks: Record<string, boolean> }; features: Record<string, number | string | null> };
export type Token = { token_mint: string; symbol: string; price: string; liquidity: string; volume: string; provider: string; event_time: string; data_quality_status: string; features: Record<string, number | null>; regime: { regime: string } };
export type Position = { token_mint: string; symbol: string; quantity: string; entry_price: string; cost_basis: string; net_liquidation_value: string; mark_time: string; strategy: string };
export type Settings = { initial_balance: string; max_position: string; max_exposure: string; max_positions: number; max_drawdown: string; daily_loss_limit: string; min_liquidity: string; max_cost_fraction: string; fee_rate: string; network_fee: string; slippage: string; uncertainty_margin: string; stop_loss: string; take_profit: string; freshness_seconds: number; signal_ttl_seconds: number; execution_delay_seconds: number; performance: string; provider: string; token_mints: string[]; aggressor_enabled: boolean; scalping_enabled: boolean; retention_days: number };
export type State = { recovery_marks: string[]; reconciliation_errors: string[]; session_id: string; cash: string; equity: string; realized: string; unrealized: string; net_pnl: string; fees: string; slippage_cost: string; max_drawdown: string; running: boolean; killed: boolean; fault: string | null; provider_healthy: boolean; decision_count: number; skipped: number; win_rate: number | null; closed: number; positions: Record<string, Position>; pending: Record<string, unknown>; suspended: string[]; last_decision: Decision | null; tokens: Token[]; settings: Settings; monitor: Record<string, string | number | null> };
