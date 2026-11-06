# Movie recommender: project summary

Written for a product or content lead who wants the short version.

## The question
Can we recommend movies with confidence, and where is the rating data too thin to trust?

## The numbers
| Measure | Value |
|---|---|
| Ratings analyzed | 100,836 |
| Users / movies | 610 / 9,724 |
| Movies with fewer than 10 ratings | 76.6% |
| Movies with 50+ ratings (used by the model) | 450 (4.6%) |
| Share of ratings from the 44 heaviest users | 40.2% |

## What it means
The model does well on popular titles. Ask it about The Godfather (1972) and the top answer is The Godfather: Part II (similarity 0.822). Most of the catalog can't be recommended this way yet because too few people have rated it. And a small group of very active users supplies a big chunk of the signal.

## Next steps
1. Use kNN suggestions for titles with 50+ ratings.
2. Use genre or popularity rules for the rest.
3. Prompt viewers to rate long-tail titles after watching, so coverage grows.
4. Track coverage each month (share of the catalog with 50+ ratings).

## Limits
This is a 610-user public sample, not live product data. Cosine similarity on raw ratings also ignores rater habits (some people score everything low, some everything high).
