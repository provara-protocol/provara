(function () {
  'use strict';

  // ───────────────────────────────────────────────────────────
  // 1. Mobile Drawer Toggle
  // ───────────────────────────────────────────────────────────
  var hamburger = document.querySelector('.nav-hamburger');
  var drawer = document.querySelector('.nav-drawer');
  var backdrop = document.querySelector('.nav-drawer-backdrop');
  var panel = document.querySelector('.nav-drawer-panel');

  function openDrawer() {
    if (!drawer) return;
    drawer.classList.add('open');
    drawer.setAttribute('aria-hidden', 'false');
    hamburger.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
    hamburger.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  if (hamburger) {
    hamburger.addEventListener('click', function () {
      var isOpen = drawer.classList.contains('open');
      if (isOpen) {
        closeDrawer();
      } else {
        openDrawer();
      }
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', closeDrawer);
  }

  if (panel) {
    var drawerLinks = panel.querySelectorAll('a');
    drawerLinks.forEach(function (link) {
      link.addEventListener('click', closeDrawer);
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && drawer && drawer.classList.contains('open')) {
      closeDrawer();
    }
  });

  window.addEventListener('resize', function () {
    if (window.innerWidth >= 768 && drawer && drawer.classList.contains('open')) {
      closeDrawer();
    }
  });

  // ───────────────────────────────────────────────────────────
  // 2. Smooth Scroll with Nav Offset
  // ───────────────────────────────────────────────────────────
  var nav = document.querySelector('.nav');

  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      var href = link.getAttribute('href');
      if (href === '#') return;

      var target = document.querySelector(href);
      if (!target) return;

      e.preventDefault();

      var navHeight = nav ? nav.offsetHeight : 0;
      var top = target.getBoundingClientRect().top + window.scrollY - navHeight - 20;

      window.scrollTo({
        top: top,
        behavior: 'smooth'
      });
    });
  });

  // ───────────────────────────────────────────────────────────
  // 3. Fade-Up Scroll Animations
  // ───────────────────────────────────────────────────────────
  var fadeObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        fadeObserver.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -40px 0px'
  });

  document.querySelectorAll('.fade-up').forEach(function (el) {
    fadeObserver.observe(el);
  });

  // ───────────────────────────────────────────────────────────
  // 4. API Code Tabs
  // ───────────────────────────────────────────────────────────
  var tabs = document.querySelectorAll('.api-tab');
  var codeBlocks = document.querySelectorAll('.api-code-block');

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      tabs.forEach(function (t) {
        t.classList.remove('active');
      });
      codeBlocks.forEach(function (block) {
        block.classList.remove('active');
      });

      tab.classList.add('active');

      var tabValue = tab.getAttribute('data-tab');
      var targetBlock = document.getElementById('code-' + tabValue);
      if (targetBlock) {
        targetBlock.classList.add('active');
      }
    });
  });

})();
