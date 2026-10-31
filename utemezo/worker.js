/**
 * basin-utemezo — Cloudflare Worker, ami óránként elindítja a GitHub Actions
 * „basin" munkafolyamatát.
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
 * Durable Object riasztása (alarm) lépteti a láncot: minden óra 4. percében
 * (UTC) indít, és ugyanabban a lépésben beállítja a következőt. A lánc első
 * szemét bármelyik kérés berakja (/allapot vagy /inditas); utána magától fut.
 *
 * MIT NEM OLD MEG
 * A futás hossza és a GitHub futtató-sor továbbra is a GitHubé. Ez a Worker
 * csak azt garantálja, hogy a KÉRÉS pontosan érkezik meg.
 *
 * TITKOK
 *   GITHUB_TOKEN — finomhangolt PAT, csak erre a repóra, Actions: read+write
 * A tokent a wrangler secret kezeli; a kódban sosem szerepel.
 */

import { DurableObject } from "cloudflare:workers";

const TULAJ = "lpapp68";
const REPO = "basin";
const MUNKAFOLYAMAT = "basin.yml";
// A kézi indítás nyilvános. Hogy egy ismételt hívás ne égesse az Actions-
// keretet, tíz percen belül legfeljebb egy kézi indítás megy ki.
const KEZI_SZUNET = 10 * 60 * 1000;

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

// A következő óra 4. perce, UTC. A kerek perceket kerüljük: azok a legterheltebbek.
function kovetkezo(most = Date.now()) {
  const d = new Date(most);
  d.setUTCMinutes(4, 0, 0);
  if (d.getTime() <= most) d.setUTCHours(d.getUTCHours() + 1);
  return d.getTime();
}

export class BasinUtemezo extends DurableObject {
  async fetch(request) {
    const ut = new URL(request.url).pathname;
    if (!(await this.ctx.storage.getAlarm())) await this.ctx.storage.setAlarm(kovetkezo());
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
    return Response.json({
      kovetkezo: new Date(await this.ctx.storage.getAlarm()).toISOString(),
      utolso: (await this.ctx.storage.get("utolso")) || null,
    });
  }

  async alarm() {
    const ido = new Date().toISOString();
    try {
      const m = await inditas(this.env);
      await this.ctx.storage.put("utolso", { ido, eredmeny: m });
      console.log(`${ido} — ${m}`);
    } catch (e) {
      // A hibát tároljuk és naplózzuk, de nem dobjuk tovább: a lánc így a
      // következő órában újrapróbál, és az /allapot megmutatja, mi történt.
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
  // /allapot — a következő indítás ideje és az utolsó eredmény.
  async fetch(keres, env) {
    const ut = new URL(keres.url).pathname;
    if (ut === "/inditas") return peldany(env).fetch("https://utemezo/most");
    if (ut === "/allapot") return peldany(env).fetch("https://utemezo/allapot");
    return new Response(
      "basin ütemező — /allapot: a lánc állapota, /inditas: azonnali indítás.\n",
      { headers: { "Content-Type": "text/plain; charset=utf-8" } }
    );
  },
};
