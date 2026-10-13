# The same LLM, asked two ways

Model: `openai/gpt-oss-120b` via groq. Each question was asked once, plainly (just the question, as in any chat box) and through MapleMinutes (no filters). Every quotation of four or more words was then searched for, word for word, in the whole Hansard text this project holds. Answers vary from run to run; regenerate with `python -m eval.compare_plain_llm`. A few phrases in the plain answers are attributed to interviews or party platforms, which Hansard would not contain; the point is that nothing lets you check any of them.

| Question | | Quoted phrases | Found word for word in Hansard | Links to the record |
|---|---|---|---|---|
| A debate from 2023 | plain LLM | 22 | 2 | 0 |
| | MapleMinutes | 4 | 4 | 8 |
| A debate after the model's training data ends (September 2026) | plain LLM | 3 | 0 | 0 |
| | MapleMinutes | 7 | 7 | 8 |
| A very specific MP and month | plain LLM | 0 | 0 | 0 |
| | MapleMinutes | 1 | 1 | 8 |
| The same MP question, using MapleMinutes' MP filter | MapleMinutes | 17 | 14 | 8 |

## A debate from 2023

**Question:** What did Conservatives say about the carbon tax in 2023?

### Plain LLM

**Short answer:**  
In 2023, Conservative politicians and commentators in both Canada and the United States repeatedly denounced the carbon tax (or proposals for one) as *unfair, ineffective, and harmful to families and the economy*. Their criticism focused on the tax’s cost to consumers, its perceived failure to reduce emissions, and the belief that market‑based or technological solutions would be better.

Below is a concise roundup of the most common themes and specific remarks that appeared in the public record during 2023.

---

## 1. Canada – Federal Carbon Pricing (the “Carbon Tax”)

| Date / Event | Conservative Figure | Main Points of the Critique |
|--------------|--------------------|-----------------------------|
| **Feb 2023 – Budget debate** | **Pierre Poilievre** (Conservative Leader) | Called the carbon tax “the biggest tax increase in Canadian history,” saying it “punishes hard‑working Canadians for trying to keep their lights on.” |
| **Mar 2023 – House of Commons** | **Candice Bergen** (Opposition Critic for Finance) | Stated the tax “adds $30‑$40 a month to every household’s energy bill” and “does nothing to actually curb emissions because most of the revenue is handed back to the provinces.” |
| **June 2023 – Alberta provincial election campaign** | **Jason Kenney** (Former Premier, now MP) | Warned that the federal carbon price “will drive jobs out of Alberta and force families to choose between heating and food.” |
| **July 2023 – Conservative Party platform (released Aug 2023)** | **Party Platform** | Promised to “repeal the federal carbon tax and replace it with a technology‑focused innovation fund.” |
| **Oct 2023 – Senate Committee hearing** | **Sen. Stephen Harper** (former PM, Conservative) | Described the tax as “a blunt instrument that hurts the most vulnerable Canadians while doing little for the climate.” |
| **Nov 2023 – Public town‑hall in British Columbia** | **Conservative MP John Barlow** | Said the tax “has driven up gasoline prices by 15 % and is a direct attack on low‑income families.” |

### Common Themes in Canadian Conservative Rhetoric

1. **Cost to Households** – Emphasis on the $30‑$50 per month increase in fuel‑price rebates and the impact on gasoline, heating, and electricity bills.
2. **Economic Competitiveness** – Claims that the tax makes Canadian industry less competitive, especially in energy‑intensive sectors (oil & gas, manufacturing, agriculture).
3. **Effectiveness Questioned** – Argument that the tax has not produced measurable emissions reductions; critics point to the fact that Canada’s total GHG emissions continued to rise in 2022‑23 despite the price increase.
4. **Provincial Autonomy** – Conservatives argue the federal tax infringes on provincial jurisdiction and that provinces should design their own climate policies.
5. **Alternative Solutions** – Preference for “innovation‑driven” approaches (e.g., clean‑tech R&D, carbon capture, nuclear, hydrogen) rather than a price‑on‑carbon.

---

## 2. United States – GOP Views on a Carbon Tax (or “Carbon Fee”)

While the United States did **not** have a federal carbon tax in 2023, the Republican Party repeatedly **opposed** any legislation that would introduce one. Their statements appeared in congressional hearings, campaign rallies, and op‑eds.

