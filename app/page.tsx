"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import * as api from "./api";

type Tab = "planner" | "realtime" | "mypage";
type Dialog = "login" | "invite" | null;

// 사용자 기기 기준 오늘. toISOString()은 UTC라 한국 오전 9시 전엔 어제가 된다.
const todayYmd = () => api.toYmd(api.localIsoDate());

export default function Home() {
  const [landing, setLanding] = useState(true);
  const [tab, setTab] = useState<Tab>("planner");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [user, setUser] = useState<api.User | null>(null);
  const [signup, setSignup] = useState(false);
  const [regions, setRegions] = useState<api.Region[]>([]);
  const [regionError, setRegionError] = useState<string | null>(null);
  const [regionCode, setRegionCode] = useState<string | null>(null);
  const [budget, setBudget] = useState("30");
  const [openStat, setOpenStat] = useState<string | null>(null);
  const member = user !== null;
  const region = regions.find((r) => r.code === regionCode) ?? null;

  // 새로고침해도 A의 세션 쿠키가 살아 있으면 로그인 상태를 복원한다.
  useEffect(() => { api.me().then((env) => { if (env.status === "success" && env.data) setUser(env.data); }); }, []);

  // 지역 선택지와 대표 좌표는 B가 관리한다 - 화면은 하드코딩하지 않는다.
  useEffect(() => {
    api.listRegions().then((env) => {
      if (env.status === "success") { setRegions(env.data); setRegionCode(env.data[0]?.code ?? null); }
      else setRegionError(api.errorMessage(env));
    });
  }, []);

  // effect 안에서도 쓰이므로 참조가 매 렌더 바뀌지 않게 고정한다.
  const openLogin = useCallback(() => setDialog("login"), []);
  const onAuthed = (next: api.User) => { setUser(next); setDialog(null); setSignup(false); };
  const doLogout = async () => { await api.logout(); setUser(null); setTab("planner"); };

  if (signup) return <Signup onBack={() => setSignup(false)} onAuthed={onAuthed} />;
  if (landing) return <Landing onStart={() => setLanding(false)} onTab={(next) => { setTab(next); setLanding(false); }} onLogin={() => { setLanding(false); setDialog("login"); }} />;

  return <main className="app-shell">
    <div className="hero-surface">
      <header className="topbar topbar-minimal">
        <div className="header-actions">{user ? <button className="profile-chip" onClick={() => setTab("mypage")}>{user.username}님 <span>✦</span></button> : <button className="login-pill" onClick={() => setDialog("login")}>로그인 <span>→</span></button>}</div>
      </header>
      <section className={`welcome-band ${tab}-hero`}>
        <div className={tab === "planner" ? "hero-copy" : "sub-hero-copy"}>{tab === "planner" ? <><p className="eyebrow">JEJU TRIP EDITION</p><h1>오늘 제주,<br /><strong>어디GO?</strong></h1><p>취향에 맞는 동선부터 지금 한적한 장소까지<br />여행의 망설임을 가볍게 덜어드릴게요.</p><span className="hero-sticker">슝! 코스 생성</span></> : tab === "realtime" ? <><p className="eyebrow">JEJU PICKS</p><h1>지금 제주에서<br /><strong>가볼 곳</strong></h1><p>오늘의 제주를 더 즐겁게 만드는<br />추천 장소를 한눈에 모아봤어요.</p></> : <><p className="eyebrow">MY TRAVEL</p><h1>나만의 제주<br /><strong>여행 기록</strong></h1><p>저장한 코스와 다녀온 장소를<br />이곳에서 차곡차곡 모아보세요.</p></>}</div>
        {tab === "planner" ? <div className="tangerine-float" aria-hidden="true"><img src="/planner-tangerine.png" alt="" /></div> : tab === "realtime" ? <div className="picks-tangerine" aria-hidden="true"><img src="/jeju-picks-tangerine.png" alt="" /></div> : <div className="mypage-tangerine" aria-hidden="true"><img src="/mypage-tangerine.png" alt="" /></div>}
      </section>
    </div>
    <section className="content-area">
      {tab === "planner" && <Planner regions={regions} region={region} regionError={regionError} setRegionCode={setRegionCode} budget={budget} setBudget={setBudget} member={member} onNeedLogin={openLogin} />}
      {tab === "realtime" && <Realtime region={region} regionError={regionError} member={member} onLogin={openLogin} />}
      {tab === "mypage" && <MyPage user={user} open={openStat} setOpen={setOpenStat} onLogin={openLogin} onInvite={() => setDialog("invite")} onLogout={doLogout} />}
    </section>
    <nav className="tabbar" aria-label="주요 메뉴">
      <TabButton active={tab === "planner"} icon="course" text="코스 짜기" onClick={() => setTab("planner")} />
      <TabButton active={tab === "realtime"} icon="recommend" text="제주 추천" onClick={() => setTab("realtime")} />
      <TabButton active={tab === "mypage"} icon="mypage" text="마이페이지" onClick={() => setTab("mypage")} />
    </nav>
    {dialog === "login" && <Login onClose={() => setDialog(null)} onAuthed={onAuthed} onSignup={() => { setDialog(null); setSignup(true); }} />}
    {dialog === "invite" && <Invite onClose={() => setDialog(null)} />}
  </main>;
}

