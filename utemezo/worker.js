/**
 * basin-utemezo — Cloudflare Worker, ami félóránként elindítja a GitHub Actions
 * „basin" munkafolyamatát, és közvetíti a paksi üzemállapotot a botnak.
 *
 * MIÉRT KELL
 * A GitHub saját `cron` ütemezése kérés, nem garancia: torlódáskor csúszik
 * vagy kimarad. A naplónk szerint az óránkénti kérésből a gyakorlatban
 * 53–130 perc lett, 2026 októberében pedig 5–7 óra. A `workflow_dispatch`
 * végpont viszont azonnal indít.
 *
 * MIÉRT DURABLE OBJECT, ÉS NEM CRON (2026-10-31)
 * A fiók ingyenes Workers-csomagjában az 5 cron-hely foglalt (az equora-muhely
 * maga hármat használ). Az erdőfigyelő NÉBIH-ütemezőjének mintájára egyetlen
 * Durable Object riasztása (alarm) lépteti a láncot: minden óra 4. és 34.
 * percében (UTC) indít, és ugyanabban a lépésben beállítja a következőt. A lánc
 * első szemét bármelyik kérés berakja (/allapot vagy /inditas); utána magától fut.
 *
 * MIÉRT FÉLÓRÁNKÉNT (2026-11-01)
 * A repó nyilvános, nyilvános repón a GitHub Actions szabványos futtatói
 * díjmentesek. (A 2026-10-31-i óránkénti döntés a repó téves, privátként vett
 * állapotán alapult.)
 *
 * /paks — A PAKSI ÜZEMÁLLAPOT KÖZVETÍTÉSE (2026-11-01)
 * A holadelej.hu Cloudflare-védelme a GitHub-futtatók IP-címeit tartósan
 * elutasítja (403), a Worker kéréseit pedig időnként. Ezért minden riasztáskor,
 * MÉG a bot indítása előtt lekérjük a paksi mezőket, és az utolsó sikeres
 * értéket eltároljuk. A /paks a 15 percnél frissebb tárolt értéket adja; ha az
 * régebbi, újrapróbál, és ha ez is elakad, a tárolt értéket adja a korával
 * (kor_perc) együtt, legfeljebb 6 óráig. Forrás: holadelej.hu /api/data, CC BY 4.0.
 *
 * TITKOK
 *   GITHUB_TOKEN — finomhangolt PAT, csak erre a repóra, Actions: read+write
 * A tokent a wrangler secret kezeli; a kódban sosem szerepel.
 */

import { DurableObject } from "cloudflare:workers";

const TULAJ = "lpapp68";
const REPO = "basin";
const MUNKAFOLYAMAT = "basin.yml";
const PERCEK = [4, 34];
// A kézi indítás nyilvános. Hogy egy ismételt hívás ne pörgesse a futásokat,
// tíz percen belül legfeljebb egy kézi indítás megy ki.
const KEZI_SZUNET = 10 * 60 * 1000;
const DELEJ = "https://holadelej.hu/api/data";
const PAKS_FRISS = 15 * 60 * 1000;
const PAKS_MAX_KOR = 6 * 60 * 60 * 1000;
const FORRAS = "holadelej.hu /api/data (CC BY 4.0), a basin-utemezo közvetítésével";

