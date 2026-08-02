// ============================================================
// Smooth Page Transitions — intercept internal link clicks
// ============================================================
(function initPageTransitions() {
    const TRANSITION_DURATION = 350; // ms — matches CSS pageLeave duration

    // Only intercept same-origin links that navigate to a new page
    function isInternalLink(a) {
        if (!a.href) return false;
        if (a.target === '_blank') return false;
        if (a.hasAttribute('download')) return false;
        // Ignore bare '#' links (toggles, drawers, etc.)
        const rawHref = a.getAttribute('href');
        if (!rawHref || rawHref === '#') return false;
        // Ignore hash-only links on the same page
        try {
            const url = new URL(a.href, location.origin);
            if (url.origin !== location.origin) return false;
            // Hash-only link on same page (scroll, not navigate)
            if (url.pathname === location.pathname && url.hash) return false;
            return true;
        } catch(e) { return false; }
    }

    document.addEventListener('click', function(e) {
        // Walk up from target to find nearest <a>
        const link = e.target.closest('a');
        if (!link || !isInternalLink(link)) return;
        if (e.ctrlKey || e.metaKey || e.shiftKey) return; // allow new-tab clicks

        e.preventDefault();
        const dest = link.href;

        // Trigger exit animation
        document.body.classList.add('page-leaving');

        // Navigate after animation completes
        setTimeout(function() {
            window.location.href = dest;
        }, TRANSITION_DURATION);
    });

    // Handle browser back/forward — re-enter smoothly
    window.addEventListener('pageshow', function(e) {
        if (e.persisted) {
            // Page was restored from bfcache — remove leaving class
            document.body.classList.remove('page-leaving');
        }
    });
})();

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, function(char) {
        return {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        }[char];
    });
}

// ============================================================
// Dark / Light Theme Toggle
// ============================================================
(function initThemeToggle() {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;

    function setTheme(theme, animate) {
        if (animate) {
            document.body.classList.add('theme-transitioning');
            setTimeout(() => document.body.classList.remove('theme-transitioning'), 600);
        }
        if (theme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
        localStorage.setItem('theme', theme);
    }

    btn.addEventListener('click', () => {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        setTheme(isDark ? 'light' : 'dark', true);
    });
})();

// ============================================================
// Mobile Hamburger Menu Toggle
// ============================================================
(function initHamburger() {
    const hamburger = document.getElementById('hamburger');
    const nav = document.getElementById('mainNav');
    if (!hamburger || !nav) return;

    hamburger.addEventListener('click', () => {
        hamburger.classList.toggle('active');
        nav.classList.toggle('nav-open');
        document.body.classList.toggle('nav-open-body');
    });

    // Close nav when a link is clicked
    nav.querySelectorAll('a').forEach(a => {
        a.addEventListener('click', () => {
            hamburger.classList.remove('active');
            nav.classList.remove('nav-open');
            document.body.classList.remove('nav-open-body');
        });
    });

    // Close nav on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && nav.classList.contains('nav-open')) {
            hamburger.classList.remove('active');
            nav.classList.remove('nav-open');
            document.body.classList.remove('nav-open-body');
        }
    });
})();

// ============================================================
// Search Overlay Functionality
// ============================================================
(function initSearch() {
    const toggle = document.getElementById('searchToggle');
    const overlay = document.getElementById('searchOverlay');
    if (!toggle || !overlay) return;

    const input = document.getElementById('searchInput');
    const results = document.getElementById('searchResults');
    const clearBtn = document.getElementById('searchClear');
    const closeBtn = document.getElementById('searchClose');
    const backdrop = overlay.querySelector('.search-overlay-backdrop');
    const container = overlay.querySelector('.search-container');
    if (!input || !results || !clearBtn || !closeBtn || !backdrop || !container) return;

    let debounceTimer = null;
    let abortController = null;

    function updateOrigin() {
        const iconRect = toggle.getBoundingClientRect();
        const overlayStyle = getComputedStyle(overlay);
        const padTop = parseFloat(overlayStyle.paddingTop) || 70;
        const overlayW = window.innerWidth;
        const containerW = Math.min(overlayW * 0.9, 640);
        const containerLeft = (overlayW - containerW) / 2;
        const originX = iconRect.left + iconRect.width / 2 - containerLeft;
        const originY = iconRect.top + iconRect.height / 2 - padTop;
        container.style.transformOrigin = `${originX}px ${originY}px`;
    }

    function openSearch(e) {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        updateOrigin();
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        if (typeof lenis !== 'undefined' && lenis) lenis.stop();
        setTimeout(() => input.focus(), 150);
    }

    function closeSearch() {
        // Recalculate origin so it collapses back toward the icon
        updateOrigin();
        overlay.classList.remove('active');
        document.body.style.overflow = '';
        if (typeof lenis !== 'undefined' && lenis) lenis.start();
        input.value = '';
        clearBtn.classList.remove('visible');
        results.innerHTML = '<div class="search-empty"><i class="fas fa-search"></i><p>Start typing to search...</p></div>';
    }

    function performSearch(query) {
        if (abortController) abortController.abort();
        if (query.length < 2) {
            results.innerHTML = '<div class="search-empty"><i class="fas fa-search"></i><p>Start typing to search...</p></div>';
            return;
        }

        results.innerHTML = '<div class="search-loading"><i class="fas fa-spinner fa-spin"></i> Searching...</div>';

        abortController = new AbortController();
        fetch(`/api/search/?q=${encodeURIComponent(query)}`, { signal: abortController.signal })
            .then(r => r.json())
            .then(data => {
                if (!data.results || data.results.length === 0) {
                    results.innerHTML = '<div class="search-no-results"><i class="fas fa-search"></i><p>No results found</p></div>';
                    return;
                }
                results.innerHTML = data.results.map(item => {
                    const name = escapeHtml(item.name || '');
                    const category = escapeHtml(item.category || '');
                    const section = escapeHtml(item.section || '');
                    const url = escapeHtml(item.url || '');
                    const price = escapeHtml(item.price || '');
                    const discountedPrice = escapeHtml(item.discounted_price || '');
                    const image = escapeHtml(item.image || '');
                    let priceHTML = '';
                    if (item.price) {
                        if (item.discounted_price && item.discount > 0) {
                            priceHTML = `<p class="search-result-price">${discountedPrice}<span class="original-price">${price}</span><span class="discount-badge">${item.discount}% OFF</span></p>`;
                        } else {
                            priceHTML = `<p class="search-result-price">${price}</p>`;
                        }
                    }
                    const imgHTML = item.image
                        ? `<img src="${image}" alt="${name}" class="search-result-img" loading="lazy">`
                        : '';
                    return `<div class="search-result-item" data-section="${section}" data-url="${url}">
                        ${imgHTML}
                        <div class="search-result-info">
                            <p class="search-result-category">${category}</p>
                            <p class="search-result-name">${name}</p>
                            ${priceHTML}
                        </div>
                        ${item.url ? '<span class="search-result-arrow"><i class="fas fa-arrow-right"></i></span>' : ''}
                    </div>`;
                }).join('');

                // Click on result → navigate to product page or scroll to section
                results.querySelectorAll('.search-result-item').forEach(el => {
                    el.addEventListener('click', () => {
                        const url = el.dataset.url;
                        const section = el.dataset.section;
                        closeSearch();

                        if (url) {
                            // Navigate to product detail page with transition
                            document.body.classList.add('page-leaving');
                            setTimeout(() => { window.location.href = url; }, 350);
                        } else if (section) {
                            const target = document.querySelector(section);
                            if (target && lenis) {
                                lenis.scrollTo(target, { offset: -80, duration: 1.2 });
                            } else {
                                window.location.href = '/' + section;
                            }
                        }
                    });
                });
            })
            .catch(err => {
                if (err.name !== 'AbortError') {
                    results.innerHTML = '<div class="search-no-results"><i class="fas fa-exclamation-circle"></i><p>Something went wrong</p></div>';
                }
            });
    }

    // Event listeners
    toggle.addEventListener('click', openSearch);
    closeBtn.addEventListener('click', closeSearch);
    backdrop.addEventListener('click', closeSearch);

    input.addEventListener('input', () => {
        const val = input.value.trim();
        clearBtn.classList.toggle('visible', val.length > 0);
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => performSearch(val), 300);
    });

    clearBtn.addEventListener('click', () => {
        input.value = '';
        clearBtn.classList.remove('visible');
        input.focus();
        results.innerHTML = '<div class="search-empty"><i class="fas fa-search"></i><p>Start typing to search...</p></div>';
    });

    // Escape to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay.classList.contains('active')) closeSearch();
    });

    // Ctrl+K / Cmd+K shortcut to open
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            overlay.classList.contains('active') ? closeSearch() : openSearch();
        }
    });
})();

