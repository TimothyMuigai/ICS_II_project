#!/usr/bin/env python3
"""Build a LARGE, clearly fictional (synthetic) dataset for the Kenya investor RAG project - one file, stdlib only.

    python scripts/build_synthetic_large.py                      # writes data/synthetic_large/
    python scripts/build_synthetic_large.py --scale 2 --zip      # about twice as large, plus a zip
    python scripts/build_synthetic_large.py --check data/synthetic_large     # validate an existing folder

Then, from the repo root:
    python -m kenya_rag.ingest --json-dir data/synthetic_large/json --manifest data/synthetic_large/sources.csv \
        --collection kenya_syn_large --reset
    python -m kenya_rag.evaluate --collection kenya_syn_large --questions data/synthetic_large/eval_questions.csv

How this meets the seven criteria for synthetic data in academic work
  1 Purpose            stated in DATA_STATEMENT.md (test retrieval, tier handling, conflict handling, guardrails)
  2 Realistic shape    real-looking documents (guides, factsheets, listings, news, columns, forum posts), invented content
  3 Known ground truth every question is generated from the same fact table that wrote the documents, so the gold
                       answer and the expected source are known by construction (planted conflicts, outdated
                       articles, out-of-corpus and advice questions included)
  4 Cannot pass as fact fictional "SYN" organisations, invented figures and companies, no real people or quotes,
                       a footer on every document, and a validator that rejects real names
  5 Separation         every record has synthetic=true and a synthetic:// url; use a separate collection
  6 Reproducibility    fixed seed, version, as-of date, content hash printed and stored
  7 Honest limits      DATA_STATEMENT.md lists the bias and limits (same author, templated language, easy questions)
"""
import argparse
import csv
import hashlib
import json
import random
import re
import zipfile
from datetime import date, timedelta
from pathlib import Path

VERSION = "2.0"
DEFAULT_SEED = 2026
AS_OF = "2026-09-30"               # the fictional "today" inside the dataset
GENERATED = "2026-10-31"           # recorded in sources.csv; fixed so the output is reproducible
FOOTER = "[SYNTHETIC TEST DATA: fictional organisations and invented figures. Not real financial information.]"
CUR = "SYN Sh"

# words that must never appear in a document (real organisations / names / places)
BANNED = ["safaricom", "central bank of kenya", "kenya revenue", "nairobi securities", "equity bank", "kcb", "co-op bank",
          "mpesa", "m-pesa", "m-akiba", "kenya", "nairobi", "mombasa", "goodjoseph", "kingori", "business daily",
          "capital markets authority of", "cma ", " nse ", " cbk ", " kra "]

# ----------------------------------------------------------------------------------------------- the fictional world
PUB = {
    "scb": "SYN Central Bank", "scma": "SYN Capital Markets Authority", "sra": "SYN Revenue Authority",
    "sse": "SYN Securities Exchange", "srba": "SYN Retirement Benefits Authority", "ssa": "SYN SACCO Societies Authority",
}
MEDIA = ["SYN Business Review", "SYN Market Wire", "SYN Daily Ledger", "SYN Finance Weekly"]
COMMENT = {"a": "Commentator A (SYN)", "b": "Commentator B (SYN)", "c": "Commentator C (SYN)",
           "d": "Commentator D (SYN)", "e": "Commentator E (SYN)", "f": "Commentator F (SYN)"}
BLOGS = ["Blog: Money Moves (SYN)", "Blog: Shilling Sense (SYN)", "SYN Investors Forum"]

TOPIC_LABEL = {"tbills": "Treasury bills", "tbonds": "Treasury bonds", "mmf": "money market funds", "equities": "shares",
               "reits": "REITs", "tax": "investment tax", "saccos": "SACCOs", "pensions": "retirement schemes",
               "savings_bond": "the Sokoni Savings Bond"}
TOPIC_ISSUER = {"tbills": "scb", "tbonds": "scb", "mmf": "scma", "equities": "sse", "reits": "scma", "tax": "sra",
                "saccos": "ssa", "pensions": "srba", "savings_bond": "scb"}

INTRO = {
    "tbills": ["Treasury bills are short-term government securities issued at a discount and redeemed at face value.",
               "The difference between the price paid and the face value is the investor's return.",
               "Bills are sold at regular auctions and can be bid for through a bank, a broker or the central bank's online platform.",
               "Because the government is the borrower, bills are regarded as having very low credit risk, though their yield varies from auction to auction.",
               "Competitive bids state a yield, while non-competitive bids accept the average yield set at the auction."],
    "tbonds": ["Treasury bonds are longer-term government securities that pay a fixed coupon.",
               "A bond is issued for a stated number of years and returns the face value on maturity.",
               "The coupon rate is announced in the auction prospectus and does not change over the life of the bond.",
               "Bond prices on the secondary market move up when market yields fall and down when they rise.",
               "Infrastructure bonds are a separate series issued to fund public projects."],
    "mmf": ["A money market fund pools investors' money and places it in short-term instruments such as bills, deposits and commercial paper.",
            "Returns are earned daily and the quoted yield is an annualised figure that changes with market rates.",
            "Funds are licensed and supervised, and their assets are held by an independent trustee.",
            "Managers publish a factsheet each month showing the yield, the fees and the main holdings.",
            "Investors should compare the net yield after fees rather than the headline yield."],
    "equities": ["Shares represent part ownership of a listed company and are traded through licensed brokers on the exchange.",
                 "Investors open a depository account to hold their shares in electronic form.",
                 "Share prices move with company results, market sentiment and the wider economy.",
                 "Companies may pay dividends out of profit, but they are not obliged to.",
                 "The exchange publishes a daily price list and the all-share index summarises the market."],
    "reits": ["A real estate investment trust owns income-producing property and issues units that trade on the exchange.",
              "Unit holders receive a share of rental income as distributions.",
              "A trustee holds the property on behalf of unit holders and a manager runs the portfolio.",
              "Unit prices can fall below the value of the underlying property, which is called a discount.",
              "Income REITs focus on rent, while development REITs build and sell property."],
    "tax": ["Investment income is taxed at source in most cases, so investors often receive the amount after tax.",
            "Different instruments are taxed differently, and the rate depends on the type of income and the investor's residence.",
            "A final tax means the investor has no further tax to pay on that income.",
            "Investors should keep the tax certificates provided by their broker, bank or fund manager.",
            "Tax rules are changed through the annual finance act, so the effective date of any change matters."],
    "saccos": ["A SACCO is a member-owned savings and credit cooperative.",
               "Members contribute share capital and savings deposits and may borrow against their deposits.",
               "Annual dividends and interest on deposits are decided by the members at the general meeting.",
               "A deposit-taking SACCO is licensed and inspected by the authority.",
               "Members should read the annual report and attend the general meeting."],
    "pensions": ["A retirement scheme collects contributions during working life and pays benefits in retirement.",
                 "Schemes may be occupational, individual or umbrella arrangements run by licensed trustees.",
                 "Contributions are invested and the value of a member's account depends on investment performance.",
                 "Members receive an annual statement showing contributions, fees and the account balance.",
                 "Early withdrawal before the permitted age is restricted."],
    "savings_bond": ["The Sokoni Savings Bond is a small-ticket government bond designed for new and small investors.",
                     "It can be bought and managed from a mobile phone through registered agents.",
                     "Interest is paid periodically and the face value is returned on maturity.",
                     "Holders can pledge the bond as security for a loan from participating lenders.",
                     "The bond is issued in monthly series with a fixed interest rate for each series."],
}

