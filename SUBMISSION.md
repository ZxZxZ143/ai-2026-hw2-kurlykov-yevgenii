# HW2 submission

**Name:**
**Student ID:**
**Group:**
**Repository:**

## AI tool disclosure

State which AI tools you used and for what. Expected and fine; undisclosed use
is not. If you used a model to help you draft a prompt, say which prompt.

>I used ChatGPT (GPT-5.6 Sol) to discuss the assignment requirements, help with Python implementation and debugging, and draft/refine the prompts used in the three sublabs.
>
>Specifically, ChatGPT helped me draft:
>- the role/system prompts in Sublab Easy;
>- the compression prompt in Sublab Medium;
>- the CV extraction and scoring prompts in Sublab Hard.
>
>I used `gpt-5.6-luna` through the OpenAI API for the actual experiments required by the assignment. The results and numbers reported in `SUBMISSION.md` are from my own program runs.

---

## Sublab Easy — one task, four roles

### Decisions per role

One row per enquiry. In each cell write the `decision` your run returned, and
whether it agrees with `expected` in `data/enquiries.json`:

| Enquiry | policy_officer | front_desk | auditor | bilingual_clerk |
|---|---|---|---|---|
| E-01 | granted — yes | granted — yes | more_info — no | granted — yes |
| E-02 | more_info — yes | more_info — yes | more_info — yes | more_info — yes |
| E-03 | refused — yes | more_info — no | refused — yes | refused — yes |
| E-04 | refused — yes | more_info — no | refused — yes | refused — yes |
| E-05 | granted — yes | granted — yes | more_info — no | granted — yes |
| E-06 | granted — yes | granted — yes | more_info — no | granted — yes |
| E-07 | granted — yes | granted — yes | more_info — no | granted — yes |
| E-08 | not_found — yes | not_found — yes | not_found — yes | not_found — yes |
| E-09 | refused — yes | more_info — no | refused — yes | refused — yes |
| E-10 | more_info — yes | more_info — yes | more_info — yes | more_info — yes |
| **agrees with `expected`** | **10/10** | **7/10** | **6/10** | **10/10** |
| **parsed** | **10/10** | **10/10** | **10/10** | **10/10** |
| **schema-valid** | **10/10** | **10/10** | **10/10** | **10/10** |

### Which field moved, on which enquiry, under which role

| Field | Enquiries that moved | Role(s) that moved it |
|---|---|---|
| `found` | none | none |
| `decision` | E-03, E-04, E-09; E-01, E-05, E-06, E-07 | front_desk; auditor |
| `amount` | E-01, E-05, E-06, E-07 | auditor |
| `missing_documents` | none | none |

Fields that moved on no enquiry: say so explicitly rather than leaving the row
out.

### Raw replies

Paste the full reply for **one enquiry where a role changed the decision** away
from the policy officer's:

```
     {
        "applicant_id": "A-203",
        "found": true,
        "decision": "more_info",
        "amount": 0,
        "missing_documents": [],
        "reason": "The application cannot be granted because the recorded GPA is 2.4, below the minimum required GPA of 2.67."
      },
```

Paste the full reply for **E-07 (the Kazakh enquiry)** from the bilingual
clerk, so the `reason` language is visible:

```
     {
        "applicant_id": "A-201",
        "found": true,
        "decision": "granted",
        "amount": 250000,
        "missing_documents": [],
        "reason": "Сіздің GPA көрсеткіші 2.67-ден жоғары, табыс санатыңыз 1 және қажетті құжаттарыңыз толық. Сізге 250000 теңге грант тағайындалды."
      },
```

### Written answers

**1. Which fields are role-sensitive and which are not?** Point at rows in your
tables.

> In my run, decision was the most role-sensitive field. The front_desk changed it on E-03, E-04 and E-09, while the auditor changed it on E-01, E-05, E-06 and E-07. amount was also role-sensitive, but only indirectly: it changed on the same four auditor cases because granted became more_info, so the grant amount became 0.
found and missing_documents were not role-sensitive at all. Neither field moved on any enquiry under any role. The bilingual_clerk also did not change any of the four structured fields, which is what I expected because its role only changes the language of reason, not the policy outcome.

