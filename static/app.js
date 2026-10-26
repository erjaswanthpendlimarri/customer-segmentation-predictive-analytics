
"use strict";

/* =========================================================
   MARKETPULSE - E-COMMERCE BUSINESS INTELLIGENCE
   ========================================================= */

const API = {
    dashboard: "/api/dashboard",
    analytics: "/api/analytics",
    health: "/health"
};

let dailySalesChart = null;
let refreshInProgress = false;

const $ = id => document.getElementById(id);

function setText(id, value) {
    const element = $(id);
    if (element) element.textContent = value;
}

function money(value) {
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(Number(value) || 0);
}

function number(value) {
    return new Intl.NumberFormat("en-IN").format(Number(value) || 0);
}

function getValue(object, keys, fallback = 0) {
    for (const key of keys) {
        if (
            object &&
            object[key] !== undefined &&
            object[key] !== null &&
            object[key] !== ""
        ) {
            return object[key];
        }
    }
    return fallback;
}

async function getJSON(url) {
    const response = await fetch(url, {
        method: "GET",
        cache: "no-store",
        headers: { Accept: "application/json" }
    });

    if (!response.ok) {
        throw new Error(`${url} returned HTTP ${response.status}`);
    }

    return response.json();
}

function getDateParameters() {
    const params = new URLSearchParams();
    const start = $("start")?.value;
    const end = $("end")?.value;

    if (start) params.set("start_date", start);
    if (end) params.set("end_date", end);

    const query = params.toString();
    return query ? `?${query}` : "";
}

/* -------------------- DASHBOARD KPIs -------------------- */

function updateDashboard(data) {
    const stats = data.dashboard || data.kpis || data.data || data;

    const grossSales = Number(getValue(stats, [
        "gross_sales", "grossSales", "gross_revenue",
        "gross_revenue_total"
    ]));

    const netSales = Number(getValue(stats, [
        "net_sales", "netSales", "net_revenue",
        "total_net_sales"
    ]));

    const orderCount = Number(getValue(stats, [
        "order_count", "total_orders", "orders",
        "completed_orders"
    ]));

    const aov = Number(getValue(stats, [
        "aov", "average_order_value", "avg_order_value"
    ], orderCount ? netSales / orderCount : 0));

    const revenue = Number(getValue(stats, [
        "total_revenue", "revenue", "gross_sales",
        "gross_revenue"
    ], grossSales));

    setText("explore-revenue", money(revenue));
    setText("explore-orders", number(orderCount));
    setText("explore-aov", money(aov));
    setText("explore-net-sales", money(netSales));

    setText("gross", money(grossSales));
    setText("net", money(netSales));
    setText("orders", number(orderCount));
    setText("aov", money(aov));

    const growth = getValue(stats, [
        "growth", "growth_rate", "revenue_growth",
        "monthly_growth"
    ], null);

    if (growth !== null) {
        const value = Number(growth);
        const display = Number.isFinite(value)
            ? `${value > 0 ? "+" : ""}${value}%`
            : String(growth);

        setText("growth", `Revenue growth: ${display}`);
    } else {
        setText(
            "growth",
            "Monthly revenue comparison will appear when comparison data is available."
        );
    }

    setText(
        "updated",
        "Last updated: " +
        new Date().toLocaleTimeString("en-IN")
    );
}

/* -------------------- DATABASE STATUS -------------------- */

async function loadDatabaseStatus() {
    const status = $("db-status");
    if (!status) return;

    const dot = status.closest(".system-status")
        ?.querySelector(".status-dot");

    try {
        const data = await getJSON(API.health);

        const connected =
            data.status === "ok" ||
            data.status === "connected" ||
            data.database === "connected" ||
            data.success === true;

        status.textContent = connected
            ? "Connected"
            : "Check database";

        if (dot) {
            dot.style.background = connected ? "#34d399" : "#fb7185";
            dot.style.boxShadow = connected
                ? "0 0 12px rgba(52,211,153,.7)"
                : "0 0 12px rgba(251,113,133,.7)";
        }
    } catch (error) {
        console.error("Database health check failed:", error);
        status.textContent = "Connection unavailable";

        if (dot) {
            dot.style.background = "#fb7185";
            dot.style.boxShadow = "0 0 12px rgba(251,113,133,.7)";
        }
    }
}

/* -------------------- TABLE HELPERS -------------------- */

function normalizeRows(data, keys) {
    for (const key of keys) {
        if (Array.isArray(data?.[key])) return data[key];
    }
    return [];
}