// ============================================================
// Lenis Smooth Scroll — momentum-based inertial scrolling
// ============================================================
let lenis = null;
if (typeof Lenis !== 'undefined') {
    lenis = new Lenis({
        duration: 1.2,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        orientation: 'vertical',
        gestureOrientation: 'vertical',
        smoothWheel: true,
        wheelMultiplier: 1,
        touchMultiplier: 2,
        infinite: false,
    });
}

// ============================================================
// Splash Cursor — comet-tail: sleek at pointer, swells outward
// (Disabled on touch devices for performance)
// ============================================================
const _prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const _hasPrimaryFinePointer = window.matchMedia ? window.matchMedia('(hover: hover) and (pointer: fine)').matches : true;
const _hasAnyFinePointer = window.matchMedia ? window.matchMedia('(any-hover: hover) and (any-pointer: fine)').matches : true;
const _hasFinePointer = _hasPrimaryFinePointer || _hasAnyFinePointer;
const _isTouchDevice = !_hasFinePointer || _prefersReducedMotion;
const _cursorAlreadyInitialized = Boolean(window.__ambavaCursorInitialized);
const _canvas = document.getElementById('cursor-canvas');
if (_canvas && _isTouchDevice) {
    _canvas.style.display = 'none';
}
if (_canvas && !_isTouchDevice && !_cursorAlreadyInitialized) {
    window.__ambavaCursorInitialized = true;
}
const _ctx = (_canvas && !_isTouchDevice && !_cursorAlreadyInitialized) ? _canvas.getContext('2d') : null;
let _cw, _ch;

