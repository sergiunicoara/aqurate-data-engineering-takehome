DELETE FROM country_category_revenue;

INSERT INTO country_category_revenue (revenue_rank, country, total_revenue_eur, order_count, last_refreshed_at)
WITH country_totals AS (
    SELECT country, ROUND(SUM(amount_eur), 2) AS total_revenue_eur, COUNT(*) AS order_count
    FROM order_values_eur
    WHERE category IN ('Books', 'Electronics') AND amount_eur IS NOT NULL
    GROUP BY country
    HAVING SUM(amount_eur) > 40000
)
SELECT RANK() OVER (ORDER BY total_revenue_eur DESC), country, total_revenue_eur, order_count, CURRENT_TIMESTAMP
FROM country_totals;

