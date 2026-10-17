(() => {
  const store = (window.__invCollect = window.__invCollect || { byKey: {} });
  function parseRow(parent) {
    const block = parent.innerText || "";
    if (!/Active/i.test(block)) return null;
    const links = Array.from(parent.querySelectorAll("a")).map(x => (x.textContent || "").trim()).filter(Boolean);
    const title = links.find(t => t.startsWith("Compatible for") || /display\+touch/i.test(t) || /display \+ touch/i.test(t) || /Compatible LCD/i.test(t) || t.startsWith("for ")) || "";
    if (!title) return null;
    const asinM = block.match(/\b(B0[A-Z0-9]{8})\b/i) || block.match(/\b(B[0-9A-Z]{9})\b/i);
    const asin = asinM ? asinM[1].toUpperCase() : "";
    let sku = "";
    for (const L of links) {
      if (L !== title && L.length >= 2 && L.length < 48 && !L.includes(" ") && !/^B0/i.test(L) && !["Set","Edit","Close"].includes(L) && !/Calculate|Migrated|View|Learn|Copy|Delete|Manage/i.test(L)) { sku = L; break; }
    }
    let qty = "", price = "";
    for (const inp of parent.querySelectorAll("input")) {
      const v = (inp.value || "").trim();
      if (!v) continue;
      if (/[\d,]+\.\d{2}/.test(v) || (/,/.test(v) && /\d/.test(v) && /\./.test(v))) { if (!price) price = v.replace(/,/g, ""); }
      else if (/^\d+$/.test(v) && Number(v) < 100000 && qty === "") qty = v;
    }
    const key = sku || asin || title;
    store.byKey[key] = { title, sku, asin, qty, price, status: "Active" };
    return key;
  }
  const rowEls = Array.from(document.querySelectorAll('[role="row"], tr, [class*="mt-row"]'));
  let parsed = 0;
  for (const el of rowEls) { if (parseRow(el)) parsed++; }
  if (parsed < 5) {
    for (const a of document.querySelectorAll("a")) {
      const t = (a.textContent || "").trim();
      if (!(t.startsWith("Compatible for") || t.startsWith("for "))) continue;
      let n = a;
      for (let i = 0; i < 10 && n; i++) {
        n = n.parentElement;
        if (!n) break;
        const txt = n.innerText || "";
        if (txt.includes("Active") && txt.length > 60 && txt.length < 5000) { if (parseRow(n)) parsed++; break; }
      }
    }
  }
  const candidates = [document.querySelector('[class*="scroll"]'), document.querySelector('[class*="virtual"]'), document.scrollingElement, document.documentElement, document.body].filter(Boolean);
  let scrolled = false;
  for (const el of candidates) {
    if (el.scrollHeight > el.clientHeight + 50) {
      el.scrollTop = Math.min(el.scrollTop + Math.max(el.clientHeight * 0.85, 600), el.scrollHeight);
      scrolled = true; break;
    }
  }
  if (!scrolled) window.scrollBy(0, 900);
  return { collected: Object.keys(store.byKey).length, parsedThisPass: parsed };
})()