function Landing({ onStart, onTab, onLogin }: { onStart: () => void; onTab: (tab: Tab) => void; onLogin: () => void }) {
  const [opening, setOpening] = useState(false);
  return <main className="landing-shell">
    <header className="landing-top">
      <button className="landing-brand" onClick={onStart} aria-label="어디GO 시작하기"><span>어디</span><b>GO!</b></button>
      <button className="landing-login" onClick={onLogin}>로그인 <span>→</span></button>
    </header>
    <section className={opening ? "landing-hero is-opening" : "landing-hero"}>
      <div className="landing-art" aria-hidden="true"><img src="/landing-jeju-hero.png" alt="" /></div>
      <div className="landing-invite">
        <p className="landing-kicker">A LITTLE INVITATION FOR YOU</p>
        <h1>오늘 제주,<br /><strong>어디GO?</strong></h1>
        <p className="landing-description">귤이가 제주 여행 초대장을<br />살포시 건넵니다.</p>
        <div className="invite-sticker" aria-hidden="true"><img src="/landing-invitation-sticker.png" alt="" /></div>
        <button className="landing-primary" onClick={() => setOpening(true)} disabled={opening}>{opening ? "초대장을 열었어요" : "시작하기"} <span>→</span></button>
      </div>
      <section className="landing-letter" aria-label="제주 여행 메뉴">
        <p>JEJU TRAVEL LETTER</p><h2>어디부터 떠나볼까요?</h2><span className="letter-line" />
        <div className="letter-tabs"><button onClick={() => onTab("planner")}><i><span className="tab-icon tab-icon-course" aria-hidden="true" /></i><b>코스 짜기</b><small>나만의 동선 만들기</small></button><button onClick={() => onTab("realtime")}><i><span className="tab-icon tab-icon-recommend" aria-hidden="true" /></i><b>제주 추천</b><small>오늘 가볼 곳 찾기</small></button><button onClick={() => onTab("mypage")}><i><span className="tab-icon tab-icon-mypage" aria-hidden="true" /></i><b>마이페이지</b><small>여행 기록 모아보기</small></button></div>
      </section>
    </section>
    <footer className="landing-foot"><span>귤 한 손, 캐리어 한 손 · 제주를 더 가볍게</span><button onClick={onStart}>바로 둘러보기 ↓</button></footer>
  </main>;
}

function TabButton({ active, icon, text, onClick }: { active: boolean; icon: "course" | "recommend" | "mypage"; text: string; onClick: () => void }) { return <button className={active ? "tab active" : "tab"} onClick={onClick}><span className={`tab-icon tab-icon-${icon}`} aria-hidden="true" />{text}</button>; }