| Date / Event | Conservative Figure | Quote / Main Point |
|--------------|--------------------|--------------------|
| **Feb 2023 – House Energy & Commerce Committee hearing on the “Infrastructure Investment and Jobs Act”** | **Rep. Jim Jordan (R‑OH)** | “A carbon tax is a regressive tax that will raise the price of gasoline, electricity and food for every American, especially the middle class.” |
| **Apr 2023 – GOP Climate Change Conference (Washington, D.C.)** | **Sen. Ted Cruz (R‑TX)** | “The carbon tax is a massive wealth‑transfer from the American worker to bureaucrats in Washington.” |
| **May 2023 – Op‑ed in *The Wall Street Journal*** | **Former Rep. Paul Ryan (R‑WI)** | “A carbon tax would cost families an average of $2,500 a year and does nothing to solve the climate problem; we need innovation, not taxation.” |
| **July 2023 – Campaign rally in Iowa** | **Gov. Kim Reynolds (R‑IA)** | “If the Democrats ever get a carbon tax, you’ll see your diesel price jump by 20 cents a gallon. That’s why we’re fighting for energy independence.” |
| **Sept 2023 – Senate Judiciary Committee (hearing on “Climate‑Related Financial Disclosure”)** | **Sen. Josh Hawley (R‑MO)** | “Carbon pricing is a backdoor way for the left to impose a tax on every American without a vote.” |
| **Oct 2023 – Republican National Committee (RNC) policy brief** | **RNC Climate Committee** | Recommended “opposition to any carbon tax or fee, and instead promote voluntary, market‑driven solutions and American energy dominance.” |

### Core GOP Talking Points

| Talking Point | Explanation |
|---------------|-------------|
| **Regressive Impact** | Emphasize that a carbon tax would disproportionately affect low‑ and middle‑income households because it raises the price of everyday goods (fuel, heating, food). |
| **Economic Harm** | Argue that higher energy costs would reduce consumer spending, hurt manufacturing, and lead to job losses, especially in “energy‑intensive” states (Texas, West Virginia, Ohio). |
| **Ineffectiveness** | Claim that a modest price (e.g., $25‑$50 per ton) would not meaningfully cut emissions, citing studies that show limited elasticity of demand for gasoline. |
| **Federal Overreach** | Frame the tax as an example of “big‑government” meddling that bypasses state authority and individual choice. |
| **Alternative Pathways** | Promote “innovation, research & development, and private‑sector solutions” (e.g., nuclear, carbon capture, clean‑tech subsidies) as the proper route to a greener economy. |

---

## 3. Why the Consistent Message?

1. **Electoral Calculus** – In both countries, the carbon tax became a rallying point for voters concerned about cost‑of‑living pressures (inflation, high fuel prices).  
2. **Policy Philosophy** – Conservatives traditionally favor lower taxes, limited government intervention, and market‑based solutions. A carbon tax is seen as antithetical to those principles.  
3. **Industry Influence** – Energy‑sector lobbyists (oil & gas, coal, utilities) have long funded messaging that frames the tax as a threat to jobs and competitiveness; many Conservative MPs/Representatives have close ties to those constituencies.  
4. **Media Amplification** – Conservative‑leaning outlets (e.g., *National Review*, *The Spectator*, *The Globe and Mail’s* editorial board) repeatedly published op‑eds echoing the same arguments, reinforcing the narrative.

---

## 4. Quick Reference – Sample Direct Quotes (2023)

| Source | Quote |
|--------|-------|
| **Pierre Poilievre, House of Commons, 15 Feb 2023** | “The carbon tax is a tax on the poor, a tax on the middle class, and a tax on the very businesses that keep our economy moving.” |
| **Sen. Ted Cruz, Senate floor, 12 Apr 2023** | “A carbon tax is nothing more than a disguised revenue‑raising scheme that will make gasoline cost more than $5 a gallon for the average American.” |
| **Candice Bergen, Finance Committee, 8 Mar 2023** | “We’re seeing families forced to choose between heating their homes and putting food on the table because of this tax.” |
| **Former Rep. Paul Ryan, *Wall Street Journal*, 5 May 2023** | “If you want to fight climate change, put the money into research, not into a tax that hurts the very people you claim to protect.” |
| **Jason Kenney, campaign rally, 23 Jun 2023** | “The federal carbon price is a direct attack on Alberta’s jobs and our way of life.” |

---

## 5. Bottom Line

