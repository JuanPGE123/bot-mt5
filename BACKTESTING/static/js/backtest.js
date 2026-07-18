const TIMEFRAMES = ["macro", "intermedia", "micro"];
const STORAGE_KEY = "bt_last_result";

document.getElementById("backtest-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("backtest-status");
    const resultsEl = document.getElementById("backtest-results");

    const par = document.getElementById("par_select").value;
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
        manejarRespuesta(data, statusEl, resultsEl, par);
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
        const par = document.getElementById("par_select").value;
        statusEl.textContent = "Cargando backtest de ejemplo (Demo)...";
        statusEl.className = "status-line";
        resultsEl.classList.add("hidden");
        try {
            const resp = await fetch("/backtest/run-demo", { method: "POST" });
            const data = await resp.json();
            manejarRespuesta(data, statusEl, resultsEl, par);
        } catch (err) {
            statusEl.textContent = "Error de red: " + err;
            statusEl.className = "status-line error";
        }
    });
}

function manejarRespuesta(data, statusEl, resultsEl, par) {
    if (!data.ok) {
        statusEl.textContent = "Error: " + data.error;
        statusEl.className = "status-line error";
        return;
    }
    statusEl.textContent = "Backtest completado.";
    statusEl.className = "status-line success";
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ data, par }));
    renderAnalysis(data.analisis);
    renderImages(data.analisis_imagenes);
    renderConfluencia(data.confluencia_multitemporal);
    resultsEl.classList.remove("hidden");
    document.getElementById("enviar-entrada-btn").classList.remove("hidden");
}

// --- Restaurar el último análisis al volver a este módulo (no se pierde al navegar) ---
(function restaurarUltimoAnalisis() {
    const guardado = sessionStorage.getItem(STORAGE_KEY);
    if (!guardado) return;
    try {
        const { data, par } = JSON.parse(guardado);
        const statusEl = document.getElementById("backtest-status");
        const resultsEl = document.getElementById("backtest-results");
        if (par) document.getElementById("par_select").value = par;
        statusEl.textContent = "Mostrando el último backtest ejecutado en esta sesión.";
        statusEl.className = "status-line";
        manejarRespuesta(data, statusEl, resultsEl, par);
    } catch (err) {
        sessionStorage.removeItem(STORAGE_KEY);
    }
})();

document.getElementById("clear-backtest-btn").addEventListener("click", () => {
    if (!confirm("¿Limpiar el análisis actual de este módulo?")) return;
    sessionStorage.removeItem(STORAGE_KEY);
    document.getElementById("backtest-form").reset();
    document.getElementById("backtest-results").classList.add("hidden");
    document.getElementById("enviar-entrada-btn").classList.add("hidden");
    document.getElementById("enviar-entrada-status").textContent = "";
    const statusEl = document.getElementById("backtest-status");
    statusEl.textContent = "";
    statusEl.className = "status-line";
});

