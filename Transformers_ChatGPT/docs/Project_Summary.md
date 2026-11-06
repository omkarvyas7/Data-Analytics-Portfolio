# Off-the-shelf NLP: project summary

Short version for someone who doesn't want to open the notebook.

## What I tried
Seven pretrained Hugging Face pipelines, plus GloVe and BERT word embeddings through Flair. All on short example sentences, no custom training.

## What came out
| Task | Result | Confidence |
|---|---|---|
| Sentiment | Positive and negative sentences both right | 0.999 |
| Zero-shot topic tagging | Picked "sports" over "politics" and "education" | 0.997 |
| Named entities | Tim Cook (person), Apple (company), San Jose (place) | 0.998+ |
| Question answering | "California" | 0.984 |
| Word meaning in context | BERT tells the two "bank"s apart, GloVe doesn't | n/a |

## Possible uses
Tagging free-text return reasons or customer comments, trending sentiment in feedback, and pulling product or place names out of support notes.

## Limits
These were a handful of test sentences, not a labeled business dataset. Before using any of this for real, I'd score it against a labeled sample and check precision and recall.