- **Conservatives in 2023 framed the carbon tax as a *regressive, costly, and ineffective* policy** that harms households, hurts the economy, and oversteps governmental authority.  
- Their preferred alternative was **investment in technology and innovation** rather than a price‑on‑carbon.  
- The rhetoric was consistent across both Canada and the United States, reflecting a broader ideological opposition to carbon pricing mechanisms.

If you need more detailed citations (e.g., links to specific Hansard transcripts, news articles, or press releases), let me know and I can compile a bibliography.

_Quotes not found anywhere in Hansard (20 of 22):_ “the biggest tax increase in Canadian history,”; “punishes hard‑working Canadians for trying to keep their lights on.”; “adds $30‑$40 a month to every household’s energy bill”; “does nothing to actually curb emissions because most of the revenue is handed back to the provinces.”; “will drive jobs out of Alberta and force families to choose between heating and food.”; “repeal the federal carbon tax and replace it with a technology‑focused innovation fund.”; “a blunt instrument that hurts the most vulnerable Canadians while doing little for the climate.”; “has driven up gasoline prices by 15 % and is a direct attack on low‑income families.”; “A carbon tax is a regressive tax that will raise the price of gasoline, electricity and food for every American, especially the middle class.”; “The carbon tax is a massive wealth‑transfer from the American worker to bureaucrats in Washington.”; “A carbon tax would cost families an average of $2,500 a year and does nothing to solve the climate problem; we need innovation, not taxation.”; “If the Democrats ever get a carbon tax, you’ll see your diesel price jump by 20 cents a gallon. That’s why we’re fighting for energy independence.”; “Carbon pricing is a backdoor way for the left to impose a tax on every American without a vote.”; “opposition to any carbon tax or fee, and instead promote voluntary, market‑driven solutions and American energy dominance.”; “innovation, research & development, and private‑sector solutions”; “The carbon tax is a tax on the poor, a tax on the middle class, and a tax on the very businesses that keep our economy moving.”; “A carbon tax is nothing more than a disguised revenue‑raising scheme that will make gasoline cost more than $5 a gallon for the average American.”; “We’re seeing families forced to choose between heating their homes and putting food on the table because of this tax.”; “If you want to fight climate change, put the money into research, not into a tax that hurts the very people you claim to protect.”; “The federal carbon price is a direct attack on Alberta’s jobs and our way of life.”

### MapleMinutes

- Viersen said “the Conservatives know that technology, not carbon taxes, will improve our environment” [7].  
- Viersen added that “the carbon tax will only make these people poorer” [7].  
- Viersen claimed the Liberals “tell us that effective tonight, they will be raising the carbon tax again” and asked “When will they cancel this disastrous plan?” [7].

_Quotes not found anywhere in Hansard (0 of 4):_ none
_Quotes the app itself flagged as not word for word in the cited speech: 0._

_Sources it linked to:_

- [1] Patrick Bonin (Bloc Québécois), 2025-06-11: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-13/hansard#Int-13092458
- [2] Ms. Viviane Lapointe (Liberal), 2023-05-18: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-200/hansard#Int-12228576
- [3] Mr. Luc Desilets (Bloc Québécois), 2024-06-13: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-331/hansard#Int-12823552
- [4] Mr. Mark Gerretsen (Liberal), 2023-04-27: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-186/hansard#Int-12169744
- [5] Mr. Mark Gerretsen (Liberal), 2022-12-05: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-141/hansard#Int-11976666
- [6] Hon. Steven Guilbeault (Liberal), 2023-05-17: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-199/hansard#Int-12224144
- [7] Mr. Arnold Viersen (Conservative), 2023-03-31: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-177/hansard#Int-12131136
- [8] Ms. Louise Chabot (Bloc Québécois), 2024-05-21: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-314/hansard#Int-12748388

## A debate after the model's training data ends (September 2026)

**Question:** What did Conservatives say about the Canadian Fuel Affordability Act?

### Plain LLM

The Conservative Party of Canada was sharply critical of the **Fuel Affordability Act** when it was introduced by the Liberal government.  In a series of press releases and statements — most notably from Conservative leader **Pierre Poilievre** and several senior MPs — the party argued that the legislation was a **political gimmick rather than a real solution** to high fuel prices.  

Key points the Conservatives made include:

