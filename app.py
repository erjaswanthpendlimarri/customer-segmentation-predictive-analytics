
import os
from datetime import date
from decimal import Decimal
from io import BytesIO
from contextlib import contextmanager

import pandas as pd
import numpy as np
import pymysql
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


# =========================================================
# DATABASE CONNECTION
# =========================================================

@contextmanager
def db_connection():
    conn = None

    try:
        conn = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "ecommerce_bi"),
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=5
        )

        yield conn

    finally:
        if conn is not None:
            conn.close()


# =========================================================
# DATE FILTER VALIDATION
# =========================================================

def get_date_filters():
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()

    try:
        start_date = date.fromisoformat(start) if start else None
        end_date = date.fromisoformat(end) if end else None
    except ValueError:
        raise ValueError("Invalid date. Use the YYYY-MM-DD format.")

    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date cannot be later than end date.")

    return start_date, end_date


# =========================================================
# FETCH SALES DATA
# =========================================================

def fetch_data(start_date=None, end_date=None):
    sql = """
        SELECT
            o.order_id,
            DATE(o.order_date) AS order_date,
            o.order_status,
            o.region,
            oi.item_id,
            oi.product_id,
            p.product_name,
            p.category,
            oi.quantity,
            oi.unit_price,
            COALESCE(oi.discount_amount, 0) AS discount_amount,
            COALESCE(oi.return_amount, 0) AS return_amount
        FROM orders o
        INNER JOIN order_items oi
            ON oi.order_id = o.order_id
        INNER JOIN products p
            ON p.product_id = oi.product_id
        WHERE LOWER(o.order_status)
            NOT IN ('cancelled', 'canceled')
    """

    params = []

    if start_date:
        sql += " AND DATE(o.order_date) >= %s"
        params.append(start_date)

    if end_date:
        sql += " AND DATE(o.order_date) <= %s"
        params.append(end_date)

    sql += " ORDER BY o.order_date"

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    df = pd.DataFrame(rows)

    if not df.empty:
        numeric_columns = [
            "quantity",
            "unit_price",
            "discount_amount",
            "return_amount"
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column], errors="coerce"
            ).fillna(0)

        df["gross_sales"] = (
            df["quantity"] * df["unit_price"]
        )

        df["net_sales"] = (
            df["gross_sales"]
            - df["discount_amount"]
            - df["return_amount"]
        )

        df["order_date"] = pd.to_datetime(
            df["order_date"], errors="coerce"
        )

        df = df.dropna(subset=["order_date"])

    return df


# =========================================================
# KPI CALCULATIONS
# =========================================================

def money(value):
    if value is None or pd.isna(value):
        return 0.0

    if isinstance(value, Decimal):
        value = float(value)

    return round(float(value), 2)


def calculate_kpis(df):
    if df.empty:
        return {
            "gross_sales": 0,
            "net_sales": 0,
            "order_count": 0,
            "aov": 0
        }

    gross_sales = df["gross_sales"].sum()
    net_sales = df["net_sales"].sum()
    order_count = int(df["order_id"].nunique())

    aov = net_sales / order_count if order_count else 0

    return {
        "gross_sales": money(gross_sales),
        "net_sales": money(net_sales),
        "order_count": order_count,
        "aov": money(aov)
    }


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


# =========================================================
# DASHBOARD API
# =========================================================