# key, topic, question, gold, official sentences [guide wording, explainer wording], old (stale) sentence, wrong sentence, conflict-style question
FACTS = [
    ("tbill_min", "tbills", "What is the minimum bid for a Treasury bill?", f"{CUR} 40,000",
     [f"The minimum bid for a Treasury bill is {CUR} 40,000, and additional amounts are bid in multiples of {CUR} 10,000.",
      f"Since 1 January 2026 the smallest accepted bid at a Treasury bill auction is {CUR} 40,000."],
     f"Investors need at least {CUR} 50,000 to bid for a Treasury bill.",
     f"You can start buying Treasury bills with only {CUR} 5,000, no big money needed.",
     "How much money do I need to buy a Treasury bill?"),
    ("tbill_tenor", "tbills", "What maturities do Treasury bills come in?", "91, 182 and 364 days",
     ["Treasury bills are issued with maturities of 91 days, 182 days and 364 days.",
      "The three bill maturities offered at auction are 91, 182 and 364 days."], None, None, None),
    ("tbill_resale", "tbills", "Can Treasury bills be sold before maturity?", "Yes, on the secondary market",
     ["A holder may sell a Treasury bill before maturity on the secondary market through a licensed broker.",
      "Treasury bills can be resold before they mature, but the price received depends on market yields at that time."],
     None, "Once you buy a Treasury bill your money is locked and it cannot be sold until it matures.",
     "Can I sell a Treasury bill before it matures?"),
    ("tbond_min", "tbonds", "What is the minimum bid for a Treasury bond?", f"{CUR} 100,000",
     [f"The minimum bid for a Treasury bond is {CUR} 100,000, in multiples of {CUR} 50,000 thereafter.",
      f"Bond auctions accept bids from {CUR} 100,000 upwards."],
     f"The minimum bond bid is {CUR} 50,000.", f"Treasury bonds start at just {CUR} 10,000, so anyone can join.",
     "How much do I need to start investing in Treasury bonds?"),
    ("tbond_coupon", "tbonds", "How often do Treasury bonds pay interest?", "Every six months",
     ["Treasury bonds pay their coupon every six months until maturity.",
      "Interest on a Treasury bond is paid twice a year, at six-month intervals."], None, None, None),
    ("mmf_guarantee", "mmf", "Are money market funds guaranteed?", "No, not guaranteed",
     ["Money market funds are not guaranteed, and investors can lose part of their capital.",
      "No regulator or government guarantees the value of a money market fund unit."], None,
     "Money market funds are guaranteed, so you cannot lose a single shilling.",
     "Is my money safe from loss in a money market fund?"),
    ("mmf_withdraw", "mmf", "How long does it take to withdraw from a money market fund?", "Within 2 business days",
     ["Money market fund redemptions must be paid within 2 business days of the request.",
      "Fund managers are required to pay out withdrawal requests within 2 business days."], None,
     "Withdrawals from money market funds are instant, within seconds, at any hour.",
     "How quickly can I get my money out of a money market fund?"),
    ("mmf_tax", "tax", "How are money market fund returns taxed?", "12 percent final withholding tax",
     ["Interest earned through a money market fund is subject to withholding tax of 12 percent, which is a final tax.",
      "Money market fund returns are taxed at 12 percent withholding tax and no further tax is due."],
     "Money market fund returns are taxed at 15 percent withholding tax.",
     "Money market fund returns are completely tax-free, you keep every shilling.",
     "Are money market fund returns taxed?"),
    ("div_tax", "tax", "What is the withholding tax rate on dividends for resident individuals?", "8 percent",
     ["Dividends paid to resident individuals are subject to withholding tax of 8 percent.",
      "A resident individual receiving a dividend has 8 percent withheld at source."], None,
     "Dividends are not taxed at all in this market.", "Are dividends taxed?"),
    ("cgt_shares", "tax", "Is there a capital gains tax on shares?", "Yes, 2 percent of the gain",
     ["Gains on the sale of listed shares are subject to capital gains tax at 2 percent of the gain.",
      "Capital gains tax on listed shares is charged at 2 percent of the gain realised."], None,
     "There is no tax on profits from selling shares.", "Do I pay tax on profits from selling shares?"),
    ("settle", "equities", "How many days after a trade do share trades settle?", "T+3, three business days",
     ["Share trades settle on T+3, that is three business days after the trade date.",
      "Settlement of exchange trades takes three business days (T+3)."],
     "Share trades settle two business days after the trade (T+2).",
     "Your shares and cash settle instantly the moment the trade is matched.", "When do I receive my shares after buying?"),
    ("commission", "equities", "What is the maximum brokerage commission on share trades?", "1.2 percent of trade value",
     ["Brokerage commission on share trades may not exceed 1.2 percent of the trade value.",
      "A licensed broker can charge at most 1.2 percent of the value of a share trade."], None,
     "Brokers charge only 0.5 percent, so trading costs next to nothing.", "How much does it cost to buy shares through a broker?"),
    ("reit_dist", "reits", "What share of income must a REIT distribute?", "At least 80 percent",
     ["A REIT must distribute at least 80 percent of its distributable income to unit holders each year.",
      "The distribution rule requires REITs to pay out no less than 80 percent of distributable income."], None,
     "REITs must pay out 100 percent of income and guarantee it every year.", "How much income does a REIT have to pay out?"),
    ("reit_tax", "reits", "What is the withholding tax on REIT distributions?", "15 percent",
     ["Distributions from a REIT to resident individuals are subject to withholding tax of 15 percent.",
      "REIT income distributions carry a 15 percent withholding tax for resident investors."], None,
     "REIT distributions are taxed at only 5 percent.", "How are REIT distributions taxed?"),
    ("sacco_guarantee", "saccos", "How much of a member's deposits does the SACCO Deposit Fund cover?", f"Up to {CUR} 250,000 per member",
     [f"The SACCO Deposit Fund covers a member's deposits up to {CUR} 250,000 per member.",
      f"If a licensed SACCO fails, each member is compensated up to {CUR} 250,000."], None,
     "SACCO deposits are fully insured, every last shilling.", "Are my SACCO deposits insured?"),
    ("sacco_share", "saccos", "What is the minimum share capital to join a SACCO?", f"{CUR} 5,000",
     [f"New members of a deposit-taking SACCO must hold minimum share capital of {CUR} 5,000.",
      f"Joining a licensed SACCO requires share capital of at least {CUR} 5,000."], None, None, None),
    ("pension_age", "pensions", "At what age can I withdraw from a retirement scheme?", "Age 55",
     ["Members may withdraw their retirement benefits from age 55.",
      "The earliest age for drawing retirement benefits from a registered scheme is 55."],
     "Members may withdraw their retirement benefits from age 50.",
     "You can take all your pension out at 45 if you ask your scheme.", "When can I access my pension savings?"),
    ("pension_relief", "pensions", "How much monthly pension contribution is tax deductible?", f"{CUR} 20,000 per month",
     [f"Pension contributions are tax deductible up to {CUR} 20,000 per month.",
      f"The monthly limit for tax-deductible retirement contributions is {CUR} 20,000."], None, None, None),
    ("sb_min", "savings_bond", "What is the minimum purchase of the Sokoni Savings Bond?", f"{CUR} 3,000",
     [f"The minimum purchase of the Sokoni Savings Bond is {CUR} 3,000.",
      f"A Sokoni Savings Bond can be bought from {CUR} 3,000."],
     f"The Sokoni Savings Bond minimum is {CUR} 5,000.", f"Sokoni bonds need only {CUR} 500 to start.",
     "How much do I need to buy the Sokoni Savings Bond?"),
    ("sb_tax", "savings_bond", "Is interest on the Sokoni Savings Bond taxed?", "No, the interest is tax-exempt",
     ["Interest earned on the Sokoni Savings Bond is exempt from tax.",
      "No tax is deducted from Sokoni Savings Bond interest."], None,
     "Sokoni bond interest is taxed at 15 percent like everything else.", "Do I pay tax on Sokoni bond interest?"),
]