function Planner({ regions, region, regionError, setRegionCode, budget, setBudget, member, onNeedLogin }: { regions: api.Region[]; region: api.Region | null; regionError: string | null; setRegionCode: (v: string) => void; budget: string; setBudget: (v: string) => void; member: boolean; onNeedLogin: () => void }) {
  // 기본값은 화면을 연 날 기준 오늘 ~ 모레(2박 3일). 날짜를 고정해두면 시간이
  // 지나 과거 날짜가 되고, 예측 집중률(오늘부터 30일치)도 붙지 않는다.
  const [startDate, setStartDate] = useState(() => api.localIsoDate(0));
  const [endDate, setEndDate] = useState(() => api.localIsoDate(2));
  const [plan, setPlan] = useState<api.PlanView | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [replanning, setReplanning] = useState<string | null>(null);
  const [replanNotice, setReplanNotice] = useState<string | null>(null);

  const generate = async () => {
    if (!region) return;
    setLoading(true); setError(null); setSaved(false); setSaveError(null);
    const env = await api.generatePlan({
      map_x: region.map_x, map_y: region.map_y,
      travel_date: api.toYmd(startDate), start_time: "09:00", end_time: "18:00",
      place_count: api.placeCountFor(startDate, endDate), theme: null,
    });
    setLoading(false);
    if (env.status === "success") setPlan(env.data);
    else { setPlan(null); setError(api.errorMessage(env)); }
  };

  const save = async () => {
    if (!member) { onNeedLogin(); return; }
    if (!plan) return;
    setSaveError(null);
    const env = await api.savePlan(plan);
    if (env.status === "success") { setSaved(true); return; }
    // 세션이 끊긴 경우엔 문구 대신 로그인 창을 띄운다.
    if (api.needsLogin(env)) { onNeedLogin(); return; }
    setSaveError(api.errorMessage(env));
  };

  // 집중률이 높은 한 곳만 교체한다 (D_frontend.md 7절: 무엇이 바뀌었는지 알린다).
  const replaceItem = async (item: api.PlanItem) => {
    if (!plan) return;
    setReplanning(item.content_id); setReplanNotice(null);
    const env = await api.replan(plan, item.content_id, "예측 집중률 높음");
    setReplanning(null);
    if (env.status === "success") {
      setPlan(env.data.plan); setSaved(false);
      setReplanNotice(env.data.change_reason);
    } else setReplanNotice(api.errorMessage(env));
  };

  return <>
    <SectionHead overline="TRIP PLANNER" title="여행 조건을 알려주세요" right="01 / 03" />
    <section className="planner-card">
      <label className="field-label">여행 날짜</label>
      <div className="date-row"><label><span>가는 날</span><input aria-label="가는 날" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label><b>→</b><label><span>오는 날</span><input aria-label="오는 날" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label></div>
      <label className="field-label">어디를 둘러볼까요?</label>
      {regionError ? <p className="form-error" role="alert">{regionError}</p>
        : regions.length === 0 ? <p className="loading-note">지역을 불러오는 중…</p>
        : <div className="chip-row">{regions.map((item) => <button key={item.code} onClick={() => setRegionCode(item.code)} className={region?.code === item.code ? "select-chip selected" : "select-chip"}>{item.name}</button>)}</div>}
      <label className="field-label">예산 <em>숙소 제외 · 1인 기준</em></label>
      <div className="budget-row"><div className="budget-input"><input aria-label="예산" type="number" value={budget} onChange={(e) => setBudget(e.target.value)} /><span>만원</span></div>{["20", "30", "50"].map((v) => <button key={v} onClick={() => setBudget(v)} className={budget === v ? "budget-preset selected" : "budget-preset"}>{v}</button>)}</div>
      <button className="primary-button full" onClick={generate} disabled={loading || !region}>{loading ? "코스를 만드는 중…" : "나만의 코스 만들기"} <span>→</span></button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </section>
    {plan && <section className="result-section">
      <div className="result-title">
        <div><p className="eyebrow">YOUR ROUTE</p><h2>{plan.title}</h2><p>{plan.summary}</p></div>
        <button className={saved ? "save-button saved" : member ? "save-button" : "secondary-button save-login-button"} onClick={save}>{saved ? "✓ 저장됨" : member ? "♡ 일정 저장" : "♡ 로그인 후 저장"}</button>
      </div>
      {saveError && <p className="form-error" role="alert">{saveError}</p>}
      {replanNotice && <p className="replan-notice" role="status">{replanNotice}</p>}
      <div className="plan-days"><article className="day-card">
        <h3>DAY 1 · {region?.name ?? "제주"}</h3>
        {plan.items.map((item) => <div className="route-item" key={item.content_id}>
          <time>{item.visit_time}</time><span>●</span>
          <div>
            <strong>{item.name}</strong>
            <p>{item.note}</p>
            <small className={item.high_congestion ? "congestion-high" : "congestion-label"}>{item.congestion_label}</small>
            {item.detail && (item.detail.use_time || item.detail.rest_date) && <dl className="route-detail">
              {item.detail.use_time && <><dt>운영</dt><dd>{item.detail.use_time}</dd></>}
              {item.detail.rest_date && <><dt>휴무</dt><dd>{item.detail.rest_date}</dd></>}
            </dl>}
            {item.high_congestion && <button className="text-button replan-button" onClick={() => replaceItem(item)} disabled={replanning !== null}>
              {replanning === item.content_id ? "다른 곳을 찾는 중…" : "다른 관광지 추천받기 →"}
            </button>}
          </div>
        </div>)}
      </article></div>
    </section>}
  </>;
}

