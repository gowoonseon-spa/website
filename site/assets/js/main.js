(function () {
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---- header: overlay → solid on scroll ---- */
  var header = document.querySelector('.site-header');
  function onScrollHeader() {
    if (window.scrollY > 24) header.classList.add('scrolled');
    else header.classList.remove('scrolled');
  }
  if (header) { onScrollHeader(); window.addEventListener('scroll', onScrollHeader, { passive: true }); }

  /* ---- mobile menu ---- */
  var menu = document.getElementById('mmenu');
  var openBtn = document.getElementById('menuOpen');
  var closeBtn = document.getElementById('menuClose');
  if (menu && openBtn && closeBtn) {
    openBtn.addEventListener('click', function () { menu.classList.add('open'); closeBtn.focus(); });
    closeBtn.addEventListener('click', function () { menu.classList.remove('open'); openBtn.focus(); });
    menu.addEventListener('click', function (e) { if (e.target.tagName === 'A') menu.classList.remove('open'); });
  }

  /* ---- drift: 동선의 결 (무한 루프 갤러리) ---- */
  document.querySelectorAll('[data-drift]').forEach(function (drift) {
    var track = drift.querySelector('.drift-track');
    var half = 0, pos = null, paused = false, inView = false;
    var dragging = false, dragX = 0, dragStart = 0;
    function measure() { half = track.scrollWidth / 2; }
    if (document.readyState === 'complete') measure();
    else window.addEventListener('load', measure);
    window.addEventListener('resize', measure);
    if ('ResizeObserver' in window) new ResizeObserver(measure).observe(track);
    // 순환: 세트 2벌이 픽셀 단위로 동일하므로 절반 폭 점프는 보이지 않는다
    drift.addEventListener('scroll', function () {
      if (!half || dragging) return;
      if (drift.scrollLeft >= half) { drift.scrollLeft -= half; pos = drift.scrollLeft; }
      else if (drift.scrollLeft <= 0 && pos !== null) { drift.scrollLeft += half; pos = drift.scrollLeft; }
    }, { passive: true });
    // 데스크톱 드래그
    drift.addEventListener('pointerdown', function (e) {
      if (e.pointerType !== 'mouse') return;
      dragging = true; dragX = e.clientX; dragStart = drift.scrollLeft;
      drift.classList.add('dragging');
    });
    window.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      var t = dragStart - (e.clientX - dragX);
      if (half) { while (t >= half) { t -= half; dragStart -= half; } while (t < 0) { t += half; dragStart += half; } }
      drift.scrollLeft = t;
    });
    ['pointerup', 'pointercancel'].forEach(function (ev) {
      window.addEventListener(ev, function () {
        if (dragging) { dragging = false; drift.classList.remove('dragging'); }
      });
    });
    // 자동 드리프트: 보일 때만. 정지는 "만료되는 홀드"로만 — 터치가 스크롤로 바뀌며
    // touchend 없이 touchcancel로 끝나도(모바일에서 흔함) 홀드가 스스로 풀리므로
    // 영구히 멈추는 상태가 없다. 마우스 호버만 지속형 정지.
    if (!reduced) {
      var hovering = false, holdUntil = 0;
      function hold() { holdUntil = performance.now() + 2600; }
      drift.addEventListener('pointerenter', function (e) { if (e.pointerType === 'mouse') hovering = true; });
      drift.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse') hovering = false; });
      ['touchstart', 'touchmove', 'pointerdown', 'wheel'].forEach(function (ev) {
        drift.addEventListener(ev, hold, { passive: true });
      });
      if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (en) { inView = en[0].isIntersecting; }).observe(drift);
      } else inView = true;
      var prevT = null;
      (function step(t) {
        var dt = prevT === null ? 0 : Math.min(t - prevT, 100);
        prevT = t;
        var held = hovering || dragging || (t !== null && t < holdUntil);
        if (half && inView && !held) {
          if (pos === null || Math.abs(drift.scrollLeft - pos) > 2) pos = drift.scrollLeft;
          // 랩 후 최소 2px 확보 — 모바일이 scrollLeft를 0으로 내림반올림하면
          // 아래 역방향 랩(<= 0)과 핑퐁하며 영구 정지하므로 0 근처에 착지 금지
          pos += 0.030 * dt; if (pos >= half) pos = Math.max(pos - half, 2);
          drift.scrollLeft = pos;
        } else if (held) pos = drift.scrollLeft;
        requestAnimationFrame(step);
      })(null);
    }
  });

  /* ---- carousels (두피 카드 등) ---- */
  document.querySelectorAll('[data-carousel]').forEach(function (root) {
    var track = root.querySelector('.carousel');
    var dots = root.querySelectorAll('.dots i');
    var slides = track.children.length;
    var idx = 0, timer = null, paused = false;
    function go(i) {
      idx = (i + slides) % slides;
      track.scrollTo({ left: track.clientWidth * idx, behavior: reduced ? 'auto' : 'smooth' });
    }
    function sync() {
      var i = Math.round(track.scrollLeft / Math.max(1, track.clientWidth));
      if (i !== idx) idx = i;
      dots.forEach(function (d, k) { d.classList.toggle('active', k === idx); });
    }
    track.addEventListener('scroll', function () { requestAnimationFrame(sync); }, { passive: true });
    ['pointerdown', 'touchstart', 'mouseenter'].forEach(function (ev) {
      root.addEventListener(ev, function () { paused = true; }, { passive: true });
    });
    root.addEventListener('mouseleave', function () { paused = false; });
    if (!reduced) timer = setInterval(function () { if (!paused) go(idx + 1); }, 5500);
    sync();
  });

  /* ---- programs: category nav active state ---- */
  var catLinks = document.querySelectorAll('.cat-nav a');
  if (catLinks.length && 'IntersectionObserver' in window) {
    var map = {};
    catLinks.forEach(function (a) { map[a.getAttribute('href').slice(1)] = a; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          catLinks.forEach(function (a) { a.classList.remove('active'); });
          var a = map[en.target.id];
          if (a) { a.classList.add('active'); a.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' }); }
        }
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    document.querySelectorAll('.category[id]').forEach(function (s) { io.observe(s); });
  }

  /* ---- tel dialog: 데스크톱(호버+정밀 포인터)에서는 tel: 대신 번호 안내 ---- */
  var telDialog = document.getElementById('telDialog');
  if (telDialog && typeof telDialog.showModal === 'function' &&
      window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    document.querySelectorAll('a[href^="tel:"]').forEach(function (a) {
      a.addEventListener('click', function (e) { e.preventDefault(); telDialog.showModal(); });
    });
    telDialog.addEventListener('click', function (e) { if (e.target === telDialog) telDialog.close(); });
    document.getElementById('telClose').addEventListener('click', function () { telDialog.close(); });
    var telCopy = document.getElementById('telCopy');
    telCopy.addEventListener('click', function () {
      function done() { telCopy.textContent = '복사되었습니다'; setTimeout(function () { telCopy.textContent = '번호 복사'; }, 1800); }
      var num = document.getElementById('telDialogNum').textContent.trim();
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(num).then(done, done);
      else done();
    });
  }

  /* ---- back to top ---- */
  var toTop = document.getElementById('toTop');
  if (toTop) {
    window.addEventListener('scroll', function () {
      toTop.classList.toggle('show', window.scrollY > 1200);
    }, { passive: true });
    toTop.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' }); });
  }
})();