function renderTable(id, rows, columns, emptyMessage) {
    const table = $(id);
    if (!table) return;

    table.replaceChildren();

    if (!Array.isArray(rows) || rows.length === 0) {
        const row = table.insertRow();
        const cell = row.insertCell();
        cell.colSpan = columns.length;
        cell.className = "empty-state";
        cell.textContent = emptyMessage;
        return;
    }

    rows.forEach(item => {
        const row = table.insertRow();

        columns.forEach(column => {
            const cell = row.insertCell();
            const value = column.value(item);
            cell.textContent = value == null ? "—" : String(value);
        });
    });
}

/* -------------------- DAILY SALES CHART -------------------- */

function updateDailySalesChart(rows) {
    const canvas = $("daily-sales-chart");

    if (!canvas || typeof Chart === "undefined") return;

    if (dailySalesChart) {
        dailySalesChart.destroy();
        dailySalesChart = null;
    }

    if (!rows.length) {
        const context = canvas.getContext("2d");
        if (context) {
            context.clearRect(0, 0, canvas.width, canvas.height);
        }
        return;
    }

    const labels = rows.map(row => getValue(row, [
        "date", "order_date", "day", "period"
    ], ""));

    const gross = rows.map(row => Number(getValue(row, [
        "gross_sales", "gross", "gross_revenue"
    ])));

    const net = rows.map(row => Number(getValue(row, [
        "net_sales", "net", "net_revenue", "sales"
    ])));

    dailySalesChart = new Chart(canvas, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Gross Sales",
                    data: gross,
                    borderColor: "#a78bfa",
                    backgroundColor: "rgba(167,139,250,.12)",
                    fill: true,
                    tension: 0.35,
                    borderWidth: 3,
                    pointRadius: 3
                },
                {
                    label: "Net Sales",
                    data: net,
                    borderColor: "#22d3ee",
                    backgroundColor: "rgba(34,211,238,.08)",
                    fill: true,
                    tension: 0.35,
                    borderWidth: 3,
                    pointRadius: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: "index"
            },
            plugins: {
                legend: {
                    labels: {
                        color: "#cbd5e1",
                        usePointStyle: true,
                        padding: 18
                    }
                },
                tooltip: {
                    callbacks: {
                        label: context =>
                            `${context.dataset.label}: ${money(context.raw)}`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(148,163,184,.10)" },
                    ticks: { color: "#94a3b8" }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: "rgba(148,163,184,.10)" },
                    ticks: {
                        color: "#94a3b8",
                        callback: value => money(value)
                    }
                }
            }
        }
    });
}

/* -------------------- ANALYTICS TABLES -------------------- */

function updateAnalytics(data) {
    const dailyRows = normalizeRows(data, [
        "daily", "daily_sales", "daily_trend", "daily_revenue"
    ]);

    const productRows = normalizeRows(data, [
        "top_products", "products", "best_products"
    ]);

    const categoryRows = normalizeRows(data, [
        "categories", "category_performance", "category_sales"
    ]);

    const regionRows = normalizeRows(data, [
        "regions", "regional_performance", "regional_sales"
    ]);

    const categoryChartRows = normalizeRows(data, [
        "category", "category_data", "category_revenue"
    ]);

    const regionChartRows = normalizeRows(data, [
        "region", "region_data", "region_revenue"
    ]);

    updateDailySalesChart(dailyRows);

    renderTable("top-products-table", productRows, [
        {
            value: row => getValue(row, [
                "product_name", "product", "name"
            ], "—")
        },
        {
            value: row => number(getValue(row, [
                "units_sold", "units", "quantity"
            ]))
        },
        {
            value: row => money(getValue(row, [
                "net_sales", "net_revenue", "sales", "revenue"
            ]))
        }
    ], "No product data available.");

    renderTable("analytics-category-table", categoryRows, [
        {
            value: row => getValue(row, [
                "category", "category_name", "name"
            ], "—")
        },
        {
            value: row => number(getValue(row, [
                "units_sold", "units", "quantity"
            ]))
        },
        {
            value: row => number(getValue(row, [
                "order_count", "orders", "total_orders"
            ]))
        },
        {
            value: row => money(getValue(row, [
                "net_sales", "net_revenue", "sales", "revenue"
            ]))
        }
    ], "No category data available.");

    renderTable("analytics-region-table", regionRows, [
        {
            value: row => getValue(row, [
                "region", "region_name", "name"
            ], "—")
        },
        {
            value: row => number(getValue(row, [
                "order_count", "orders", "total_orders"
            ]))
        },
        {
            value: row => money(getValue(row, [
                "net_sales", "net_revenue", "sales", "revenue"
            ]))
        }
    ], "No regional data available.");

    const categoryTotals = categoryChartRows.length
        ? categoryChartRows
        : categoryRows;

    const totalCategorySales = categoryTotals.reduce(
        (sum, row) => sum + Number(getValue(row, [
            "net_sales", "net_revenue", "sales", "revenue"
        ])),
        0
    );

    renderTable("category-table", categoryTotals.map(row => {
        const sales = Number(getValue(row, [
            "net_sales", "net_revenue", "sales", "revenue"
        ]));

        return {
            ...row,
            _displaySales: sales,
            _displayShare: totalCategorySales
                ? `${(sales / totalCategorySales * 100).toFixed(1)}%`
                : "0%"
        };
    }), [
        {
            value: row => getValue(row, [
                "category", "category_name", "name"
            ], "—")
        },
        {
            value: row => money(row._displaySales)
        },
        {
            value: row => row._displayShare
        }
    ], "No category performance data available.");

    showMessage(
        "analytics-message",
        `Analytics loaded: ${dailyRows.length} daily records, ` +
        `${productRows.length} products, ${categoryRows.length} categories ` +
        `and ${regionRows.length} regions.`
    );

    // Refresh charts only when their existing Flask URLs are available.
    if (categoryChartRows.length) {
        refreshChartImage("category-chart");
    }

    if (regionChartRows.length) {
        refreshChartImage("region-chart");
    }
}

