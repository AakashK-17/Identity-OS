// Hone Workspace — app shell

const { useState: uS, useEffect: uE } = React;

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
          <Tab id="workspace" view={view} onView={onView} icon={<Icon.Folder/>}>Workspace<span className="kbd">W</span></Tab>
          <Tab id="history"   view={view} onView={onView} icon={<Icon.History/>}>History<span className="kbd">H</span></Tab>
          <Tab id="system"    view={view} onView={onView} icon={<Icon.System/>}>System<span className="kbd">S</span></Tab>
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
          <button className="out" onClick={() => window.HoneBridge?.logout?.()}>Log out</button>
        </div>
      </div>
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
  const snapshot = useHoneState();

  uE(() => {
    const onKey = (e) => {
      if (e.target.matches('input, textarea')) return;
      if (e.key === 'w' || e.key === 'W') setView('workspace');
      if (e.key === 'h' || e.key === 'H') setView('history');
      if (e.key === 's' || e.key === 'S') setView('system');
      if (e.key === 'b' || e.key === 'B') setDrawerOpen(true);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

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
          {view === 'system'  && <SystemView/>}
        </div>
      </div>

      <BaseResumeDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} snapshot={snapshot}/>
      <StrikeOverlay show={generating}/>
    </React.Fragment>
  );
}

ReactDOM.createRoot(document.getElementById('hone-workspace-root')).render(<App/>);
