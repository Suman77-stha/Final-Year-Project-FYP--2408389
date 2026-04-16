// ===============================
// GLOBAL VARIABLES
// ===============================
let mainChart;
let miniCharts = {};
let miniChartCache = {};


// ===============================
// DATE LABEL GENERATOR
// ===============================
function formatDateLabels(historyLength, futureLength) {
    const labels = [];
    const today = new Date();

    for (let i = historyLength; i > 0; i--) {
        const d = new Date();
        d.setDate(today.getDate() - i);
        labels.push(d.toLocaleDateString("en-US", { month: "short", day: "numeric" }));
    }

    for (let i = 1; i <= futureLength; i++) {
        const d = new Date();
        d.setDate(today.getDate() + i);
        labels.push(d.toLocaleDateString("en-US", { month: "short", day: "numeric" }));
    }

    return labels;
}


// ===============================
// MAIN CHART FUNCTION
// ===============================
function loadMainChart(symbol, range = "7D") {

    const canvas = document.getElementById("lineChart");
    if (!canvas) return;

    fetch(`/FYP/api/stock-prediction/?symbol=${symbol}&range=${range}`)
        .then(res => res.json())
        .then(data => {

            const closePrices = data.close_prices || [];
            const futurePrices = data.future_days || [];

            const labels = formatDateLabels(closePrices.length, futurePrices.length);

            const paddedClose = [...closePrices, ...new Array(futurePrices.length).fill(null)];
            const paddedFuture = [...new Array(closePrices.length).fill(null), ...futurePrices];

            if (mainChart) mainChart.destroy();

            mainChart = new Chart(canvas, {
                type: "line",
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: "Actual Price",
                            data: paddedClose,
                            borderColor: "#00ffae",
                            backgroundColor: "rgba(0,255,174,0.2)",
                            fill: true,
                            tension: 0.45,
                            pointRadius: 0
                        },
                        {
                            label: "Prediction",
                            data: paddedFuture,
                            borderColor: "#ff9800",
                            borderDash: [5, 5],
                            fill: false,
                            tension: 0.45,
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,

                    interaction: {
                        mode: "index",
                        intersect: false
                    },

                    plugins: {
                        legend: {
                            labels: { color: "#ccc" }
                        },
                        tooltip: {
                            backgroundColor: "#111",
                            titleColor: "#fff",
                            bodyColor: "#00ffae",
                            borderColor: "#00ffae",
                            borderWidth: 1,
                            padding: 10,
                            displayColors: false,
                            callbacks: {
                                title: function(context) {
                                    return context[0].label; // short date
                                },
                                label: function(context) {
                                    if (context.parsed.y === null) return "";
                                    return "$" + context.parsed.y.toFixed(2);
                                }
                            }
                        }
                    },

                    scales: {
                        x: {
                            ticks: { color: "#888" },
                            grid: { color: "rgba(255,255,255,0.05)" }
                        },
                        y: {
                            ticks: {
                                color: "#888",
                                callback: val => "$" + val
                            },
                            grid: { color: "rgba(255,255,255,0.05)" }
                        }
                    },

                    hover: {
                        mode: "nearest",
                        intersect: false
                    }
                }
            });

            // ✅ POINTER CURSOR
            canvas.style.cursor = "pointer";

            // ✅ SYNC MINI CHART
            const miniData = { labels, closePrices, paddedFuture };
            miniChartCache[symbol] = miniData;

            if (miniCharts[symbol]) {
                updateMiniChart(symbol, miniData);
            }

            const title = document.getElementById("chartTitle");
            if (title) title.innerText = symbol + " Price Prediction";
        })
        .catch(err => console.error("Chart error:", err));
}