@app.route("/api/dashboard")
def dashboard_api():
    try:
        start, end = get_date_filters()
        df = fetch_data(start, end)

        kpis = calculate_kpis(df)

        if df.empty:
            return jsonify({
                "kpis": kpis,
                "monthly": [],
                "categories": [],
                "regions": [],
                "growth": None,
                "message": "No eligible sales found for this date range."
            })

        # Monthly revenue
        monthly_df = df.copy()

        monthly_df["month"] = (
            monthly_df["order_date"]
            .dt.to_period("M")
            .astype(str)
        )

        monthly = (
            monthly_df.groupby("month", as_index=False)["net_sales"]
            .sum()
            .sort_values("month")
        )

        monthly_data = [
            {
                "month": row["month"],
                "revenue": money(row["net_sales"])
            }
            for _, row in monthly.iterrows()
        ]

        # Category revenue
        category_df = (
            df.groupby("category", dropna=False, as_index=False)["net_sales"]
            .sum()
            .sort_values("net_sales", ascending=False)
        )

        categories = [
            {
                "category": (
                    str(row["category"])
                    if pd.notna(row["category"])
                    else "Uncategorized"
                ),
                "revenue": money(row["net_sales"])
            }
            for _, row in category_df.iterrows()
        ]

        # Regional revenue
        region_df = (
            df.groupby("region", dropna=False, as_index=False)["net_sales"]
            .sum()
            .sort_values("net_sales", ascending=False)
        )

        regions = [
            {
                "region": (
                    str(row["region"])
                    if pd.notna(row["region"])
                    else "Not specified"
                ),
                "revenue": money(row["net_sales"])
            }
            for _, row in region_df.iterrows()
        ]

        # Growth: latest month compared with previous month
        growth = None

        if len(monthly) >= 2:
            previous = float(monthly.iloc[-2]["net_sales"])
            current = float(monthly.iloc[-1]["net_sales"])

            if previous != 0:
                growth = round(
                    ((current - previous) / abs(previous)) * 100,
                    2
                )

        return jsonify({
            "kpis": kpis,
            "monthly": monthly_data,
            "categories": categories,
            "regions": regions,
            "growth": growth,
            "message": ""
        })

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        app.logger.exception("Dashboard query failed")

        return jsonify({
            "error": "Unable to load dashboard data.",
            "hint": (
                "Check that MySQL is running, the ecommerce_bi "
                "database and tables exist, and your .env settings are correct."
            )
        }), 500


# =========================================================
# CHART STYLING
# =========================================================

BG_COLOR = "#0b1020"
PANEL_COLOR = "#11192f"
TEXT_COLOR = "#e2e8f0"
MUTED_COLOR = "#94a3b8"
GRID_COLOR = "#334155"

PURPLE = "#a78bfa"
CYAN = "#22d3ee"
BLUE = "#60a5fa"
PINK = "#fb7185"
GREEN = "#34d399"


def style_axes(ax):
    ax.set_facecolor(PANEL_COLOR)

    ax.tick_params(
        axis="both",
        colors=MUTED_COLOR,
        labelsize=9
    )

    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.title.set_color(TEXT_COLOR)

    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)

    ax.grid(
        axis="y",
        color=GRID_COLOR,
        linestyle="--",
        linewidth=0.7,
        alpha=0.55
    )

    ax.set_axisbelow(True)


# =========================================================
# CHART IMAGE ENDPOINTS
# =========================================================

