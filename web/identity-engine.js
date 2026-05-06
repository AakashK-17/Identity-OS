/* ============================================================
   IDENTITY OS — LIVE INTELLIGENCE ENGINE
   Three.js scene system. Multiple "modes" share a renderer pool.
   Reveals nothing technical — purely abstract visualization.
   ============================================================ */
(function(global){
  'use strict';

  // Lazy three.js import via global THREE
  function ready(cb){ if (global.THREE) cb(); else setTimeout(()=>ready(cb),20); }

  // -----------------------------
  // Glyph atlas — abstract symbols, never readable text
  // -----------------------------
  function makeGlyphTexture(){
    const c = document.createElement('canvas');
    c.width = c.height = 512;
    const ctx = c.getContext('2d');
    const glyphs = ['◇','○','△','□','◯','◊','✦','◆','▲','●','▽','◐','◑','◒','◓','⬡','⬢','⌬','⏣','⎔'];
    const cell = 128;
    ctx.fillStyle = 'rgba(0,0,0,0)';
    ctx.fillRect(0,0,512,512);
    ctx.fillStyle = 'rgba(217,210,180,1)';
    ctx.font = '70px serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (let i=0;i<16;i++){
      const x = (i%4)*cell + cell/2;
      const y = Math.floor(i/4)*cell + cell/2;
      ctx.fillText(glyphs[i % glyphs.length], x, y);
    }
    const tex = new THREE.CanvasTexture(c);
    tex.needsUpdate = true;
    return tex;
  }

  // -----------------------------
  // Core orb scene — used in hero, CTA, loader (different intensities)
  // -----------------------------
  function CoreScene(canvas, opts){
    opts = opts || {};
    const intensity = opts.intensity || 1;       // overall brightness
    const palette = opts.palette || 'warm';       // 'warm' | 'dark'
    const interactive = opts.interactive !== false;
    const showGlyphs = opts.glyphs !== false;
    const showRings  = opts.rings  !== false;
    const showThreads = opts.threads !== false;

    const colors = palette === 'dark'
      ? { core1: 0xcdc193, core2: 0x5d614a, ring: 0xd9d2b4, glyph: 0xe9e4d2, thread: 0xb8b894, bg: 0x000000, bgAlpha: 0 }
      : { core1: 0xddd6c0, core2: 0x7d8064, ring: 0x5d614a, glyph: 0x2a2823, thread: 0x7d8064, bg: 0x000000, bgAlpha: 0 };

    const renderer = new THREE.WebGLRenderer({ canvas, antialias:true, alpha:true, powerPreference:'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.35));
    renderer.setClearColor(colors.bg, colors.bgAlpha);

    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    cam.position.set(0, 0, 6);

    // ---- Core sphere: lat-lon wireframe + soft inner ----
    const coreGroup = new THREE.Group();
    scene.add(coreGroup);

    const innerGeom = new THREE.SphereGeometry(1.05, 32, 24);
    const innerMat  = new THREE.MeshBasicMaterial({ color: colors.core1, transparent:true, opacity: .15 * intensity });
    const innerMesh = new THREE.Mesh(innerGeom, innerMat);
    coreGroup.add(innerMesh);

    const wireGeom = new THREE.SphereGeometry(1.4, 22, 16);
    const wireMat  = new THREE.MeshBasicMaterial({ color: colors.core2, wireframe:true, transparent:true, opacity: .35 * intensity });
    const wireMesh = new THREE.Mesh(wireGeom, wireMat);
    coreGroup.add(wireMesh);

    // hot core particle cluster
    const coreParticleCount = 260;
    const cpGeom = new THREE.BufferGeometry();
    const cpPos = new Float32Array(coreParticleCount * 3);
    for (let i=0;i<coreParticleCount;i++){
      // distribute on a sphere of radius ~1
      const t = Math.random()*Math.PI*2;
      const p = Math.acos(2*Math.random()-1);
      const r = 0.85 + Math.random()*0.2;
      cpPos[i*3]   = r*Math.sin(p)*Math.cos(t);
      cpPos[i*3+1] = r*Math.sin(p)*Math.sin(t);
      cpPos[i*3+2] = r*Math.cos(p);
    }
    cpGeom.setAttribute('position', new THREE.BufferAttribute(cpPos, 3));
    const cpMat = new THREE.PointsMaterial({
      color: colors.core1, size: 0.04, transparent:true, opacity: .9 * intensity,
      blending: THREE.AdditiveBlending, depthWrite:false
    });
    const corePoints = new THREE.Points(cpGeom, cpMat);
    coreGroup.add(corePoints);

    // ---- Orbital rings ----
    const rings = [];
    if (showRings){
      const ringDefs = [
        { r: 2.2, tilt:[0.1, 0, 0.0], speed:  0.15, opa: .55 },
        { r: 2.6, tilt:[0.0, 0.4, 0.6], speed: -0.10, opa: .35 },
        { r: 3.0, tilt:[0.6, 0.0, 0.2], speed:  0.07, opa: .25 },
      ];
      ringDefs.forEach(d=>{
        const g = new THREE.RingGeometry(d.r, d.r+0.005, 128);
        const m = new THREE.MeshBasicMaterial({ color: colors.ring, transparent:true, opacity: d.opa * intensity, side: THREE.DoubleSide });
        const ring = new THREE.Mesh(g, m);
        ring.rotation.set(d.tilt[0], d.tilt[1], d.tilt[2]);
        ring.userData.speed = d.speed;
        scene.add(ring);
        rings.push(ring);

        // tracer dot on the ring
        const dotGeom = new THREE.SphereGeometry(0.05, 8, 8);
        const dotMat  = new THREE.MeshBasicMaterial({ color: colors.core1, transparent:true, opacity: .9 * intensity });
        const dot = new THREE.Mesh(dotGeom, dotMat);
        dot.userData = { radius: d.r, speed: d.speed * 4, phase: Math.random()*Math.PI*2, ring };
        scene.add(dot);
        rings.push(dot);
      });
    }

    // ---- Drifting glyphs (abstract — never readable text) ----
    let glyphPoints = null;
    if (showGlyphs){
      const tex = makeGlyphTexture();
      const N = 32;
      const gPos = new Float32Array(N*3);
      const gOff = new Float32Array(N);
      for (let i=0;i<N;i++){
        const r = 2.2 + Math.random()*1.8;
        const t = Math.random()*Math.PI*2;
        const p = Math.acos(2*Math.random()-1);
        gPos[i*3]   = r*Math.sin(p)*Math.cos(t);
        gPos[i*3+1] = r*Math.sin(p)*Math.sin(t)*0.5;
        gPos[i*3+2] = r*Math.cos(p);
        gOff[i] = Math.random()*Math.PI*2;
      }
      const gg = new THREE.BufferGeometry();
      gg.setAttribute('position', new THREE.BufferAttribute(gPos, 3));
      const gm = new THREE.PointsMaterial({
        size: 0.22, map: tex, color: colors.glyph,
        transparent:true, opacity: .65 * intensity,
        blending: THREE.AdditiveBlending, depthWrite:false
      });
      glyphPoints = new THREE.Points(gg, gm);
      glyphPoints.userData = { offsets: gOff };
      scene.add(glyphPoints);
    }

    // ---- Connection threads (form/dissolve) ----
    const threads = [];
    if (showThreads){
      const THREAD_COUNT = 3;
      for (let i=0;i<THREAD_COUNT;i++){
        const g = new THREE.BufferGeometry();
        const pts = new Float32Array(2*3);
        g.setAttribute('position', new THREE.BufferAttribute(pts, 3));
        const m = new THREE.LineBasicMaterial({ color: colors.thread, transparent:true, opacity:0 });
        const line = new THREE.Line(g, m);
        line.userData = { life: Math.random(), maxLife: 2 + Math.random()*2, p1: new THREE.Vector3(), p2: new THREE.Vector3() };
        scene.add(line);
        threads.push(line);
      }
    }

    function regenThread(line){
      const r1 = 1.0 + Math.random()*0.4;
      const r2 = 2.2 + Math.random()*1.0;
      const t1 = Math.random()*Math.PI*2;
      const p1 = Math.acos(2*Math.random()-1);
      const t2 = Math.random()*Math.PI*2;
      const p2 = Math.acos(2*Math.random()-1);
      line.userData.p1.set(r1*Math.sin(p1)*Math.cos(t1), r1*Math.sin(p1)*Math.sin(t1), r1*Math.cos(p1));
      line.userData.p2.set(r2*Math.sin(p2)*Math.cos(t2), r2*Math.sin(p2)*Math.sin(t2)*0.6, r2*Math.cos(p2));
      const arr = line.geometry.attributes.position.array;
      arr[0]=line.userData.p1.x; arr[1]=line.userData.p1.y; arr[2]=line.userData.p1.z;
      arr[3]=line.userData.p2.x; arr[4]=line.userData.p2.y; arr[5]=line.userData.p2.z;
      line.geometry.attributes.position.needsUpdate = true;
      line.userData.life = 0;
      line.userData.maxLife = 1.5 + Math.random()*2;
    }
    threads.forEach(regenThread);

    // ---- Mouse reactivity ----
    let mx = 0, my = 0, tmx = 0, tmy = 0;
    if (interactive){
      function onMove(e){
        const rect = canvas.getBoundingClientRect();
        tmx = ((e.clientX - rect.left) / rect.width  - 0.5) * 2;
        tmy = ((e.clientY - rect.top)  / rect.height - 0.5) * 2;
      }
      window.addEventListener('mousemove', onMove);
      window.addEventListener('touchmove', e=>{ if (e.touches[0]) onMove(e.touches[0]); }, {passive:true});
    }

    // ---- Resize ----
    function resize(){
      const r = canvas.getBoundingClientRect();
      const w = Math.max(2, Math.floor(r.width));
      const h = Math.max(2, Math.floor(r.height));
      if (renderer.domElement.width === w * renderer.getPixelRatio() && renderer.domElement.height === h * renderer.getPixelRatio()) return;
      renderer.setSize(w, h, false);
      cam.aspect = w/h;
      cam.updateProjectionMatrix();
    }
    let roPending = false;
    const ro = new ResizeObserver(()=>{ if (roPending) return; roPending = true; requestAnimationFrame(()=>{ roPending = false; resize(); }); });
    ro.observe(canvas.parentElement || canvas);
    resize();

    // ---- Animation loop ----
    let raf = null, t0 = performance.now(), running = true, lastT = t0;
    function tick(now){
      if (!running) return;
      raf = requestAnimationFrame(tick);
      now = now || performance.now();
      const t = (now - t0) / 1000;
      const dt = Math.min(0.05, (now - lastT) / 1000);
      lastT = now;
      const dtN = dt * 60;  // normalize to 60fps units

      // Mouse smooth
      mx += (tmx - mx) * 0.06 * dtN;
      my += (tmy - my) * 0.06 * dtN;

      const breathe = 1 + Math.sin(t * 1.3) * 0.04;
      coreGroup.scale.setScalar(breathe);
      coreGroup.rotation.y += 0.003 * dtN;
      coreGroup.rotation.x = my * 0.3;
      coreGroup.rotation.z = mx * 0.2;

      wireMesh.rotation.y -= 0.005 * dtN;
      wireMesh.rotation.x += 0.002 * dtN;

      corePoints.rotation.y += 0.002 * dtN;
      corePoints.rotation.x -= 0.001 * dtN;

      // Rings + tracer dots
      rings.forEach(r=>{
        if (r.userData.speed && r.geometry instanceof THREE.RingGeometry){
          r.rotation.z += r.userData.speed * 0.01;
        } else if (r.userData.ring){
          r.userData.phase += r.userData.speed * 0.01;
          const ang = r.userData.phase;
          const local = new THREE.Vector3(Math.cos(ang)*r.userData.radius, Math.sin(ang)*r.userData.radius, 0);
          local.applyEuler(r.userData.ring.rotation);
          r.position.copy(local);
        }
      });

      // Glyphs
      if (glyphPoints){
        glyphPoints.rotation.y += 0.0015;
        glyphPoints.rotation.x = Math.sin(t*0.3) * 0.1;
        const offsets = glyphPoints.userData.offsets;
        const arr = glyphPoints.geometry.attributes.position.array;
        for (let i=0;i<offsets.length;i++){
          const wob = Math.sin(t*0.6 + offsets[i]) * 0.02;
          arr[i*3+1] += wob * 0.05;
        }
        glyphPoints.geometry.attributes.position.needsUpdate = true;
      }

      // Threads — fade in/out
      threads.forEach(line=>{
        line.userData.life += dt;
        const lt = line.userData.life / line.userData.maxLife;
        if (lt >= 1){ regenThread(line); return; }
        // bell-curve opacity
        const o = Math.sin(lt * Math.PI) * 0.5 * intensity;
        line.material.opacity = o;
      });

      // Camera subtle parallax
      cam.position.x += ((mx * 0.6) - cam.position.x) * 0.04 * dtN;
      cam.position.y += ((-my * 0.4) - cam.position.y) * 0.04 * dtN;
      cam.lookAt(0,0,0);

      renderer.render(scene, cam);
    }
    raf = requestAnimationFrame(tick);

    return {
      pause(){ running = false; if (raf) cancelAnimationFrame(raf); },
      resume(){ if (!running){ running=true; raf=requestAnimationFrame(tick); } },
      destroy(){
        running=false; if (raf) cancelAnimationFrame(raf);
        ro.disconnect();
        renderer.dispose();
      },
      renderer, scene, cam
    };
  }

  // -----------------------------
  // Mini scene — for "how it works" steps
  // Different ambient pattern per step
  // -----------------------------
  function MiniScene(canvas, mode){
    const renderer = new THREE.WebGLRenderer({ canvas, antialias:true, alpha:true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.25));
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    cam.position.set(0,0,4);

    let obj;
    if (mode === 'foundation'){
      // stacking grid
      const g = new THREE.Group();
      for (let i=0;i<5;i++){
        const ring = new THREE.Mesh(
          new THREE.TorusGeometry(0.6 - i*0.08, 0.012, 8, 48),
          new THREE.MeshBasicMaterial({ color: 0x5d614a, transparent:true, opacity: 0.6 - i*0.08 })
        );
        ring.position.y = -0.3 + i*0.15;
        ring.rotation.x = Math.PI/2;
        g.add(ring);
      }
      obj = g;
    } else if (mode === 'signal'){
      // waveform
      const N = 48;
      const pts = new Float32Array(N*3);
      for (let i=0;i<N;i++){ pts[i*3]= -1+ (i/(N-1))*2; pts[i*3+1]=0; pts[i*3+2]=0; }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(pts,3));
      obj = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0x5d614a }));
      obj.userData = { type:'wave', N };
    } else if (mode === 'rewrite'){
      // particle swap
      const N = 90;
      const pts = new Float32Array(N*3);
      for (let i=0;i<N;i++){
        pts[i*3]= (Math.random()-0.5)*1.6;
        pts[i*3+1]= (Math.random()-0.5)*1.2;
        pts[i*3+2]= (Math.random()-0.5)*0.4;
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(pts,3));
      obj = new THREE.Points(g, new THREE.PointsMaterial({ color: 0x5d614a, size:0.04, transparent:true, opacity:.8 }));
      obj.userData = { type:'swap' };
    } else { // artifact
      // box assembling
      const g = new THREE.Group();
      const m = new THREE.MeshBasicMaterial({ color: 0x5d614a, wireframe:true });
      const cube = new THREE.Mesh(new THREE.BoxGeometry(0.9,1.2,0.05), m);
      g.add(cube);
      const inner = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.04),
        new THREE.MeshBasicMaterial({ color: 0x5d614a, transparent:true, opacity:.5 }));
      for (let i=0;i<5;i++){
        const ln = inner.clone();
        ln.position.set(0, 0.4 - i*0.18, 0.04);
        g.add(ln);
      }
      obj = g;
    }
    scene.add(obj);

    function resize(){
      const r = canvas.getBoundingClientRect();
      const w = Math.max(2, Math.floor(r.width));
      const h = Math.max(2, Math.floor(r.height));
      if (renderer.domElement.width === w * renderer.getPixelRatio() && renderer.domElement.height === h * renderer.getPixelRatio()) return;
      renderer.setSize(w, h, false);
      cam.aspect = w/h; cam.updateProjectionMatrix();
    }
    let roP = false;
    const ro = new ResizeObserver(()=>{ if (roP) return; roP = true; requestAnimationFrame(()=>{ roP = false; resize(); }); });
    ro.observe(canvas.parentElement || canvas);
    resize();

    let t0 = performance.now(), running = true, raf = null;
    function tick(){
      if (!running) return;
      raf = requestAnimationFrame(tick);
      const t = (performance.now()-t0)/1000;
      if (obj.userData && obj.userData.type === 'wave'){
        const arr = obj.geometry.attributes.position.array;
        for (let i=0;i<obj.userData.N;i++){
          arr[i*3+1] = Math.sin(i*0.3 + t*3) * 0.3 * Math.exp(-Math.abs(i-obj.userData.N/2)/30);
        }
        obj.geometry.attributes.position.needsUpdate = true;
      } else if (obj.userData && obj.userData.type === 'swap'){
        const arr = obj.geometry.attributes.position.array;
        for (let i=0;i<arr.length;i+=3){
          arr[i+1] += Math.sin(t*2 + i*0.05)*0.003;
        }
        obj.geometry.attributes.position.needsUpdate = true;
        obj.rotation.y += 0.005;
      } else {
        obj.rotation.y += 0.005;
        obj.rotation.x = Math.sin(t)*0.15;
      }
      renderer.render(scene, cam);
    }
    raf = requestAnimationFrame(tick);
    return {
      pause(){ running=false; if (raf) cancelAnimationFrame(raf); },
      resume(){ if(!running){ running=true; raf=requestAnimationFrame(tick);} },
      destroy(){ running=false; if (raf) cancelAnimationFrame(raf); ro.disconnect(); renderer.dispose(); }
    };
  }

  global.IdentityOS = { CoreScene, MiniScene, ready };
})(window);
