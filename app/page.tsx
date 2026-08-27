"use client";

import { FormEvent, useState } from "react";

type Tab = "planner" | "realtime" | "mypage";
type Dialog = "login" | "invite" | null;

const regions = ["제주시", "서귀포", "서귀 동쪽", "제주 서쪽"];
const days = [
  ["DAY 1 · 제주시", [["09:30", "동문시장", "제주식 아침으로 천천히 시작"], ["13:00", "사려니숲길", "나무 그늘 아래 가벼운 산책"], ["17:20", "이호테우 해변", "노을 보기 좋은 마지막 코스"]]],
  ["DAY 2 · 제주 서쪽", [["10:00", "협재 해변", "아침 햇살이 예쁜 바다"], ["14:00", "금능리", "조용한 골목과 로컬 카페"]]],
] as const;

export default function Home() {
  const [landing, setLanding] = useState(true);
  const [tab, setTab] = useState<Tab>("planner");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [member, setMember] = useState(false);
  const [signup, setSignup] = useState(false);
  const [region, setRegion] = useState("제주시");
  const [budget, setBudget] = useState("30");
  const [generated, setGenerated] = useState(false);
  const [saved, setSaved] = useState(false);
  const [openStat, setOpenStat] = useState<string | null>(null);
  const login = (e?: FormEvent) => { e?.preventDefault(); setMember(true); setDialog(null); setSignup(false); };

  if (signup) return <Signup onBack={() => setSignup(false)} onSubmit={login} />;
  if (landing) return <Landing onStart={() => setLanding(false)} onTab={(next) => { setTab(next); setLanding(false); }} onLogin={() => { setLanding(false); setDialog("login"); }} />;

  return <main className="app-shell">
    <div className="hero-surface">
      <header className="topbar topbar-minimal">
        <div className="header-actions">{member ? <button className="profile-chip" onClick={() => setTab("mypage")}>예지님 <span>✦</span></button> : <button className="login-pill" onClick={() => setDialog("login")}>로그인 <span>→</span></button>}</div>
      </header>
      <section className={`welcome-band ${tab}-hero`}>
        <div className={tab === "planner" ? "hero-copy" : "sub-hero-copy"}>{tab === "planner" ? <><p className="eyebrow">JEJU TRIP EDITION</p><h1>오늘 제주,<br /><strong>어디GO?</strong></h1><p>취향에 맞는 동선부터 지금 한적한 장소까지<br />여행의 망설임을 가볍게 덜어드릴게요.</p><span className="hero-sticker">슝! 코스 생성</span></> : tab === "realtime" ? <><p className="eyebrow">JEJU PICKS</p><h1>지금 제주에서<br /><strong>가볼 곳</strong></h1><p>오늘의 제주를 더 즐겁게 만드는<br />추천 장소를 한눈에 모아봤어요.</p></> : <><p className="eyebrow">MY TRAVEL</p><h1>나만의 제주<br /><strong>여행 기록</strong></h1><p>저장한 코스와 다녀온 장소를<br />이곳에서 차곡차곡 모아보세요.</p></>}</div>
        {tab === "planner" ? <div className="tangerine-float" aria-hidden="true"><img src="/planner-tangerine.png" alt="" /></div> : tab === "realtime" ? <div className="picks-tangerine" aria-hidden="true"><img src="/jeju-picks-tangerine.png" alt="" /></div> : <div className="mypage-tangerine" aria-hidden="true"><img src="/mypage-tangerine.png" alt="" /></div>}
      </section>
    </div>
    <section className="content-area">
      {tab === "planner" && <Planner region={region} setRegion={setRegion} budget={budget} setBudget={setBudget} generated={generated} setGenerated={setGenerated} saved={saved} member={member} onSave={() => member ? setSaved(!saved) : setDialog("login")} />}
      {tab === "realtime" && <Realtime member={member} onLogin={() => setDialog("login")} />}
      {tab === "mypage" && <MyPage member={member} open={openStat} setOpen={setOpenStat} onLogin={() => setDialog("login")} onInvite={() => setDialog("invite")} />}
    </section>
    <nav className="tabbar" aria-label="주요 메뉴">
      <TabButton active={tab === "planner"} icon="course" text="코스 짜기" onClick={() => setTab("planner")} />
      <TabButton active={tab === "realtime"} icon="recommend" text="제주 추천" onClick={() => setTab("realtime")} />
      <TabButton active={tab === "mypage"} icon="mypage" text="마이페이지" onClick={() => setTab("mypage")} />
    </nav>
    {dialog === "login" && <Login onClose={() => setDialog(null)} onLogin={login} onSignup={() => { setDialog(null); setSignup(true); }} />}
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
        <div className="letter-tabs"><button onClick={() => onTab("planner")}><i>✦</i><b>코스 짜기</b><small>나만의 동선 만들기</small></button><button onClick={() => onTab("realtime")}><i>◌</i><b>제주 추천</b><small>오늘 가볼 곳 찾기</small></button><button onClick={() => onTab("mypage")}><i>⌂</i><b>마이페이지</b><small>여행 기록 모아보기</small></button></div>
      </section>
    </section>
    <footer className="landing-foot"><span>귤 한 손, 캐리어 한 손 · 제주를 더 가볍게</span><button onClick={onStart}>바로 둘러보기 ↓</button></footer>
  </main>;
}

