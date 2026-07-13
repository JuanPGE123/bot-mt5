const TIMEFRAMES = ["macro", "intermedia", "micro"];

document.getElementById("backtest-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("backtest-status");
    const resultsEl = document.getElementById("backtest-results");

    const formData = new FormData();
    formData.append("csv_file", document.getElementById("csv_file").files[0]);
    TIMEFRAMES.forEach((tf) => {
        const file = document.getElementById(`image_${tf}`).files[0];
        if (file) formData.append(`image_${tf}`, file);
    });

    statusEl.textContent = "Ejecutando backtest...";
    statusEl.className = "status-line";
    resultsEl.classList.add("hidden");

    try {
        const resp = await fetch("/backtest/run", { method: "POST", body: formData });
        const data = await resp.json();
        manejarRespuesta(data, statusEl, resultsEl);
    } catch (err) {
        statusEl.textContent = "Error de red: " + err;
        statusEl.className = "status-line error";
    }
});

const demoBtn = document.getElementById("run-demo-btn");
if (demoBtn) {
    demoBtn.addEventListener("click", async () => {
        const statusEl = document.getElementById("backtest-status");
        const resultsEl = document.getElementById("backtest-results");
        statusEl.textContent = "Cargando backtest de ejemplo (Demo)...";
        statusEl.className = "status-line";
        resultsEl.classList.add("hidden");
        try {
            const resp = await fetch("/backtest/run-demo", { method: "POST" });
            const data = await resp.json();
            manejarRespuesta(data, statusEl, resultsEl);
        } catch (err) {
            statusEl.textContent = "Error de red: " + err;
            statusEl.className = "status-line error";
        }
    });
}

function manejarRespuesta(data, statusEl, resultsEl) {
    if (!data.ok) {
        statusEl.textContent = "Error: " + data.error;
        statusEl.className = "status-line error";
        return;
    }
    statusEl.textContent = "Backtest completado.";
    statusEl.className = "status-line success";
    renderAnalysis(data.analisis);
    renderImages(data.analisis_imagenes);
    renderConfluencia(data.confluencia_multitemporal);
    resultsEl.classList.remove("hidden");
}

function renderAnalysis(a) {
    // TP / SL
    const tpSl = a.sugerencia_tp_sl;
    document.getElementById("tp-sl-box").innerHTML = `
        <div class="kpi-row"><span class="label">Precio actual</span><span class="value">${fmtNum(tpSl.precio_actual)}</span></div>
        <div class="kpi-row"><span class="label">Zona entrada Fibo</span><span class="value">${(tpSl.zona_entrada_fibo.ratio * 100).toFixed(1)}% → ${fmtNum(tpSl.zona_entrada_fibo.precio)}</span></div>
        <div class="kpi-row"><span class="label">Take Profit</span><span class="value">${fmtNum(tpSl.take_profit)}</span></div>
        <div class="kpi-row"><span class="label">Stop Loss</span><span class="value">${fmtNum(tpSl.stop_loss)}</span></div>
        <div class="kpi-row"><span class="label">Riesgo/Beneficio</span><span class="value">1 : ${tpSl.riesgo_beneficio}</span></div>
    `;

    // Estadísticas scalping
    const vol = a.volatilidad_sesion;
    const volLinea = vol.error
        ? vol.error
        : `${vol.sesion_mas_volatil} (hora UTC ${vol.hora_mas_volatil_utc}h)`;
    const tf = a.temporalidad_detectada;
    document.getElementById("stats-box").innerHTML = `
        <div class="kpi-row"><span class="label">Temporalidad detectada</span><span class="value">${tf.minutos_por_vela} min/vela (${tf.clasificacion})</span></div>
        <div class="kpi-row"><span class="label">ATR (scalping)</span><span class="value">${fmtNum(a.atr_scalping)}</span></div>
        <div class="kpi-row"><span class="label">Sesión más volátil</span><span class="value">${volLinea}</span></div>
        <div class="kpi-row"><span class="label">Impulso detectado</span><span class="value">${a.ultimo_impulso.direccion}</span></div>
        <div class="kpi-row"><span class="label">Rango diario promedio</span><span class="value">${a.analisis_diario.rango_diario_promedio ?? "-"}</span></div>
    `;

    // Soportes / Resistencias
    const sr = a.soportes_resistencias;
    document.getElementById("sr-box").innerHTML =
        "<strong>Resistencias</strong>" +
        sr.resistencias.map((r) => `<div class="sr-level"><span>${fmtNum(r.nivel)}</span><span>${r.toques} toques</span></div>`).join("") +
        "<br><strong>Soportes</strong>" +
        sr.soportes.map((s) => `<div class="sr-level"><span>${fmtNum(s.nivel)}</span><span>${s.toques} toques</span></div>`).join("");

    // Fibonacci
    document.getElementById("fibo-box").innerHTML = a.fibonacci
        .map(
            (f) =>
                `<div class="fibo-level ${f.zona_clave ? "key" : ""}"><span>${(f.ratio * 100).toFixed(1)}%</span><span>${fmtNum(f.precio)} ${f.zona_clave ? '<span class="tag-key">CLAVE</span>' : ""}</span></div>`
        )
        .join("");

    // Win-rate Fibo
    const wr = a.win_rate_fibo;
    document.getElementById("winrate-box").innerHTML = Object.entries(wr)
        .map(
            ([nivel, v]) =>
                `<div class="kpi-row"><span class="label">Nivel ${nivel}%</span><span class="value">${v.win_rate}% (${v.aciertos}/${v.toques} toques)</span></div>`
        )
        .join("");

    // Zona de reversión + puntos A/B Fibonacci
    const zr = a.zona_reversion_fibonacci;
    const reversalBox = document.getElementById("reversal-box");
    if (zr.nota) {
        reversalBox.innerHTML = `<p class="status-line">${zr.nota}</p>`;
    } else {
        reversalBox.innerHTML = `
            <div class="kpi-row"><span class="label">Punto A</span><span class="value">${zr.punto_A.tipo} @ ${fmtNum(zr.punto_A.precio)}</span></div>
            <div class="kpi-row"><span class="label">Punto B</span><span class="value">${zr.punto_B.tipo} @ ${fmtNum(zr.punto_B.precio)}</span></div>
            <div class="kpi-row"><span class="label">Reversión esperada</span><span class="value">${zr.direccion_reversion_esperada}</span></div>
            <div class="kpi-row"><span class="label">Zona confirmada</span><span class="value">${zr.zona_reversion_confirmada ? "Sí" : "No"} (confianza ${zr.confianza})</span></div>
            <p class="status-line">${zr.instruccion}</p>
        `;
    }

    // Patrones de velas y trampas de mercado
    const patternsBox = document.getElementById("patterns-box");
    const patrones = a.patrones_de_velas || [];
    const trampas = a.trampas_de_mercado || [];
    let html = "";
    if (patrones.length) {
        html += "<strong>Patrones de velas recientes</strong>" + patrones
            .map((p) => `<div class="sr-level"><span>${p.patron} (${p.tipo})</span><span>${p.direccion}${p.fecha ? " · " + p.fecha : ""}</span></div>`)
            .join("");
    }
    if (trampas.length) {
        html += "<br><strong>Trampas / Fakeouts detectados</strong>" + trampas
            .map((t) => `<div class="sr-level"><span>${t.senal}</span><span>nivel ${fmtNum(t.nivel_afectado)}${t.fecha ? " · " + t.fecha : ""}</span></div>`)
            .join("");
    }
    patternsBox.innerHTML = html || '<p class="status-line">Sin patrones ni trampas relevantes en las velas recientes.</p>';
}