type PicksResult = { key: string; places: api.Place[]; rates: Record<string, api.CongestionView>; message: string | null };

function Realtime({ region, regionError, member, onLogin }: { region: api.Region | null; regionError: string | null; member: boolean; onLogin: () => void }) {
  const [reloadKey, setReloadKey] = useState(0);
  const [result, setResult] = useState<PicksResult | null>(null);
  // 지역/재시도가 바뀌면 key가 달라지고, 결과 key가 따라잡을 때까지 로딩으로 본다.
  const key = `${region?.code ?? ""}#${reloadKey}`;
  const mapX = region?.map_x;
  const mapY = region?.map_y;

  useEffect(() => {
    if (mapX === undefined || mapY === undefined) return;
    let cancelled = false;
    (async () => {
      const env = await api.nearby(mapX, mapY);
      if (cancelled) return;
      if (env.status !== "success") { setResult({ key, places: [], rates: {}, message: api.errorMessage(env) }); return; }
      // 집중률 실패는 관광지 목록 표시를 막지 않는다 (D_frontend.md 9절).
      // 이름을 함께 넘겨 B가 관광지당 상세조회를 또 하지 않게 한다.
      const cong = await api.congestion(env.data, todayYmd());
      if (cancelled) return;
      setResult({ key, places: env.data, rates: cong.status === "success" ? cong.data : {}, message: null });
    })();
    return () => { cancelled = true; };
  }, [mapX, mapY, key]);

  if (regionError) return <><SectionHead overline="JEJU PICKS" title="제주에서 만날 곳" /><p className="form-error" role="alert">{regionError}</p></>;
  const current = result && result.key === key ? result : null;
  if (!current) return <><SectionHead overline="JEJU PICKS" title="제주에서 만날 곳" /><p className="loading-note">제주 관광지를 불러오는 중…</p></>;
  if (current.message) return <><SectionHead overline="JEJU PICKS" title="제주에서 만날 곳" /><p className="form-error" role="alert">{current.message}</p><button className="secondary-button" onClick={() => setReloadKey((n) => n + 1)}>다시 시도</button></>;

  const rates = current.rates;
  const [head, ...rest] = current.places;
  return <><SectionHead overline="JEJU PICKS" title="제주에서 만날 곳" />
    {head && <section className="open-recommend">
      <p className="card-kicker">지금 이 지역 <span>OPEN</span></p>
      <h3>오늘은 조금 느리게,<br />이곳은 어때요?</h3>
      <div className="quiet-place"><div>🌿</div><p><b>{head.name}</b><br />{rates[head.content_id]?.label ?? "혼잡도 예측 정보 없음"}</p><button aria-label={`${head.name} 보기`}>→</button></div>
    </section>}
    <div className="recommend-grid">{rest.map((place) => <article className="recommend-card" key={place.content_id}>
      <p className="card-kicker">{place.category ?? "제주 추천"}{member && <span>MEMBER</span>}</p>
      <h3>{place.name}</h3>
      <p>{rates[place.content_id]?.label ?? "혼잡도 예측 정보 없음"}</p>
      <p className="card-detail">{place.addr}</p>
      <div className="mock-lines"><i /><i /><i /></div>
      {!member && <button className="lock-layer" onClick={onLogin}><b>🔒</b><span>로그인하고 확인하기</span></button>}
    </article>)}</div>
  </>;
}