**2. Which enquiries are most sensitive to the role, and why those?** Say what
E-03, E-04, E-07 and E-10 are each testing.

>E-03 and E-04 were highly role-sensitive because both are cases where the normal policy outcome is refused, so the front_desk role changes the decision to more_info. E-03 tests a refusal caused by GPA below the minimum, while E-04 tests a refusal caused by an income band outside the allowed range.   enquiries
E-07 tests language rather than policy. It is the same applicant as E-01, but the enquiry is in Kazakh. The structured result stayed the same, while the bilingual_clerk returned the reason in Kazakh, so this enquiry tests whether language can change without changing the decision.   enquiries
E-10 tests whether the model trusts the record or the applicant's claim. The user says that the id card was uploaded, but the record still does not contain it, so the correct result remains more_info with id_card missing. All roles kept that result, which shows that the source-of-truth rule held.

**3. Where does discretion belong — the role paragraph, or code that reads
`decision` afterwards?** Say what a downstream program can and cannot tell
about which role produced a record.

>The experiment shows that discretion can be expressed in the role paragraph, because changing only the role changed decision for some enquiries. However, if the decision has real consequences, I would not rely on the role prompt alone.
A downstream program that receives only the final JSON can see values such as decision, amount, and missing_documents, but it cannot reliably know why that decision was produced or which role caused it unless the role is explicitly stored as metadata. For example, more_info could come from the policy because a document is missing, from the front_desk replacing a refusal, or from the auditor refusing to grant on the first reading.
Therefore, role-based discretion can live in the prompt for the experiment, but production code should keep the role explicitly and apply or verify important business rules after the model response.

**4. Is a role a boundary?** Say in Week 2 terms what the role paragraph is
made of, and what you would put in code — not in the prompt — if a wrong
`decision` were expensive.

>No. A role is not a security or correctness boundary. In Week 2 terms, the role paragraph is still just tokens added to the model's input context. It can influence the continuation, but it does not guarantee that the model will obey it. The assignment itself makes this distinction important: the role changes behavior, but it is not a security control.
If a wrong decision were expensive, I would put the critical rules in deterministic code. The program should validate the JSON, verify that the applicant exists, check GPA, income band and required documents directly from the records, compute the allowed amount itself, and reject or override any model output that violates those rules. I would also log which role produced the response and keep the raw model output for auditing.

---

## Sublab Medium — memory you choose

### Tokens per call

| Call | A — never compressed | B — compressed at the `compress` turn |
|---|---:|---:|
| 1 | 749 | 749 |
| 2 | 861 | 885 |
| 3 | 924 | 971 |
| 4 | 994 | 1047 |
| 5 | 1041 | 1101 |
| 6 | 1121 | 1165 |
| 7 | 1195 | 1251 |
| 8 | 1275 | 1329 |
| 9 | 1336 | 1410 |
| 10 | 1438 | 1305 (`compress`) |
| 11 | 1516 | 1042 |
| 12 | — | 1104 |
| **peak** | **1516** | **1410** |
| **total for the run** | **12450** | **13359** |

### Probes after the conversation

| Probe | Tests | A retrieved? | A answer | B retrieved? | B answer |
|---|---|---|---|---|---|
| Q-1 identity | turn 1 | yes | You are **Daniyar Qoshan**, applicant **A-202**. | yes | You are **Daniyar Qoshan**, applicant **A-202**. |
| Q-2 missing document | turn 5 | yes | Your **id card** is still missing from the official record. | yes | Your **ID card** is still missing from the official record. |
| Q-3 band and amount | turns 3–4 | yes | Your official record lists your income band as **2**, corresponding to a grant amount of **150,000 KZT**. | yes | Your recorded income band is **2**, which corresponds to **150,000 KZT**. |
| Q-4 the constraint | turn 6 | yes | You said you can come to the office on **Thursdays**. The official records do not specify office hours or submission days. | yes | You can come to the office on **Thursdays** to submit your ID card. |
| Q-5 the open question | turn 7 | yes | You asked whether a **scanned letter from your employer** would count or whether you needed to provide the **original**. I said the policy does not specify whether an employer’s letter, scanned or original, is accepted. | yes | You asked whether a **scanned employer letter would count**, or whether the **original is required**. That has not been clarified in the available records. |
| **retrieved** | | **5/5** | | **5/5** | |