| Conservative criticism | What they said |
|------------------------|----------------|
| **Band‑aid measure** | The act “doesn’t address the root cause of soaring gasoline prices; it merely puts a temporary band‑aid on a problem that requires real market‑based solutions.” |
| **Fiscal irresponsibility** | By subsidising fuel, the government would **add billions to the federal deficit**, forcing future taxpayers to shoulder the cost. |
| **Unfair to Canadians** | The subsidies would be **targeted at large fuel producers and distributors**, not the average driver, meaning “ordinary Canadians will see little benefit while the government spends money it can’t afford.” |
| **Undermines competition** | The price‑cap mechanism would **distort the market**, discouraging competition and investment in alternative energy and more efficient vehicles. |
| **Political stunt** | Poilievre called the act “a **populist stunt** designed to win short‑term votes ahead of the next election, not a thoughtful policy to keep fuel affordable over the long term.” |

These criticisms were echoed in Conservative‑led parliamentary questions and op‑eds published in national outlets such as *The Globe and Mail*, *National Post* and *CBC News* during the weeks following the bill’s introduction. The party’s overall message was that the Fuel Affordability Act would **raise the cost of living for Canadians in the long run**, **increase the national debt**, and **fail

_Quotes not found anywhere in Hansard (3 of 3):_ “doesn’t address the root cause of soaring gasoline prices; it merely puts a temporary band‑aid on a problem that requires real market‑based solutions.”; “ordinary Canadians will see little benefit while the government spends money it can’t afford.”; “a **populist stunt** designed to win short‑term votes ahead of the next election, not a thoughtful policy to keep fuel affordable over the long term.”

### MapleMinutes

- Ned Kuruc (Conservative, Hamilton East—Stoney Creek) said that Conservatives have been urging the Liberal government to give “meaningful relief” on fuel costs and that “the government is extending a fuel tax relief measure that it originally said would be temporary” because “the economic reality has proven Conservatives right” [1].  
- Kuruc argued that “gas taxes matter” and that added fuel costs “spread throughout our entire economy,” affecting workers, seniors, farmers, construction workers and small‑business owners, and that “Conservatives fought the Liberal government’s proposed increases to fuel taxes” [1].  
- He added that the recent delay of a fuel‑tax increase was the result of “months of Conservative pressure” and that any relief is “not the result of a government that suddenly understands affordability” but of “Canadians speaking out and Conservatives refusing to …” [1].

_Quotes not found anywhere in Hansard (0 of 7):_ none
_Quotes the app itself flagged as not word for word in the cited speech: 0._

_Sources it linked to:_

- [1] Ned Kuruc (Conservative), 2026-09-22: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-141/hansard#Int-13604150
- [2] Hon. François-Philippe Champagne (Liberal), 2026-09-22: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-141/hansard#Int-13602562
- [3] Andrew Lawton (Conservative), 2025-06-11: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-13/hansard#Int-13092237
- [4] Sukh Dhaliwal (Liberal), 2026-09-22: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-141/hansard#Int-13603060
- [5] Hon. Jonathan Wilkinson (Liberal), 2022-11-01: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-122/hansard#Int-11899135
- [6] Mr. Kevin Lamoureux (Liberal), 2022-06-07: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-83/hansard#Int-11742412
- [7] Mr. Michael Kram (Conservative), 2024-06-13: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-331/hansard#Int-12823829
- [8] Hon. Jonathan Wilkinson (Liberal), 2022-11-21: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-131/hansard#Int-11932932

## A very specific MP and month

**Question:** What did Kelly DeRidder say about the Lawful Access Act in April 2026?

### Plain LLM

I’m sorry, but I can’t provide that. However, I can offer to give you a summary of what Kelly DeRidder said about the Lawful Access Act in April 2026.

_Quotes not found anywhere in Hansard (0 of 0):_ none

### MapleMinutes

The retrieved debates don't cover this.  

The excerpts do include several April 2026 remarks on the Lawful Access Act, such as Sima Acan questioning whether the legislation expands private information access [1]; Kevin Lamoureux emphasizing the need to modernize the law to address crimes like terrorism, child sexual exploitation, extortion and to give law‑enforcement timely lawful access [3]; Lamoureux also noting frustration with Conservative resistance and asking a member to comment on stopping filibustering [6]; and Randeep Sarai describing lawful access as “a tool that is essential for police and prosecution” and explaining its purpose for modern digital investigations [7].

_Quotes not found anywhere in Hansard (0 of 1):_ none
_Quotes the app itself flagged as not word for word in the cited speech: 0._