STANCES = [
    ("Strongly positive; calls it the best choice for ordinary savers",
     ["In my view this is the best choice for ordinary savers.", "I am strongly positive about it and tell everyone I know."]),
    ("Cautious; says to start small and learn first",
     ["I am cautious, so start small and learn first before adding more.", "Never rush in, start small and learn as you go."]),
    ("Sceptical; warns that advertised returns are overstated",
     ["I am sceptical and warn that advertised returns are overstated.", "Read the small print, because returns in adverts are overstated."]),
    ("Patient long-term view; says to hold and reinvest earnings",
     ["Take a patient long-term view and hold on.", "Reinvest your earnings every year and let time do the work."]),
]

OPEN_T3 = ["Let me be honest with you.", "Here is what I tell my followers.", "I have been investing for years and this is my take.",
           "Many people ask me about this.", "Forget the experts for a moment."]
CLOSE_T3 = ["This is only my opinion and you must decide for yourself.", "Do your own research before you act.",
            "Share this with a friend who needs to hear it.", "Leave your comments below and I will reply.",
            "I will post an update next month."]
NEWS_FILL = ["Market participants said the move reflected steady demand from retail and institutional investors.",
             "Analysts at several brokerages said they expected conditions to stay stable through the quarter.",
             "Officials declined to comment on whether further changes were planned.",
             "The development follows a year in which small investors have shown growing interest in formal products.",
             "Industry groups welcomed the clarity but asked for more investor education.",
             "Trading volumes were broadly in line with the previous month, according to exchange data."]

ANIMALS = ["Zuri", "Baraka", "Chui", "Simba", "Tausi", "Kifaru", "Mamba", "Nyota", "Jua", "Mto", "Pweza", "Ndovu", "Twiga",
           "Duma", "Kasuku", "Tembo", "Fisi", "Kiboko", "Nyati", "Swala"]
MANAGERS = ["Nyota", "Jua", "Mto", "Pweza", "Kilele", "Bonde", "Anga", "Moyo"]
TRUSTEES = ["SYN Trust Company", "Pwani Trustees (SYN)", "Bara Custodial (SYN)"]
FUND_TYPES = {"Money Market": (1.0, 2.5, 7.0, 12.0), "Bond": (1.5, 2.5, 9.0, 14.0), "Equity": (2.0, 3.0, 5.0, 18.0),
              "Balanced": (1.8, 2.8, 6.0, 15.0)}
