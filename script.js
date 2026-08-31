/* Interaktion: mobilmeny, FAQ-dragspel och storlekstabbar på produktsidorna. */

document.addEventListener('DOMContentLoaded', () => {
  const header = document.querySelector('.site-header');
  const toggle = header && header.querySelector('.nav-toggle');

  if (header && toggle) {
    toggle.addEventListener('click', () => {
      const open = header.dataset.open === 'true';
      header.dataset.open = String(!open);
      toggle.setAttribute('aria-expanded', String(!open));
    });
  }

  document.querySelectorAll('.faq__item').forEach((item) => {
    const button = item.querySelector('.faq__q');
    if (!button) return;
    button.addEventListener('click', () => {
      const open = item.dataset.open === 'true';
      item.parentElement.querySelectorAll('.faq__item').forEach((other) => {
        other.dataset.open = 'false';
        const b = other.querySelector('.faq__q');
        if (b) b.setAttribute('aria-expanded', 'false');
      });
      item.dataset.open = String(!open);
      button.setAttribute('aria-expanded', String(!open));
    });
  });

  // Produktsektionen på startsidan: listan till vänster byter vilken produkt
  // som visas till höger. Utan JS visas den första produkten.
  const showcase = document.querySelector('[data-showcase]');
  if (showcase) {
    const states = showcase.querySelectorAll('[data-state]');
    const items = showcase.querySelectorAll('[data-goto]');

    const setIndex = (index) => {
      states.forEach((el) => el.classList.toggle('is-active', Number(el.dataset.state) === index));
      items.forEach((el) => {
        const on = Number(el.dataset.goto) === index;
        el.classList.toggle('is-active', on);
        if (on) el.setAttribute('aria-current', 'true');
        else el.removeAttribute('aria-current');
      });
    };

    items.forEach((el) => {
      el.addEventListener('click', () => setIndex(Number(el.dataset.goto)));
    });
    setIndex(0);
  }

  // Bildsnurra: viewporten scrollar med snap, så knapparna behöver bara
  // flytta scrollpositionen. Utan JS fungerar svep och tangentbord ändå.
  // Parallax på de helbreda bildbanden, som på nasps.se: bilden förskjuts i
  // halva scrollhastigheten. Bilden är 240 % av ramens höjd och rörelsen
  // begränsas till 70 % åt vardera hållet, vilket ger 0,5 px per scrollad
  // pixel och håller ramen helt täckt hela vägen.
  const bands = document.querySelectorAll('[data-parallax]');
  const stillhet = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (bands.length && !stillhet.matches) {
    let queued = false;

    const paint = () => {
      queued = false;
      const vh = window.innerHeight;
      bands.forEach((frame) => {
        const image = frame.querySelector('img');
        if (!image) return;
        const box = frame.getBoundingClientRect();
        if (box.bottom < 0 || box.top > vh) return;
        // -1 när ramen precis kommer in nedifrån, +1 när den lämnat uppåt
        const progress = ((vh - box.top) / (vh + box.height)) * 2 - 1;
        const offset = Math.max(-1, Math.min(1, progress)) * box.height * 0.7;
        image.style.transform = `translate3d(0, ${offset.toFixed(1)}px, 0)`;
      });
    };

    const schedule = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(paint);
    };

    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    paint();
  }

  document.querySelectorAll('[data-carousel]').forEach((carousel) => {
    const viewport = carousel.querySelector('.carousel__viewport');
    const slides = carousel.querySelectorAll('.carousel__slide');
    const dots = carousel.querySelectorAll('[data-goto]');
    const caption = carousel.querySelector('[data-caption]');
    const prev = carousel.querySelector('[data-prev]');
    const next = carousel.querySelector('[data-next]');
    if (!viewport || slides.length < 2) return;

    const current = () => Math.round(viewport.scrollLeft / viewport.clientWidth);

    const sync = () => {
      const index = Math.min(Math.max(current(), 0), slides.length - 1);
      dots.forEach((dot, i) => {
        dot.classList.toggle('is-active', i === index);
        if (i === index) dot.setAttribute('aria-current', 'true');
        else dot.removeAttribute('aria-current');
      });
      if (caption) {
        const img = slides[index].querySelector('img');
        if (img) caption.textContent = img.alt;
      }
      if (prev) prev.disabled = index === 0;
      if (next) next.disabled = index === slides.length - 1;
    };

    const goTo = (index) => {
      viewport.scrollTo({ left: index * viewport.clientWidth, behavior: 'smooth' });
    };

    if (prev) prev.addEventListener('click', () => goTo(current() - 1));
    if (next) next.addEventListener('click', () => goTo(current() + 1));
    dots.forEach((dot) => dot.addEventListener('click', () => goTo(Number(dot.dataset.goto))));

    let ticking;
    viewport.addEventListener('scroll', () => {
      clearTimeout(ticking);
      ticking = setTimeout(sync, 60);
    }, { passive: true });
    window.addEventListener('resize', sync);
    carousel.dataset.enhanced = 'true';
    sync();
  });

  document.querySelectorAll('.video[data-video]').forEach((video) => {
    const play = video.querySelector('.video__play');
    if (!play) return;
    play.addEventListener('click', () => {
      const frame = document.createElement('iframe');
      frame.src = `https://www.youtube.com/embed/${video.dataset.video}?autoplay=1&rel=0&modestbranding=1&playsinline=1`;
      frame.title = 'YouTube video';
      frame.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; fullscreen';
      frame.allowFullscreen = true;
      video.replaceChildren(frame);
    });
  });

  // Produktsidornas storlekstabbar. Exporten innehåller bara data för den
  // första storleken; övriga visar ett tomt läge, precis som i originalet.
  document.querySelectorAll('.tdt-root, .ct-root, .cv-root, .ss-root, .sa-root').forEach((root) => {
    const tabs = root.querySelectorAll('.tdt-tab, .ct-tab, .cv-tab, .sa-tab, .ss-tab');
    if (!tabs.length) return;
    const sections = root.querySelectorAll('.tdt-section, .ct-section, .cv-section, .sa-section, .ss-section');
    const empty = document.createElement('div');
    empty.className = 'tdt-empty';
    empty.hidden = true;
    empty.textContent = 'No data available for this size.';
    root.appendChild(empty);

    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => {
        tabs.forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');
        const first = index === 0;
        sections.forEach((s) => { s.hidden = !first; });
        empty.hidden = first;
      });
    });
  });
});
