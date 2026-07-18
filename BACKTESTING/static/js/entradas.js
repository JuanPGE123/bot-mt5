document.getElementById("entrada-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const statusEl = document.getElementById("entrada-status");
    const payload = Object.fromEntries(new FormData(form).entries());

    try {
        const resp = await fetch("/entradas/add", {
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
        statusEl.textContent = "Entrada agregada.";
        statusEl.className = "status-line success";
        setTimeout(() => window.location.reload(), 500);
    } catch (err) {
        statusEl.textContent = "Error de red: " + err;
        statusEl.className = "status-line error";
    }
});

document.querySelectorAll(".delete-entrada-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        if (!confirm("¿Eliminar esta entrada?")) return;
        const resp = await fetch(`/entradas/delete/${id}`, { method: "POST" });
        const data = await resp.json();
        if (data.ok) {
            document.querySelector(`.entry-card[data-id="${id}"]`).remove();
        }
    });
});

const clearBtn = document.getElementById("clear-entradas-btn");
if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
        if (!confirm("¿Borrar TODAS las entradas registradas? Esta acción no se puede deshacer.")) return;
        const resp = await fetch("/entradas/clear", { method: "POST" });
        const data = await resp.json();
        if (data.ok) window.location.reload();
    });
}