@app.route("/chart/<chart_type>")
def chart(chart_type):
    if chart_type not in {"monthly", "category", "region"}:
        return jsonify({"error": "Unknown chart type"}), 404

    fig = None

    try:
        start, end = get_date_filters()
        df = fetch_data(start, end)

        fig, ax = plt.subplots(
            figsize=(8, 3.5),
            dpi=130
        )

        fig.patch.set_facecolor(BG_COLOR)
        ax.set_facecolor(PANEL_COLOR)

        if df.empty:
            ax.text(
                0.5,
                0.5,
                "No data for selected period",
                ha="center",
                va="center",
                color=MUTED_COLOR,
                fontsize=12,
                transform=ax.transAxes
            )

            ax.set_axis_off()

        elif chart_type == "monthly":
            temp = df.copy()

            temp["month"] = (
                temp["order_date"]
                .dt.to_period("M")
                .astype(str)
            )

            grouped = (
                temp.groupby("month")["net_sales"]
                .sum()
                .sort_index()
            )

            ax.plot(
                grouped.index,
                grouped.values,
                color=CYAN,
                marker="o",
                markerfacecolor=PURPLE,
                markeredgecolor="#ffffff",
                markeredgewidth=1.2,
                linewidth=2.8,
                markersize=6
            )

            # Soft area below the revenue line
            ax.fill_between(
                range(len(grouped)),
                grouped.values,
                color=CYAN,
                alpha=0.10
            )

            ax.set_xticks(range(len(grouped)))
            ax.set_xticklabels(
                grouped.index,
                rotation=30,
                ha="right"
            )

            ax.set_title(
                "Revenue Trend",
                loc="left",
                fontsize=14,
                fontweight="bold",
                pad=14
            )

            ax.set_ylabel("Net sales (₹)", fontsize=9)
            ax.set_xlabel("Month", fontsize=9)

            style_axes(ax)

            ax.grid(
                axis="x",
                visible=False
            )

        elif chart_type == "category":
            grouped = (
                df.groupby("category")["net_sales"]
                .sum()
                .sort_values()
            )

            labels = [
                str(label) if pd.notna(label) else "Uncategorized"
                for label in grouped.index
            ]

            colors = [
                PURPLE if i % 3 == 0
                else CYAN if i % 3 == 1
                else BLUE
                for i in range(len(grouped))
            ]

            bars = ax.barh(
                labels,
                grouped.values,
                color=colors,
                edgecolor="none",
                height=0.58
            )

            ax.bar_label(
                bars,
                fmt="₹%.0f",
                padding=5,
                color=TEXT_COLOR,
                fontsize=8
            )

            ax.set_title(
                "Net Sales by Category",
                loc="left",
                fontsize=14,
                fontweight="bold",
                pad=14
            )

            ax.set_xlabel("Net sales (₹)", fontsize=9)

            style_axes(ax)
            ax.grid(axis="y", visible=False)
            ax.grid(axis="x", color=GRID_COLOR, alpha=0.45)

        elif chart_type == "region":
            grouped = (
                df.groupby("region", dropna=False)["net_sales"]
                .sum()
                .sort_values()
            )

            labels = [
                str(label) if pd.notna(label) else "Not specified"
                for label in grouped.index
            ]

            colors = [
                CYAN if i % 2 == 0 else BLUE
                for i in range(len(grouped))
            ]

            bars = ax.barh(
                labels,
                grouped.values,
                color=colors,
                edgecolor="none",
                height=0.58
            )

            ax.bar_label(
                bars,
                fmt="₹%.0f",
                padding=5,
                color=TEXT_COLOR,
                fontsize=8
            )

            ax.set_title(
                "Net Sales by Region",
                loc="left",
                fontsize=14,
                fontweight="bold",
                pad=14
            )

            ax.set_xlabel("Net sales (₹)", fontsize=9)

            style_axes(ax)
            ax.grid(axis="y", visible=False)
            ax.grid(axis="x", color=GRID_COLOR, alpha=0.45)

        ax.margins(x=0.12)
        fig.tight_layout(pad=2)

        image = BytesIO()

        fig.savefig(
            image,
            format="png",
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
            dpi=130
        )

        image.seek(0)

        return send_file(
            image,
            mimetype="image/png",
            max_age=0
        )

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        app.logger.exception("Chart generation failed")

        return jsonify({
            "error": "Unable to generate chart. Check database configuration."
        }), 500

    finally:
        if fig is not None:
            plt.close(fig)


# =========================================================
# RULE-BASED CUSTOMER SEGMENTATION
# =========================================================