/* ===============================
       1. TRADE MODAL
    =============================== */
    window.openTrade = function (type) {
        const modal = document.getElementById("tradeModal");
        const title = document.getElementById("tradeTitle");
        const action = document.getElementById("trade_action");

        if (!modal) return;

        modal.style.display = "flex";

        if (type === "buy") {
            title.innerText = "Buy Stock";
            action.value = "buy";
        } else {
            title.innerText = "Sell Stock";
            action.value = "sell";
        }

        document.getElementById("trade_symbol").value = "";
        document.getElementById("trade_price").value = "";
        document.getElementById("trade_qty").value = "";
        document.getElementById("trade_total").value = "";
    };

    window.closeTrade = function () {
        const modal = document.getElementById("tradeModal");
        if (modal) modal.style.display = "none";
    };


    /* ===============================
       2. TOTAL CALCULATION
    =============================== */
    const priceInput = document.getElementById("trade_price");
    const qtyInput = document.getElementById("trade_qty");
    const totalInput = document.getElementById("trade_total");

    if (priceInput && qtyInput && totalInput) {

        function updateTotal() {
            let p = parseFloat(priceInput.value);
            let q = parseInt(qtyInput.value);

            if (!isNaN(p) && !isNaN(q) && q > 0) {
                totalInput.value = (p * q).toFixed(2);
            } else {
                totalInput.value = "";
            }
        }

        priceInput.addEventListener("input", updateTotal);
        qtyInput.addEventListener("input", updateTotal);
    }


    /* ===============================
       3. AUTO FETCH STOCK PRICE
    =============================== */
    const symbolInput = document.getElementById("trade_symbol");

    if (symbolInput) {
        symbolInput.addEventListener("blur", function () {

            const symbol = symbolInput.value.trim().toUpperCase();
            if (!symbol) return;

            fetch(`/FYP/get-live-price/?symbol=${symbol}`)
                .then(res => res.json())
                .then(data => {
                    if (data.price !== null && data.price !== undefined) {
                        priceInput.value = parseFloat(data.price).toFixed(2);
                    } else {
                        priceInput.value = "";
                        alert("Symbol not found");
                    }
                })
                .catch(err => {
                    console.error("Price fetch error:", err);
                    priceInput.value = "";
                });
        });
    }


// ===============================
// DOM READY
// ===============================
document.addEventListener("DOMContentLoaded", function () {

    // MINI CHART INIT
    document.querySelectorAll(".crypto-card").forEach(card => {

        const graphDiv = card.querySelector(".s_graph");
        if (!graphDiv) return;

        const canvas = document.createElement("canvas");
        graphDiv.innerHTML = "";
        graphDiv.appendChild(canvas);

        const text = card.querySelector("h5")?.innerText || "";
        const symbolMatch = text.match(/\(([^)]+)\)/);
        const symbol = symbolMatch ? symbolMatch[1].trim().toUpperCase() : "TSLA";

        createOrUpdateMiniChart(symbol, canvas);
    });

    // MAIN CHART LOAD
    const params = new URLSearchParams(window.location.search);
    let symbol = (params.get("symbol") || "AAPL").toUpperCase();

    loadMainChart(symbol, "7D");

    // RANGE BUTTONS
    document.querySelectorAll(".chart-buttons button").forEach(btn => {
        btn.addEventListener("click", function () {

            document.querySelectorAll(".chart-buttons button")
                .forEach(b => b.classList.remove("active"));

            this.classList.add("active");

            loadMainChart(symbol, this.dataset.range);
        });
    });

    // TRADE INPUT EVENTS
    const priceInput = document.getElementById("trade_price");
    const qtyInput = document.getElementById("trade_qty");

    if (priceInput) priceInput.addEventListener("input", updateTotal);
    if (qtyInput) qtyInput.addEventListener("input", updateTotal);

    // AUTO PRICE FETCH
    const symbolInput = document.getElementById("trade_symbol");

    if (symbolInput) {
        symbolInput.addEventListener("blur", function () {

            const newSymbol = symbolInput.value.trim().toUpperCase();
            if (!newSymbol) return;

            fetch(`/FYP/get-live-price/?symbol=${newSymbol}`)
                .then(res => res.json())
                .then(data => {

                    if (data.price !== null) {
                        document.getElementById("trade_price").value = parseFloat(data.price).toFixed(2);
                    }

                    symbol = newSymbol;
                    loadMainChart(symbol, "7D");

                })
                .catch(err => console.error(err));
        });
    }

});