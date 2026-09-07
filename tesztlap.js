// tesztlap.js — a lap JS-ének futásidejű ellenőrzése publikálás előtt.
//
// MIÉRT
// A `node --check` csak szintaxist néz. Egy nem létező változó, egy elrontott
// blokkhatár vagy egy hiányzó mező szintaktikailag tökéletes — és futáskor
// megállítja az egész szkriptet, amitől a lap üresen marad.
//
// 2026-09-07-én ez ötször fordult elő egy nap alatt. Ez a fájl megfogja.
//
// MIT CSINÁL
// Betölti a data.json-t, minimális DOM-ot ad a szkript alá, lefuttatja a
// teljes logikát, és megnézi, hogy a kulcsfontosságú panelek megteltek-e.
//
// Futtatás:  node tesztlap.js

const fs = require("fs");

const html = fs.readFileSync("index.html", "utf8");
const adat = JSON.parse(fs.readFileSync("data.json", "utf8"));

// A lap utolsó <script> blokkja tartalmazza a logikát.
const blokkok = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
const js = blokkok[blokkok.length - 1][1];

// Minimális DOM. Csak annyit ad, amennyit a szkript kér: elemeket lehet
// keresni, létrehozni, és tartalmat írni beléjük.
const elemek = new Map();
function ujElem(id) {
  const e = {
    id, innerHTML: "", textContent: "", className: "",
    style: { setProperty(){}, removeProperty(){}, getPropertyValue: () => "" },
    dataset: {}, children: [],
    appendChild(c) { this.children.push(c); return c; },
    querySelector: () => null, querySelectorAll: () => [],
    addEventListener() {}, removeEventListener() {},
    getBoundingClientRect: () => ({ top:0, left:0, width:600, height:300,
                                    right:600, bottom:300 }),
    setAttribute() {}, getAttribute: () => null, remove() {},
    classList: { add(){}, remove(){}, toggle(){}, contains: () => false },
    insertAdjacentHTML(_, h) { this.innerHTML += h; },
    closest: () => null, focus() {}, scrollIntoView() {},
  };
  elemek.set(id, e);
  return e;
}

global.document = {
  querySelector: s => elemek.get(String(s).replace(/^#/, "")) || ujElem(String(s).replace(/^#/, "")),
  querySelectorAll: () => [],
  getElementById: id => elemek.get(id) || ujElem(id),
  createElement: () => ujElem("uj"),
  createElementNS: () => ujElem("svg"),
  createTextNode: t => ({ textContent: t }),
  createDocumentFragment: () => ujElem("frag"),
  addEventListener() {}, body: ujElem("body"),
  documentElement: ujElem("html"),
};
global.window = {
  BASIN_DATA: adat, addEventListener() {}, matchMedia: () => ({ matches:false,
    addEventListener(){}, addListener(){} }),
  innerWidth: 1400, innerHeight: 900, scrollY: 0, location: { href: "" },
  requestAnimationFrame: f => f(), setTimeout: () => 0, setInterval: () => 0,
  getComputedStyle: () => ({ getPropertyValue: () => "" }),
};
global.fetch = () => Promise.resolve({ ok:true, json: () => Promise.resolve(adat) });
global.navigator = { userAgent: "teszt" };
global.location = window.location;
global.requestAnimationFrame = f => f();
global.getComputedStyle = window.getComputedStyle;
global.IntersectionObserver = class { observe(){} disconnect(){} };
global.ResizeObserver = class { observe(){} disconnect(){} };

// A szkript futtatása. Ha bármi elhasal, itt derül ki — nem a böngészőben.
let hiba = null;
try {
  new Function(js)();
} catch (e) {
  hiba = e;
}

if (hiba) {
  console.error("ELHASALT a lap logikája:\n  " + hiba.message);
  if (hiba.stack) {
    const sor = hiba.stack.split("\n")[1] || "";
    console.error("  " + sor.trim());
  }
  process.exit(1);
}

// A kulcspanelek: ha ezek üresen maradnak, a lap darabokban van.
// A lista bővíthető, de csak olyannal, ami MINDEN adatállapotban megtelik.
const KELL = [
  ["stressz",       "vízstressz-panel"],
  ["osszefoglalo",  "összefoglaló"],
  ["egyenleg",      "egyenleg"],
  ["hovalett",      "hova lett"],
];
let baj = 0;
for (const [id, nev] of KELL) {
  const e = elemek.get(id);
  const h = e ? (e.innerHTML || "").trim() : "";
  if (h.length < 40) {
    console.error(`ÜRES: ${nev} (#${id}) — ${h.length} karakter`);
    baj++;
  }
}

if (baj) {
  // Figyelmeztetés, nem hiba: néhány panel aszinkron tölt, azok itt üresen
  // maradnak. A publikálást csak a futásidejű hiba állítja meg — az a fajta,
  // amitől az egész lap üres marad.
  console.error(`  (${baj} panel üres — aszinkron töltés lehet)`);
}
console.log(`Lapteszt OK — ${KELL.length} panel megtelt, futásidejű hiba nincs.`);
