# HW2 — A grant office that answers in JSON

**Course:** CSS-4007 · Artificial Intelligence · Narxoz University
**Assigned:** Week 3 — *Prompting & Structured Output*
**Due:** see the LMS
**Points:** 4 pts total → **4%** of your final grade

You are building three programs for a (fictional) grant office. Six applicants
are on file, a rule decides who qualifies, and every answer has to come back as
one fixed JSON shape. The office is the setting, not the exercise. The exercise
is that **getting a model to produce something a program can rely on is a
design problem with measurable parts**: what you put in the system prompt, what
you choose to keep in the context, and what you do with the answer once you
have it.

This repository contains **data and this README. It contains no code.** You
write all three programs yourself, from the specifications below. That is
deliberate: the interesting decisions in this homework are the prompts, the
state you keep, and the rules you write down — not the plumbing, which you
already built in HW1.

It builds on what you already have. HW1 made you call models and read usage.
Week 2's deck showed you that a prompt is tokens entering the same stack and
that the model is continuing a document rather than following orders. Week 3's
deck turns that into roles, system instructions, schemas and validation, and
Week 4's into what actually goes into the context. You will use all of it, and
the written answers force you to explain your results in those terms rather
than in vibes.

## 0. How this works

You work in **your own fork** of this repository. Do not open pull requests
against it.

1. **Fork it** (the **Fork** button, top right). Keep your fork **public**, so
   the instructor can read it without being added to anything.
2. Clone *your fork* and work there.
3. Write the three programs described below. Put each one in the `sublab_*`
   directory named in its section — those directories contain nothing but a
   package marker.
4. Fill in `SUBMISSION.md`. **Everything is graded from that file** — your
   tables, your transcripts, your written answers. Code that runs but produces
   no numbers in `SUBMISSION.md` earns nothing.
5. Push to your fork, and submit your fork's link on the LMS before the deadline.

> There is no autograder. A human reads your `SUBMISSION.md` against your code.
> That cuts both ways: nothing checks your work as you go, so run things more
> than once and paste the numbers you actually got.

**What has to run.** Three commands, from the repository root, each printing
the tables you need for `SUBMISSION.md`:

| Sublab | You create | It runs as |
|---|---|---|
| Easy | `sublab_easy/role_prompts.py` | `python -m sublab_easy.role_prompts` |
| Medium | `sublab_medium/chat_memory.py` | `python -m sublab_medium.chat_memory` and `python -m sublab_medium.chat_memory --interactive` |
| Hard | `sublab_hard/cv_extract_and_rank.py` | `python -m sublab_hard.cv_extract_and_rank` |

Use those file names and module paths. The marker runs them. How you structure
the code inside them is up to you.