@app.route("/api/customer-segments")
def customer_segments_api():
    try:
        sql = """
            SELECT
                c.customer_id,
                c.customer_name,
                c.region,
                o.order_id,
                o.order_date,
                oi.quantity,
                oi.unit_price,
                COALESCE(oi.discount_amount, 0) AS discount_amount,
                COALESCE(oi.return_amount, 0) AS return_amount
            FROM customers c
            LEFT JOIN orders o
                ON o.customer_id = c.customer_id
                AND LOWER(o.order_status)
                    NOT IN ('cancelled', 'canceled')
            LEFT JOIN order_items oi
                ON oi.order_id = o.order_id
            ORDER BY c.customer_id
        """

        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

        if not rows:
            return jsonify({
                "customers": [],
                "total_customers": 0,
                "message": "No customers found."
            })

        df = pd.DataFrame(rows)

        df["order_date"] = pd.to_datetime(
            df["order_date"],
            errors="coerce"
        )

        for column in [
            "quantity",
            "unit_price",
            "discount_amount",
            "return_amount"
        ]:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            ).fillna(0)

        df["net_sales"] = (
            df["quantity"] * df["unit_price"]
            - df["discount_amount"]
            - df["return_amount"]
        )

        today = pd.Timestamp(date.today())
        customers = []

        for customer_id, group in df.groupby(
            "customer_id",
            sort=True
        ):
            valid_orders = group.dropna(
                subset=["order_id", "order_date"]
            )

            frequency = int(
                valid_orders["order_id"].nunique()
            )

            monetary = money(
                group["net_sales"].sum()
            )

            if frequency:
                last_date = valid_orders["order_date"].max()

                recency = max(
                    0,
                    (today - last_date.normalize()).days
                )
            else:
                recency = None

            if frequency == 0:
                segment = "No Purchases"

            elif recency <= 30 and frequency >= 3:
                segment = "Champions"

            elif frequency >= 2 and recency >= 90:
                segment = "At Risk"

            elif frequency >= 2:
                segment = "Loyal Customers"

            elif recency <= 30:
                segment = "New Customers"

            else:
                segment = "Needs Attention"

            customers.append({
                "customer_id": int(customer_id),
                "customer_name": str(
                    group["customer_name"].iloc[0]
                ),
                "region": str(
                    group["region"].iloc[0] or "Not specified"
                ),
                "recency_days": recency,
                "frequency": frequency,
                "monetary": monetary,
                "segment": segment
            })

        return jsonify({
            "customers": customers,
            "total_customers": len(customers),
            "message": (
                "Rule-based RFM segmentation using order recency, "
                "purchase frequency, and monetary value. "
                "Results depend on the available demo data."
            )
        })

    except Exception:
        app.logger.exception("Customer segmentation failed")

        return jsonify({
            "error": "Unable to load customer segments."
        }), 500


# =========================================================
# DATABASE HEALTH CHECK
# =========================================================

@app.route("/health")
def health():
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                result = cur.fetchone()

        if not result or result.get("ok") != 1:
            raise RuntimeError("Database health check failed.")

        return jsonify({
            "status": "ok",
            "database": "connected"
        })

    except Exception:
        app.logger.exception("Database health check failed")

        return jsonify({
            "status": "error",
            "database": "disconnected"
        }), 500


# =========================================================
# MACHINE-LEARNING CUSTOMER SEGMENTATION
# =========================================================

from customer_model import get_customer_segments


@app.route("/api/ml-customer-segments")
def ml_customer_segments():
    try:
        customers = get_customer_segments()

        return jsonify({
            "success": True,
            "total_customers": len(customers),
            "customers": customers
        })

    except Exception:
        app.logger.exception(
            "Could not load ML customer segments"
        )

        return jsonify({
            "success": False,
            "message": "Unable to load ML customer segments"
        }), 500


# =========================================================
# ADVANCED ANALYTICS + DATE-FILTERED REPORTS
# =========================================================

