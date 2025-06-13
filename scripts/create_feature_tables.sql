-- Create geo_features table
CREATE TABLE IF NOT EXISTS geo_features (
    zip VARCHAR(5) PRIMARY KEY,
    pop INTEGER,
    bb_adoption_pct DECIMAL(5, 3),
    house_value_med INTEGER,
    income_household_med INTEGER,
    unemployment_rate DECIMAL(5, 2),
    num_establishments INTEGER,
    pop_density DECIMAL(10, 2),
    affluence DECIMAL(10, 2),
    growth_rate DECIMAL(5, 2)
);

-- Create vertical_features table
CREATE TABLE IF NOT EXISTS vertical_features (
    category_primary VARCHAR(100) PRIMARY KEY,
    review_count_p10 INTEGER,
    review_count_p20 INTEGER,
    review_count_p40 INTEGER,
    review_count_p50 INTEGER,
    review_count_p60 INTEGER,
    review_count_p80 INTEGER,
    review_count_p90 INTEGER,
    is_target BOOLEAN DEFAULT FALSE,
    alias TEXT[],
    parent_alias TEXT[]
);