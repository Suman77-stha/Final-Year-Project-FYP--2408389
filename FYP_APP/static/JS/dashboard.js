document.addEventListener("DOMContentLoaded", function () {

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


    /* ===============================
       4. MINI STOCK GRAPHS
    =============================== */
    document.querySelectorAll(".crypto-card").forEach(card => {

        const graphDiv = card.querySelector(".s_graph");
        if (!graphDiv) return;

        const canvas = document.createElement("canvas");
        graphDiv.innerHTML = "";
        graphDiv.appendChild(canvas);

        const ctx = canvas.getContext("2d");

        const text = card.querySelector("h5")?.innerText || "";
        const symbolMatch = text.match(/\(([^)]+)\)/);
        const symbol = symbolMatch ? symbolMatch[1].trim().toUpperCase() : "TSLA";

        fetch(`/FYP/api/stock-prediction/?symbol=${symbol}&range=7D`)
            .then(res => res.json())
            .then(data => {

                const closePrices = data.close_prices || [];
                const futurePrices = data.future_prices || [];

                const labels = [
                    ...(data.history_labels || []),
                    ...(data.future_labels || [])
                ];

                const predictionData = [
                    ...new Array(closePrices.length).fill(null),
                    ...futurePrices
                ];

                new Chart(ctx, {
                    type: "line",
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                data: closePrices,
                                borderColor: "#00ffae",
                                backgroundColor: "rgba(0,255,174,0.1)",
                                fill: true,
                                tension: 0.4,
                                pointRadius: 0
                            },
                            {
                                data: predictionData,
                                borderColor: "#ff9800",
                                borderDash: [6, 6],
                                tension: 0.4,
                                pointRadius: 0
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: { x: { display: false }, y: { display: false } }
                    }
                });

            })
            .catch(err => console.error("Mini chart error:", err));
    });


    /* ===============================
       5. MAIN BIG CHART
    =============================== */
    let mainChart;
    let currentRange = "7D";

    function loadMainChart(symbol, range = "7D") {

        symbol = symbol.trim().toUpperCase();

        fetch(`/FYP/api/stock-prediction/?symbol=${symbol}&range=${range}`)
            .then(res => {
                if (!res.ok) throw new Error("API error");
                return res.json();
            })
            .then(data => {

                const closePrices = data.close_prices || [];
                const futurePrices = data.future_prices || [];

                const labels = [
                    ...(data.history_labels || []),
                    ...(data.future_labels || [])
                ];

                const predictionData = [
                    ...new Array(closePrices.length).fill(null),
                    ...futurePrices
                ];

                if (mainChart) mainChart.destroy();

                const ctx = document.getElementById("lineChart");

                mainChart = new Chart(ctx, {
                    type: "line",
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: "Real Price",
                                data: closePrices,
                                borderColor: "#00ffae",
                                backgroundColor: "rgba(0,255,174,0.15)",
                                fill: true,
                                tension: 0.4
                            },
                            {
                                label: "Prediction",
                                data: predictionData,
                                borderColor: "#ff9800",
                                borderDash: [6, 6],
                                tension: 0.4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false
                    }
                });

                const title = document.getElementById("chartTitle");
                if (title) title.innerText = symbol + " Chart";

            })
            .catch(err => console.error("Main chart error:", err));
    }

    // Load default chart
    const urlParams = new URLSearchParams(window.location.search);
    const symbol = (urlParams.get("symbol") || "AAPL").trim().toUpperCase();

    loadMainChart(symbol, "7D");


    /* ===============================
       6. RANGE BUTTONS
    =============================== */
    document.querySelectorAll(".chart-buttons button").forEach(btn => {

        btn.addEventListener("click", function () {

            document.querySelectorAll(".chart-buttons button")
                .forEach(b => b.classList.remove("active"));

            this.classList.add("active");

            currentRange = this.dataset.range;

            loadMainChart(symbol, currentRange);
        });
    });


    /* ===============================
       7. DONUT CHART
    =============================== */
    const donutCanvas = document.getElementById("donutChart");

    if (donutCanvas) {

        new Chart(donutCanvas, {
            type: "doughnut",
            data: {
                labels: ["BTC", "ETH", "USDT"],
                datasets: [{
                    data: [763.51, 677.52, 57.76],
                    backgroundColor: ["#f7931a","#627eea","#26a17b"],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "70%",
                plugins: { legend: { display: false } }
            }
        });
    }


    /* ===============================
       8. BAR CHART (6 MONTH P/L)
    =============================== */
    const barCanvas = document.getElementById("barChart");

if (barCanvas) {

    fetch(`/FYP/api/stock-6month/?symbol=${symbol}`)
        .then(res => res.json())
        .then(data => {

            new Chart(barCanvas, {
                type: "bar",
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: symbol + " (6M)",
                        data: data.data,
                        backgroundColor: data.data.map((v, i, arr) =>
                            i > 0 && v > arr[i-1] ? "#22c55e" : "#ef4444"
                        )
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });

        })
        .catch(err => console.error("Bar chart error:", err));
}

});
document.addEventListener("DOMContentLoaded", function() {
    const priceInput = document.getElementById("trade_price");
    if (priceInput) {
        priceInput.addEventListener("input", updateTotal);
    }
});