### The state my compression produced

```json
{
  "applicant_id": "A-202",
  "topic": "Study grant eligibility and document submission",
  "facts": [
    "The applicant's name is Daniyar Qoshan.",
    "The applicant sent their transcript last week.",
    "The applicant's income band is 2, according to their family's certificate.",
    "The applicant could not upload their ID card because the scanner at home broke.",
    "The applicant says they can only come to the office on Thursdays because they have lab all week otherwise.",
    "The applicant says their sister Aruzhan applied last year and is also on file."
  ],
  "decisions": [
    "The applicant currently does not qualify for the study grant because the ID card is missing from the official record.",
    "The transcript and ID card are required documents.",
    "If the ID card is added to the official record, the potential grant amount is 150,000 KZT.",
    "Applicants are assessed individually, so the sister's record does not change the applicant's eligibility."
  ],
  "constraints": [
    "The applicant can submit the ID card only on Thursdays.",
    "The applicant has lab commitments throughout the rest of the week.",
    "The ID card must be added to the official record before the application can qualify."
  ],
  "open_questions": [
    "Whether a scanned employer letter counts or whether the original is required.",
    "Whether the grant decision would be made the same day if the applicant brings the ID card on Thursday."
  ],
  "language": "English and Kazakh"
}
```

### Written answers

**1. What did compression buy?** Peak tokens both ways, probes retrieved both
ways, and — if a probe was lost — which one and which turn it came from.

>Compression reduced the peak input size from 1,516 tokens in the uncompressed run to 1,410 tokens in the compressed run, a reduction of about 7%. At the same time, both runs retrieved 5/5 probes, so none of the tested information was lost. The compressed state retained the applicant identity, missing ID card, income band and grant amount, Thursday constraint, and the unresolved employer-letter question.
However, compression did not reduce the total input cost in this short conversation. The uncompressed run used 12,450 input tokens, while the compressed run used 13,359, because the compression operation itself required an additional model call. The benefit appears on later calls: after compression, the probe requests were around 1,160 input tokens instead of about 1,550.

**2. Why must the state be structured rather than a paragraph?** You could have
asked for "a summary". Say what changes when the summary is an object with
named fields.

>A paragraph summary is readable for a person, but the program cannot reliably know where one type of information ends and another begins. With a structured state, information has named fields such as facts, decisions, constraints, and open_questions. The application can validate their types, require every field to exist, and reject a malformed summary before deleting the original conversation.
The structure also forces the model to distinguish different kinds of memory. For example, the Thursday availability belongs in constraints, while the employer-letter question belongs in open_questions. In a free-text paragraph those details could easily be merged, omitted, or become difficult for code to retrieve reliably. The schema additionally forbids unexpected fields, which makes different compression runs comparable.

**3. What is missing from your state that you would add?** Name what you would
add and what you would drop to pay for it.

>I would add provenance, for example a source turn or source type for important memory items. The current state preserves facts such as the income band and Thursday availability, but after compression it no longer tells the program exactly where each statement came from. This would be useful when distinguishing an applicant's claim from an official record or when auditing how a remembered fact entered the conversation.
To pay for it, I would remove some redundant text from decisions. For example, statements such as “the transcript and ID card are required documents” can already be reconstructed from the policy and do not need to consume memory on every later call. I would prefer a smaller number of high-value remembered facts with provenance over repeating information that is already present in the permanent system context.

**4. When is compression the wrong choice?** Name a conversation where it would
lose something that cannot be recovered, and say whether your program would
notice.

