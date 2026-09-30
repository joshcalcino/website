(() => {
  "use strict";

  function initializeSite() {
    const menuToggle = document.querySelector("[data-menu-toggle]");
    const navigation = document.getElementById("site-nav");

    if (menuToggle && navigation) {
      const desktop = window.matchMedia("(min-width: 760px)");
      const setMenuOpen = (open) => {
        menuToggle.setAttribute("aria-expanded", String(open));
        navigation.toggleAttribute("data-open", open);
      };

      setMenuOpen(false);
      menuToggle.addEventListener("click", () => {
        setMenuOpen(menuToggle.getAttribute("aria-expanded") !== "true");
      });
      navigation.addEventListener("click", (event) => {
        if (event.target.closest("a")) setMenuOpen(false);
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && menuToggle.getAttribute("aria-expanded") === "true") {
          setMenuOpen(false);
          menuToggle.focus();
        }
      });
      desktop.addEventListener("change", (event) => {
        if (event.matches) setMenuOpen(false);
      });
    }

    const galleryItems = Array.from(document.querySelectorAll("a[data-gallery-item]"));
    const lightbox = document.querySelector("dialog[data-lightbox]");

    // The original image links remain usable when native dialogs are unavailable.
    if (!galleryItems.length || !lightbox || typeof lightbox.showModal !== "function") return;

    const image = lightbox.querySelector("[data-lightbox-image]");
    const caption = lightbox.querySelector("[data-lightbox-caption]");
    const count = lightbox.querySelector("[data-lightbox-count]");
    const previous = lightbox.querySelector("[data-lightbox-prev]");
    const next = lightbox.querySelector("[data-lightbox-next]");
    const closeButtons = lightbox.querySelectorAll("[data-lightbox-close]");

    if (!image || !caption || !count || !previous || !next || !closeButtons.length) return;

    let currentIndex = 0;
    let openingLink = null;

    function showImage(index) {
      currentIndex = (index + galleryItems.length) % galleryItems.length;
      const item = galleryItems[currentIndex];
      const thumbnail = item.querySelector("img");
      image.alt = item.dataset.alt ?? thumbnail?.alt ?? "";
      image.src = item.href;
      caption.textContent = item.dataset.caption ?? "";
      caption.hidden = caption.textContent.trim() === "";
      count.textContent = `${currentIndex + 1} of ${galleryItems.length}`;
      previous.disabled = galleryItems.length < 2;
      next.disabled = galleryItems.length < 2;
    }

    galleryItems.forEach((item, index) => {
      item.addEventListener("click", (event) => {
        if (
          event.defaultPrevented || event.button !== 0 ||
          event.metaKey || event.ctrlKey || event.shiftKey || event.altKey ||
          item.hasAttribute("download") ||
          (item.target && item.target.toLowerCase() !== "_self")
        ) return;

        showImage(index);
        openingLink = item;
        lightbox.showModal();
        document.body.classList.add("lightbox-open");
        event.preventDefault();
      });
    });

    previous.addEventListener("click", () => showImage(currentIndex - 1));
    next.addEventListener("click", () => showImage(currentIndex + 1));
    closeButtons.forEach((button) => {
      button.addEventListener("click", () => lightbox.close());
    });

    lightbox.addEventListener("keydown", (event) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        showImage(currentIndex + (event.key === "ArrowLeft" ? -1 : 1));
      }
      // Escape retains the native dialog's dismissal behavior.
    });

    lightbox.addEventListener("click", (event) => {
      if (event.target !== lightbox) return;
      const bounds = lightbox.getBoundingClientRect();
      const outside = event.clientX < bounds.left || event.clientX > bounds.right ||
        event.clientY < bounds.top || event.clientY > bounds.bottom;
      if (outside) lightbox.close();
    });

    lightbox.addEventListener("close", () => {
      document.body.classList.remove("lightbox-open");
      if (openingLink?.isConnected) openingLink.focus({ preventScroll: true });
      openingLink = null;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeSite, { once: true });
  } else {
    initializeSite();
  }
})();