function renderImages(imagenes) {
    const box = document.getElementById("images-box");
    const entradas = Object.entries(imagenes || {}).filter(([, v]) => v);
    if (entradas.length === 0) {
        box.innerHTML = '<p class="status-line">No se subieron imágenes.</p>';
        return;
    }
    box.innerHTML = entradas
        .map(([tf, img]) => {
            if (img.error) {
                return `<div class="img-block"><h4>${tf}</h4><p class="status-line error">${img.error}</p></div>`;
            }
            const precios = img.ocr.posibles_precios.join(", ") || "Ninguno detectado";
            const zonas = img.zonas_visuales.zonas_horizontales_detectadas
                .map((z) => `${z.posicion_y_pct}% alto (${z.num_lineas_agrupadas} líneas)`)
                .join(", ") || "Ninguna";
            return `<div class="img-block">
                <h4>${tf}: ${img.archivo}</h4>
                <div class="kpi-row"><span class="label">Precios detectados (OCR)</span><span class="value">${precios}</span></div>
                <div class="kpi-row"><span class="label">Zonas horizontales visuales</span><span class="value">${zonas}</span></div>
            </div>`;
        })
        .join("");
}

function renderConfluencia(c) {
    const box = document.getElementById("confluencia-box");
    if (!c || c.confluencia === "sin_datos") {
        box.innerHTML = `<p class="status-line">${c ? c.mensaje : "Sin datos."}</p>`;
        return;
    }
    box.innerHTML = `
        <div class="kpi-row"><span class="label">Temporalidades recibidas</span><span class="value">${c.temporalidades_recibidas.join(", ") || "-"}</span></div>
        <div class="kpi-row"><span class="label">Temporalidades faltantes</span><span class="value">${c.temporalidades_faltantes.join(", ") || "Ninguna"}</span></div>
        <div class="kpi-row"><span class="label">Sesgo visual de confluencia</span><span class="value">${c.sesgo_visual_confluencia}</span></div>
        <div class="kpi-row"><span class="label">Dirección impulso (CSV)</span><span class="value">${c.impulso_csv_direccion ?? "-"}</span></div>
        <div class="kpi-row"><span class="label">¿Alineado con el CSV?</span><span class="value">${c.alineado_con_impulso_csv === null ? "N/D" : (c.alineado_con_impulso_csv ? "Sí" : "No")}</span></div>
    `;
}

// --- Panel de noticias ---
async function loadNews() {
    const pair = document.getElementById("news-pair-select").value;
    const list = document.getElementById("news-list");
    list.innerHTML = '<p class="status-line">Cargando noticias...</p>';
    try {
        const resp = await fetch(`/news/fetch?pair=${encodeURIComponent(pair)}`);
        const data = await resp.json();
        if (!data.noticias || data.noticias.length === 0) {
            list.innerHTML = '<p class="status-line">Sin noticias disponibles en este momento.</p>';
            return;
        }
        list.innerHTML = data.noticias
            .map(
                (n) => `<div class="news-item">
                    <a href="${n.link || "#"}" target="_blank" rel="noopener">${n.titulo}</a>
                    <span class="news-source">${n.fuente}${n.fecha ? " · " + n.fecha : ""}</span>
                </div>`
            )
            .join("");
    } catch (err) {
        list.innerHTML = `<p class="status-line error">Error cargando noticias: ${err}</p>`;
    }
}

function fmtNum(n) {
    return n === null || n === undefined ? "-" : n;
}

document.getElementById("news-refresh-btn").addEventListener("click", loadNews);
document.getElementById("news-pair-select").addEventListener("change", loadNews);
loadNews();