>Compression is the wrong choice when the exact wording or sequence of the conversation matters. For example, in a legal complaint, consent flow, financial dispute, or conversation containing an exact promise made by an employee, replacing the transcript with a summary could lose the precise wording, order, or qualification of a statement. Once the original turns are discarded, that information cannot be reconstructed from the compressed state.
My program would not necessarily notice this loss. It validates that the memory object has the correct schema, but schema validity only proves that the object has the expected fields and types. It does not prove that every important detail from the original conversation survived. In this experiment the five probes provide an external check and all five survived, but in a real conversation there may be important details for which no probe exists. Therefore, for high-stakes conversations I would retain the original transcript and use compressed state only as working memory, not as the only copy.

---

## Sublab Hard — stories in, CVs out, the best candidate by code

### Part 1 — extraction

| Story | Parsed? | Valid? | Fields that came back `null` | Traps hit |
|---|---|---|---|---|
| story-01 | yes | yes | `candidate_id` | `missing_information` |
| story-02 | yes | yes | `candidate_id`, `graduation_year`, `gpa_4_scale` | `non_published_outputs`, `missing_information` |
| story-03 | yes | yes | `candidate_id` | `gpa_conversion`, `non_published_outputs`, `missing_information` |
| story-04 | yes | yes | `candidate_id` | `non_published_outputs`, `missing_information` |
| story-05 | yes | yes | `candidate_id` | `non_published_outputs`, `missing_information` |
| story-06 | yes | yes | `candidate_id`, `graduation_year`, `gpa_4_scale` | `non_published_outputs`, `contradiction`, `missing_information` |

The four traps, for reference: no GPA stated · a GPA on another scale · a paper
that is not published · a story that contradicts itself.

Paste the extraction for **story-06**, the one that contradicts itself:

```json
{
  "candidate_id": null,
  "full_name": "Nurzhan Abilov",
  "degree": "BSc in Statistics",
  "graduation_year": null,
  "gpa": {
    "gpa_4_scale": null,
    "original_value": null,
    "original_scale": null
  },
  "languages": [
    "Kazakh",
    "Russian",
    "English"
  ],
  "published_peer_reviewed_outputs": 1,
  "other_publication_statuses": [
    {
      "status": "poster",
      "evidence": "One poster at a local event, which I do not think counts."
    }
  ],
  "relevant_experience_months": 40,
  "uncountable_experience": [],
  "evidence": {
    "candidate_id": null,
    "full_name": "Nurzhan Abilov",
    "degree": "I graduated in 2024 with a BSc in Statistics.",
    "graduation_year": [
      "I graduated in 2024 with a BSc in Statistics.",
      "I am currently a final-year student graduating in 2026"
    ],
    "gpa": [
      "My GPA was 3.2.",
      "Actually I should double-check that, I think it was 3.5 — the 3.2 might be from the transcript I printed in third year."
    ],
    "languages": "Languages: Kazakh, Russian, English.",
    "published_outputs": "one paper published, in a peer-reviewed proceedings, on survey weighting.",
    "experience": "I have been at an insurance analytics team since February 2023, which is about forty months."
  },
  "ambiguities": [
    {
      "field": "graduation_year",
      "claims": [
        "I graduated in 2024 with a BSc in Statistics.",
        "I am currently a final-year student graduating in 2026"
      ]
    },
    {
      "field": "gpa",
      "claims": [
        "My GPA was 3.2.",
        "Actually I should double-check that, I think it was 3.5 — the 3.2 might be from the transcript I printed in third year."
      ]
    }
  ]
}
```

### Part 2 — scores and the winner

| Candidate | academic (0–5) | research (0–5) | experience (0–5) | weighted total (code) |
|---|---:|---:|---:|---:|
| story-01 | 5.0 | 5.0 | 2.0 | 4.40 |
| story-02 | 3.0 | 0.0 | 5.0 | 2.50 |
| story-03 | 4.9 | 2.5 | 2.9 | 3.78 |
| story-04 | 4.0 | 2.5 | 5.0 | 3.75 |
| story-05 | 5.0 | 2.5 | 1.25 | 3.50 |
| story-06 | 2.0 | 2.5 | 5.0 | 2.75 |