## 1. Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env .env             # then put your key in .env
```

You need one account:

| Provider | Env var | Used for |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `gpt-5.6-luna` |

All three sublabs run the same model, so the only thing that changes between
the runs you compare is what your program sends. That is what makes the
comparisons meaningful.

**`.env` is in `.gitignore`. Never commit a key.** Your fork is public, so a
committed key is readable by anyone, and bots scan GitHub for them within
minutes. A key pushed to GitHub is a
key someone else is already using — if it happens, revoke it immediately and
say so in `SUBMISSION.md`. Disclosure costs you nothing; a silent leaked key is
an integrity issue.

**Estimated total spend for the whole assignment: under $0.20.** Tens of short
calls to one cheap model, plus a handful of longer ones in Sublab Hard where
the model reads a page of text. If you are spending dollars, you have a bug —
probably a loop that never terminates, or a conversation you resend without
ever compressing it. Sublab Medium is partly about why that second one is a
*bill* problem, not just a correctness one.

## 2. What is in `data/`

| File | What it is |
|---|---|
| `records.json` | The six applicants on file: id, name, city, GPA, income band, documents |
| `policy.json` | The grant rule, in prose and in machine-readable form |
| `enquiries.json` | Ten scripted enquiries, each with the structured answer the record demands |
| `chat_script.json` | Sublab Medium's scripted conversation and its five probes |
| `memory_state.schema.json` | The shape the compressed conversation must take |
| `candidate_rubric.json` | Sublab Hard's three criteria, their weights, and the counting rules |
| `candidates/story-01.md` … `story-06.md` | Six scholarship candidates, as unstructured written applications |

**Read the data before you write anything.** `enquiries.json` includes
enquiries that are traps: a name that is not in the records, a person who
claims their file was updated when the record says otherwise, and an enquiry in
Kazakh. `expected` on each row is what the record and the rule demand — that is
the reference every role in Sublab Easy is measured against. It is *not* "the
truth about the applicant": in E-10 the applicant claims a document the record
does not show, and the record wins.

The contract every answer must take, in every sublab:

```json
{
  "applicant_id": "A-201",
  "found": true,
  "decision": "granted",
  "amount": 250000,
  "missing_documents": [],
  "reason": "GPA 3.4 and income band 1, with both documents on file."
}
```

`decision` is one of `granted`, `refused`, `more_info`, `not_found`. `reason`
is free text for a human; the other five fields are what a program reads, and
`found`, `decision`, `amount` and `missing_documents` are what gets checked.

## 3. Sublab Easy — one task, four roles (1 pt)

File: `sublab_easy/role_prompts.py`

One task, one model, one JSON shape, ten enquiries — and **four system
prompts**. The role is the only thing that changes between the four runs. Same
record block, same rule, same shape description, same enquiries: if the output
moves, the role moved it.

Write a system message for each of these four roles:

| Role | What it is told to be |
|---|---|
| `policy_officer` | Applies the rule exactly as written: grants what the rule allows, refuses what it refuses, asks for a missing document, softens nothing, and treats no claim in the enquiry as evidence |
| `front_desk` | Never turns an applicant away with a refusal: anything the rule cannot grant today comes back as `more_info`, with what the applicant would need to return with |
| `auditor` | Never grants on a first reading: reports what the record shows, marks anything needing a second reader as `more_info`, and names the rule or document it is relying on |
| `bilingual_clerk` | Decides exactly as the policy officer would, but writes `reason` in the language the enquiry was written in |

Run each role over all ten enquiries. For every (role, enquiry) record:
did the reply parse, does it satisfy the schema, and do the four structured
fields agree with `expected`?

Then the part that matters: for each of the four structured fields — `found`,
`decision`, `amount`, `missing_documents` — say **which enquiries moved away
from the policy officer, and under which roles**. A role that moved nothing is
a result, not a gap in your table; report it.

In `SUBMISSION.md` give the four role tables, the field-movement table, and
answer:

- **Which fields are role-sensitive and which are not?** Point at rows. One of
  the four roles is expected to move `decision` on some enquiries and one is
  expected to move only `reason` — say which is which from your own counts.
- **Which enquiries are most sensitive to the role, and why those?** Think about
  what E-03, E-04, E-07 and E-10 are testing before you answer.
- **Where does discretion belong** — in the role paragraph, or in code that
  reads `decision` afterwards? Your answer should say what a program downstream
  can and cannot tell about which role produced a record.
- **Is a role a boundary?** The auditor refuses to grant; the bilingual clerk
  writes in another language. Neither is a security control. Say in Week 2 terms
  what the role paragraph is made of, and what you would put in code — not in
  the prompt — if a wrong `decision` were expensive.

**Grading:** the four roles run with per-enquiry rows and the field-movement
table (0.6) + the four written answers (0.4).

## 4. Sublab Medium — memory you choose: the `compress` command (1.5 pt)

File: `sublab_medium/chat_memory.py`

The office assistant now remembers the conversation, which means your program
decides on every call what to send. Week 3's last points are exactly this: a
call is stateless, a chat application only looks like it remembers because it
resends the thread, and you cannot keep everything for five separate reasons.
Memory is not storage, it is selection.

Build a session with a switch in it:

- **Uncompressed.** The messages sent are the system message plus every turn so
  far, and the token count grows with the conversation forever.
- **Compressed.** When the applicant's turn is `compress` — the command, not
  something they said — your program asks the model to summarise the
  conversation into **one structured state object**, checks that object against
  `data/memory_state.schema.json`, throws the turns away, and continues from the
  state. From the next call on, the state is what is sent.

If the summary does not parse or does not validate, it must not silently
replace the conversation: say so, keep the history, and continue. Losing a
conversation to a malformed summary is the failure this design is meant to
prevent.

`data/chat_script.json` holds the twelve scripted turns, the `<compress>`
marker, and the five probes asked afterwards. Run the script twice — once with
the command acting, once with it skipped — so that both runs send the same
twelve turns. Record, for each call, the tokens you sent; and for each probe,
whether the answer actually contains the fact the probe is testing.

Also make `--interactive` work: a real chat where you can type `compress` and
watch what happens to what is sent, and where `tokens` prints what the last
call cost. Play with it before you write your answers; the scripted run gives
you the table, this gives you the feel of what a summary drops.

In `SUBMISSION.md` give both token tables (per call, and the peak for each
run), the five probe results for both runs, the state object your compression
produced, and answer:

- **What did compression buy?** Give the peak token count both ways and the
  number of probes retrieved both ways. If a probe was lost, name it and say
  which turn it came from.
- **Why must the state be structured rather than a paragraph?** You could have
  asked for "a summary". Say what changes when the summary is an object with
  named fields.
- **What is missing from your state that you would add?** The schema gives you
  seven fields; the conversation contains more than seven things. Say what you
  would add and what you would drop to pay for it.
- **When is compression the wrong choice?** Name a conversation where
  compressing would lose something that cannot be recovered, and say whether
  your program would notice.

**Grading:** both runs working, with the token tables, the probe results and
the state object (0.75) + the four written answers (0.75).

## 5. Sublab Hard — stories in, CVs out, the best candidate by code (1.5 pt)

File: `sublab_hard/cv_extract_and_rank.py`

The office has one funded scholarship and six applications. There is no form
and no structured data: `data/candidates/` holds six written stories, in
different registers, one of them in Kazakh. Your program has to read them,
build a structured record from each, have the model score them against a stated
rubric, and **decide the winner in code**.

### Part 1 — extract a CV from each story (0.5)

Design the record yourself, with at least these fields: candidate id, full
name, degree, graduation year, `gpa_4_scale` (and the scale the story used),
languages, number of **published** peer-reviewed outputs, total countable
months of relevant experience, and an evidence quote for each field you fill.
Add whatever else the stories make you need.

The rules go **in the prompt**, not in your head, and the marker checks that
they are there:

- A fact the story does not state is `null`. Never estimated. No GPA means no
  GPA — not an inferred one.
- A GPA on another scale is converted to a 4.0 scale, and the original scale is
  recorded beside it.
- A paper is published only when the story says published or accepted.
  *Submitted*, *under review*, *in preparation* and *in press* are not
  published: record them separately and do not count them.
- Contradictions are not resolved and not averaged: the field is `null`, and the
  contradiction is recorded.

For each story in `SUBMISSION.md`: did the reply parse, did it validate, which
fields came back `null`, and which of the traps above it hit.

### Part 2 — score, and compute the winner yourself (0.5)

`data/candidate_rubric.json` holds the three criteria, their weights and the
counting rules. Put them in the prompt and ask the model for **a 0–5 score for
each of the three criteria and nothing else it has to compute**. Then your code
computes the weighted total and names the winner.

That split is the point. A number in a sentence is not a number a program can
compare; a field is. So: the model scores, the code ranks.

Then, in a separate call, ask the model in prose which candidate should win.
Paste both answers.

### Part 3 — written answers (0.5)

- **Which rule did you have to add, and what broke without it?** Name the story
  that forced it.
- **Where did the model guess, and where did your code have to decide?** Give
  one example of each, from your own run.
- **Your prose ranking and your computed ranking — did they agree?** If they
  disagreed, say which one you trust and why. If they agreed, say what you
  would need to see before you would trust the prose one alone.
- **The rubric has no anchor for a contradicted field.** It says what a 0 means
  and what a 5 means; it does not say what to do when the story says 3.2 and
  then 3.5. Say what you did, and what you think the rule should be.
- **The top two candidates in your run: how close were they?** If they were
  within 0.05 of each other, what would you tell the committee — and what would
  you do differently in the extraction to make that call defensible?

**Grading:** extraction with the rules in the prompt and the trap table (0.5) +
scores, the computed total, the winner and the prose comparison (0.5) + the five
written answers (0.5).

The winner itself is not graded, and you will not be marked down for a
different order than your classmate's: the scores come from the model, so two
correct submissions can rank the same six stories differently. What is graded
is that the scores arrived as fields rather than in a sentence, that the total
was computed by your code rather than asserted by the model, and that you said
where the rules left you a gap.

## 6. Submission checklist

- [ ] `sublab_easy/role_prompts.py` runs all four roles and prints the field-movement table
- [ ] `sublab_medium/chat_memory.py` runs both modes, and `--interactive` accepts `compress`
- [ ] `sublab_hard/cv_extract_and_rank.py` extracts six records, scores them and computes a winner
- [ ] `SUBMISSION.md` complete, with every table and every written answer
- [ ] `.env` **not** committed (`git log --all -- .env` returns nothing)
- [ ] Your fork is public, and its link is submitted on the LMS

## 7. Academic integrity

Discuss concepts with classmates freely; the code and the written answers must
be your own. **Disclose AI tool assistance in `SUBMISSION.md`** — this is
expected and fine, and undisclosed use is not.

Note the obvious: every sublab here hands you a language model whose output you
are asked to judge, and a model writing your analysis for you is the subject of
the analysis, not a shortcut around it. In Sublab Hard in particular the
temptation is real — you are asked to rank six candidates by the model's own
scores, so a model that also writes your written answers is marking its own
homework. Your answers have to be about *your* run.
