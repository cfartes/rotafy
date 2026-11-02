/* Isolated sandbox: no app session, credential storage, or parent DOM access. */
window.addEventListener("message", async event => {
  if (event.source !== parent || event.data?.type !== "rotafy-route" || window.routeLoaded) return;
  const { key, planned, positions } = event.data;
  const status = document.getElementById("status");
  if (!/^[A-Za-z0-9_-]{10,512}$/.test(key || "") || !Array.isArray(planned) || !Array.isArray(positions) || positions.length > 10000) return;
  window.routeLoaded = true;
  status.textContent = "Carregando Google Maps…";
  try {
    await new Promise((resolve, reject) => {
      window.routeMapReady = resolve;
      const script = document.createElement("script");
      script.src = "https://maps.googleapis.com/maps/api/js?" + new URLSearchParams({ key, callback: "routeMapReady", loading: "async", v: "quarterly", language: "pt-BR" });
      script.referrerPolicy = "origin"; script.onerror = reject;
      window.gm_authFailure = () => reject(new Error("auth"));
      document.head.append(script);
      setTimeout(() => reject(new Error("timeout")), 20000);
    });
    const maps = google.maps;
    const map = new maps.Map(document.getElementById("map"), { center: { lat: -14.2, lng: -51.9 }, zoom: 4, renderingType: "RASTER", streetViewControl: false, mapTypeControl: false, fullscreenControl: false });
    const bounds = new maps.LatLngBounds();
    const valid = p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude) && Math.abs(p.latitude) <= 90 && Math.abs(p.longitude) <= 180;
    const actual = positions.filter(valid), path = actual.map(p => ({ lat: p.latitude, lng: p.longitude }));
    path.forEach(p => bounds.extend(p));
    new maps.Polyline({ map, path, strokeColor: "#087f5b", strokeWeight: 4 });
    for (const [i, p] of actual.entries()) {
      if (i !== 0 && i !== actual.length - 1) continue;
      new maps.Marker({ map, position: { lat: p.latitude, lng: p.longitude }, title: `GPS · ${new Date(p.captured_at).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })} · Precisão ${Math.round(p.accuracy_m)} m`, icon: { path: maps.SymbolPath.CIRCLE, scale: 7, fillColor: "#087f5b", fillOpacity: 1, strokeWeight: 1 } });
    }
    const geocoder = new maps.Geocoder(), cache = new Map();
    let located = 0, previous = null;
    const limit = 100;
    for (const [i, p] of planned.slice(0, limit).entries()) {
      status.textContent = `Localizando pontos planejados: ${i + 1}/${Math.min(planned.length, limit)}…`;
      const address = typeof p.query === "string" ? p.query.slice(0, 1024) : "";
      if (!address || !p.address) { previous = null; continue; }
      try {
        if (!cache.has(address)) cache.set(address, geocoder.geocode({ address, region: "BR" }));
        const response = await cache.get(address);
        if (response.results.length !== 1 || response.results[0].partial_match) { previous = null; continue; }
        const point = response.results[0].geometry.location;
        bounds.extend(point); located++;
        new maps.Marker({ map, position: point, label: { text: String(i + 1), color: "#ffffff" }, icon: { path: maps.SymbolPath.CIRCLE, scale: 12, fillColor: "#205bce", fillOpacity: 1, strokeWeight: 1 }, title: `${p.name} · ${p.address}${p.scheduled_at ? " · " + new Date(p.scheduled_at).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" }) : ""}` });
        if (previous) new maps.Polyline({ map, path: [previous, point], strokeColor: "#205bce", strokeWeight: 3 });
        previous = point;
      } catch { previous = null; }
    }
    if (!bounds.isEmpty()) { map.fitBounds(bounds, 35); maps.event.addListenerOnce(map, "idle", () => { if (map.getZoom() > 17) map.setZoom(17); }); }
    status.textContent = `${located}/${planned.length} pontos planejados localizados · ${actual.length} amostras GPS. Azul: planejado. Verde: realizado. Pontos não localizados não são ligados.${planned.length > limit ? " Limite de 100 pontos planejados por comparação." : ""}`;
  } catch { status.textContent = "Não foi possível carregar o mapa. Confira a chave web, as APIs habilitadas, a conexão e as cotas do Google. A lista do roteiro continua disponível no app."; }
});