function MyPage({ user, open, setOpen, onLogin, onInvite, onLogout }: { user: api.User | null; open: string | null; setOpen: (v: string | null) => void; onLogin: () => void; onInvite: () => void; onLogout: () => void }) {
  const [loaded, setLoaded] = useState<{ userId: number; plans: api.SavedPlan[]; message: string | null } | null>(null);
  const [detail, setDetail] = useState<api.PlanDetail | null>(null);
  const [detailFor, setDetailFor] = useState<number | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  // 목록에는 제목/날짜/개수만 있다. 상세는 A가 B에 실시간 재조회한 현재
  // 관광지 정보까지 합쳐서 내려준다.
  const openDetail = async (planId: number) => {
    setDetailFor(planId); setDetail(null); setDetailError(null);
    const env = await api.getPlanDetail(planId);
    if (env.status === "success") { setDetail(env.data); return; }
    if (api.needsLogin(env)) { setDetailFor(null); onLogin(); return; }
    setDetailError(api.errorMessage(env));
  };
  const closeDetail = () => { setDetailFor(null); setDetail(null); setDetailError(null); };

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const userId = user.user_id;
    api.listPlans().then((env) => {
      if (cancelled) return;
      if (env.status === "success") setLoaded({ userId, plans: env.data, message: null });
      // 세션이 끊겼으면 목록 대신 로그인 창으로 보낸다.
      else if (api.needsLogin(env)) onLogin();
      else setLoaded({ userId, plans: [], message: api.errorMessage(env) });
    });
    return () => { cancelled = true; };
  }, [user, onLogin]);

  // 로그아웃 후 다른 계정으로 로그인해도 이전 계정의 목록이 잠깐 보이지 않게 한다.
  const current = user && loaded && loaded.userId === user.user_id ? loaded : null;
  const plans = current?.plans ?? [];
  const message = current?.message ?? null;

  if (!user) return <><SectionHead overline="MY TRAVEL" title="나의 제주 기록" /><section className="guest-profile"><div className="empty-avatar">?</div><div><h3>아직 여행 프로필이 비어 있어요</h3><p>로그인하고 내 취향에 맞는 여행을 쌓아보세요.</p></div><button className="secondary-button" onClick={onLogin}>로그인하기</button></section><Menu locked onLogin={onLogin} /></>;

  const stats: [string, string, string][] = [["저장한 일정", String(plans.length), "saved"], ["다녀온 곳", "-", "visited"], ["초대한 친구", "-", "friends"]];
  return <>
    <section className="member-profile"><div className="member-avatar">{user.username.slice(0, 1).toUpperCase()}</div><div><p className="eyebrow">MY TRAVEL</p><h2>{user.username}님의 제주</h2><p>회원번호 {user.user_id}</p></div><button className="icon-button">⚙</button></section>
    <section className="stat-grid">{stats.map(([label, count, key]) => <button className={open === key ? "stat-card open" : "stat-card"} onClick={() => setOpen(open === key ? null : key)} key={key}><small>{label}</small><strong>{count}</strong><span>›</span></button>)}</section>
    {message && <p className="form-error" role="alert">{message}</p>}
    {open === "saved" && <section className="expanded-list"><p className="eyebrow">SAVED</p>
      {plans.length === 0 ? <p className="empty-note">저장된 일정이 없습니다.</p> : plans.map((plan) => <button className="list-row" key={plan.plan_id} onClick={() => openDetail(plan.plan_id)}><span>✦</span><div><b>{plan.title}</b><small>{api.formatYmd(plan.travel_date)} · 방문지 {plan.items.length}곳</small></div><em>›</em></button>)}
    </section>}
    {detailFor !== null && <PlanDetailView planId={detailFor} detail={detail} error={detailError} onClose={closeDetail} />}
    {(open === "visited" || open === "friends") && <section className="expanded-list"><p className="eyebrow">{open.toUpperCase()}</p><p className="empty-note">아직 연동된 기록이 없습니다.</p></section>}
    <Menu onInvite={onInvite} onLogout={onLogout} />
  </>;
}

