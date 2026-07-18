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
        if (data.trade) prependTradeRow(data.trade);
        form.reset();
        psicoForm.reset();
    } catch (err) {
        statusEl.textContent = "Error de red: " + err;
        statusEl.className = "status-line error";
    }
});

function prependTradeRow(t) {
    const tbody = document.getElementById("trades-tbody");
    const pnlClass = (t.pnl || 0) > 0 ? "pnl-pos" : ((t.pnl || 0) < 0 ? "pnl-neg" : "");
    const tr = document.createElement("tr");
    tr.dataset.id = t.id;
    tr.innerHTML = `
        <td>${t.fecha}</td>
        <td>${t.par}</td>
        <td>${t.direccion}</td>
        <td>${t.entrada}</td>
        <td>${t.stop_loss}</td>
        <td>${t.take_profit}</td>
        <td>${t.precio_salida ?? "-"}</td>
        <td class="${pnlClass}">${t.pnl ?? "-"}</td>
        <td>${t.resultado ?? "-"}</td>
        <td><button class="btn-danger delete-trade-btn" data-id="${t.id}">Eliminar</button></td>
    `;
    tbody.prepend(tr);
    attachDeleteHandler(tr.querySelector(".delete-trade-btn"));
}

// --- Prellenar el formulario si se llega desde "Enviar a Diario" (módulo Entradas) ---
(function prellenarDesdeEntradas() {
    const params = new URLSearchParams(window.location.search);
    if (!params.has("par")) return;
    const form = document.getElementById("trade-form");
    ["par", "direccion", "entrada", "stop_loss", "take_profit"].forEach((campo) => {
        if (params.has(campo) && form.elements[campo]) form.elements[campo].value = params.get(campo);
    });
    document.getElementById("trade-status").textContent = "Datos precargados desde Entradas. Completa fecha y notas para registrar.";
})();

function attachDeleteHandler(btn) {
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
}
document.querySelectorAll(".delete-trade-btn").forEach(attachDeleteHandler);

document.getElementById("clear-journal-btn").addEventListener("click", async () => {
    if (!confirm("¿Borrar TODAS las operaciones del diario? Esta acción no se puede deshacer.")) return;
    const resp = await fetch("/journal/clear", { method: "POST" });
    const data = await resp.json();
    if (data.ok) {
        document.getElementById("trades-tbody").innerHTML = "";
        updateStats(data.stats);
        renderPsicoAlert(data.riesgo);
    }
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