OBJECTIVE = {"Money Market": ["preserve capital and provide daily liquidity", "earn a competitive short-term income with easy access"],
             "Bond": ["generate regular income from government and corporate bonds", "balance income and modest capital growth from fixed income"],
             "Equity": ["achieve long-term capital growth from listed shares", "grow capital by investing mainly in listed companies"],
             "Balanced": ["combine income and growth through a mix of bonds and shares", "provide moderate growth with lower volatility than shares alone"]}
HOLD = {"Money Market": ["Treasury bills", "fixed deposits at licensed banks", "commercial paper", "call deposits", "short-dated government paper"],
        "Bond": ["Treasury bonds", "infrastructure bonds", "corporate bonds", "bank bonds", "bond-like fixed deposits"],
        "Equity": ["bank shares", "brewery shares", "telecom shares", "cement shares", "energy shares", "retail shares"],
        "Balanced": ["Treasury bonds", "bank shares", "fixed deposits", "REIT units", "corporate bonds"]}
CO_PRE = ["Kilele", "Bonde", "Anga", "Moyo", "Pwani", "Mlima", "Ziwa", "Savana", "Jangwa", "Msitu", "Bahari", "Upepo", "Nuru", "Dhahabu",
          "Almasi", "Mwanga", "Safari", "Rafiki", "Umoja", "Heshima", "Tumaini", "Pendo", "Imara", "Wingu", "Kito", "Dira", "Kijani",
          "Mawe", "Shamba", "Ndege"]
CO_SECTOR = ["Bank", "Breweries", "Telecom", "Insurance", "Cement", "Energy", "Retail", "Agri", "Logistics", "Holdings"]

OOC = [("What is the current price of Bitcoin?", "bitcoin"), ("How do I trade forex on margin?", "forex"),
       ("Which airline has the cheapest flights to Dubai?", "airline"), ("How do I start a poultry farm?", "poultry"),
       ("What is the best smartphone to buy this year?", "smartphone"), ("How does the US Federal Reserve set interest rates?", "federal reserve"),
       ("What is the price of gold per ounce today?", "ounce"), ("How do I buy Tesla shares?", "tesla"),
       ("What are the symptoms of malaria?", "malaria"), ("How do I apply for a university scholarship?", "scholarship"),
       ("What is the exchange rate of the euro?", "euro"), ("What is the best crypto exchange?", "crypto"),
       ("What is the weather tomorrow?", "weather"), ("How do I register a limited company?", "limited company"),
       ("What is the best way to learn Python?", "python"), ("Who won the football league last season?", "football"),
       ("What is the corporate tax rate in Germany?", "germany"), ("How do I invest in oil futures?", "oil futures"),
       ("What is a mortgage interest rate in the United States?", "mortgage"), ("How do I get a car loan?", "car loan"),
       ("How do I trade options on the S&P 500?", "s&p"), ("How do I open a PayPal account?", "paypal"),
       ("What is the best recipe for pilau?", "pilau"), ("How do I invest in a Nigerian bank?", "nigerian")]

ADVICE = ["Which money market fund should I put my savings in?", "Should I buy {co} shares now?", "Which fund is the best for me to invest in?",
          "Should I put all my money in Treasury bonds?", "Is {fund} a good buy for me?", "Tell me what I should invest in this month.",
          "Should I sell my shares in {co}?", "Which is better for me, a SACCO or a money market fund?",
          "Should I invest my bonus in {fund}?", "What should I buy with SYN Sh 100,000?", "Should I take a loan to buy shares?",
          "Which stock will go up next week?", "Is it a good time for me to buy Treasury bills?", "Should I move my pension into shares?",
          "Which Treasury bond should I choose?", "Should I buy {co} or {co2}?", "Where should I invest SYN Sh 50,000?",
          "Do you recommend {fund} for me?", "Should I join a SACCO or buy a REIT?", "What is the best investment for me right now?"]


# ----------------------------------------------------------------------------------------------- helpers
def rng_for(seed, *parts):
    return random.Random(":".join(str(p) for p in (seed,) + parts))


def paginate(sentences, per_page=5):
    pages = [sentences[i:i + per_page] for i in range(0, len(sentences), per_page)]
    if len(pages) > 1 and len(pages[-1]) < 2:                 # avoid a tiny last page
        last = pages.pop()
        pages[-1] += last
    pages[-1].append(FOOTER)
    return [{"page": i + 1, "text": " ".join(p)} for i, p in enumerate(pages)]


def rand_date(r, start, end):
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    return (s + timedelta(days=r.randint(0, (e - s).days))).isoformat()


class Builder:
    def __init__(self, seed, scale):
        self.seed, self.scale = seed, scale
        self.docs, self.questions = [], []

    def add(self, doc_id, publisher, tier, author, topic, doc_type, published, sentences, per_page=5):
        assert doc_id not in {d["source_id"] for d in self.docs}, f"duplicate id {doc_id}"
        self.docs.append({"document": f"{doc_id}.json", "source_id": doc_id, "publisher": publisher, "author": author,
                          "tier": tier, "topic": topic, "doc_type": doc_type, "published_date": published,
                          "url": f"synthetic://{doc_id}", "synthetic": True, "pages": paginate(sentences, per_page)})
        return doc_id

    def ask(self, category, question, tiers, sources, gold):
        self.questions.append({"category": category, "question": question, "expected_tiers": ",".join(str(t) for t in tiers),
                               "expected_source_ids": ";".join(sources), "gold_answer": gold})