function resizeCanvas() {
    _cw = window.innerWidth;
    _ch = window.innerHeight;
    if (_canvas) {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        _canvas.width = Math.floor(_cw * dpr);
        _canvas.height = Math.floor(_ch * dpr);
        _canvas.style.width = `${_cw}px`;
        _canvas.style.height = `${_ch}px`;
        if (_ctx) {
            _ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
    }
}
resizeCanvas();
window.addEventListener('resize', resizeCanvas, { passive: true });

if (_ctx) {
// Luxury color palette
const SPLASH_COLORS = [
    [196, 165, 123],  // gold
    [232, 213, 196],  // light accent
    [180, 140, 100],  // deep gold
    [255, 200, 140],  // warm peach
    [160, 120, 80],   // bronze
    [220, 180, 140],  // soft tan
    [255, 220, 180],  // cream gold
    [200, 160, 120],  // caramel
];

const POOL_SIZE = 300;
let _mx = -100, _my = -100, _prevMx = -100, _prevMy = -100;
let _isHovering = false;
let _mouseOnPage = false;
let _lastTime = performance.now();

// ---- Particle: starts tiny at cursor, grows as it drifts, then fades ----
class Particle {
    constructor() { this.alive = false; }
    init(x, y, vx, vy, peakSize, cr, cg, cb, life) {
        this.x = x; this.y = y;
        this.vx = vx; this.vy = vy;
        this.peakSize = peakSize;   // max size it grows to
        this.cr = cr; this.cg = cg; this.cb = cb;
        this.life = life; this.maxLife = life;
        this.alive = true;
        return this;
    }
    update(dt) {
        const f = dt * 60;
        this.life -= dt;
        const friction = Math.pow(0.96, f);
        this.vx *= friction;
        this.vy *= friction;
        this.vy += 0.008 * f;       // very subtle gravity
        this.x += this.vx * f;
        this.y += this.vy * f;
        if (this.life <= 0) { this.alive = false; }
    }
    draw(ctx) {
        // age: 0 = just born → 1 = about to die
        const age = 1 - Math.max(this.life / this.maxLife, 0);

        // SIZE: starts tiny (sleek), swells to peak around 60% of life, then shrinks
        // bell-curve shape: sin(π * age)^0.7 — fast rise, gentle fall
        const sizeCurve = Math.pow(Math.sin(Math.PI * age), 0.7);
        const size = this.peakSize * sizeCurve;
        if (size < 0.2) return;

        // ALPHA: starts subtle, peaks in middle, fades out smoothly
        // Use smoothstep for the fade-in and cubic for fade-out
        let alpha;
        if (age < 0.15) {
            // Quick fade-in
            const t = age / 0.15;
            alpha = t * t * 0.6;
        } else {
            // Smooth fade-out after peak
            const t = Math.max(this.life / this.maxLife, 0);
            alpha = t * t * 0.6;
        }

        ctx.globalAlpha = alpha;
        ctx.beginPath();
        ctx.arc(this.x, this.y, size, 0, Math.PI * 2);
        ctx.fillStyle = `rgb(${this.cr},${this.cg},${this.cb})`;
        ctx.fill();
    }
}

const pool = [];
for (let i = 0; i < POOL_SIZE; i++) pool.push(new Particle());

function getParticle() {
    for (let i = 0; i < POOL_SIZE; i++) {
        if (!pool[i].alive) return pool[i];
    }
    let oldest = pool[0];
    for (let i = 1; i < POOL_SIZE; i++) {
        if (pool[i].life < oldest.life) oldest = pool[i];
    }
    return oldest;
}

function spawnTrail(x, y, speed) {
    // Fewer particles = cleaner trail; speed-responsive
    const count = _isHovering ? Math.floor(speed * 0.4 + 2) : Math.floor(speed * 0.2 + 1);
    const peakSize = _isHovering ? 7 : 5;
    for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2;
        // Gentle outward drift so particles spread behind cursor
        const force = (Math.random() * 0.6 + 0.15) * Math.min(speed * 0.08, 1.8);
        const [cr, cg, cb] = SPLASH_COLORS[Math.floor(Math.random() * SPLASH_COLORS.length)];
        getParticle().init(
            x + (Math.random() - 0.5) * 2,   // spawn right at cursor
            y + (Math.random() - 0.5) * 2,
            Math.cos(angle) * force,
            Math.sin(angle) * force,
            Math.random() * peakSize + 1.5,   // peak size (grows into this)
            cr, cg, cb,
            Math.random() * 0.7 + 0.5         // 0.5–1.2s life
        );
    }
}

// Interpolate along mouse path for continuous trail
function spawnInterpolated(x0, y0, x1, y1) {
    const dx = x1 - x0, dy = y1 - y0;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < 2) return;
    const steps = Math.min(Math.floor(dist / 8), 10);
    for (let s = 0; s <= steps; s++) {
        const t = s / Math.max(steps, 1);
        spawnTrail(x0 + dx * t, y0 + dy * t, dist / Math.max(steps, 1));
    }
}

document.addEventListener('mousemove', (e) => {
    _mx = e.clientX;
    _my = e.clientY;
    _mouseOnPage = true;
    spawnInterpolated(_prevMx, _prevMy, _mx, _my);
    _prevMx = _mx;
    _prevMy = _my;
}, { passive: true });

document.addEventListener('mouseout', () => { _mouseOnPage = false; });
document.addEventListener('mouseenter', () => { _mouseOnPage = true; });

// Hover detection
document.addEventListener('mouseover', (e) => {
    if (e.target.closest('a, button, .btn, .featured-card, .flip-card, .showcase-item, input, textarea')) {
        _isHovering = true;
    }
});
document.addEventListener('mouseout', (e) => {
    if (e.target.closest('a, button, .btn, .featured-card, .flip-card, .showcase-item, input, textarea')) {
        _isHovering = false;
    }
});

// Click burst — particles bloom outward from cursor
document.addEventListener('click', (e) => {
    for (let i = 0; i < 20; i++) {
        const angle = (Math.PI * 2 / 20) * i + (Math.random() - 0.5) * 0.25;
        const force = Math.random() * 3 + 1.5;
        const [cr, cg, cb] = SPLASH_COLORS[Math.floor(Math.random() * SPLASH_COLORS.length)];
        getParticle().init(
            e.clientX, e.clientY,
            Math.cos(angle) * force,
            Math.sin(angle) * force,
            Math.random() * 6 + 3,
            cr, cg, cb,
            Math.random() * 0.5 + 0.4
        );
    }
});

function cursorLoop(now) {
    if (!_ctx) return;
    const dt = Math.min((now - _lastTime) / 1000, 0.05);
    _lastTime = now;

    _ctx.clearRect(0, 0, _cw, _ch);
    _ctx.globalAlpha = 1;

    for (let i = 0; i < POOL_SIZE; i++) {
        const p = pool[i];
        if (!p.alive) continue;
        p.update(dt);
        if (p.alive) p.draw(_ctx);
    }
    _ctx.globalAlpha = 1;

    requestAnimationFrame(cursorLoop);
}
requestAnimationFrame(cursorLoop);
}

// Parallax is now handled in the main animation loop below — no separate handler needed

// Scroll Animation for Elements
// NOTE: .featured-card, .showcase-item, .flip-card, .stat-card get 3D
// transform effects from the cylindrical scroll animation (tick()) on the
// home page. No opacity manipulation — elements stay fully visible.

