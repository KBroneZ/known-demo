# Local PR: root-canal-extraction-how-decide-austin (clinic-a)

- Status: **needs-human**; verdict path: BLOQUEAR; auto-fix rounds: 0
- Topic: wondering if i should get the root canal or just have them pull the tooth?
- Cost: $0.0293 (2 input / 1519 output tokens, excluding QA calls' tokens)
- Time: 42.6 s wall (brief 0.0s, draft 14.59s, qa 28.0s)

## A person must

- [ ] BLOQUEAR (model only, confirm or dismiss) false_medical_claim: 'Call soon if you have tooth pain that lingers or wakes you at night, swelling in your gums or face, ': Facial swelling can signal a spreading infection that needs same-day care, and the post omits the ficha's emergency guidance (trouble breathing or swallowing, or swelling spreading to the face or neck, means going to an emergency room or calling 911).
- [ ] BLOQUEAR (model only, confirm or dismiss) fact_vs_ficha: 'Our published prices include a new patient exam with X-rays for $129 and an emergency exam for $95.': The ficha limits the $129 price to new patients paying without insurance, and the post states it without that qualifier.

## Files

brief.md, draft.md, qa-r*.json, changes.diff, needs-human.md (not published)
