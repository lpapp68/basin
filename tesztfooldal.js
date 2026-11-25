// tesztfooldal.js — a főoldal (fooldal.html) futásidejű ellenőrzése publikálás előtt (2026-11-25).
//
// Ugyanaz az elv, mint a tesztlap.js-ben: betölti a data.json-t, minimális DOM-ot ad a szkript alá,
// lefuttatja a logikát, és megnézi, hogy a főoldal blokkjai megteltek-e.
//
// Két szabály a laikus olvasóért:
//   • a négy kártyán összesen legfeljebb NAGY_MAX nagy szám áll;
//   • a főoldalon a szakmai rövidítések (LKV, m³/s, EOF, …) nem jelennek meg.
//
// Futtatás:  node tesztfooldal.js
const fs = require("fs");

const NAGY_MAX = 8;
const TILTOTT = [/\bLKV\b/, /\bLNV\b/, /m³\/s/, /\bEOF\b/, /mascon/i, /maradéktag/i, /percentilis/i, /\bQ50\b/];

const html = fs.readFileSync("fooldal.html", "utf8");
const adat = JSON.parse(fs.readFileSync(process.argv[2] || "data.json", "utf8"));
const blokkok = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
const js = blokkok[blokkok.length - 1][1];

const elemek = new Map();
const elem = id => {
  if (!elemek.has(id)) elemek.set(id, { id, innerHTML: "", textContent: "", value: "", placeholder: "",
    addEventListener() {}, setAttribute() {} });
  return elemek.get(id);
};
global.window = { BASIN_DATA: adat };
global.document = { querySelector: s => elem(String(s).replace(/^#/, "")), querySelectorAll: () => [] };
global.location = { hash: "" };

let hiba = 0;
try { new Function(js)(); } catch (e) { console.error("FUTÁSIDEJŰ HIBA:", e.stack || e); process.exit(1); }

const kell = { ma: 40, kartyak: 200, helyek: 20, terkep: 2000 };
for (const [id, min] of Object.entries(kell)) {
  const n = elem(id).innerHTML.length;
  if (n < min) { console.error(`ÜRES: #${id} — ${n} karakter`); hiba++; }
}
const kartyaHtml = elem("kartyak").innerHTML;
const nagy = (kartyaHtml.match(/class="nagy"/g) || []).length;
if (nagy > NAGY_MAX) { console.error(`TÚL SOK NAGY SZÁM: ${nagy} > ${NAGY_MAX}`); hiba++; }
const latszo = (elem("ma").innerHTML + kartyaHtml).replace(/<[^>]+>/g, " ");
for (const t of TILTOTT) if (t.test(latszo)) { console.error(`SZAKSZÓ A FŐOLDALON: ${t}`); hiba++; }
const F = window.BASIN_FOOLDAL || {};
if (hiba) process.exit(1);
console.log(`Főoldal-teszt OK — kiemelt: „${F.ma && F.ma.cim}”, ${F.kartyak} kártya, ${nagy} nagy szám, ${F.helyek} hely a keresőben.`);