function PlanDetailView({ planId, detail, error, onClose }: { planId: number; detail: api.PlanDetail | null; error: string | null; onClose: () => void }) {
  const stale = detail !== null && detail.items.some((i) => i.current === null);
  return <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="plan-detail-title" onClick={onClose}>
    <div className="modal-card plan-detail-card" onClick={(e) => e.stopPropagation()}>
      <button type="button" className="close-button" onClick={onClose}>×</button>
      {error ? <><p className="eyebrow">SAVED PLAN</p><h2 id="plan-detail-title">일정을 불러오지 못했어요</h2><p className="form-error" role="alert">{error}</p></>
        : detail === null ? <><p className="eyebrow">SAVED PLAN</p><h2 id="plan-detail-title">불러오는 중…</h2><p className="loading-note">저장한 일정 #{planId}을 여는 중입니다.</p></>
        : <>
          <p className="eyebrow">SAVED PLAN</p>
          <h2 id="plan-detail-title">{detail.title}</h2>
          <p className="modal-copy">{api.formatYmd(detail.travel_date)} · 방문지 {detail.items.length}곳</p>
          {stale && <p className="detail-stale">일부 장소는 최신 관광 정보를 불러오지 못해 저장된 내용만 표시합니다.</p>}
          <div className="detail-list">
            {detail.items.map((item) => <article className="detail-item" key={item.content_id}>
              <time>{item.visit_time}</time>
              <div>
                <strong>{item.name}</strong>
                {item.note && <p>{item.note}</p>}
                {item.current ? <dl className="detail-meta">
                  {item.current.addr && <><dt>주소</dt><dd>{item.current.addr}</dd></>}
                  {item.current.category && <><dt>분류</dt><dd>{item.current.category}</dd></>}
                  {item.current.use_time && <><dt>운영시간</dt><dd>{item.current.use_time}</dd></>}
                  {item.current.rest_date && <><dt>휴무일</dt><dd>{item.current.rest_date}</dd></>}
                </dl> : <p className="detail-meta-missing">현재 관광지 정보를 불러오지 못했습니다.</p>}
              </div>
            </article>)}
          </div>
        </>}
      <button type="button" className="primary-button full" onClick={onClose}>닫기</button>
    </div>
  </div>;
}

function Menu({ locked, onLogin, onInvite, onLogout }: { locked?: boolean; onLogin?: () => void; onInvite?: () => void; onLogout?: () => void }) { return <div className="menu-card"><button onClick={locked ? onLogin : onInvite}>친구 초대 <span>{locked ? "🔒" : "→"}</span></button><button onClick={locked ? onLogin : undefined}>회원정보 수정 <span>{locked ? "🔒" : "›"}</span></button><button disabled={locked} onClick={onLogout}>로그아웃 <span>→</span></button></div>; }
function SectionHead({ overline, title, right }: { overline: string; title: string; right?: string }) { return <section className="section-head"><div><p className="eyebrow">{overline}</p><h2>{title}</h2></div>{right && <span className="head-right">{right}</span>}</section>; }