document.getElementById("enviar-entrada-btn").addEventListener("click", async () => {
    const statusEl = document.getElementById("enviar-entrada-status");
    const guardado = sessionStorage.getItem(STORAGE_KEY);
    if (!guardado) return;
    const { data, par } = JSON.parse(guardado);
    const a = data.analisis;
    const orden = a.sugerencia_orden;
    const tpSl = a.sugerencia_tp_sl;
    const direccion = a.ultimo_impulso.direccion === "alcista" ? "COMPRA" : "VENTA";

    const payload = {
        par: par || "N/D",
        direccion,
        tipo_orden: orden.tipo_orden,
        precio_entrada: orden.precio_entrada_sugerido,
        stop_loss: tpSl.stop_loss,
        take_profit: tpSl.take_profit,
        riesgo_beneficio: tpSl.riesgo_beneficio,
        temporalidad: a.temporalidad_detectada.clasificacion,
        motivo: orden.motivo,
        origen: "backtest",
    };

    try {
        const resp = await fetch("/entradas/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const result = await resp.json();
        if (!result.ok) {
            statusEl.textContent = "Error: " + result.error;
            statusEl.className = "status-line error";
            return;
        }
        statusEl.textContent = "Entrada enviada al módulo Entradas.";
        statusEl.className = "status-line success";
    } catch (err) {
        statusEl.textContent = "Error de red: " + err;
        statusEl.className = "status-line error";
    }
});

function renderAnalysis(a) {
    // Tipo de orden sugerida (mercado / limit / stop)
    const orden = a.sugerencia_orden;
    document.getElementById("orden-box").innerHTML = `
        <div class="kpi-row"><span class="label">Tipo de orden</span><span class="value">${orden.tipo_orden}</span></div>
        <div class="kpi-row"><span class="label">Precio de entrada</span><span class="value">${fmtNum(orden.precio_entrada_sugerido)}</span></div>
        <div class="kpi-row"><span class="label">¿En zona ahora?</span><span class="value">${orden.en_zona_actualmente ? "Sí" : "No"}</span></div>
        <div class="kpi-row"><span class="label">Motivo</span><span class="value">${orden.motivo}</span></div>
    `;

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

// ---------------------------------------------------------------------------
// Módulo de Análisis de Backtesting Avanzado (Multi-Temporal: Macro/Intermedio/Micro)
// ---------------------------------------------------------------------------
const TIMEFRAMES_MTF = ["macro", "intermedio", "micro"];
const MTF_STORAGE_KEY = "bt_last_mtf_result";

document.getElementById("mtf-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("mtf-status");
    const resultsEl = document.getElementById("mtf-results");

    const formData = new FormData();
    TIMEFRAMES_MTF.forEach((tf) => {
        formData.append(`csv_${tf}`, document.getElementById(`csv_${tf}`).files[0]);
    });

    statusEl.textContent = "Ejecutando análisis multi-temporal...";
    statusEl.className = "status-line";
    resultsEl.classList.add("hidden");

    try {
        const resp = await fetch("/backtest/run-mtf", { method: "POST", body: formData });
        const data = await resp.json();
        if (!data.ok) {
            statusEl.textContent = "Error: " + data.error;
            statusEl.className = "status-line error";
            return;
        }
        statusEl.textContent = "Análisis multi-temporal completado.";
        statusEl.className = "status-line success";
        sessionStorage.setItem(MTF_STORAGE_KEY, JSON.stringify(data.mtf));
        renderMtf(data.mtf);
        resultsEl.classList.remove("hidden");
    } catch (err) {
        statusEl.textContent = "Error de red: " + err;
        statusEl.className = "status-line error";
    }
});

(function restaurarUltimoMtf() {
    const guardado = sessionStorage.getItem(MTF_STORAGE_KEY);
    if (!guardado) return;
    try {
        const mtf = JSON.parse(guardado);
        document.getElementById("mtf-status").textContent = "Mostrando el último análisis multi-temporal ejecutado en esta sesión.";
        renderMtf(mtf);
        document.getElementById("mtf-results").classList.remove("hidden");
    } catch (err) {
        sessionStorage.removeItem(MTF_STORAGE_KEY);
    }
})();

function renderMtf(mtf) {
    const r = mtf.resumen_general;
    document.getElementById("mtf-resumen-box").innerHTML = `
        <div class="kpi-row"><span class="label">Dirección Macro (prioridad)</span><span class="value">${r.direccion_macro}</span></div>
        <div class="kpi-row"><span class="label">Precio actual (Micro)</span><span class="value">${fmtNum(r.precio_actual)}</span></div>
        <div class="kpi-row"><span class="label">Estructura Macro / Intermedio / Micro</span><span class="value">${r.estructura.macro} / ${r.estructura.intermedio} / ${r.estructura.micro}</span></div>
        <div class="kpi-row"><span class="label">Alineación total 3 temporalidades</span><span class="value">${r.alineacion_total ? "Sí" : "No"}</span></div>
        <div class="kpi-row"><span class="label">Setups de alta probabilidad</span><span class="value">${r.total_setups_alta_probabilidad}</span></div>
    `;

    const setupsBox = document.getElementById("mtf-setups-box");
    const setups = mtf.setups_alta_probabilidad || [];
    if (!setups.length) {
        setupsBox.innerHTML = '<p class="status-line">Sin confluencia accionable (&ge;2 temporalidades) alineada con la estructura Macro.</p>';
    } else {
        setupsBox.innerHTML = setups
            .map(
                (s, i) => `
            <div class="setup-card">
                <div class="setup-card-header">
                    <span class="tag-key">#${i + 1} ${s.direccion}</span>
                    <span>${s.nivel_confluencia}</span>
                </div>
                <div class="kpi-row"><span class="label">Entrada sugerida</span><span class="value">${fmtNum(s.precio_entrada_sugerido)} (zona ${fmtNum(s.zona_entrada.min)} – ${fmtNum(s.zona_entrada.max)})</span></div>
                <div class="kpi-row"><span class="label">Stop Loss</span><span class="value">${fmtNum(s.stop_loss)}</span></div>
                <div class="kpi-row"><span class="label">Take Profit</span><span class="value">${fmtNum(s.take_profit)}</span></div>
                <div class="kpi-row"><span class="label">Riesgo/Beneficio</span><span class="value">1 : ${s.riesgo_beneficio}</span></div>
                <div class="kpi-row"><span class="label">Temporalidades confluentes</span><span class="value">${s.temporalidades_confluentes.join(" + ")}</span></div>
                <div class="kpi-row"><span class="label">Alternativas de entrada</span><span class="value">${s.alternativas_de_entrada.join(", ")}</span></div>
            </div>`
            )
            .join("");
    }

    const detalleBox = document.getElementById("mtf-detalle-box");
    detalleBox.innerHTML = TIMEFRAMES_MTF.map((tf) => {
        const d = mtf.detalle_por_temporalidad[tf];
        const fibo = d.fibonacci_retroceso
            .filter((f) => f.zona_clave)
            .map((f) => `<div class="fibo-level key"><span>${(f.ratio * 100).toFixed(1)}%</span><span>${fmtNum(f.precio)}</span></div>`)
            .join("");
        const sr = d.soportes_resistencias.resistencias
            .slice(0, 3)
            .map((z) => `<div class="sr-level"><span>R ${fmtNum(z.nivel)}</span><span>${z.toques} toques</span></div>`)
            .join("") +
            d.soportes_resistencias.soportes
                .slice(0, 3)
                .map((z) => `<div class="sr-level"><span>S ${fmtNum(z.nivel)}</span><span>${z.toques} toques</span></div>`)
                .join("");
        return `<div class="panel">
            <h4>${tf.toUpperCase()} (peso ${d.peso})</h4>
            <div class="kpi-row"><span class="label">Dirección</span><span class="value">${d.direccion}</span></div>
            <div class="kpi-row"><span class="label">Precio actual</span><span class="value">${fmtNum(d.precio_actual)}</span></div>
            <div class="kpi-row"><span class="label">ATR</span><span class="value">${fmtNum(d.atr)}</span></div>
            <strong>Fibonacci clave (50% / 61.8%)</strong>${fibo}
            <strong>SR principales</strong>${sr}
        </div>`;
    }).join("");

    const confluenciasBox = document.getElementById("mtf-confluencias-box");
    const clusters = mtf.confluencias || [];
    confluenciasBox.innerHTML = clusters.length
        ? clusters
              .map(
                  (c) => `<div class="sr-level">
                <span>${fmtNum(c.precio_centro)} (${fmtNum(c.zona_min)} – ${fmtNum(c.zona_max)})</span>
                <span>${c.nivel_confluencia} · ${c.componentes.map((k) => `${k.temporalidad}:${k.origen}`).join(", ")}</span>
            </div>`
              )
              .join("")
        : '<p class="status-line">Sin clusters detectados.</p>';
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
