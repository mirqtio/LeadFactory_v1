#!/usr/bin/env python3
"""Load geo and vertical features into production database"""
import pandas as pd
from database.session import SessionLocal
from database.models import GeoFeatures, VerticalFeatures
from decimal import Decimal

# Load and insert geo features
session = SessionLocal()
try:
    # Geo features
    df = pd.read_csv('/tmp/geo_features.csv')
    df = df.fillna(0)
    
    for _, row in df.iterrows():
        geo = GeoFeatures(
            zip=str(row['zip'])[:5],
            pop=int(row['pop']) if row['pop'] else None,
            bb_adoption_pct=Decimal(str(row['bb_adoption_pct'])) if row['bb_adoption_pct'] else None,
            house_value_med=int(row['house_value_med']) if row['house_value_med'] else None,
            income_household_med=int(row['income_household_med']) if row['income_household_med'] else None,
            unemployment_rate=Decimal(str(row['unemployment_rate'])) if row['unemployment_rate'] and row['unemployment_rate'] != -6666666.66 else None,
            num_establishments=int(row['num_establishments']) if row['num_establishments'] else None,
            pop_density=Decimal(str(row['pop_density'])) if row['pop_density'] else None,
            affluence=Decimal(str(row['affluence'])) if row['affluence'] and abs(row['affluence']) < 1000000 else None,
            growth_rate=Decimal(str(row['growth_rate'])) if row['growth_rate'] else None
        )
        session.merge(geo)
    
    session.commit()
    geo_count = session.query(GeoFeatures).count()
    print(f'Loaded {geo_count} geo features')
    
    # Vertical features
    df = pd.read_csv('/tmp/vertical_features_raw_yelp.csv')
    df = df.fillna('')
    
    for _, row in df.iterrows():
        vert = VerticalFeatures(
            category_primary=row['category_primary'],
            review_count_p10=int(row['review_count_p10']) if row['review_count_p10'] else None,
            review_count_p20=int(row['review_count_p20']) if row['review_count_p20'] else None,
            review_count_p40=int(row['review_count_p40']) if row['review_count_p40'] else None,
            review_count_p50=int(row['review_count_p50']) if row['review_count_p50'] else None,
            review_count_p60=int(row['review_count_p60']) if row['review_count_p60'] else None,
            review_count_p80=int(row['review_count_p80']) if row['review_count_p80'] else None,
            review_count_p90=int(row['review_count_p90']) if row['review_count_p90'] else None,
            is_target=bool(row['is_target']) if 'is_target' in row else False,
            alias=row['alias'].split(',') if row['alias'] else [],
            parent_alias=row['parent_alias'].split(',') if row['parent_alias'] else []
        )
        session.merge(vert)
    
    session.commit()
    vert_count = session.query(VerticalFeatures).count()
    print(f'Loaded {vert_count} vertical features')
    
except Exception as e:
    print(f'Error: {e}')
    session.rollback()
finally:
    session.close()