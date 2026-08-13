/**
 * basin-utemezo — Cloudflare Worker, ami félóránként elindítja a
 * GitHub Actions „basin" munkafolyamatát.
 *
 * MIÉRT KELL
 * A GitHub saját `cron` ütemezése kérés, nem garancia: torlódáskor csúszik
 * vagy kimarad. A naplónk szerint az óránkénti kérésből a gyakorlatban
 * 53–130 perc lett. A Cloudflare cron-triggere ezzel szemben percre pontos,
 * és a `workflow_dispatch` végponton keresztül azonnal indít.
 *
 * MIT NEM OLD MEG
 * A futás hossza és a GitHub futtató-sor továbbra is a GitHubé. Ez a Worker
 * csak azt garantálja, hogy a KÉRÉS pontosan érkezik meg.
 *
 * TITKOK
 *   GITHUB_TOKEN — finomhangolt PAT, csak erre a repóra, Actions: read+write
 * A tokent a wrangler secret kezeli; a kódban sosem szerepel.
 */

const TULAJ = "lpapp68";
const REPO = "basin";
const MUNKAFOLYAMAT = "basin.yml";

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

export default {
  // Az ütemezett futás. A hibát nem nyeljük el: a Cloudflare naplójában
  // látszania kell, ha a token lejárt vagy a repó átnevezésre került.
  async scheduled(esemeny, env, ctx) {
    ctx.waitUntil(
      inditas(env).then(
        (m) => console.log(`${new Date().toISOString()} — ${m}`),
        (e) => {
          console.error(`${new Date().toISOString()} — HIBA: ${e.message}`);
          throw e;
        }
      )
    );
  },

  // Kézi próbához: böngészőből meghívva ugyanazt teszi.
  // Nem védjük jelszóval — legrosszabb esetben valaki fölöslegesen
  // elindítja a gyűjtést, ami nem okoz kárt.
  async fetch(keres, env) {
    if (new URL(keres.url).pathname !== "/inditas") {
      return new Response(
        "basin ütemező — a /inditas útvonal indítja a gyűjtést.\n",
        { headers: { "Content-Type": "text/plain; charset=utf-8" } }
      );
    }
    try {
      return new Response(await inditas(env) + "\n");
    } catch (e) {
      return new Response(`hiba: ${e.message}\n`, { status: 502 });
    }
  },
};