function TabButton({ active, icon, text, onClick }: { active: boolean; icon: "course" | "recommend" | "mypage"; text: string; onClick: () => void }) { return <button className={active ? "tab active" : "tab"} onClick={onClick}><span className={`tab-icon tab-icon-${icon}`} aria-hidden="true" />{text}</button>; }

function Planner({ region, setRegion, budget, setBudget, generated, setGenerated, saved, member, onSave }: { region: string; setRegion: (v: string) => void; budget: string; setBudget: (v: string) => void; generated: boolean; setGenerated: (v: boolean) => void; saved: boolean; member: boolean; onSave: () => void }) {
  return <>
    <SectionHead overline="TRIP PLANNER" title="여행 조건을 알려주세요" right="01 / 03" />
    <section className="planner-card">
      <label className="field-label">여행 날짜</label>
      <div className="date-row"><label><span>가는 날</span><input aria-label="가는 날" type="date" defaultValue="2026-09-12" /></label><b>→</b><label><span>오는 날</span><input aria-label="오는 날" type="date" defaultValue="2026-09-14" /></label></div>
      <label className="field-label">어디를 둘러볼까요?</label>
      <div className="chip-row">{regions.map((item) => <button key={item} onClick={() => setRegion(item)} className={region === item ? "select-chip selected" : "select-chip"}>{item}</button>)}</div>
      <label className="field-label">예산 <em>숙소 제외 · 1인 기준</em></label>
      <div className="budget-row"><div className="budget-input"><input aria-label="예산" type="number" value={budget} onChange={(e) => setBudget(e.target.value)} /><span>만원</span></div>{["20", "30", "50"].map((v) => <button key={v} onClick={() => setBudget(v)} className={budget === v ? "budget-preset selected" : "budget-preset"}>{v}</button>)}</div>
      <button className="primary-button full" onClick={() => setGenerated(true)}>나만의 코스 만들기 <span>→</span></button>
    </section>
    {generated && <section className="result-section"><div className="result-title"><div><p className="eyebrow">YOUR ROUTE</p><h2>{region}에서 시작하는 2박 3일</h2><p>이동 시간을 줄이고, 여행의 결을 살렸어요.</p></div><button className={saved ? "save-button saved" : member ? "save-button" : "secondary-button save-login-button"} onClick={onSave}>{saved ? "✓ 저장됨" : member ? "♡ 일정 저장" : "♡ 로그인 후 저장"}</button></div><div className="plan-days">{days.map(([title, entries]) => <article className="day-card" key={title}><h3>{title}</h3>{entries.map(([time, place, desc]) => <div className="route-item" key={place}><time>{time}</time><span>●</span><div><strong>{place}</strong><p>{desc}</p></div></div>)}</article>)}</div></section>}
  </>;
}

function Realtime({ member, onLogin }: { member: boolean; onLogin: () => void }) {
  const locks = [["지금 붐비는 지역", "성산일출봉", "평소보다 32% 혼잡해요"], ["회원 방문 기록", "연동 · 애월", "이번 달 많이 찾은 장소"], ["10분 거리 핫플", "제주공항 근처", "지금 바로 갈 수 있는 곳"]];
  return <><SectionHead overline="JEJU PICKS" title="제주에서 만날 곳" /><section className="open-recommend"><p className="card-kicker">어제보다 한적한 곳 <span>OPEN</span></p><h3>오늘은 조금 느리게,<br />이곳은 어때요?</h3><div className="quiet-place"><div>🌿</div><p><b>사려니숲길</b><br />어제보다 <strong>24% 한적</strong>해요</p><button aria-label="사려니숲길 보기">→</button></div></section><div className="recommend-grid">{locks.map(([title, place, detail]) => <article className="recommend-card" key={title}><p className="card-kicker">{title}{member && <span>MEMBER</span>}</p><h3>{place}</h3><p>{detail}</p><div className="mock-lines"><i /><i /><i /></div>{!member && <button className="lock-layer" onClick={onLogin}><b>🔒</b><span>로그인하고 확인하기</span></button>}</article>)}</div></>;
}