async function inditas(env) {
  const valasz = await fetch(
    `https://api.github.com/repos/${TULAJ}/${REPO}/actions/workflows/${MUNKAFOLYAMAT}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        // A GitHub kötelezővé teszi; enélkül 403-at ad.
        "User-Agent": "basin-utemezo",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );
  // 204 = elfogadva, tartalom nélkül. Minden más hiba.
  if (valasz.status !== 204) {
    const szoveg = await valasz.text();
    throw new Error(`GitHub ${valasz.status}: ${szoveg.slice(0, 300)}`);
  }
  return "elindítva";
}

// A paksi mezők a holadelej.hu-ról; két próbálkozás, köztük rövid szünet.
async function paksLekeres() {
  let utolso = "";
  for (let i = 0; i < 2; i++) {
    try {
      const v = await fetch(DELEJ, {
        headers: {
          "User-Agent": "basin-utemezo (+https://basin.equora.institute) — paksi üzemállapot",
          Accept: "application/json",
        },
      });
      if (v.status === 200) {
        const d = await v.json();
        return {
          paksUnits: d.paksUnits ?? null,
          plants: { paks: d.plants ? d.plants.paks ?? null : null },
          generatedAt: d.generatedAt ?? null,
        };
      }
      utolso = `holadelej.hu ${v.status}`;
    } catch (e) {
      utolso = String((e && e.message) || e);
    }
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw new Error(utolso);
}

// A következő indítási perc (UTC): a PERCEK közül az első, ami még előttünk van.
function kovetkezo(most = Date.now()) {
  for (let ora = 0; ora < 2; ora++) {
    for (const p of PERCEK) {
      const d = new Date(most);
      d.setUTCHours(d.getUTCHours() + ora, p, 0, 0);
      if (d.getTime() > most) return d.getTime();
    }
  }
  return most + 30 * 60 * 1000;
}

export class BasinUtemezo extends DurableObject {
  async paksFrissit() {
    try {
      const adat = await paksLekeres();
      await this.ctx.storage.put("paks", { adat, ido: Date.now() });
      return null;
    } catch (e) {
      const uzenet = String((e && e.message) || e);
      await this.ctx.storage.put("paks_hiba", { ido: new Date().toISOString(), hiba: uzenet });
      return uzenet;
    }
  }

  async paksValasz() {
    let t = await this.ctx.storage.get("paks");
    let hiba = null;
    if (!t || Date.now() - t.ido > PAKS_FRISS) {
      hiba = await this.paksFrissit();
      t = await this.ctx.storage.get("paks");
    }
    if (!t || Date.now() - t.ido > PAKS_MAX_KOR) {
      return Response.json({ hiba: hiba || "nincs tárolt érték" }, { status: 502 });
    }
    return Response.json({
      ...t.adat,
      frissitve: new Date(t.ido).toISOString(),
      kor_perc: Math.round((Date.now() - t.ido) / 60000),
      forras: FORRAS,
    });
  }

  async fetch(request) {
    const ut = new URL(request.url).pathname;
    const most = await this.ctx.storage.getAlarm();
    // A riasztást az új ütemhez igazítjuk, ha a korábbi kód távolabbi időpontra tette.
    if (!most || most > kovetkezo()) await this.ctx.storage.setAlarm(kovetkezo());
    if (ut === "/paks") return this.paksValasz();
    if (ut === "/most") {
      const utolso = await this.ctx.storage.get("utolso");
      const kezi = await this.ctx.storage.get("kezi");
      if (!kezi || Date.now() - kezi > KEZI_SZUNET) {
        await this.ctx.storage.put("kezi", Date.now());
        await this.alarm();
      } else if (utolso) {
        utolso.megjegyzes = "a kézi indítás tíz percen belül megismételve — kimaradt";
      }
    }
    const paks = await this.ctx.storage.get("paks");
    return Response.json({
      kovetkezo: new Date(await this.ctx.storage.getAlarm()).toISOString(),
      utolso: (await this.ctx.storage.get("utolso")) || null,
      paks_frissitve: paks ? new Date(paks.ido).toISOString() : null,
      paks_hiba: (await this.ctx.storage.get("paks_hiba")) || null,
    });
  }

  async alarm() {
    const ido = new Date().toISOString();
    // Előbb a paksi érték, hogy a bot már a friss tárolt értéket kapja.
    await this.paksFrissit();
    try {
      const m = await inditas(this.env);
      await this.ctx.storage.put("utolso", { ido, eredmeny: m });
      console.log(`${ido} — ${m}`);
    } catch (e) {
      // A hibát tároljuk és naplózzuk, de nem dobjuk tovább: a lánc így a
      // következő indításkor újrapróbál, és az /allapot megmutatja, mi történt.
      const uzenet = String((e && e.message) || e);
      await this.ctx.storage.put("utolso", { ido, hiba: uzenet }).catch(() => {});
      console.error(`${ido} — HIBA: ${uzenet}`);
    } finally {
      await this.ctx.storage.setAlarm(kovetkezo());
    }
  }
}

const peldany = (env) => env.UTEMEZO.get(env.UTEMEZO.idFromName("basin"));

export default {
  // /inditas — kézi próba: azonnal indít (tízpercenként legfeljebb egyszer).
  // /allapot — a következő indítás ideje, az utolsó eredmény és a paksi érték frissessége.
  // /paks    — a paksi blokkteljesítmény a holadelej.hu-ról, a botnak.
  async fetch(keres, env) {
    const ut = new URL(keres.url).pathname;
    if (ut === "/inditas") return peldany(env).fetch("https://utemezo/most");
    if (ut === "/allapot") return peldany(env).fetch("https://utemezo/allapot");
    if (ut === "/paks") return peldany(env).fetch("https://utemezo/paks");
    return new Response(
      "basin ütemező — /allapot: a lánc állapota, /inditas: azonnali indítás, /paks: paksi üzemállapot.\n",
      { headers: { "Content-Type": "text/plain; charset=utf-8" } }
    );
  },
};
