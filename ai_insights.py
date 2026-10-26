
from flask import Blueprint, jsonify
from datetime import date, timedelta
import numpy as np
import pymysql


def create_ai_blueprint(db_connection):
    ai = Blueprint("ai_insights", __name__)

    def fetch_all(connection, query, params=None):
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()

    def get_daily_sales(connection):
        return fetch_all(
            connection,
            """
            SELECT
                DATE(o.order_date) AS sale_date,
                ROUND(SUM(
                    oi.quantity * oi.unit_price
                ), 2) AS gross_sales,
                ROUND(SUM(
                    oi.quantity * oi.unit_price
                    - COALESCE(oi.discount_amount, 0)
                    - COALESCE(oi.return_amount, 0)
                ), 2) AS net_sales
            FROM orders o
            INNER JOIN order_items oi
                ON oi.order_id = o.order_id
            WHERE LOWER(COALESCE(o.order_status, ''))
                NOT IN ('cancelled', 'canceled')
            GROUP BY DATE(o.order_date)
            ORDER BY DATE(o.order_date)
            """
        )

    def get_product_sales(connection):
        return fetch_all(
            connection,
            """
            SELECT
                p.product_name,
                ROUND(SUM(
                    oi.quantity * oi.unit_price
                    - COALESCE(oi.discount_amount, 0)
                    - COALESCE(oi.return_amount, 0)
                ), 2) AS net_sales,
                SUM(oi.quantity) AS units_sold
            FROM orders o
            JOIN order_items oi
                ON oi.order_id = o.order_id
            JOIN products p
                ON p.product_id = oi.product_id
            WHERE LOWER(COALESCE(o.order_status, ''))
                NOT IN ('cancelled', 'canceled')
            GROUP BY p.product_id, p.product_name
            ORDER BY net_sales DESC
            """
        )

    def get_region_sales(connection):
        return fetch_all(
            connection,
            """
            SELECT
                COALESCE(o.region, 'Unknown') AS region,
                ROUND(SUM(
                    oi.quantity * oi.unit_price
                    - COALESCE(oi.discount_amount, 0)
                    - COALESCE(oi.return_amount, 0)
                ), 2) AS net_sales,
                COUNT(DISTINCT o.order_id) AS order_count
            FROM orders o
            JOIN order_items oi
                ON oi.order_id = o.order_id
            WHERE LOWER(COALESCE(o.order_status, ''))
                NOT IN ('cancelled', 'canceled')
            GROUP BY COALESCE(o.region, 'Unknown')
            ORDER BY net_sales DESC
            """
        )

    def to_date(value):
        if isinstance(value, date):
            return value
        if hasattr(value, "date"):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        raise ValueError("Unexpected date value in sales data")

    def money(value):
        return round(float(value or 0), 2)

    def calculate_growth(recent, previous):
        if previous == 0:
            if recent == 0:
                return 0.0
            return None

        return (recent - previous) / abs(previous) * 100

    @ai.get("/api/ai-insights")
    def ai_insights():
        try:
            with db_connection() as connection:
                daily_rows = get_daily_sales(connection)
                products = get_product_sales(connection)
                regions = get_region_sales(connection)

            # Convert database results into a date-indexed dictionary.
            sales_by_date = {}

            for row in daily_rows:
                sale_date = to_date(row["sale_date"])
                sales_by_date[sale_date] = {
                    "gross": money(row["gross_sales"]),
                    "net": money(row["net_sales"])
                }

            if not sales_by_date:
                return jsonify({
                    "success": True,
                    "message": "No eligible sales records were found.",
                    "summary": {},
                    "daily_sales": [],
                    "forecast": [],
                    "anomalies": [],
                    "recommendations": [
                        "Add eligible order records to begin sales analysis."
                    ],
                    "top_products": [],
                    "regions": []
                })

            # Fill missing calendar days with zero sales.
            first_day = min(sales_by_date)
            last_day = max(sales_by_date)
            all_days = []
            current_day = first_day

            while current_day <= last_day:
                sales = sales_by_date.get(
                    current_day, {"gross": 0, "net": 0}
                )

                all_days.append({
                    "date": current_day.isoformat(),
                    "gross_sales": sales["gross"],
                    "net_sales": sales["net"]
                })

                current_day += timedelta(days=1)

            # Compare the latest seven calendar days against the
            # preceding seven calendar days.
            latest = all_days[-7:]
            previous = all_days[-14:-7]

            recent_total = money(
                sum(day["net_sales"] for day in latest)
            )
            previous_total = money(
                sum(day["net_sales"] for day in previous)
            )

            # Require 14 calendar days for a meaningful comparison.
            enough_history = len(all_days) >= 14

            if enough_history:
                growth = calculate_growth(
                    recent_total, previous_total
                )
            else:
                growth = None

            if not enough_history:
                trend = "Insufficient history"
            elif growth is None:
                trend = (
                    "Increasing"
                    if recent_total > 0
                    else "Insufficient history"
                )
            elif growth > 5:
                trend = "Increasing"
            elif growth < -5:
                trend = "Decreasing"
            else:
                trend = "Stable"

            # Detect unusual sales days using median absolute deviation.
            recent_days = all_days[-90:]
            values = np.array(
                [day["net_sales"] for day in recent_days],
                dtype=float
            )

            median = float(np.median(values))
            deviations = np.abs(values - median)
            mad = float(np.median(deviations))
            anomalies = []

            if mad > 0:
                for day in recent_days:
                    score = (
                        abs(day["net_sales"] - median)
                        / (1.4826 * mad)
                    )

                    if score >= 3.5:
                        anomalies.append({
                            "date": day["date"],
                            "net_sales": day["net_sales"],
                            "type": (
                                "Unusually high"
                                if day["net_sales"] > median
                                else "Unusually low"
                            ),
                            "score": round(float(score), 2)
                        })

            # Forecast seven days using a linear trend over up to
            # 30 calendar days. These are estimates, not guarantees.
            forecast = []
            forecast_history = all_days[-30:]

            y = np.array(
                [day["net_sales"] for day in forecast_history],
                dtype=float
            )

            if len(y) >= 3:
                x = np.arange(len(y), dtype=float)
                slope, intercept = np.polyfit(x, y, 1)

                for offset in range(1, 8):
                    predicted = max(
                        0.0,
                        float(
                            intercept + slope * (
                                len(y) + offset - 1
                            )
                        )
                    )

                    forecast.append({
                        "date": (
                            last_day + timedelta(days=offset)
                        ).isoformat(),
                        "predicted_net_sales": round(predicted, 2)
                    })

            # Prepare product and region results.
            top_products = [
                {
                    "product_name": product["product_name"],
                    "net_sales": money(product["net_sales"]),
                    "units_sold": int(product["units_sold"] or 0)
                }
                for product in products
            ]

            region_results = [
                {
                    "region": region["region"],
                    "net_sales": money(region["net_sales"]),
                    "order_count": int(region["order_count"] or 0)
                }
                for region in regions
            ]

            # Generate recommendations from actual recorded results.
            recommendations = []

            if trend == "Increasing":
                recommendations.append(
                    f"Net sales increased by {growth:.2f}% compared "
                    "with the preceding seven-day period. Identify "
                    "which products and regions contributed most."
                )
            elif trend == "Decreasing":
                recommendations.append(
                    f"Net sales decreased by {abs(growth):.2f}% "
                    "compared with the preceding seven-day period. "
                    "Review recent orders, discounts, returns, "
                    "pricing, and product availability."
                )
            elif trend == "Stable":
                recommendations.append(
                    "Net sales are broadly stable. Test a small, "
                    "measurable promotion and compare its results "
                    "with the preceding period."
                )
            else:
                recommendations.append(
                    "At least 14 calendar days of sales history are "
                    "needed for a seven-day trend comparison. "
                    "Treat early trends and forecasts cautiously."
                )

            if top_products:
                best = top_products[0]

                recommendations.append(
                    f"{best['product_name']} has the highest "
                    f"recorded net sales at "
                    f"₹{best['net_sales']:,.2f}, with "
                    f"{best['units_sold']} units sold. "
                    "Review its margin and stock availability "
                    "before planning promotions."
                )

                if len(top_products) >= 2:
                    lowest = min(
                        top_products,
                        key=lambda product: product["net_sales"]
                    )

                    recommendations.append(
                        f"Among the products returned by the analysis, "
                        f"{lowest['product_name']} has the lowest "
                        f"net sales at ₹{lowest['net_sales']:,.2f}. "
                        "Check its sales volume, pricing, and returns "
                        "before deciding whether to change its strategy."
                    )

            if region_results:
                best_region = region_results[0]

                recommendations.append(
                    f"{best_region['region']} leads recorded regional "
                    f"net sales at ₹{best_region['net_sales']:,.2f}, "
                    f"across {best_region['order_count']} orders. "
                    "Compare regional demand and delivery costs "
                    "before expanding."
                )

                if len(region_results) >= 2:
                    lowest_region = min(
                        region_results,
                        key=lambda region: region["net_sales"]
                    )

                    recommendations.append(
                        f"{lowest_region['region']} has the lowest "
                        "recorded net sales among the analyzed regions. "
                        "Review order counts, local demand, and "
                        "delivery coverage before taking action."
                    )

            if anomalies:
                recommendations.append(
                    f"The analysis detected {len(anomalies)} unusual "
                    "sales day(s). Check those dates for promotions, "
                    "bulk orders, missing records, or returns."
                )
            else:
                recommendations.append(
                    "No unusual sales days were detected by the "
                    "current statistical rule. This does not guarantee "
                    "that every sales pattern is normal."
                )

            return jsonify({
                "success": True,
                "summary": {
                    "trend": trend,
                    "recent_7_day_sales": recent_total,
                    "previous_7_day_sales": previous_total,
                    "growth_percent": (
                        round(growth, 2)
                        if growth is not None
                        else None
                    ),
                    "days_analyzed": len(all_days),
                    "latest_recorded_date": last_day.isoformat()
                },
                "daily_sales": all_days,
                "forecast": forecast,
                "anomalies": anomalies,
                "recommendations": recommendations,
                "top_products": top_products,
                "regions": region_results
            })

        except Exception:
            ai.logger.exception("AI insights calculation failed")
            return jsonify({
                "success": False,
                "message": (
                    "Unable to calculate AI insights. "
                    "Check the Flask terminal logs."
                )
            }), 500

    return ai
