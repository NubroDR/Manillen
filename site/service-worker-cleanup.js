const appBase = new URL("./", import.meta.url);
const cacheSuffix = "::shinyliveServiceworker";
const failures = [];

function isInAppScope(url) {
  return url.origin === appBase.origin && url.pathname.startsWith(appBase.pathname);
}

async function unregisterLegacyWorkers() {
  if (!("serviceWorker" in navigator)) return;

  let registrations;
  try {
    registrations = await navigator.serviceWorker.getRegistrations();
  } catch (error) {
    failures.push(error);
    return;
  }

  for (const registration of registrations) {
    if (new URL(registration.scope).pathname !== appBase.pathname) continue;
    try {
      if (!(await registration.unregister())) {
        failures.push(new Error(`Service worker bleef actief voor ${registration.scope}`));
      }
    } catch (error) {
      failures.push(error);
    }
  }
}

async function clearLegacyCaches() {
  if (!("caches" in window)) return;

  let cacheNames;
  try {
    cacheNames = await caches.keys();
  } catch (error) {
    failures.push(error);
    return;
  }

  for (const name of cacheNames.filter((key) => key.endsWith(cacheSuffix))) {
    try {
      const cache = await caches.open(name);
      const requests = await cache.keys();
      for (const request of requests) {
        if (isInAppScope(new URL(request.url)) && !(await cache.delete(request))) {
          failures.push(new Error(`Cache-item kon niet worden verwijderd: ${request.url}`));
        }
      }
      if ((await cache.keys()).length === 0) await caches.delete(name);
    } catch (error) {
      failures.push(error);
    }
  }
}

await unregisterLegacyWorkers();
await clearLegacyCaches();

if (failures.length > 0) {
  console.error("Opruimen van oude Manillen offline opslag is niet volledig gelukt.", failures);
  const status = document.querySelector("#legacy-worker-status");
  if (status) {
    status.textContent =
      "De oude offline opslag kon niet volledig worden opgeruimd. Ververs de pagina; wis zo nodig de sitegegevens voor dit pad.";
    status.hidden = false;
  }
}