function Login({ onClose, onAuthed, onSignup }: { onClose: () => void; onAuthed: (user: api.User) => void; onSignup: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setPending(true); setError(null);
    const env = await api.login(username, password);
    setPending(false);
    if (env.status === "success" && env.data) onAuthed(env.data);
    else setError(api.errorMessage(env) ?? "로그인에 실패했습니다.");
  };

  return <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="login-title"><form className="modal-card" onSubmit={submit}><button type="button" className="close-button" onClick={onClose}>×</button><div className="brand-mark">GO</div><p className="eyebrow">WELCOME BACK</p><h2 id="login-title">다시 만나네요, 여행자님</h2><p className="modal-copy">로그인하고 저장한 일정과 제주 추천을 확인하세요.</p><label>아이디<input required placeholder="아이디를 입력하세요" value={username} onChange={(e) => setUsername(e.target.value)} /></label><label>비밀번호<input required type="password" placeholder="비밀번호를 입력하세요" value={password} onChange={(e) => setPassword(e.target.value)} /></label>{error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button full" disabled={pending}>{pending ? "로그인 중…" : "로그인하기"}</button><button type="button" className="signup-link" onClick={onSignup}>아직 어디GO 회원이 아니신가요? <b>회원가입</b></button><button type="button" className="text-button" onClick={onClose}>계속 둘러보기</button></form></div>;
}

function Invite({ onClose }: { onClose: () => void }) { const [copied, setCopied] = useState(false); return <div className="modal-backdrop" role="dialog" aria-modal="true"><div className="modal-card invite-card"><button className="close-button" onClick={onClose}>×</button><div className="invite-emoji">✉</div><p className="eyebrow">TRIP INVITE</p><h2>함께 제주를 걸어요</h2><p className="modal-copy">저장한 일정에 친구를 초대합니다.</p><div className="invite-code"><span>GO-JEJU-0926</span><button onClick={() => setCopied(true)}>{copied ? "복사됨" : "복사"}</button></div><button className="primary-button full" onClick={() => setCopied(true)}>{copied ? "코드를 복사했어요" : "코드 보내기"}</button></div></div>; }

function Signup({ onBack, onAuthed }: { onBack: () => void; onAuthed: (user: api.User) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setPending(true); setError(null);
    const created = await api.register(username, password);
    if (created.status !== "success") { setPending(false); setError(api.errorMessage(created)); return; }
    // 가입 직후 바로 로그인해 세션 쿠키를 받는다 (A의 register는 쿠키를 주지 않는다).
    const env = await api.login(username, password);
    setPending(false);
    if (env.status === "success" && env.data) onAuthed(env.data);
    else setError(api.errorMessage(env));
  };

  return <main className="signup-shell"><section className="signup-panel"><button className="text-button back" onClick={onBack}>← 돌아가기</button><div className="brand-mark">GO</div><p className="eyebrow">JEJU TRIP COMPANION</p><h1>여행 취향을 알려주세요</h1><p className="signup-copy">가입 후에는 내 일정 저장과 제주 맞춤 추천을 이용할 수 있어요.</p><form className="signup-form" onSubmit={submit}><label>아이디<input required placeholder="로그인에 쓸 아이디" value={username} onChange={(e) => setUsername(e.target.value)} /></label><label>비밀번호<input required type="password" minLength={8} placeholder="8자 이상" value={password} onChange={(e) => setPassword(e.target.value)} /></label><label>이메일<input type="email" placeholder="you@example.com" /></label><label>닉네임<input placeholder="여행에서 부를 이름" /></label><div className="two-inputs"><label>이름<input placeholder="이름" /></label><label>전화번호<input type="tel" placeholder="010-0000-0000" /></label></div><label className="check-row"><input type="checkbox" required /> 필수 약관과 개인정보 처리방침에 동의합니다.</label>{error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button full" disabled={pending}>{pending ? "가입 중…" : "가입 완료하고 시작하기"}</button></form></section></main>;
}