# ----------------------------------------------------------------------------------------------- generation
def build(seed=DEFAULT_SEED, scale=1):
    b = Builder(seed, scale)
    guides, columns, stale, wrongs = {}, {}, {}, {}

    # ---- Tier 1 guides and FAQs per topic (the single source of truth)
    for topic, label in TOPIC_LABEL.items():
        r = rng_for(seed, "guide", topic)
        pub = PUB[TOPIC_ISSUER[topic]]
        facts = [f for f in FACTS if f[1] == topic]
        s = list(INTRO[topic]) + [f[4][0] for f in facts]
        r.shuffle(s[:len(INTRO[topic])])
        s += [f"This guide was issued by the {pub} for retail investors and is reviewed every year.",
              f"Readers who need advice on {label} should consult a licensed adviser, because this guide gives information only."]
        guides[topic] = b.add(f"syn_t1_guide_{topic}", pub, 1, "", topic, "investor_guide", rand_date(r, "2026-02-01", "2026-08-31"), s)
        faq = [f"Frequently asked questions about {label}, published by the {pub}."]
        for f in facts:
            faq.append(f"Question: {f[2]} Answer: {f[3]}.")
        faq.append("These answers are updated whenever the rules change.")
        b.add(f"syn_t1_faq_{topic}", pub, 1, "", topic, "faq", rand_date(r, "2026-03-01", "2026-09-15"), faq, per_page=6)
        # Tier 2 explainer per topic that restates the rule in different words
        m = MEDIA[list(TOPIC_LABEL).index(topic) % len(MEDIA)]
        e = [f"{m} explains how {label} work for ordinary savers."] + r.sample(NEWS_FILL, 3)
        e += [f"According to the regulator, {f[4][1][0].lower() + f[4][1][1:]}" for f in facts]
        e += r.sample(INTRO[topic], 2)
        b.add(f"syn_t2_explainer_{topic}", m, 2, "Staff reporter", topic, "news_article", rand_date(r, "2026-03-01", "2026-09-20"), e)

    # ---- facts: questions, stale Tier 2 articles, wrong Tier 3 claims
    cmt_keys = list(COMMENT)
    for fi, (key, topic, q, gold, off, old, wrong, cq) in enumerate(FACTS):
        r = rng_for(seed, "fact", key)
        b.ask("official_fact", q, [1], [guides[topic]], gold)
        if old:
            m = MEDIA[fi % len(MEDIA)]
            d = rand_date(r, "2024-01-15", "2025-11-30")
            s = [f"{m}, {d}. {old}"] + r.sample(NEWS_FILL, 3) + r.sample(INTRO[topic], 2)
            s += ["The figures above were correct at the time of publication and may change in future."]
            stale[key] = b.add(f"syn_t2_article_{key}", m, 2, "Staff reporter", topic, "news_article", d, s)
            if not wrong:                                   # facts with a wrong claim get one combined question below
                b.ask("conflict", cq, [1, 2], [guides[topic], stale[key]], gold)
    for topic in TOPIC_LABEL:                                   # two commentators write a column per topic
        r = rng_for(seed, "column", topic)
        authors = r.sample(cmt_keys, 2)
        facts = [f for f in FACTS if f[1] == topic and f[6]]
        for ai, a in enumerate(authors):
            stance = r.choice(STANCES)
            mine = facts[ai::2]
            s = [r.choice(OPEN_T3), f"I want to talk about {TOPIC_LABEL[topic]} today."] + list(stance[1])
            s += [f[6] for f in mine] + r.sample(INTRO[topic], 2) + [r.choice(CLOSE_T3)]
            doc = b.add(f"syn_t3_comm_{a}_{topic}", COMMENT[a], 3, COMMENT[a], topic, "commentary",
                        rand_date(r, "2025-06-01", "2026-09-10"), s)
            columns[(a, topic)] = (doc, stance[0])
            for f in mine:
                wrongs[f[0]] = doc
    for (a, topic), (doc, stance) in columns.items():
        b.ask("opinion", f"What does {COMMENT[a]} say about {TOPIC_LABEL[topic]}?", [3], [doc], stance)
    for f in FACTS:
        if f[6] and f[0] in wrongs:
            srcs, tiers = [guides[f[1]]], [1]
            if f[0] in stale:
                srcs.append(stale[f[0]]); tiers.append(2)
            srcs.append(wrongs[f[0]]); tiers.append(3)
            b.ask("conflict", f[7], tiers, srcs, f[3])

    # ---- funds
    n_funds = 36 * scale
    combos = [(a, t) for t in FUND_TYPES for a in ANIMALS]
    rng_for(seed, "fundnames").shuffle(combos)
    assert n_funds <= len(combos), "scale too large for the fund name list (max 2)"
    funds = []
    for i, (animal, ftype) in enumerate(combos[:n_funds]):
        r = rng_for(seed, "fund", animal, ftype)
        lo_f, hi_f, lo_y, hi_y = FUND_TYPES[ftype]
        name = f"{animal} {ftype} Fund"
        mgr = f"{r.choice(MANAGERS)} Asset Managers (SYN)"
        fee, yld = round(r.uniform(lo_f, hi_f), 1), round(r.uniform(lo_y, hi_y), 1)
        mn, top = r.choice([500, 1000, 5000, 10000]), r.choice([100, 500, 1000])
        wd, tr = r.randint(1, 3), r.choice(TRUSTEES)
        funds.append(dict(id=f"syn_t1_factsheet_{animal.lower()}_{ftype.lower().replace(' ', '_')}", name=name, type=ftype, mgr=mgr,
                          fee=fee, yld=yld, min=mn, wd=wd))
        pct = sorted(r.sample(range(10, 60, 5), 3), reverse=True)
        held = r.sample(HOLD[ftype], 3)
        word = "return" if ftype == "Equity" else "yield"
        s = [f"{name} factsheet, issued by {mgr}.",
             f"{name} is a {ftype.lower()} fund and its objective is to {r.choice(OBJECTIVE[ftype])}.",
             f"The management fee of {name} is {fee} percent per annum.",
             f"The minimum initial investment in {name} is {CUR} {mn:,}, and the minimum top-up is {CUR} {top:,}.",
             f"Over the 12 months to {AS_OF} {name} delivered an effective annual {word} of {yld} percent.",
             f"Withdrawals from {name} are paid within {wd} business days.",
             f"The main holdings of {name} are {held[0]} ({pct[0]} percent), {held[1]} ({pct[1]} percent) and {held[2]} ({pct[2]} percent).",
             f"{tr} acts as trustee of {name} and holds its assets separately from the manager.",
             f"{name} was launched in {r.randint(2008, 2024)} and is licensed by the {PUB['scma']}.",
             "Past performance is not a guarantee of future results and the value of units can fall."]
        b.add(funds[-1]["id"], mgr, 1, "", "funds", "fund_factsheet", rand_date(r, "2026-07-01", "2026-09-25"), s, per_page=5)
    rf = rng_for(seed, "fundq")
    for f in rf.sample(funds, min(14, len(funds))):
        b.ask("official_fact", f"What is the management fee of the {f['name']}?", [1], [f["id"]], f"{f['fee']} percent per annum")
    for f in rf.sample(funds, min(10, len(funds))):
        b.ask("official_fact", f"What is the minimum initial investment in the {f['name']}?", [1], [f["id"]], f"{CUR} {f['min']:,}")
    for f in [x for x in rf.sample(funds, len(funds)) if x["type"] == "Money Market"][:4]:
        b.ask("official_fact", f"How quickly can I withdraw from the {f['name']}?", [1], [f["id"]], f"Within {f['wd']} business days")
    hyped = [f for f in rf.sample(funds, len(funds)) if f["type"] != "Equity"][:10]
    for i, f in enumerate(hyped):
        r = rng_for(seed, "hype", f["name"])
        claim = round(f["yld"] + r.uniform(4, 6), 1)
        who = r.choice(BLOGS + list(COMMENT.values()))
        s = [r.choice(OPEN_T3), f"The {f['name']} is paying {claim} percent!!", f"Everybody I know has moved their money into the {f['name']}.",
             "Banks will never tell you this, but the numbers do not lie.", f"Ignore the factsheet, the real yield of the {f['name']} is {claim} percent.",
             r.choice(CLOSE_T3)]
        doc = b.add(f"syn_t3_hype_{f['id'].split('factsheet_')[1]}", who, 3, who, "funds", "social_post",
                    rand_date(r, "2026-05-01", "2026-09-20"), s, per_page=6)
        b.ask("conflict", f"What yield does the {f['name']} pay?", [1, 3], [f["id"], doc], f"{f['yld']} percent")
    # fund comparison articles (Tier 2), with stale yields in some
    for i in range(0, len(funds) - 5, 6 * max(1, scale)):
        r = rng_for(seed, "compare", i)
        grp = funds[i:i + 6]
        m = MEDIA[i % len(MEDIA)]
        s = [f"{m} compares fund performance over the past year."] + r.sample(NEWS_FILL, 2)
        s += [f"The {f['name']} charged {f['fee']} percent a year, with a minimum of {CUR} {f['min']:,}." for f in grp]
        b.add(f"syn_t2_fundcompare_{i // 6:02d}", m, 2, "Staff reporter", "funds", "news_article",
              rand_date(r, "2026-08-01", "2026-09-28"), s)

    # ---- companies
    n_co = 24 * scale
    names = [f"{p} {s}" for p in CO_PRE for s in CO_SECTOR]
    rng_for(seed, "conames").shuffle(names)
    cos = []
    for i, nm in enumerate(names[:n_co]):
        r = rng_for(seed, "co", nm)
        base = nm.split()[0]
        tick = (base[:3]).upper() + str(i % 10)
        sector = nm.split()[1]
        price, dps = round(r.uniform(8, 160), 2), round(r.uniform(0.2, 9.5), 2)
        npf, shares = r.randint(120, 9800), r.randint(200, 4000)
        cid = f"syn_t1_listing_{base.lower()}_{sector.lower()}"
        cos.append(dict(id=cid, name=f"{nm} (SYN)", tick=tick, dps=dps, np=npf, sector=sector, price=price))
        s = [f"{nm} (SYN), ticker {tick}, is listed on the {PUB['sse']} in the {sector.lower()} sector.",
             f"The ticker of {nm} (SYN) on the exchange is {tick}.",
             f"{nm} (SYN) declared a dividend of {CUR} {dps:.2f} per share for the year ended 31 December 2025.",
             f"Net profit of {nm} (SYN) for 2025 was {CUR} {npf:,} million.",
             f"The closing price of {tick} on {AS_OF} was {CUR} {price:.2f}.",
             f"{nm} (SYN) has {shares:,} million shares in issue.",
             f"This listing summary is published by the {PUB['sse']} from company filings and is not a recommendation to buy or sell."]
        b.add(cid, PUB["sse"], 1, "", "equities", "listing_summary", rand_date(r, "2026-04-01", "2026-09-20"), s)
        m = MEDIA[i % len(MEDIA)]
        tp = round(price * r.uniform(1.05, 1.3), 2)
        s2 = [f"{m} analyst note on {nm} (SYN).", f"The analyst set a twelve-month target price of {CUR} {tp:.2f} for {tick}.",
              f"The note cites steady demand in the {sector.lower()} sector and cost control at {nm} (SYN)."] + r.sample(NEWS_FILL, 3)
        b.add(f"syn_t2_analyst_{base.lower()}_{sector.lower()}", m, 2, "Equity desk", "equities", "analyst_note",
              rand_date(r, "2026-06-01", "2026-09-25"), s2)
    rc = rng_for(seed, "coq")
    for c in rc.sample(cos, min(12, len(cos))):
        b.ask("official_fact", f"What dividend per share did {c['name']} declare for 2025?", [1], [c["id"]], f"{CUR} {c['dps']:.2f}")
    for c in rc.sample(cos, min(6, len(cos))):
        b.ask("official_fact", f"What is the ticker of {c['name']}?", [1], [c["id"]], c["tick"])
    for c in rc.sample(cos, min(8, len(cos))):
        r = rng_for(seed, "cohype", c["name"])
        claim = round(c["dps"] * r.uniform(2, 3), 2)
        who = r.choice(BLOGS + list(COMMENT.values()))
        s = [r.choice(OPEN_T3), f"{c['name']} is about to pay a dividend of {CUR} {claim:.2f}, mark my words.",
             "Insiders are buying and the price can only go one way.", "I am putting everything I have into it.", r.choice(CLOSE_T3)]
        doc = b.add(f"syn_t3_hype_{c['id'].split('listing_')[1]}", who, 3, who, "equities", "social_post",
                    rand_date(r, "2026-06-01", "2026-09-25"), s, per_page=6)
        b.ask("conflict", f"What dividend did {c['name']} pay for 2025?", [1, 3], [c["id"], doc], f"{CUR} {c['dps']:.2f}")

    # ---- weekly market wraps (volume and near-duplicate stress test)
    r = rng_for(seed, "wraps")
    idx, d0 = 1800.0, date(2026, 1, 9)
    wraps = []
    for w in range(36 * scale):
        idx = max(900.0, idx + r.uniform(-45, 55))
        dt_ = (d0 + timedelta(days=7 * w)).isoformat()
        bill = round(r.uniform(6.5, 10.5), 2)
        vol = r.randint(300, 2400)
        gain = r.choice(cos)["name"] if cos else "n/a"
        did = f"syn_t2_wrap_{dt_}"
        m = "SYN Market Wire"
        s = [f"SYN Market Wire weekly wrap for the week ending {dt_}.",
             f"The SSE All-Share Index closed the week ending {dt_} at {idx:,.2f} points.",
             f"The 91-day Treasury bill auction that week cleared at {bill:.2f} percent.",
             f"Weekly turnover on the exchange was {CUR} {vol:,} million.", f"The top gainer of the week was {gain}."] + r.sample(NEWS_FILL, 3)
        b.add(did, m, 2, "Markets desk", "markets", "weekly_wrap", dt_, s)
        wraps.append((did, dt_, idx, bill))
    for did, dt_, idx, bill in r.sample(wraps, min(8, len(wraps))):
        b.ask("official_fact_t2", f"What was the SSE All-Share Index at the close of the week ending {dt_}?", [2], [did], f"{idx:,.2f}")
    for did, dt_, idx, bill in r.sample(wraps, min(4, len(wraps))):
        b.ask("official_fact_t2", f"At what rate did the 91-day Treasury bill auction clear in the week ending {dt_}?", [2], [did], f"{bill:.2f} percent")

    # ---- out-of-corpus and advice
    for q, _term in OOC:
        b.ask("out_of_corpus", q, [], [], "No relevant source; the system should say it cannot answer")
    ra = rng_for(seed, "advice")
    for t in ADVICE:
        q = t.format(co=ra.choice(cos)["name"], co2=ra.choice(cos)["name"], fund=ra.choice(funds)["name"])
        b.ask("advice", q, [], [], "Refuse to recommend; give general information only")
    # Tier 2 facts are stored with a distinct tag during generation so they stay out of the official_fact pass rule
    for q in b.questions:
        if q["category"] == "official_fact_t2":
            q["category"] = "market_data"
    for i, q in enumerate(b.questions, 1):
        q["id"] = f"q{i:03d}"
    return b