**Winner, computed by my code: story-01 — Aziza Bekova, 4.40**

**The model's prose answer, asked separately ("who should win?"):**

>I recommend **Aziza Bekova** for the scholarship. Her story provides the strongest combination of academic achievement—a **3.8/4.0 GPA**—and research output, with **two published peer-reviewed papers**. Although her directly relevant experience is limited to eight months, the strength and clarity of her academic and publication record make her the most compelling candidate overall.


### Part 3 — written answers

**1. Which rule did you have to add, and what broke without it?** Name the
story that forced it.

>I had to make the publication rule more explicit: an output should count as a published peer-reviewed output only when the story establishes both that it is published/accepted and that it is peer-reviewed. story-02 forced this clarification. It says that Dias has a published paper in student conference proceedings, but it never establishes that the proceedings are peer-reviewed. In the final extraction this paper was therefore recorded separately and published_peer_reviewed_outputs remained 0. Without this rule, the model could have treated the word “published” alone as sufficient and incorrectly increased the research count and score.

**2. Where did the model guess, and where did your code have to decide?** One
example of each, from your run.

>The model had discretion when assigning intermediate rubric scores because the rubric mainly defines the endpoints. For example, story-03 had one published peer-reviewed paper, and the model assigned a research score of 2.5/5. That value is a model judgement rather than a deterministic calculation.
The code decided the final weighted totals and ranking. For example, for story-01 it used the model's scores academic=5, research=5, and experience=2, then calculated 0.5×5 + 0.3×5 + 0.2×2 = 4.40. The Python code then sorted all six totals and selected story-01 as the winner.

**3. Did your prose ranking and your computed ranking agree?** Say which one
you trust and why — and if they agreed, what you would need to see before
trusting the prose one alone.

>Yes. Both methods selected Aziza Bekova (story-01). The computed ranking gave her 4.40, and the separate prose call also recommended her because of her strong academic record and two published peer-reviewed outputs. 
I trust the computed ranking more because its inputs are explicit structured scores and the weighted calculation is deterministic and inspectable. The prose recommendation may reach the same result, but it does not guarantee that the model applied all weights consistently. Before trusting the prose result alone, I would want repeated evidence that it applies the same rubric consistently and exposes the criterion scores and calculation behind its recommendation.

**4. The rubric has no anchor for a contradicted field.** The stories say 3.2
and then 3.5; the rubric defines a 0 and a 5 and nothing in between for this
case. Say what you did and what the rule should be.

>In story-06, the story gives GPA values of 3.2 and 3.5, and also gives conflicting graduation information. I did not choose one value or average them. The extractor set both gpa_4_scale and graduation_year to null and stored both claims in ambiguities, as required by the contradiction rule. 
The scoring model then returned an academic score of 2, using the remaining non-contradicted academic information rather than reconstructing the missing GPA.   
I think the rubric should define this case explicitly. A contradicted numeric field should be treated as unavailable and excluded from scoring rather than inferred or averaged. The criterion should then be scored only from uncontested evidence; if the rubric does not provide enough anchors to do that consistently, the candidate should be sent for manual review instead of letting the model invent an intermediate rule.

**5. How close were your top two candidates?** If they were within 0.05, say
what you would tell the committee and what you would change in the extraction
to make that call defensible.

>The top two were not especially close. story-01 scored 4.40 and story-03 scored 3.78, giving a gap of 0.62. Therefore, the special 0.05 near-tie case did not apply in my run.   
If the gap had been within 0.05, I would tell the committee that the ranking was too sensitive to model judgement to treat the ordering as decisive. I would re-check the extraction evidence, especially converted GPA, publication status, and counted experience months, and ideally perform a second independent extraction or manual review before making the final decision.

---

## Reflection (optional, one short paragraph)

Having now written a role prompt, compressed a conversation, and ranked six
extractions — what will you do differently the next time you build something
that has to get reliable structured output out of a model?

>From the very beginning, I will separate the responsibilities of the model and the deterministic code. In critical areas, I will aim to rely more on deterministic logic, carefully validate the LLM's responses, and correct them if necessary.
