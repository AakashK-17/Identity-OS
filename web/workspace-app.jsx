// Hone Workspace — app shell

const { useState: uS, useEffect: uE } = React;

const primaryTabs = [
  ["workspace", "Workspace", <Icon.Folder/>, "W"],
  ["history", "History", <Icon.History/>, "H"],
  ["profile", "Profile", <Icon.Save/>, "P"],
  ["system", "System", <Icon.System/>, "S"],
];

const routeViews = new Set(["workspace", "history", "profile", "settings", "system", "about", "privacy", "terms", "support", "data"]);

function Nav({ view, onView, onOpenDrawer, user }) {
  const displayName = user?.name || user?.email || "Workspace";
  const firstName = displayName.split(" ")[0];
  const initial = displayName.trim().charAt(0).toUpperCase() || "H";
  return (
    <nav className="nav">
      <div className="nav-l">
        <div className="nav-brand" onClick={() => onView('workspace')}>
          <HoneMark size={28} breathe/>
          <span className="nav-name">Hone<span className="dot">.</span></span>
        </div>
        <div className="nav-tabs">
          {primaryTabs.map(([id, label, icon, key]) => (
            <Tab key={id} id={id} view={view} onView={onView} icon={icon}>{label}<span className="kbd">{key}</span></Tab>
          ))}
        </div>
      </div>
      <div className="nav-r">
        <div className="nav-search">
          <span className="icon"><Icon.Search/></span>
          <input placeholder="Search workspaces, JDs, memory…"/>
          <span className="kbd">⌘ K</span>
        </div>
        <button className="nav-base-btn" onClick={onOpenDrawer} title="Edit base resume">
          <div className="av">{initial}</div>
          <span>Base resume</span>
          <span className="kbd">B</span>
        </button>
        <div className="user-chip">
          <div className="av">{initial}</div>
          <span className="nm">{firstName}</span>
        </div>
        <button className="logout-btn" onClick={() => window.HoneBridge?.logout?.()} title="Log out">
          <Icon.LogOut/>
          <span>Log out</span>
        </button>
      </div>
    </nav>
  );
}

function MobileNav({ view, onView }) {
  return (
    <nav className="mobile-nav" aria-label="Workspace navigation">
      <Tab id="workspace" view={view} onView={onView} icon={<Icon.Folder/>}>Workspace</Tab>
      <Tab id="history" view={view} onView={onView} icon={<Icon.History/>}>History</Tab>
      <Tab id="profile" view={view} onView={onView} icon={<Icon.Save/>}>Profile</Tab>
      <Tab id="system" view={view} onView={onView} icon={<Icon.System/>}>System</Tab>
    </nav>
  );
}

function Tab({ id, view, onView, icon, children }) {
  const active = view === id;
  return (
    <button className={"nav-tab" + (active ? " active" : "")} onClick={() => onView(id)}>
      <span className="tab-bg"></span>
      <span className="tab-dot"></span>
      {icon}
      <span>{children}</span>
    </button>
  );
}

function App() {
  const [view, setView] = uS('workspace');
  const [generating, setGenerating] = uS(false);
  const [drawerOpen, setDrawerOpen] = uS(false);
  const [promptedSetup, setPromptedSetup] = uS(false);
  const snapshot = useHoneState();

  uE(() => {
    const viewFromHash = () => {
      const next = (window.location.hash || "#workspace").replace("#", "");
      if (routeViews.has(next)) setView(next);
    };
    const onKey = (e) => {
      if (e.target.matches('input, textarea')) return;
      if (e.key === 'w' || e.key === 'W') setView('workspace');
      if (e.key === 'h' || e.key === 'H') setView('history');
      if (e.key === 's' || e.key === 'S') setView('system');
      if (e.key === 'p' || e.key === 'P') setView('profile');
      if (e.key === 'g' || e.key === 'G') setView('settings');
      if (e.key === 'b' || e.key === 'B') setDrawerOpen(true);
    };
    const onRoute = (event) => {
      const next = event.detail || "workspace";
      if (routeViews.has(next)) {
        setView(next);
        if (window.location.hash !== `#${next}`) window.history.replaceState(null, "", `#${next}`);
      }
    };
    viewFromHash();
    window.addEventListener('keydown', onKey);
    window.addEventListener('hone:view', onRoute);
    window.addEventListener('hashchange', viewFromHash);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('hone:view', onRoute);
      window.removeEventListener('hashchange', viewFromHash);
    };
  }, []);

  uE(() => {
    if (!snapshot.user || promptedSetup || snapshot.profile == null) return;
    const profile = snapshot.profile || {};
    const hasMemory = Boolean(
      profile.onboarding_complete ||
      profile.experiences?.length ||
      profile.projects?.length ||
      profile.education?.length ||
      profile.certifications?.length ||
      String(profile.skills || "").trim()
    );
    if (!hasMemory) {
      setDrawerOpen(true);
      setPromptedSetup(true);
    }
  }, [snapshot.user?.email, snapshot.profile, promptedSetup]);

  function trigger() {
    setGenerating(true);
    setTimeout(() => setGenerating(false), 2300);
  }

  return (
    <React.Fragment>
      <div className="bg-base"></div>
      <div className="bg-grain"></div>
      <AmbientGlow/>

      <Nav view={view} onView={setView} onOpenDrawer={() => setDrawerOpen(true)} user={snapshot.user}/>
      <MobileNav view={view} onView={setView}/>

      <div className="view-stack">
        <div className="view view-enter" key={view}>
          {view === 'workspace' && (
            <WorkspaceView
              onGenerate={trigger}
              onOpenDrawer={() => setDrawerOpen(true)}
              onGoHistory={() => setView('history')}
              snapshot={snapshot}
            />
          )}
          {view === 'history' && <HistoryView snapshot={snapshot} onOpenResume={() => setView('workspace')}/>}
          {view === 'profile' && <ProfileView snapshot={snapshot} onOpenDrawer={() => setDrawerOpen(true)}/>}
          {view === 'settings' && <SettingsView snapshot={snapshot}/>}
          {view === 'about' && <AboutView/>}
          {view === 'privacy' && <PrivacyView/>}
          {view === 'terms' && <TermsView/>}
          {view === 'support' && <SupportView/>}
          {view === 'data' && <DataControlsView snapshot={snapshot}/>}
          {view === 'system'  && <SystemView/>}
        </div>
      </div>

      <BaseResumeDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} snapshot={snapshot}/>
      <StrikeOverlay show={false}/>
    </React.Fragment>
  );
}

ReactDOM.createRoot(document.getElementById('hone-workspace-root')).render(<App/>);
