# Retrieval evaluation (50 questions)

Retrieval over the full index with no filters. **debate** = a chunk from the expected debate, bill, speaker or dates; **strict** = that, and it also contains a verified key phrase (this tier favours keyword matching, so read both). With 50 questions, one question is 2 percentage points.

| Configuration | hit@1 | recall@5 | recall@10 | MRR@10 | P@5 | fact recall@8 | ms/query |
|---|---|---|---|---|---|---|---|
| **debate** | | | | | | | |
| dense | 46% | 70% | 82% | 0.572 | 41% | 96% | 346 |
| sparse | 46% | 76% | 84% | 0.581 | 46% | 98% | 3629 |
| hybrid | 48% | 72% | 82% | 0.592 | 45% | 98% | 3854 |
| hybrid+rerank | 42% | 76% | 84% | 0.557 | 44% | 98% | 6100 |
| **strict** | | | | | | | |
| dense | 42% | 66% | 82% | 0.537 | 36% | 96% | 346 |
| sparse | 44% | 74% | 80% | 0.561 | 40% | 98% | 3629 |
| hybrid | 42% | 72% | 80% | 0.553 | 42% | 98% | 3854 |
| hybrid+rerank | 36% | 74% | 82% | 0.513 | 38% | 98% | 6100 |

recall@k = share of questions with at least one relevant chunk in the top k. fact recall@8 = share of the key phrases present in the top 8 chunks (what the LLM sees).

## By domain (recall@5 / MRR@10, debate tier)

| domain | n | dense | sparse | hybrid | hybrid+rerank |
|---|---|---|---|---|---|
| finance_economy | 16 | 56% / 0.40 | 69% / 0.56 | 62% / 0.47 | 69% / 0.47 |
| foreign_relations | 16 | 69% / 0.61 | 69% / 0.50 | 69% / 0.57 | 69% / 0.56 |
| law_security | 18 | 83% / 0.69 | 89% / 0.67 | 83% / 0.72 | 89% / 0.63 |

## By Parliament (recall@5 / MRR@10, debate tier)

| parliament | n | dense | sparse | hybrid | hybrid+rerank |
|---|---|---|---|---|---|
| 43 | 14 | 79% / 0.62 | 86% / 0.61 | 86% / 0.71 | 79% / 0.57 |
| 44 | 21 | 71% / 0.53 | 71% / 0.59 | 71% / 0.52 | 81% / 0.61 |
| 45 | 15 | 60% / 0.58 | 73% / 0.54 | 60% / 0.58 | 67% / 0.47 |

## By question type (recall@5 / MRR@10, debate tier)

| type | n | dense | sparse | hybrid | hybrid+rerank |
|---|---|---|---|---|---|
| paraphrase | 8 | 62% / 0.64 | 62% / 0.53 | 62% / 0.62 | 62% / 0.48 |
| speaker | 2 | 0% / 0.00 | 50% / 0.25 | 0% / 0.08 | 50% / 0.12 |
| topic | 40 | 75% / 0.59 | 80% / 0.61 | 78% / 0.61 | 80% / 0.59 |

## Questions where hybrid+rerank found no relevant chunk in the top 10 (8)

- L43-05: How did opposition parties react to the 2020 ban on military-style rifles?
- M43-04: How did the opposition criticise the government's borrowing in the fall 2020 economic update?
- L44-06: What would the bill on critical cyber systems require telecom companies to do?
- F44-01: How did MPs respond to Russia's invasion of Ukraine?
- M44-01: What did Pierre Poilievre say about the carbon tax in the House?
- F45-02: What did MPs say about American duties on softwood lumber exports?
- M45-01: What did Conservatives say about the size of the deficit in the 2025 budget?
- M45-03: How does the groceries and essentials benefit work?

## Answer faithfulness (automatic checks on 10 generated answers)

- Answers with every citation number valid: 10/10
- Sentences or bullets carrying a citation: 57/64
- Quoted phrases found word for word in the cited excerpt: 86/92
- Answers saying the debates do not cover the question: 0/10

These checks cannot tell whether a cited excerpt really supports a claim. `eval/faithfulness_sample.md` lists every answer next to its sources for a manual read.

