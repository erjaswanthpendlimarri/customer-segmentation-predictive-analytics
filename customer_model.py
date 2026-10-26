
import os
import pandas as pd
import pymysql

from pathlib import Path
from dotenv import load_dotenv
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Load .env from the project folder
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)


def get_customer_segments():
    connection = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "ecommerce_bi"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

    try:
        query = """
            SELECT
                c.customer_id,
                c.customer_name,
                c.region,
                COUNT(DISTINCT o.order_id) AS frequency,
                COALESCE(SUM(
                    oi.quantity * oi.unit_price
                    - COALESCE(oi.discount_amount, 0)
                    - COALESCE(oi.return_amount, 0)
                ), 0) AS monetary,
                DATEDIFF(
                    (SELECT MAX(order_date) FROM orders),
                    MAX(o.order_date)
                ) AS recency_days
            FROM customers c
            LEFT JOIN orders o
                ON c.customer_id = o.customer_id
                AND LOWER(o.order_status) NOT IN ('cancelled', 'canceled')
            LEFT JOIN order_items oi
                ON o.order_id = oi.order_id
            GROUP BY
                c.customer_id,
                c.customer_name,
                c.region
            ORDER BY c.customer_id
        """

        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        df = pd.DataFrame(rows)

        if df.empty:
            return []

        features = ["recency_days", "frequency", "monetary"]

        for column in features:
            df[column] = pd.to_numeric(
                df[column], errors="coerce"
            ).fillna(0)

        if len(df) < 3:
            raise ValueError("At least 3 customer records are needed.")

        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(df[features])

        model = KMeans(
            n_clusters=3,
            random_state=42,
            n_init=10
        )

        df["cluster"] = model.fit_predict(scaled_features)

        summary = df.groupby("cluster")[features].mean()

        summary["engagement_score"] = (
            summary["frequency"].rank(pct=True)
            + summary["monetary"].rank(pct=True)
            + (1 - summary["recency_days"].rank(pct=True))
        )

        ranked_clusters = summary["engagement_score"].sort_values(
            ascending=False
        ).index.tolist()

        labels = [
            "High Engagement",
            "Medium Engagement",
            "Low Engagement"
        ]

        cluster_names = dict(zip(ranked_clusters, labels))
        df["segment"] = df["cluster"].map(cluster_names)

        return df[
            [
                "customer_id",
                "customer_name",
                "region",
                "recency_days",
                "frequency",
                "monetary",
                "cluster",
                "segment"
            ]
        ].to_dict(orient="records")

    finally:
        connection.close()


if __name__ == "__main__":
    try:
        customers = get_customer_segments()

        print("\nCUSTOMER SEGMENTATION - K-MEANS")
        print("-" * 60)

        for customer in customers:
            print(
                f"{customer['customer_name']} | "
                f"Recency: {customer['recency_days']} days | "
                f"Orders: {customer['frequency']} | "
                f"Spending: ₹{customer['monetary']:.2f} | "
                f"Segment: {customer['segment']}"
            )

        print(f"\nTotal customers analyzed: {len(customers)}")

    except Exception as error:
        print("Customer model failed:", error)
