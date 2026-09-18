/** D(BFF, 기본 :8003)의 /ui/* JSON API 클라이언트.
 *
 * 화면은 A/B/C를 직접 부르지 않는다 - 항상 D만 거친다(D_frontend.md 11, 15절).
 * D는 실패해도 HTTP 200을 주고 envelope의 status로 결과를 알려주므로,
 * 호출측은 res.ok가 아니라 status로 분기해야 한다.
 */

export type ErrorData = { message: string; retryable: boolean; code?: string | null };

export type Envelope<T> =
  | { status: "success"; data: T }
  | { status: "empty"; message: string }
  | { status: "error"; data: ErrorData };

export type User = { user_id: number; username: string };

/** 지역 선택지. 좌표는 화면이 아니라 B가 관리한다 (B_openapi/region.py). */
export type Region = { code: string; name: string; map_x: number; map_y: number };

export type Place = {
  content_id: string;
  name: string;
  addr: string;
  map_x: number;
  map_y: number;
  dist: number;
  image: string | null;
  category?: string | null;
  use_time?: string | null;
  rest_date?: string | null;
  expected_stay_minutes?: number | null;
  overview?: string | null;
};

export type CongestionView = { has_data: boolean; rate: number | null; label: string; is_high: boolean };

export type PlanItem = {
  content_id: string;
  order: number;
  visit_time: string;
  name: string;
  note: string;
  /** note와 별개로 내려오는 집중률 라벨. note는 LLM 설명으로 덮인다. */
  congestion_label: string;
  high_congestion: boolean;
  replan_prompt?: { message: string; target_name: string };
  /** 최종 일정에 뽑힌 장소만 조회되는 상세정보 (소개문/운영시간/휴무일). */
  detail: Place | null;
};

export type ReplanResult = { plan: PlanView; changed_content_id: string; change_reason: string };

export type PlanView = { title: string; summary: string; travel_date: string; items: PlanItem[] };

export type SavedPlanItem = { content_id: string; name: string; order: number; visit_time: string; note: string | null };
export type SavedPlan = { plan_id: number; title: string; travel_date: string; items: SavedPlanItem[] };

/** 저장 일정 상세. current는 B에서 실시간 재조회한 현재 관광지 정보이며,
 *  B 호출이 실패하면 null이다 (저장된 기본 정보만으로도 화면은 그린다). */
export type PlanDetailItem = {
  content_id: string;
  name: string;
  order: number;
  visit_time: string;
  note: string | null;
  current: Place | null;
};
export type PlanDetail = { plan_id: number; title: string; travel_date: string; items: PlanDetailItem[] };

// 기본값 ""(같은 origin) - vite dev 서버와 worker가 /ui 를 D로 프록시한다.
// 다른 호스트의 D를 쓰려면 NEXT_PUBLIC_BFF_BASE_URL 을 설정한다.
const BASE: string =
  (typeof process !== "undefined" && process.env && process.env.NEXT_PUBLIC_BFF_BASE_URL) || "";

const NETWORK_ERROR = { message: "서버에 연결하지 못했습니다.\n잠시 후 다시 시도해주세요.", retryable: true };

async function call<T>(path: string, method = "GET", body?: unknown): Promise<Envelope<T>> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      credentials: "include",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    return { status: "error", data: NETWORK_ERROR };
  }

  // D가 잡지 못한 예외(500)나 FastAPI 검증 오류(422)는 envelope이 아니다.
  if (!res.ok) {
    return {
      status: "error",
      data: { message: `요청을 처리하지 못했습니다. (HTTP ${res.status})`, retryable: res.status >= 500 },
    };
  }
  try {
    return (await res.json()) as Envelope<T>;
  } catch {
    return { status: "error", data: NETWORK_ERROR };
  }
}

/** status가 error/empty면 화면에 띄울 문구를, success면 null을 돌려준다. */
export function errorMessage(env: Envelope<unknown>): string | null {
  if (env.status === "error") return env.data.message;
  if (env.status === "empty") return env.message;
  return null;
}

/** 실패 원인이 "로그인이 필요함"인지. 이때는 문구 대신 로그인 창을 띄운다. */
export function needsLogin(env: Envelope<unknown>): boolean {
  return env.status === "error" && (env.data.code === "AUTH_REQUIRED" || env.data.code === "SESSION_EXPIRED");
}