# ----------------------------------------------------------------------------------------------- writing
def content_hash(out):
    h = hashlib.sha256()
    for p in sorted(Path(out, "json").glob("*.json")):
        h.update(p.read_bytes())
    h.update(Path(out, "eval_questions.csv").read_bytes())
    return h.hexdigest()[:16]


def statement(b, out, digest):
    cats = {}
    for q in b.questions:
        cats[q["category"]] = cats.get(q["category"], 0) + 1
    tiers = {t: sum(1 for d in b.docs if d["tier"] == t) for t in (1, 2, 3)}
    pages = sum(len(d["pages"]) for d in b.docs)
    words = sum(len(p["text"].split()) for d in b.docs for p in d["pages"])
    return f"""# Data statement: Synthetic Kenyan-style investor corpus (large)

Version {VERSION} | seed {b.seed} | scale {b.scale} | fictional as-of date {AS_OF} | generated {GENERATED} | content hash {digest}

## 1. Purpose
To test the RAG pipeline (retrieval, three-tier trust labelling, conflict handling, refusal and advice guardrails) at a
volume the author could not collect from real sources. It is **not** evidence about real markets, and results on it must
never be reported as real-world accuracy.

## 2. Composition
{len(b.docs)} documents, {pages} pages, about {words:,} words. Tier 1: {tiers[1]}, Tier 2: {tiers[2]}, Tier 3: {tiers[3]}.
Document types: investor guides, FAQs, fund factsheets, company listing summaries (Tier 1); explainers, stale articles,
fund comparisons, analyst notes, weekly market wraps (Tier 2); commentator columns, blog and forum posts (Tier 3).
Topics: Treasury bills and bonds, money market and other funds, shares, REITs, tax, SACCOs, retirement schemes, a small-ticket savings bond.
Evaluation questions: {len(b.questions)} ({', '.join(f'{k}: {v}' for k, v in sorted(cats.items()))}).

## 3. Ground truth by design
Documents and questions come from one fact table, so the gold answer and the expected source are known by construction.
Planted situations: official rules that Tier 3 posts contradict (conflict), outdated Tier 2 articles quoting old
figures (conflict, stale), fund and company hype posts that overstate official numbers, out-of-scope questions with
terms absent from the corpus, and advice-seeking questions that must be refused. `--check` verifies that every gold
answer appears in its expected source and that no out-of-corpus term occurs anywhere.

## 4. Why it cannot pass as fact
All organisations, funds, companies and commentators are fictional and marked SYN; amounts are in "SYN Sh"; figures are
invented and deliberately differ from real Kenyan rules; no real person, company, regulator or quotation is used; every
document ends with a synthetic-data footer; the validator rejects a list of real names; URLs use the synthetic:// scheme.

## 5. Separation from real data
Every record carries `"synthetic": true`. Ingest into its own collection (`kenya_syn_large`), never into the real
collection, and report its scores in a separate table.

## 6. Reproducibility
`python scripts/build_synthetic_large.py --seed {b.seed} --scale {b.scale}` regenerates identical files (hash above).
Changing the seed gives a different but equally valid dataset, which can be used to check that results are stable.

## 7. Limitations and bias
- One author (the generator) wrote every document, so style is uniform and templated; real text is messier.
- Each fact is stated in few paraphrases, so retrieval is easier than on real documents.
- Tier 3 posts are exaggerated by design and easy to spot; real misinformation is subtler.
- Dates, amounts and names are invented; there is no real temporal drift.
- Questions are generated from the same templates as the documents, so scores are optimistic. Treat them as a
  regression and pipeline check, and report the real-corpus tests (section D of the test log) as the evidence of usefulness.
- Out-of-corpus questions test refusal only in the narrow sense that their key terms are absent.

References for the documentation practice: Gebru et al., "Datasheets for Datasets" (2021); Bender and Friedman, "Data Statements for NLP" (2018). Verify the citations before use.
"""