@app.route("/api/date-report")
def date_report_api():
    try:
        start, end = get_date_filters()

        if not start or not end:
            return jsonify({
                "success": False,
                "error": "Both start and end dates are required."
            }), 400

        df = fetch_data(start, end)
        kpis = calculate_kpis(df)

        return jsonify({
            "success": True,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "kpis": kpis,
            "message": (
                "Report generated successfully."
                if not df.empty
                else "No eligible sales found for this date range."
            )
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception:
        app.logger.exception("Date-filtered report failed")
        return jsonify({
            "success": False,
            "error": "Unable to generate date-filtered report."
        }), 500


@app.route("/api/analytics")
def advanced_analytics_api():
    try:
        start, end = get_date_filters()
        df = fetch_data(start, end)

        if df.empty:
            return jsonify({
                "success": True,
                "start_date": start.isoformat() if start else None,
                "end_date": end.isoformat() if end else None,
                "kpis": calculate_kpis(df),
                "daily_sales": [],
                "top_products": [],
                "category_performance": [],
                "regional_performance": [],
                "message": "No eligible sales found for this date range."
            })

        # Daily sales trend
        daily_df = (
            df.groupby(df["order_date"].dt.strftime("%Y-%m-%d"))[
                ["gross_sales", "net_sales"]
            ]
            .sum()
            .reset_index()
        )

        daily_sales = [
            {
                "date": row["order_date"],
                "gross_sales": money(row["gross_sales"]),
                "net_sales": money(row["net_sales"])
            }
            for _, row in daily_df.iterrows()
        ]

        # Best-performing products by net sales
        product_df = (
            df.groupby("product_id", dropna=False)
            .agg(
                product_name=("product_name", "first"),
                units_sold=("quantity", "sum"),
                gross_sales=("gross_sales", "sum"),
                net_sales=("net_sales", "sum"),
                order_count=("order_id", "nunique")
            )
            .reset_index()
            .sort_values("net_sales", ascending=False)
            .head(10)
        )

        top_products = [
            {
                "product_id": (
                    int(row["product_id"])
                    if pd.notna(row["product_id"]) else None
                ),
                "product_name": str(row["product_name"]),
                "units_sold": int(row["units_sold"]),
                "gross_sales": money(row["gross_sales"]),
                "net_sales": money(row["net_sales"]),
                "order_count": int(row["order_count"])
            }
            for _, row in product_df.iterrows()
        ]

        # Category performance
        category_df = (
            df.groupby("category", dropna=False)
            .agg(
                net_sales=("net_sales", "sum"),
                gross_sales=("gross_sales", "sum"),
                units_sold=("quantity", "sum"),
                order_count=("order_id", "nunique")
            )
            .reset_index()
            .sort_values("net_sales", ascending=False)
        )

        category_performance = [
            {
                "category": (
                    str(row["category"])
                    if pd.notna(row["category"])
                    else "Uncategorized"
                ),
                "net_sales": money(row["net_sales"]),
                "gross_sales": money(row["gross_sales"]),
                "units_sold": int(row["units_sold"]),
                "order_count": int(row["order_count"])
            }
            for _, row in category_df.iterrows()
        ]

        # Regional performance
        region_df = (
            df.groupby("region", dropna=False)
            .agg(
                net_sales=("net_sales", "sum"),
                gross_sales=("gross_sales", "sum"),
                order_count=("order_id", "nunique")
            )
            .reset_index()
            .sort_values("net_sales", ascending=False)
        )

        regional_performance = [
            {
                "region": (
                    str(row["region"])
                    if pd.notna(row["region"])
                    else "Not specified"
                ),
                "net_sales": money(row["net_sales"]),
                "gross_sales": money(row["gross_sales"]),
                "order_count": int(row["order_count"])
            }
            for _, row in region_df.iterrows()
        ]

        return jsonify({
            "success": True,
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "kpis": calculate_kpis(df),
            "daily_sales": daily_sales,
            "top_products": top_products,
            "category_performance": category_performance,
            "regional_performance": regional_performance,
            "message": "Advanced analytics generated successfully."
        })

    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception:
        app.logger.exception("Advanced analytics query failed")
        return jsonify({
            "success": False,
            "error": "Unable to generate advanced analytics."
        }), 500


# =========================================================
# APPLICATION START
# =========================================================

from ai_insights import create_ai_blueprint

app.register_blueprint(create_ai_blueprint(db_connection))

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
