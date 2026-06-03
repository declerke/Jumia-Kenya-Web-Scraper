/*
  mart_discount_leaders
  ----------------------
  Top 20 discounted products per category for the most recent scrape_date.

  Used by Superset "Discount Leaders" chart.
*/

WITH ranked AS (

    SELECT
        category,
        product_name,
        brand,
        current_price_kes,
        old_price_kes,
        discount_pct,
        price_delta_kes,
        product_url,
        scrape_date,
        ROW_NUMBER() OVER (
            PARTITION BY category
            ORDER BY discount_pct DESC NULLS LAST, price_delta_kes DESC NULLS LAST
        ) AS rank_in_category
    FROM {{ ref('fct_product_prices') }}
    WHERE
        discount_pct IS NOT NULL
        AND discount_pct > 0
        -- Only use the most recent scrape
        AND scrape_date = (SELECT MAX(scrape_date) FROM {{ ref('fct_product_prices') }})

)

SELECT
    category,
    rank_in_category,
    product_name,
    brand,
    current_price_kes,
    old_price_kes,
    discount_pct,
    price_delta_kes,
    product_url,
    scrape_date
FROM ranked
WHERE rank_in_category <= 20
ORDER BY category, rank_in_category
