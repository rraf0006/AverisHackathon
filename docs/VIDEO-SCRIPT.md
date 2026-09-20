# ShipCheck — 5-minute video script

One continuous read-through. Paste straight into a teleprompter or transcriber.
Timings below are measured from the actual word counts at a normal presenting
pace (~145 words per minute), not estimated. The spoken text runs **4 minutes 0
seconds**; read a little slower, with pauses, and it lands around **4:30**. Either
way it is comfortably inside the 5-minute cap, with room if Taabish's opening
runs over.

Speaking order is one contiguous block per person, matching the slide deck.

---

## 1. TAABISH — slides 1–2 — ~30 sec

> **[REPLACE THIS BLOCK WITH TAABISH'S OWN SCRIPT]**
>
> Keep it to **30 seconds**. It has to land two things before Riely takes over:
> the scale of the problem (2,000 emails a day, draft Bills of Lading checked by
> hand against the Shipping Instruction, one miss ships a wrong document), and
> who the team is.
>
> If his version runs longer than 30 seconds, take the time out of slide 5 or
> slide 9 — not out of slide 7, which carries the results.
>
> *Fallback, if he doesn't send one in time:*
>
> "Averis's documentation team gets up to two thousand emails a day. Buried in
> them are draft Bills of Lading that must be checked, field by field, against
> the customer's Shipping Instruction. Miss one, and the container ships on a
> wrong document. We're CodePulse. I'm Taabish, I built the AI layer. Erwyna did
> full-stack and integration, Nandhini ran the AI accounts and validation,
> Charvhi added Malay and Chinese support, and Riely stress-tested the whole
> thing."

---

## 2. RIELY — slides 3–5 — 72 sec (175 words)

**Slide 3 — The Inbox Problem** *(bring the energy, this is the hook)*

One shared inbox, five kinds of email mixed together: BL checks, new Shipping
Instructions, invoice queries, updates and spam. Staff open each one by hand.
Every draft BL means comparing seven fields across two documents that label them
differently. One missed mistake means an amendment, a delay, and sometimes a
fine. That's the job ShipCheck takes over.

**Slide 4 — Our Solution**

ShipCheck sorts the entire inbox automatically — every email labelled, so
nothing stays buried. Every draft BL is checked against its Shipping Instruction
in seconds. And every result shows its evidence: click any field and you see the
exact line it came from. When it isn't sure, it says so.

**Slide 5 — How It Works**

Four steps. Sort — fast keyword rules, with AI stepping in only when the rules
aren't sure. Read — it opens txt, PDF, Word and Excel, and finds the seven
fields even when the labels differ. Compare — this is code, not AI, so the
result is deterministic and repeatable. Ask a person — anything unclear goes to
a review queue with the reason attached. It never guesses.

---

## 3. NANDHINI — slides 6–7 — 51 sec (124 words)

**Slide 6 — Where the AI Helps**

The AI is used where it earns its place, not everywhere. It sorts the emails the
keyword rules can't read confidently, in any wording or language. It matches
unfamiliar field labels and quotes the source text. Gemini reads scanned,
image-only PDFs that contain no text at all. And on every mismatch we find, the
AI independently re-reads both documents as a second reviewer — it agreed with
the rules forty-six times out of forty-six.

**Slide 7 — Proven on 520 Emails**

On the organisers' five hundred and twenty emails: every email sorted correctly,
forty-six out of forty-six mistakes caught, zero false alarms — scored with
their own answer checker. We also wrote a hundred automated tests using emails
and documents the system has never seen, including Malay, Chinese, Spanish and
Vietnamese.

---

## 4. CHARVHI — slides 8–9 — 48 sec (116 words)

**Slide 8 — The Impact**

That's about forty-four hours of staff time saved on this one batch, and it
scales — the rules sort five hundred and twenty emails in about a second, so two
thousand a day is comfortable. And the team trusts it, because every flag shows
its evidence.

**Slide 9 — Challenges We Solved**

The hard parts. Misleading subject lines — we trust the body, not the subject.
Company names that look different but aren't: L.L.C. versus LLC, A-slash-S
versus AS. Ports with two legitimate names — JNPT and Nhava Sheva are the same
place. Weights in tonnes on one document and pounds on the other. We found four
of those by deliberately trying to break our own system, and we fixed every one.

---

## 5. ERWYNA — slide 10 — 38 sec (18 sec spoken + 20 sec demo)

Next: connect straight to Outlook instead of files, learn from reviewer
corrections so the rules improve themselves, and add more languages and document
types.

The code is public on GitHub. Let me show you it running.

> **[DEMO — 20 sec, screen recording]**
> Open the Inbox. Click the email marked **DOESN'T MATCH**. Point at the two red
> rows — Consignee and Notify party. Click one row so the evidence line opens,
> showing the exact text pulled from each document. Then click **Needs a person**
> to show the queue, each with its reason.

Stop BL mistakes before they ship. Thank you.

---

## Recording notes

- Say numbers as words: "forty-six out of forty-six", "five hundred and twenty".
- The two lines that carry the most weight are *"zero false alarms"* (slide 7)
  and *"it never guesses"* (slide 5). Pause after both.
- Leave a half-second gap between speakers so the edit has somewhere to cut.
- If the whole thing runs long, cut slide 4 down first — slide 3 already makes
  the point, and slide 4 is the most compressible.
- There is roughly a minute spare. If Taabish's opening needs 60 seconds rather
  than 30, it still fits without touching anyone else's block.
