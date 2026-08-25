DELETE FROM order_values_eur;

INSERT INTO order_values_eur (
    source_hash, order_id, customer_id, country, category, original_amount, original_currency,
    fx_reference_date, fx_rate_date_used, fx_rate_used, amount_eur, calculated_at
)
SELECT
    c.source_hash, c.order_id, c.customer_id, c.country, c.category, c.line_amount, c.currency,
    c.fx_reference_date,
    CASE WHEN c.currency = 'EUR' THEN c.fx_reference_date ELSE fx.rate_date END,
    CASE WHEN c.currency = 'EUR' THEN 1.0 ELSE fx.rate END,
    CASE WHEN c.currency = 'EUR' THEN c.line_amount ELSE c.line_amount * fx.rate END,
    CURRENT_TIMESTAMP
FROM orders_clean c
LEFT JOIN fx_rates fx
  ON fx.base_currency = c.currency
 AND fx.quote_currency = 'EUR'
 AND fx.rate_date = (
     SELECT MAX(candidate.rate_date)
     FROM fx_rates candidate
     WHERE candidate.base_currency = c.currency
       AND candidate.quote_currency = 'EUR'
       AND candidate.rate_date <= c.fx_reference_date
 );

DELETE FROM customer_spend_eur;

INSERT INTO customer_spend_eur (customer_id, total_spend_eur, order_count, last_refreshed_at)
SELECT customer_id, ROUND(SUM(amount_eur), 2), COUNT(*), CURRENT_TIMESTAMP
FROM order_values_eur
WHERE customer_id IS NOT NULL AND amount_eur IS NOT NULL
GROUP BY customer_id;

