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

        const nulosMsg = data.nulos_limpiados > 0 ? ` (${data.nulos_limpiados} filas con nulos descartadas)` : "";
        statusEl.textContent = `${data.filas_totales} velas obtenidas · últimos ${data.ventana_meses} mes(es)${nulosMsg}.`;
        statusEl.className = "status-line success";

        renderPreview(data.columnas, data.vista_previa);
        document.getElementById("download-link").href =
            "/data/download?path=" + encodeURIComponent(data.archivo);
        resultPanel.classList.remove("hidden");
    } catch (err) {
        statusEl.textContent = "Error de red: " + err;
        statusEl.className = "status-line error";
    }
});

function renderPreview(columnas, filas) {
    const thead = document.querySelector("#preview-table thead");
    const tbody = document.querySelector("#preview-table tbody");
    thead.innerHTML = "<tr>" + columnas.map((c) => `<th>${c}</th>`).join("") + "</tr>";
    tbody.innerHTML = filas
        .map((fila) => "<tr>" + columnas.map((c) => `<td>${fila[c] ?? "-"}</td>`).join("") + "</tr>")
        .join("");
}