// Add animation keyframes dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes slideInLeft {
        from {
            opacity: 0;
            transform: translateX(-50px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(50px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
`;
document.head.appendChild(style);

// Form Submission
const contactForm = document.querySelector('.contact-form');
if (contactForm) {
    contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = contactForm.querySelector('button[type="submit"]');
        if (btn) { btn.disabled = true; btn.textContent = 'Sending...'; }
        try {
            const formData = new FormData(contactForm);
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value
                || document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
            const resp = await fetch('/api/contact/', {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData,
                credentials: 'same-origin',
            });
            const data = await resp.json();
            if (data.ok) {
                contactForm.reset();
                contactForm.innerHTML = '<div style="text-align:center;padding:2rem;"><i class="fas fa-check-circle" style="font-size:2.5rem;color:#4CAF50;margin-bottom:1rem;"></i><p style="font-size:1.1rem;">Thank you! We\'ll get back to you soon.</p></div>';
            } else {
                alert(data.error || Object.values(data.errors || {})[0] || 'Something went wrong. Please try again.');
            }
        } catch (err) {
            alert('Network error. Please try again.');
        }
        if (btn) { btn.disabled = false; btn.textContent = 'Send Message'; }
    });
}

// Smooth Scroll for Navigation — powered by Lenis
document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
        const href = link.getAttribute('href');
        if (href !== '#' && document.querySelector(href)) {
            e.preventDefault();
            const targetElement = document.querySelector(href);
            const headerHeight = document.querySelector('header')?.offsetHeight || 0;

            if (href === '#home') {
                // Scroll to top for home
                if (lenis) lenis.scrollTo(0, { duration: 1.5 });
                else window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                // Scroll to element with header offset
                if (lenis) {
                    lenis.scrollTo(targetElement, {
                        offset: -headerHeight,
                        duration: 1.5
                    });
                } else {
                    targetElement.scrollIntoView({ behavior: 'smooth' });
                }
            }
        }
    });
});

// Add hover effect to buttons
document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-3px)';
    });
    btn.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
    });
});

// Counter Animation for Stats
const stats = document.querySelectorAll('.stat-number');
const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && !entry.target.dataset.counted) {
            entry.target.dataset.counted = true;
            animateCounter(entry.target);
        }
    });
}, { threshold: 0.5 });

stats.forEach(stat => counterObserver.observe(stat));

function animateCounter(element) {
    const finalValue = element.textContent;
    const finalNumber = parseInt(finalValue);
    let currentNumber = 0;
    
    if (!isNaN(finalNumber)) {
        const increment = finalNumber / 50;
        const timer = setInterval(() => {
            currentNumber += increment;
            if (currentNumber >= finalNumber) {
                element.textContent = finalValue;
                clearInterval(timer);
            } else {
                element.textContent = Math.floor(currentNumber) + (finalValue.includes('+') ? '+' : '');
            }
        }, 30);
    }
}

// ============================================================
// Cylindrical 3D Scroll Animations — "Round Page" Effect
// ============================================================
// Only active on the home page (where .hero and homepage sections exist)
// ============================================================

function lerp(a, b, t) { return a + (b - a) * t; }

const _isHomePage = !!document.querySelector('.hero, #home');

// Cache ALL DOM lookups once at startup — only meaningful on home page
const _sections       = _isHomePage ? document.querySelectorAll('section') : [];
const _showcaseItems  = document.querySelectorAll('.showcase-item');
const _featuredCards  = document.querySelectorAll('.featured-card');
const _flipCards      = document.querySelectorAll('.flip-card');
const _statCards      = document.querySelectorAll('.stat-card');
const _floatingEls    = document.querySelectorAll('.floating');
const _sectionHeaders = Array.from(document.querySelectorAll('.section-header')).map(h => ({
    el: h,
    h2: h.querySelector('h2'),
    p:  h.querySelector('p')
}));
const _heroText       = document.querySelector('.floating-text');
const _heroBackground = document.querySelector('.hero-background');

// Per-element state — stores current lerped values
const _st = new WeakMap();
function S(el, def) { if (!_st.has(el)) _st.set(el, { ...def }); return _st.get(el); }

// Base lerp factor at 60 fps — delta-time corrected in tick()
const BASE_LERP = 0.12;
const DEAD = 0.04;
let _lastY = 0, _running = false, _wh = window.innerHeight;
let _prevTime = 0;

window.addEventListener('resize', () => { _wh = window.innerHeight; }, { passive: true });

function tick(now) {
    // Delta-time normalization — same speed at 60/120/144 Hz
    if (!_prevTime) _prevTime = now;
    const dt = Math.min(now - _prevTime, 50); // cap at 50ms to prevent jumps
    _prevTime = now;
    const dtFactor = dt / 16.667; // 1.0 at 60fps
    const L = 1 - Math.pow(1 - BASE_LERP, dtFactor); // frame-rate independent lerp

    const scrollY = window.scrollY;
    const vel = Math.abs(scrollY - _lastY);
    _lastY = scrollY;
    let alive = false;

    // ── PHASE 1: Batch all DOM reads (getBoundingClientRect) ──
    const secRects = new Array(_sections.length);
    for (let i = 0; i < _sections.length; i++) secRects[i] = _sections[i].getBoundingClientRect();

    const showcaseRects = new Array(_showcaseItems.length);
    for (let i = 0; i < _showcaseItems.length; i++) showcaseRects[i] = _showcaseItems[i].getBoundingClientRect();

    const featRects = new Array(_featuredCards.length);
    for (let i = 0; i < _featuredCards.length; i++) featRects[i] = _featuredCards[i].getBoundingClientRect();

    const flipRects = new Array(_flipCards.length);
    for (let i = 0; i < _flipCards.length; i++) flipRects[i] = _flipCards[i].getBoundingClientRect();

    const statRects = new Array(_statCards.length);
    for (let i = 0; i < _statCards.length; i++) statRects[i] = _statCards[i].getBoundingClientRect();

    const headerRects = new Array(_sectionHeaders.length);
    for (let i = 0; i < _sectionHeaders.length; i++) headerRects[i] = _sectionHeaders[i].el.getBoundingClientRect();

    const heroTextRect = _heroText ? _heroText.getBoundingClientRect() : null;

    // ── PHASE 2: Compute + batch all DOM writes ──

    // ── Sections: cylindrical page rotation ──
    const halfH = _wh * 0.5;
    const invRange = 1 / (_wh * 0.6);
    for (let i = 0; i < _sections.length; i++) {
        const sec = _sections[i];
        const rect = secRects[i];
        const center = rect.top + rect.height * 0.5;
        const dist = (center - halfH) * invRange;
        const clamped = dist < -1 ? -1 : dist > 1 ? 1 : dist;
        const absClamped = clamped < 0 ? -clamped : clamped;

        const tgtRX = clamped * -12;
        const tgtSc = 1 - absClamped * 0.06;
        const tgtTY = clamped * 30;

        const s = S(sec, { rx: 0, sc: 1, ty: 0 });
        s.rx = lerp(s.rx, tgtRX, L);
        s.sc = lerp(s.sc, tgtSc, L);
        s.ty = lerp(s.ty, tgtTY, L);

        // Only write if values changed meaningfully
        const dRX = s.rx - tgtRX, dTY = s.ty - tgtTY;
        if (dRX > DEAD || dRX < -DEAD || dTY > DEAD || dTY < -DEAD) alive = true;

        sec.style.transform = `perspective(1200px) rotateX(${s.rx.toFixed(1)}deg) scale(${s.sc.toFixed(3)}) translateY(${s.ty.toFixed(0)}px)`;
        sec.style.transformOrigin = clamped > 0 ? 'center top' : 'center bottom';
    }

    // ── Showcase items: staggered fan-in from below ──
    const inv07 = 1 / (_wh * 0.7);
    for (let i = 0; i < _showcaseItems.length; i++) {
        const el = _showcaseItems[i];
        const rect = showcaseRects[i];
        if (rect.top > _wh + 300 || rect.bottom < -300) continue;
        const p = (_wh - rect.top) * inv07;
        const pCl = p < 0 ? 0 : p > 1 ? 1 : p;
        const stagger = (i % 4) * 0.08;
        const prog = (pCl - stagger) / (1 - stagger);
        const progress = prog < 0 ? 0 : prog > 1 ? 1 : prog;
        const inv = 1 - progress;

        const tgtRX = inv * 25;
        const tgtTY = inv * 60;

        const s = S(el, { rx: tgtRX, ty: tgtTY });
        s.rx = lerp(s.rx, tgtRX, L);
        s.ty = lerp(s.ty, tgtTY, L);
        el.style.transform = `perspective(800px) rotateX(${s.rx.toFixed(1)}deg) translateY(${s.ty.toFixed(0)}px)`;
        el.style.transformOrigin = 'center bottom';
        const d = s.rx - tgtRX;
        if (d > DEAD || d < -DEAD) alive = true;
    }

    // ── Featured cards: rotate in from side like card deck ──
    for (let i = 0; i < _featuredCards.length; i++) {
        const card = _featuredCards[i];
        const rect = featRects[i];
        if (rect.top > _wh + 300 || rect.bottom < -300) continue;
        const raw = (_wh - rect.top) * inv07;
        const p = raw < 0 ? 0 : raw > 1 ? 1 : raw;

        const direction = (i & 1) ? -1 : 1;
        const inv = 1 - p;
        const tgtRY = inv * 20 * direction;
        const tgtTX = inv * 40 * direction;
        const tgtSc = 0.88 + p * 0.12;

        const s = S(card, { ry: tgtRY, tx: tgtTX, sc: tgtSc });
        s.ry = lerp(s.ry, tgtRY, L);
        s.tx = lerp(s.tx, tgtTX, L);
        s.sc = lerp(s.sc, tgtSc, L);
        card.style.transform = `perspective(900px) rotateY(${s.ry.toFixed(1)}deg) translateX(${s.tx.toFixed(0)}px) scale(${s.sc.toFixed(3)})`;
        if (!card.classList.contains('active') && p > 0.15) card.classList.add('active', 'reveal-element');
        const d = s.ry - tgtRY;
        if (d > DEAD || d < -DEAD) alive = true;
    }

    // ── Flip cards: unfold from bottom edge ──
    const inv065 = 1 / (_wh * 0.65);
    for (let i = 0; i < _flipCards.length; i++) {
        const card = _flipCards[i];
        const rect = flipRects[i];
        if (rect.top > _wh + 300 || rect.bottom < -300) continue;
        const raw = (_wh - rect.top) * inv065;
        const pCl = raw < 0 ? 0 : raw > 1 ? 1 : raw;
        const stagger = (i % 4) * 0.06;
        const prog = (pCl - stagger) / (1 - stagger);
        const progress = prog < 0 ? 0 : prog > 1 ? 1 : prog;
        const inv = 1 - progress;

        const tgtRX = inv * 35;
        const tgtTY = inv * 50;

        const s = S(card, { rx: tgtRX, ty: tgtTY });
        s.rx = lerp(s.rx, tgtRX, L);
        s.ty = lerp(s.ty, tgtTY, L);
        card.style.transform = `perspective(800px) rotateX(${s.rx.toFixed(1)}deg) translateY(${s.ty.toFixed(0)}px)`;
        card.style.transformOrigin = 'center bottom';
        const d = s.rx - tgtRX;
        if (d > DEAD || d < -DEAD) alive = true;
    }

    // ── Section headers: rotate in with text shadow depth ──
    const inv06 = 1 / (_wh * 0.6);
    for (let i = 0; i < _sectionHeaders.length; i++) {
        const { h2, p: pEl } = _sectionHeaders[i];
        const rect = headerRects[i];
        const raw = (_wh - rect.top) * inv06;
        const progress = raw < 0 ? 0 : raw > 1 ? 1 : raw;
        if (h2) {
            const inv = 1 - progress;
            const tgtRX = inv * 20;
            const tgtTY = inv * 25;
            const s = S(h2, { rx: tgtRX, ty: tgtTY });
            s.rx = lerp(s.rx, tgtRX, L);
            s.ty = lerp(s.ty, tgtTY, L);
            h2.style.transform = `perspective(600px) rotateX(${s.rx.toFixed(1)}deg) translateY(${s.ty.toFixed(0)}px)`;
            h2.style.transformOrigin = 'center bottom';
            const d = s.rx - tgtRX;
            if (d > DEAD || d < -DEAD) alive = true;
        }
        if (pEl) {
            const inv = 1 - progress;
            const tgtTY = inv * 18;
            const s = S(pEl, { ty: tgtTY });
            s.ty = lerp(s.ty, tgtTY, L);
            pEl.style.transform = `translateY(${s.ty.toFixed(0)}px)`;
        }
    }

    // ── Stat cards: flip up from flat ──
    const inv05 = 1 / (_wh * 0.5);
    for (let i = 0; i < _statCards.length; i++) {
        const card = _statCards[i];
        const rect = statRects[i];
        if (rect.top > _wh + 100) continue;
        const raw = (_wh - rect.top) * inv05;
        const pCl = raw < 0 ? 0 : raw > 1 ? 1 : raw;
        const stagger = (i % 4) * 0.1;
        const prog = (pCl - stagger) / (1 - stagger);
        const progress = prog < 0 ? 0 : prog > 1 ? 1 : prog;
        const inv = 1 - progress;

        const tgtRX = inv * 45;
        const tgtSc = 0.8 + progress * 0.2;

        const s = S(card, { rx: tgtRX, sc: tgtSc });
        s.rx = lerp(s.rx, tgtRX, L);
        s.sc = lerp(s.sc, tgtSc, L);
        card.style.transform = `perspective(600px) rotateX(${s.rx.toFixed(1)}deg) scale(${s.sc.toFixed(3)})`;
        card.style.transformOrigin = 'center bottom';
        if (pCl > 0.8 && !card.hasAttribute('data-animated')) {
            card.setAttribute('data-animated', 'true');
            const counter = card.querySelector('.stat-number');
            if (counter) animateCounter(counter);
        }
        const d = s.rx - tgtRX;
        if (d > DEAD || d < -DEAD) alive = true;
    }

    // ── Floating elements ──
    for (let i = 0; i < _floatingEls.length; i++) {
        const el = _floatingEls[i];
        const phase = (scrollY * 0.12 + i * 60) % 360;
        const tY = Math.sin(phase * 0.01745) * 10;
        const s = S(el, { ty: 0 });
        s.ty = lerp(s.ty, tY, L);
        el.style.transform = `translate3d(0,${s.ty.toFixed(1)}px,0)`;
        const d = s.ty - tY;
        if (d > DEAD || d < -DEAD) alive = true;
    }

    // ── Hero text — rotate + parallax ──
    if (_heroText && heroTextRect) {
        const prog = (halfH - heroTextRect.top) / halfH;
        const progCl = prog < -1 ? -1 : prog > 1 ? 1 : prog;
        const tgtTY = progCl * 20;
        const tgtRX = progCl * -5;
        const absProg = progCl < 0 ? -progCl : progCl;
        const tgtOp = 1 - absProg * 0.3;
        const s = S(_heroText, { ty: 0, rx: 0, op: 1 });
        s.ty = lerp(s.ty, tgtTY, L);
        s.rx = lerp(s.rx, tgtRX, L);
        s.op = lerp(s.op, tgtOp < 0.2 ? 0.2 : tgtOp, L);
        _heroText.style.transform = `perspective(600px) rotateX(${s.rx.toFixed(1)}deg) translateY(${s.ty.toFixed(1)}px)`;
        const d = s.ty - tgtTY;
        if (d > DEAD || d < -DEAD) alive = true;
    }

    if (alive || vel > 0.2) {
        _running = true;
        requestAnimationFrame(tick);
    } else {
        _running = false;
        _prevTime = 0; // reset so next start doesn't get a huge dt
    }
}

function startTick() { if (_isHomePage && !_running) { _running = true; _prevTime = 0; requestAnimationFrame(tick); } }
window.addEventListener('scroll', startTick, { passive: true });

// Unified rAF loop — drives both Lenis smooth scroll and our 3D animations
function globalRAF(time) {
    if (lenis) lenis.raf(time);        // advance Lenis interpolation
    requestAnimationFrame(globalRAF);
}
requestAnimationFrame(globalRAF);
startTick();

// Lightweight mouse parallax on hero background (cached ref)
if (_heroBackground) {
    let _mx = 0, _my = 0, _cx = 0, _cy = 0, _mRunning = false;
    document.addEventListener('mousemove', (e) => {
        _mx = (e.clientX / window.innerWidth - 0.5) * 10;
        _my = (e.clientY / window.innerHeight - 0.5) * 10;
        if (!_mRunning) { _mRunning = true; requestAnimationFrame(mouseTick); }
    }, { passive: true });
    function mouseTick() {
        _cx = lerp(_cx, _mx, 0.06);
        _cy = lerp(_cy, _my, 0.06);
        _heroBackground.style.transform = `translate3d(${_cx.toFixed(1)}px,${_cy.toFixed(1)}px,0)`;
        if (Math.abs(_cx - _mx) > 0.05 || Math.abs(_cy - _my) > 0.05) {
            requestAnimationFrame(mouseTick);
        } else {
            _mRunning = false;
        }
    }
}

// Images are always visible — native lazy loading handles load timing.
// No opacity hiding or fadeInUp animation needed.

// Mobile Menu Toggle (if needed)
const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
if (mobileMenuToggle) {
    mobileMenuToggle.addEventListener('click', () => {
        const nav = document.querySelector('nav');
        nav.classList.toggle('active');
    });
}

// ============================================================
// Profile Dropdown Toggle
// ============================================================
(function initProfileDropdown() {
    const wrap = document.querySelector('.profile-dropdown-wrap');
    const trigger = document.getElementById('profileTrigger');
    const dropdown = document.getElementById('profileDropdown');
    if (!trigger || !dropdown || !wrap) return;

    trigger.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const isOpen = dropdown.classList.contains('open');
        if (isOpen) {
            dropdown.classList.remove('open');
            wrap.classList.remove('open');
        } else {
            dropdown.classList.add('open');
            wrap.classList.add('open');
        }
    });

    // Close when clicking outside
    document.addEventListener('click', (e) => {
        if (!wrap.contains(e.target)) {
            dropdown.classList.remove('open');
            wrap.classList.remove('open');
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && dropdown.classList.contains('open')) {
            dropdown.classList.remove('open');
            wrap.classList.remove('open');
            trigger.focus();
        }
    });
})();

// ============================================================
// Shopping Cart — Slide-out Drawer
// ============================================================
(function initCart() {
    function readStoredCart() {
        try {
            const raw = localStorage.getItem('ambava_cart');
            if (!raw) return [];
            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed : [];
        } catch (err) {
            localStorage.removeItem('ambava_cart');
            return [];
        }
    }

    let cart = readStoredCart();
    const trimCartValue = (value) => String(value || '').trim();

    function normalizeCartItem(item) {
        if (!item || typeof item !== 'object') return null;
        const name = trimCartValue(item.name);
        const slug = trimCartValue(item.slug);
        const identifier = slug || name;
        if (!identifier) return null;

        const price = Number.parseInt(item.price, 10);
        const quantity = Number.parseInt(item.quantity, 10);

        return {
            name: name || slug,
            slug,
            price: Number.isFinite(price) ? price : 0,
            image: trimCartValue(item.image),
            size: trimCartValue(item.size),
            quantity: Number.isFinite(quantity) && quantity > 0 ? quantity : 1,
        };
    }

    function getCartIdentifier(item) {
        return trimCartValue(item?.slug) || trimCartValue(item?.name);
    }

    function getCartKey(identifier, size) {
        return `${identifier}||${trimCartValue(size)}`;
    }

    cart = Array.isArray(cart) ? cart.map(normalizeCartItem).filter(Boolean) : [];

    // DOM references
    const toggleBtn = document.getElementById('cartToggle');
    const overlay = document.getElementById('cartOverlay');
    const closeBtn = document.getElementById('cartClose');
    const backdrop = overlay?.querySelector('.cart-overlay-backdrop');
    const body = document.getElementById('cartBody');
    const footer = document.getElementById('cartFooter');
    const badge = document.getElementById('cartBadge');
    const subtotalEl = document.getElementById('cartSubtotal');

    if (!overlay || !toggleBtn || !closeBtn || !backdrop || !body || !footer || !badge || !subtotalEl) return;

    // ── Open / Close ──
    function openCart(e) {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        if (typeof lenis !== 'undefined' && lenis) lenis.stop();
        renderCart();
    }

    function closeCart() {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
        if (typeof lenis !== 'undefined' && lenis) lenis.start();
        // Reset item animations for next open
        body.querySelectorAll('.cart-item').forEach(el => {
            el.style.animation = 'none';
        });
    }

    toggleBtn.addEventListener('click', openCart);
    closeBtn.addEventListener('click', closeCart);
    backdrop.addEventListener('click', closeCart);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay.classList.contains('active')) closeCart();
    });

    // ── Save to localStorage ──
    function saveCart() {
        localStorage.setItem('ambava_cart', JSON.stringify(cart));
    }

    // ── Badge update ──
    function updateBadge() {
        const total = cart.reduce((s, i) => s + i.quantity, 0);
        badge.textContent = total;
        if (total > 0) {
            badge.classList.add('visible');
        } else {
            badge.classList.remove('visible');
        }
    }

    function bumpBadge() {
        badge.classList.remove('bump');
        void badge.offsetWidth; // reflow to restart animation
        badge.classList.add('bump');
    }

    // ── Toast notification ──
    function showToast(message) {
        // Remove previous toast
        document.querySelectorAll('.cart-toast').forEach(t => {
            t.classList.remove('show');
            setTimeout(() => t.remove(), 400);
        });

        const toast = document.createElement('div');
        toast.className = 'cart-toast';
        toast.innerHTML = `<i class="fas fa-check-circle"></i> ${escapeHtml(message)}`;
        document.body.appendChild(toast);

        requestAnimationFrame(() => {
            requestAnimationFrame(() => toast.classList.add('show'));
        });

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 550);
        }, 2500);
    }

    // ── Add to cart (exposed globally for shop page) ──
    window.addToCart = addToCart;
    function addToCart(name, price, image, size, slug) {
        const normalizedName = trimCartValue(name);
        const normalizedSlug = trimCartValue(slug);
        const normalizedSize = trimCartValue(size);
        const identifier = normalizedSlug || normalizedName;
        const parsedPrice = Number.parseInt(price, 10);

        if (!identifier || !Number.isFinite(parsedPrice)) return;

        const existing = cart.find(i => getCartIdentifier(i) === identifier && (i.size || '') === normalizedSize);
        if (existing) {
            existing.quantity += 1;
        } else {
            cart.push({
                name: normalizedName || normalizedSlug,
                slug: normalizedSlug,
                price: parsedPrice,
                image: trimCartValue(image),
                size: normalizedSize,
                quantity: 1,
            });
        }
        saveCart();
        updateBadge();
        bumpBadge();
        showToast(`${normalizedName || 'Item'} added to cart!`);
        // If cart is open, re-render
        if (overlay.classList.contains('active')) renderCart();
    }

    // ── Remove from cart ──
    function removeItem(identifier, size, el) {
        size = trimCartValue(size);
        if (el) {
            el.classList.add('removing');
            el.style.maxHeight = el.scrollHeight + 'px';
            requestAnimationFrame(() => {
                el.style.maxHeight = '0';
            });
            setTimeout(() => {
                cart = cart.filter(i => !(getCartIdentifier(i) === identifier && (i.size || '') === size));
                saveCart();
                updateBadge();
                renderCart();
            }, 400);
        } else {
            cart = cart.filter(i => !(getCartIdentifier(i) === identifier && (i.size || '') === size));
            saveCart();
            updateBadge();
            renderCart();
        }
    }

    // ── Update quantity ──
    function updateQty(identifier, size, delta) {
        size = trimCartValue(size);
        const item = cart.find(i => getCartIdentifier(i) === identifier && (i.size || '') === size);
        if (!item) return;
        item.quantity += delta;
        if (item.quantity <= 0) {
            const key = getCartKey(identifier, size);
            const el = body.querySelector(`[data-cart-key="${CSS.escape(key)}"]`);
            removeItem(identifier, size, el);
            return;
        }
        saveCart();
        updateBadge();

        // Animate the quantity display instead of full re-render
        const key = getCartKey(identifier, size);
        const el = body.querySelector(`[data-cart-key="${CSS.escape(key)}"]`);
        if (el) {
            const qtyEl = el.querySelector('.cart-qty-display');
            const priceEl = el.querySelector('.cart-item-price');
            if (qtyEl) {
                qtyEl.textContent = item.quantity;
                qtyEl.classList.remove('pop');
                void qtyEl.offsetWidth;
                qtyEl.classList.add('pop');
            }
            if (priceEl) {
                priceEl.textContent = `₹${(item.price * item.quantity).toLocaleString('en-IN')}`;
                priceEl.classList.remove('updated');
                void priceEl.offsetWidth;
                priceEl.classList.add('updated');
            }
            // Update subtotal
            const total = cart.reduce((s, i) => s + i.price * i.quantity, 0);
            subtotalEl.textContent = `₹${total.toLocaleString('en-IN')}`;
        } else {
            renderCart();
        }
    }

    // ── Render cart items ──
    function renderCart() {
        if (cart.length === 0) {
            body.innerHTML = `
                <div class="cart-empty-state">
                    <i class="fas fa-shopping-bag"></i>
                    <p>Your bag is empty</p>
                    <span>Discover something extraordinary</span>
                </div>`;
            footer.style.display = 'none';
            return;
        }

        footer.style.display = '';
        const total = cart.reduce((s, i) => s + i.price * i.quantity, 0);
        subtotalEl.textContent = `₹${total.toLocaleString('en-IN')}`;

        body.innerHTML = cart.map((item, idx) => {
            const imgHTML = item.image
                ? `<img src="${item.image}" alt="${item.name}" class="cart-item-img">`
                : `<div class="cart-item-img-placeholder"><i class="fas fa-image"></i></div>`;
            const sizeHTML = item.size ? `<span class="cart-item-size">Size: ${item.size}</span>` : '';
            const identifier = getCartIdentifier(item);
            const cartKey = getCartKey(identifier, item.size || '');
            return `
                <div class="cart-item" style="animation-delay:${idx * 0.09}s" data-name="${item.name}" data-slug="${item.slug || ''}" data-size="${item.size || ''}" data-cart-key="${cartKey}">
                    ${imgHTML}
                    <div class="cart-item-details">
                        <p class="cart-item-name">${item.name}</p>
                        ${sizeHTML}
                        <p class="cart-item-price">₹${(item.price * item.quantity).toLocaleString('en-IN')}</p>
                        <div class="cart-item-controls">
                            <button class="cart-qty-btn" data-action="minus"><i class="fas fa-minus"></i></button>
                            <span class="cart-qty-display">${item.quantity}</span>
                            <button class="cart-qty-btn" data-action="plus"><i class="fas fa-plus"></i></button>
                        </div>
                    </div>
                    <button class="cart-item-remove" title="Remove"><i class="fas fa-trash-alt"></i></button>
                </div>`;
        }).join('');

        // Attach event listeners
        body.querySelectorAll('.cart-item').forEach(el => {
            const identifier = el.dataset.slug || el.dataset.name;
            const size = el.dataset.size || '';
            el.querySelector('[data-action="minus"]').addEventListener('click', () => updateQty(identifier, size, -1));
            el.querySelector('[data-action="plus"]').addEventListener('click', () => updateQty(identifier, size, 1));
            el.querySelector('.cart-item-remove').addEventListener('click', () => removeItem(identifier, size, el));
        });
    }

    // ── Wire up all add-to-cart buttons ──
    function bindAddToCartButtons(scope) {
        scope.querySelectorAll('.add-to-cart').forEach(btn => {
            if (btn.dataset.cartBound === 'true') return;
            btn.dataset.cartBound = 'true';
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                const name = this.dataset.product;
                const price = this.dataset.price;
                const size = (this.dataset.size || '').trim();
                const slug = (this.dataset.slug || '').trim();
                const requiresSize = (this.dataset.requiresSize || '').toLowerCase() === 'true';
                const productUrl = this.dataset.productUrl || '';
                // Try to grab the image from the sibling or parent
                let image = this.dataset.image || '';
                if (!image) {
                    const card = this.closest('.showcase-item, .collection-card, .featured-card, .product-card');
                    if (card) {
                        const img = card.querySelector('img');
                        if (img) image = img.src;
                    }
                }
                if (requiresSize && !size) {
                    if (productUrl) {
                        window.location.href = `${productUrl}#sizeOptions`;
                    } else {
                        showToast('Please select a size on the product page.');
                    }
                    return;
                }
                addToCart(name, price, image, size, slug);
            });
        });
    }

    window.bindAddToCartButtons = bindAddToCartButtons;

    bindAddToCartButtons(document);

    // ── Initialize on load ──
    updateBadge();
    // Migrate old cart data
    const oldCart = localStorage.getItem('cart');
    if (oldCart && cart.length === 0) {
        try {
            cart = JSON.parse(oldCart).map(normalizeCartItem).filter(Boolean);
            saveCart();
            localStorage.removeItem('cart');
            updateBadge();
        } catch (e) {
            localStorage.removeItem('cart');
        }
    }
})();