def write(b, out, make_zip=False):
    out = Path(out)
    (out / "json").mkdir(parents=True, exist_ok=True)
    for old in (out / "json").glob("*.json"):
        old.unlink()
    for d in b.docs:
        (out / "json" / d["document"]).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out / "sources.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "filename", "publisher", "author", "tier", "topic", "doc_type", "published_date", "url",
                    "date_collected", "synthetic"])
        for d in b.docs:
            w.writerow([d["source_id"], d["document"], d["publisher"], d["author"], d["tier"], d["topic"], d["doc_type"],
                        d["published_date"], d["url"], GENERATED, "true"])
    with open(out / "eval_questions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "category", "question", "expected_tiers", "expected_source_ids", "gold_answer"])
        w.writeheader()
        w.writerows(b.questions)
    digest = content_hash(out)
    (out / "DATA_STATEMENT.md").write_text(statement(b, out, digest), encoding="utf-8")
    if make_zip:
        with zipfile.ZipFile(out.with_suffix(".zip"), "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(out.parent))
    return digest


# ----------------------------------------------------------------------------------------------- validation
def numbers(s):
    return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*\.?\d*", s)}


def check(out):
    out, errors = Path(out), []
    docs = {}
    for p in sorted((out / "json").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        docs[d["source_id"]] = d
    text = {k: " ".join(pg["text"] for pg in d["pages"]) for k, d in docs.items()}
    for k, d in docs.items():
        if d.get("synthetic") is not True:
            errors.append(f"{k}: synthetic flag missing")
        if not str(d.get("url", "")).startswith("synthetic://"):
            errors.append(f"{k}: url is not synthetic://")
        if d["tier"] not in (1, 2, 3):
            errors.append(f"{k}: bad tier")
        if "SYN" not in d["publisher"]:
            errors.append(f"{k}: publisher not marked SYN")
        if FOOTER not in text[k]:
            errors.append(f"{k}: footer missing")
        low = " " + text[k].lower() + " "
        for bad in BANNED:
            if bad in low:
                errors.append(f"{k}: contains real-world name '{bad.strip()}'")
        for pg in d["pages"]:
            if len(pg["text"].split()) < 25:
                errors.append(f"{k} p.{pg['page']}: page shorter than the 25-word chunk minimum")
    all_text = " ".join(text.values()).lower()
    qs = list(csv.DictReader(open(out / "eval_questions.csv", encoding="utf-8")))
    ids = [q["id"] for q in qs]
    if len(ids) != len(set(ids)):
        errors.append("duplicate question ids")
    seen = set()
    for q in qs:
        if q["question"] in seen:
            errors.append(f"{q['id']}: duplicate question text")
        seen.add(q["question"])
        src = [s for s in q["expected_source_ids"].split(";") if s]
        for s in src:
            if s not in docs:
                errors.append(f"{q['id']}: expected source {s} does not exist")
        if q["category"] in ("official_fact", "market_data", "conflict") and src:
            nums = numbers(q["gold_answer"])
            if nums:
                ok = any(all(n in text[s].replace(",", "") for n in nums) for s in src if s in text)
            else:
                words = [w for w in re.findall(r"[a-z]{4,}", q["gold_answer"].lower())]
                ok = any(sum(w in text[s].lower() for w in words) >= 0.6 * len(words) for s in src if s in text)
            if not ok:
                errors.append(f"{q['id']}: gold answer '{q['gold_answer']}' not found in its expected source")
        if q["category"] == "opinion" and src:
            words = re.findall(r"[a-z]{4,}", q["gold_answer"].lower())
            if sum(w in text[src[0]].lower() for w in words) < 0.6 * len(words):
                errors.append(f"{q['id']}: opinion gold not reflected in the column")
    for q, term in OOC:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", all_text):
            errors.append(f"out-of-corpus term '{term}' appears in the corpus")
    cats = {}
    for q in qs:
        cats[q["category"]] = cats.get(q["category"], 0) + 1
    tiers = {t: sum(1 for d in docs.values() if d["tier"] == t) for t in (1, 2, 3)}
    print(f"{len(docs)} documents (tiers {tiers}), {sum(len(d['pages']) for d in docs.values())} pages, {len(qs)} questions {cats}")
    print("VALIDATION PASSED" if not errors else f"VALIDATION FAILED: {len(errors)} problem(s)")
    for e in errors[:40]:
        print(" -", e)
    return not errors


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/synthetic_large")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--scale", type=int, default=1, choices=[1, 2], help="1 = about 195 documents, 2 = about 315")
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--check", metavar="DIR", help="only validate an existing folder")
    a = ap.parse_args()
    if a.check:
        raise SystemExit(0 if check(a.check) else 1)
    builder = build(a.seed, a.scale)
    h = write(builder, a.out, a.zip)
    print(f"Wrote {a.out}  (seed {a.seed}, scale {a.scale}, content hash {h})")
    raise SystemExit(0 if check(a.out) else 1)