function MyPage({ member, open, setOpen, onLogin, onInvite }: { member: boolean; open: string | null; setOpen: (v: string | null) => void; onLogin: () => void; onInvite: () => void }) {
  if (!member) return <><SectionHead overline="MY TRAVEL" title="나의 제주 기록" /><section className="guest-profile"><div className="empty-avatar">?</div><div><h3>아직 여행 프로필이 비어 있어요</h3><p>로그인하고 내 취향에 맞는 여행을 쌓아보세요.</p></div><button className="secondary-button" onClick={onLogin}>로그인하기</button></section><Menu locked onLogin={onLogin} /></>;
  const stats = [["저장한 일정", "3", "saved"], ["다녀온 곳", "12", "visited"], ["초대한 친구", "4", "friends"]];
  const rows: Record<string, [string, string, string]> = { saved: ["✦", "9월, 천천히 걷는 제주", "2026.09.12 - 09.14 · 제주시"], visited: ["◌", "이호테우 해변", "2026.08.02 방문 완료"], friends: ["♡", "친구 3명 참여 중", "수락 대기 1명"] };
  return <><section className="member-profile"><div className="member-avatar">Y</div><div><p className="eyebrow">MY TRAVEL</p><h2>예지님의 제주</h2><p>yeji@eodiego.com · 2026.08 가입</p></div><button className="icon-button">⚙</button></section><section className="stat-grid">{stats.map(([label, count, key]) => <button className={open === key ? "stat-card open" : "stat-card"} onClick={() => setOpen(open === key ? null : key)} key={key}><small>{label}</small><strong>{count}</strong><span>›</span></button>)}</section>{open && <section className="expanded-list"><p className="eyebrow">{open.toUpperCase()}</p><button className="list-row"><span>{rows[open][0]}</span><div><b>{rows[open][1]}</b><small>{rows[open][2]}</small></div><em>›</em></button></section>}<Menu onInvite={onInvite} /></>;
}

function Menu({ locked, onLogin, onInvite }: { locked?: boolean; onLogin?: () => void; onInvite?: () => void }) { return <div className="menu-card"><button onClick={locked ? onLogin : onInvite}>친구 초대 <span>{locked ? "🔒" : "→"}</span></button><button onClick={locked ? onLogin : undefined}>회원정보 수정 <span>{locked ? "🔒" : "›"}</span></button><button disabled>로그아웃 <span>→</span></button></div>; }
function SectionHead({ overline, title, right }: { overline: string; title: string; right?: string }) { return <section className="section-head"><div><p className="eyebrow">{overline}</p><h2>{title}</h2></div>{right && <span className="head-right">{right}</span>}</section>; }

function Login({ onClose, onLogin, onSignup }: { onClose: () => void; onLogin: (e: FormEvent) => void; onSignup: () => void }) { return <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="login-title"><form className="modal-card" onSubmit={onLogin}><button type="button" className="close-button" onClick={onClose}>×</button><div className="brand-mark">GO</div><p className="eyebrow">WELCOME BACK</p><h2 id="login-title">다시 만나요, 여행자님</h2><p className="modal-copy">로그인하고 저장한 일정과 제주 추천을 확인하세요.</p><label>아이디<input required placeholder="아이디를 입력하세요" /></label><label>비밀번호<input required type="password" placeholder="비밀번호를 입력하세요" /></label><button className="primary-button full">로그인하기</button><button type="button" className="signup-link" onClick={onSignup}>아직 어디GO 회원이 아니신가요? <b>회원가입</b></button><button type="button" className="text-button" onClick={onClose}>계속 둘러보기</button></form></div>; }
function Invite({ onClose }: { onClose: () => void }) { const [copied, setCopied] = useState(false); return <div className="modal-backdrop" role="dialog" aria-modal="true"><div className="modal-card invite-card"><button className="close-button" onClick={onClose}>×</button><div className="invite-emoji">✉</div><p className="eyebrow">TRIP INVITE</p><h2>함께 제주를 걸어요</h2><p className="modal-copy">‘9월, 천천히 걷는 제주’ 일정에 친구를 초대합니다.</p><div className="invite-code"><span>GO-JEJU-0926</span><button onClick={() => setCopied(true)}>{copied ? "복사됨" : "복사"}</button></div><button className="primary-button full" onClick={() => setCopied(true)}>{copied ? "코드를 복사했어요" : "코드 보내기"}</button></div></div>; }
function Signup({ onBack, onSubmit }: { onBack: () => void; onSubmit: (e: FormEvent) => void }) { return <main className="signup-shell"><section className="signup-panel"><button className="text-button back" onClick={onBack}>← 돌아가기</button><div className="brand-mark">GO</div><p className="eyebrow">JEJU TRIP COMPANION</p><h1>여행 취향을 알려주세요</h1><p className="signup-copy">가입 후에는 내 일정 저장과 제주 맞춤 추천을 이용할 수 있어요.</p><form className="signup-form" onSubmit={onSubmit}><label>이메일<input required type="email" placeholder="you@example.com" /></label><label>닉네임<input required placeholder="여행에서 부를 이름" /></label><div className="two-inputs"><label>이름<input required placeholder="이름" /></label><label>전화번호<input required type="tel" placeholder="010-0000-0000" /></label></div><label>연락처<input placeholder="선택 · 인스타그램, 카카오톡 등" /></label><label className="check-row"><input type="checkbox" required /> 필수 약관과 개인정보 처리방침에 동의합니다.</label><button className="primary-button full">가입 완료하고 시작하기</button></form></section></main>; }