function showMessage(id, message) {
    setText(id, message);
}

/* -------------------- FLASK CHART IMAGES -------------------- */

function refreshChartImage(id) {
    const image = $(id);
    if (!image) return;

    const source = image.getAttribute("src") || "";

    // Preserve the Flask-generated chart URL and its chart_type parameter.
    if (!source.startsWith("/")) return;

    const url = new URL(source, window.location.origin);
    url.searchParams.set("_refresh", Date.now());

    image.src = url.pathname + url.search;
}

/* -------------------- MAIN DASHBOARD LOADER -------------------- */

async function loadDashboard() {
    if (refreshInProgress) return;

    refreshInProgress = true;

    const refreshButton = $("refresh");
    if (refreshButton) refreshButton.disabled = true;

    try {
        const query = getDateParameters();

        const [dashboardResult, analyticsResult] =
            await Promise.allSettled([
                getJSON(API.dashboard + query),
                getJSON(API.analytics + query)
            ]);

        if (dashboardResult.status === "fulfilled") {
            const result = dashboardResult.value;

            if (result.success === false) {
                throw new Error(
                    result.message || "Dashboard data could not be loaded."
                );
            }

            updateDashboard(result);
        } else {
            console.error(
                "Dashboard API failed:",
                dashboardResult.reason
            );
            setText("updated", "Dashboard data unavailable");
        }

        if (analyticsResult.status === "fulfilled") {
            const result = analyticsResult.value;

            if (result.success === false) {
                showMessage(
                    "analytics-message",
                    result.message || "Analytics data could not be loaded."
                );
            } else {
                updateAnalytics(result);
            }
        } else {
            console.error(
                "Analytics API failed:",
                analyticsResult.reason
            );

            showMessage(
                "analytics-message",
                "Unable to load analytics. Check the /api/analytics endpoint."
            );
        }

        await loadDatabaseStatus();

        refreshChartImage("monthly-chart");
        refreshChartImage("category-chart");
        refreshChartImage("region-chart");

    } catch (error) {
        console.error("Dashboard loading error:", error);
        setText("updated", "Unable to refresh dashboard");
    } finally {
        refreshInProgress = false;
        if (refreshButton) refreshButton.disabled = false;
    }
}

/* -------------------- FILTERS -------------------- */

function applyFilters() {
    const start = $("start")?.value;
    const end = $("end")?.value;

    if (start && end && start > end) {
        alert("Start date must be earlier than or equal to the end date.");
        return;
    }

    loadDashboard();
}

/* -------------------- NAVIGATION -------------------- */

function setupNavigation() {
    const links = document.querySelectorAll(
        '.sidebar-nav a[href^="#"]'
    );

    links.forEach(link => {
        link.addEventListener("click", () => {
            links.forEach(item => item.classList.remove("active"));
            link.classList.add("active");
        });
    });
}

/* -------------------- STARTUP -------------------- */

document.addEventListener("DOMContentLoaded", () => {
    setupNavigation();

    $("refresh")?.addEventListener("click", loadDashboard);
    $("apply")?.addEventListener("click", applyFilters);

    loadDashboard();
});

window.loadDashboard = loadDashboard;
window.applyDashboardFilters = applyFilters;
