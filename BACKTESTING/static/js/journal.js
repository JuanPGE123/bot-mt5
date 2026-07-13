document.getElementById("trade-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const psicoForm = document.getElementById("psico-form");
    const statusEl = document.getElementById("trade-status");

    const payload = {
        ...Object.fromEntries(new FormData(form).entries()),
        ...Object.fromEntries(new FormData(psicoForm).entries()),
    };

    try {
        const resp = await fetch("/journal/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await resp.json();
        if (!data.ok) {
            statusEl.textContent = "Error: " + data.error;
            statusEl.className = "status-line error";
            return;
        }
        statusEl.textContent = "Operación y psicología registradas.";
        statusEl.className = "status-line success";
        updateStats(data.stats);
        renderPsicoAlert(data.riesgo);
        setTimeout(() => window.location.reload(), 800);
    } catch (err) {
        statusEl.textContent = "Error de red: " + err;
        statusEl.className = "status-line error";
    }
});

document.querySelectorAll(".delete-trade-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        if (!confirm("¿Eliminar esta operación del diario?")) return;
        const resp = await fetch(`/journal/delete/${id}`, { method: "POST" });
        const data = await resp.json();
        if (data.ok) {
            document.querySelector(`tr[data-id="${id}"]`).remove();
            updateStats(data.stats);
            renderPsicoAlert(data.riesgo);
        }
    });
});

function updateStats(stats) {
    document.getElementById("stat-pnl").textContent = stats.pnl_total;
    document.getElementById("stat-winrate").textContent = stats.win_rate + "%";
    document.getElementById("stat-streak").textContent = stats.racha_actual + " " + stats.racha_tipo;
    document.getElementById("stat-total").textContent = stats.total_trades;
}

function renderPsicoAlert(riesgo) {
    if (!riesgo) return;
    const panel = document.getElementById("psico-alert-panel");
    panel.dataset.nivel = riesgo.nivel_riesgo;
    const alertasHtml = (riesgo.alertas && riesgo.alertas.length)
        ? `<ul id="psico-alertas-list">${riesgo.alertas.map((a) => `<li>${a}</li>`).join("")}</ul>`
        : "";
    panel.innerHTML = `
        <h3>Alerta Psicológica — No Quemar la Cuenta</h3>
        <p class="kpi-row"><span class="label">Nivel de riesgo</span><span class="value">${riesgo.nivel_riesgo.toUpperCase()}</span></p>
        <p class="status-line">${riesgo.recomendacion_principal}</p>
        ${alertasHtml}
    `;
}
