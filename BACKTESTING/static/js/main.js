// Utilidades compartidas entre vistas
function fmtNum(n, decimals = 5) {
    if (n === null || n === undefined || Number.isNaN(n)) return "-";
    return Number(n).toFixed(decimals);
}