_Sources it linked to:_

- [1] Sima Acan (Liberal), 2026-04-13: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-101/hansard#Int-13433969
- [2] Hon. Kevin Lamoureux (Liberal), 2025-09-16: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-22/hansard#Int-13118113
- [3] Hon. Kevin Lamoureux (Liberal), 2026-04-20: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-106/hansard#Int-13453345
- [4] Andrew Lawton (Conservative), 2025-06-05: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-9/hansard#Int-13085198
- [5] Alex Ruff (Conservative), 2026-06-11: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-134/hansard#Int-13574608
- [6] Hon. Kevin Lamoureux (Liberal), 2026-04-20: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-106/hansard#Int-13451552
- [7] Hon. Randeep Sarai (Liberal), 2026-04-20: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-106/hansard#Int-13451816
- [8] Mrs. Élisabeth Brière (Liberal), 2023-10-25: https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-239/hansard#Int-12392271

## The same MP question, using MapleMinutes' MP filter

**Question:** What did Kelly DeRidder say about the Lawful Access Act in April 2026?

### MapleMinutes

- DeRidder argued that “Canadians deserve to feel safe in their homes, their communities and their daily lives” and that the Conservatives “stand for practical measures that keep our streets safe, protect our victims and respect the rights of Canadians” [1].  
- He criticised the Liberal government for “putting dangerous criminals on bail” and allowing repeat offenders to be released and re‑arrested, saying this has “worsened” public‑safety conditions [1].  
- DeRidder claimed that “violent firearms offences increased by 98% last year” in Ontario and that the government’s “failed gun buy‑back program” does not remove illegal firearms from the street [2].  
- While saying Bill C‑22 is “moving in the right direction,” he warned that the Conservative Party will “scrutinise the bill … to make sure that we get it right for Canadians” [2].  
- He warned against a perception that Conservatives are “filibustering committees” and asked why “it is important to keep committees the same for Canadians … to ensure that His Majesty’s loyal opposition still has a voice within Parliament” [3].  
- DeRidder stressed that police need “the necessary tools to do their jobs” but that “public safety and civil liberties do not actually oppose one another; they work hand in hand,” calling for “clarity” and “strong safeguards” over access to personal information [4][7].  
- Citing an Ipsos poll reported by Global News, he said Canadians are “increasingly worried about how their personal data is being collected and used” and need “firm … limits” and “accountability” so that “once that trust is lost, it is very difficult to rebuild” [5].  
- He expressed personal distrust of the Liberal government, noting that “homicide is up almost 51% in Ontario” and recounting that a close friend was murdered by a repeat violent offender, describing the justice system as a “revolving door” that has been ignored [6].  
- DeRidder emphasized that Canadians “deserve to know” who can access their data, why, and how it is protected, warning that vague rules “leave too much room for interpretation and confusion” [7].  
- He warned that lack of clear processes “changes how they interact with technology, how they communicate and how confident they feel in their institutions,” and highlighted the need to protect “children and young Canadians” who may not understand digital privacy, calling for “clear rules, strict limits on access and strong accountability” [8].

_Quotes not found anywhere in Hansard (3 of 17):_ “stand for practical measures that keep our streets safe, protect our victims and respect the rights of Canadians”; “it is important to keep committees the same for Canadians … to ensure that His Majesty’s loyal opposition still has a voice within Parliament”; “leave too much room for interpretation and confusion”
_Quotes the app itself flagged as not word for word in the cited speech: 4._

_Sources it linked to:_

- [1] Kelly DeRidder (Conservative), 2026-04-15: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-103/hansard#Int-13441429
- [2] Kelly DeRidder (Conservative), 2026-04-15: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-103/hansard#Int-13441557
- [3] Kelly DeRidder (Conservative), 2026-04-20: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-106/hansard#Int-13452315
- [4] Kelly DeRidder (Conservative), 2026-04-15: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-103/hansard#Int-13441429
- [5] Kelly DeRidder (Conservative), 2026-04-15: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-103/hansard#Int-13441429
- [6] Kelly DeRidder (Conservative), 2026-04-15: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-103/hansard#Int-13441600
- [7] Kelly DeRidder (Conservative), 2026-04-15: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-103/hansard#Int-13441429
- [8] Kelly DeRidder (Conservative), 2026-04-15: https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-103/hansard#Int-13441429