// --- 인증 (A) ---------------------------------------------------------------
export const register = (username: string, password: string) =>
  call<User>("/ui/auth/register", "POST", { username, password });
export const login = (username: string, password: string) =>
  call<User>("/ui/auth/login", "POST", { username, password });
export const logout = () => call<null>("/ui/auth/logout", "POST", {});
export const me = () => call<User | null>("/ui/auth/me");

// --- 지역 / 관광지 / 집중률 (B) ---------------------------------------------
export const listRegions = () => call<Region[]>("/ui/regions");
/** 반경은 보내지 않는다 - B의 설정값을 코스 생성과 똑같이 쓴다. */
export const nearby = (map_x: number, map_y: number) =>
  call<Place[]>("/ui/places/nearby", "POST", { map_x, map_y });
/** 이름을 함께 넘겨야 B가 관광지당 상세조회를 한 번 더 하지 않는다. */
export const congestion = (places: { content_id: string; name: string }[], travel_date: string) =>
  call<Record<string, CongestionView>>("/ui/places/congestion", "POST", {
    travel_date,
    targets: places.map((p) => ({ content_id: p.content_id, name: p.name })),
  });

// --- 일정 생성 (C) / 저장 (A) ------------------------------------------------
export const generatePlan = (req: {
  map_x: number;
  map_y: number;
  travel_date: string;
  start_time: string;
  end_time: string;
  place_count: number;
  theme?: string | null;
}) => call<PlanView>("/ui/plan/generate", "POST", req);

/** 집중률이 높은 한 곳만 다른 관광지로 교체한다. */
export const replan = (plan: PlanView, target_content_id: string, reason: string) =>
  call<ReplanResult>("/ui/plan/replan", "POST", {
    plan: {
      title: plan.title,
      travel_date: plan.travel_date,
      summary: plan.summary,
      items: plan.items.map((i) => ({
        content_id: i.content_id,
        name: i.name,
        order: i.order,
        visit_time: i.visit_time,
        note: i.note,
        congestion_label: i.congestion_label,
        high_congestion: i.high_congestion,
        // 이미 받아둔 상세정보를 돌려보내야 C가 대상 좌표를 다시 조회하지 않는다.
        detail: i.detail,
      })),
    },
    target_content_id,
    reason,
  });

export const savePlan = (plan: PlanView) =>
  call<SavedPlan>("/ui/plans", "POST", {
    title: plan.title,
    travel_date: plan.travel_date,
    items: plan.items.map((i) => ({
      content_id: i.content_id,
      name: i.name,
      order: i.order,
      visit_time: i.visit_time,
      note: i.note,
    })),
  });

export const listPlans = () => call<SavedPlan[]>("/ui/plans");
export const getPlanDetail = (planId: number) => call<PlanDetail>(`/ui/plans/${planId}`);

// --- 화면 조건 -> API 파라미터 변환 ------------------------------------------

/** 공통 계약의 "YYYYMMDD" -> 화면 표기용 "2026.09.12". */
export const formatYmd = (ymd: string) =>
  /^\d{8}$/.test(ymd) ? `${ymd.slice(0, 4)}.${ymd.slice(4, 6)}.${ymd.slice(6)}` : ymd;

/** 사용자 기기 기준 오늘(+offsetDays)을 "YYYY-MM-DD"로.
 *  toISOString()은 UTC라서 한국 시간 오전 9시 전에는 어제 날짜가 나온다. */
export function localIsoDate(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** <input type="date">의 "YYYY-MM-DD" -> 공통 계약의 "YYYYMMDD". */
export const toYmd = (isoDate: string) => isoDate.replaceAll("-", "");

/** 여행 일수 -> 방문지 수. C는 하루치 일정만 만들므로 상한을 둔다. */
export function placeCountFor(startIso: string, endIso: string): number {
  const start = Date.parse(startIso);
  const end = Date.parse(endIso);
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return 3;
  const days = Math.round((end - start) / 86_400_000) + 1;
  return Math.min(8, Math.max(2, days * 2));
}
