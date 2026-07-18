const STORAGE_KEY = "data_last_result";

document.getElementById("fetch-btn").addEventListener("click", async () => {
    const pair = document.getElementById("pair-select").value;
    const timeframe = document.getElementById("tf-select").value;
    const meses = parseInt(document.getElementById("meses-input").value, 10) || 6;
    const statusEl = document.getElementById("fetch-status");
    const resultPanel = document.getElementById("result-panel");

    statusEl.textContent = "Consultando histórico...";
    statusEl.className = "status-line";
    resultPanel.classList.add("hidden");

    try {
        const resp = await fetch("/data/fetch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pair, timeframe, meses }),
        });
        const data = await resp.json();

        if (!data.ok) {
            statusEl.textContent = "Error: " + data.error;
            statusEl.className = "status-line error";
            return;
        }

        mostrarResultado(data, pair, timeframe, statusEl, resultPanel);
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ data, pair, timeframe }));
    } catch (err) {
        statusEl.textContent = "Error de red: " + err;
        statusEl.className = "status-line error";
    }
});

function mostrarResultado(data, pair, timeframe, statusEl, resultPanel) {
    const nulosMsg = data.nulos_limpiados > 0 ? ` (${data.nulos_limpiados} filas con nulos descartadas)` : "";
    statusEl.textContent = `${data.filas_totales} velas obtenidas · últimos ${data.ventana_meses} mes(es)${nulosMsg}.`;
    statusEl.className = "status-line success";

    renderPreview(data.columnas, data.vista_previa);
    document.getElementById("download-link").href =
        "/data/download?path=" + encodeURIComponent(data.archivo);
    resultPanel.classList.remove("hidden");
}

// --- Restaurar el último resultado al volver a este módulo (no se pierde al navegar) ---
(function restaurarUltimoFetch() {
    const guardado = sessionStorage.getItem(STORAGE_KEY);
    if (!guardado) return;
    try {
        const { data, pair, timeframe } = JSON.parse(guardado);
        const statusEl = document.getElementById("fetch-status");
        const resultPanel = document.getElementById("result-panel");
        if (pair) document.getElementById("pair-select").value = pair;
        if (timeframe) document.getElementById("tf-select").value = timeframe;
        mostrarResultado(data, pair, timeframe, statusEl, resultPanel);
        statusEl.textContent = "Mostrando la última consulta ejecutada en esta sesión. " + statusEl.textContent;
    } catch (err) {
        sessionStorage.removeItem(STORAGE_KEY);
    }
})();

document.getElementById("clear-data-btn").addEventListener("click", () => {
    if (!confirm("¿Limpiar el resultado actual de este módulo?")) return;
    sessionStorage.removeItem(STORAGE_KEY);
    document.getElementById("result-panel").classList.add("hidden");
    const statusEl = document.getElementById("fetch-status");
    statusEl.textContent = "";
    statusEl.className = "status-line";
});

function renderPreview(columnas, filas) {
    const thead = document.querySelector("#preview-table thead");
    const tbody = document.querySelector("#preview-table tbody");
    thead.innerHTML = "<tr>" + columnas.map((c) => `<th>${c}</th>`).join("") + "</tr>";
    tbody.innerHTML = filas
        .map((fila) => "<tr>" + columnas.map((c) => `<td>${fila[c] ?? "-"}</td>`).join("") + "</tr>")
        .join("");
}
