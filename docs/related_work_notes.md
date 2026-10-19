# Related-work notes (ViAdminShift)

Every entry in the paper's bibliography was checked against its primary page:
ACL Anthology `.bib` (used verbatim, key renamed), NeurIPS proceedings BibTeX, PMLR page meta tags,
OpenReview (venue), or the arXiv API record. 39 bib entries; 38 are cited in the related-work section.
`gao2025localbench` is kept for possible use and is not cited.
Test compile with IEEEtran + `cite`: no undefined citations, no BibTeX warnings. The section fills about 0.9 page in two columns.

## Corrections to the task brief (please propagate)
- **Wallat et al. 2026** (2026.findings-acl.103) has **three** authors: Wallat, Nejdl, **Sikdar**. Cite it as "Wallat et al.".
- **arXiv 2506.07270** is *not* titled "Temporal Wiki QA". It is Özer & Yıldız, "Question Answering under Temporal Conflict: Evaluating and Organizing Evolving Knowledge with LLMs". It *introduces* two benchmarks named "Temporal Wiki" and "Unified Clark".
- **arXiv 2512.14554**: the arXiv listing and API still use the title "VLegal-Bench: Cognitively Grounded Benchmark for Vietnamese Legal Reasoning of LLMs" with 9 authors (Dong, N.T. … Vu, B.).
  - The **v5 full text** is retitled "Benchmarking Vietnamese Legal Knowledge of Large Language Models" (benchmark name "VietLegal").
  - The same title appears as a **poster at the ICML 2026 AI for Law Workshop**, which is not the main conference (icml.cc/virtual/2026/80607). That listing has a different author list that adds Dung D. Le.
  - We cite the arXiv record as `dong2025vlegal`, with `howpublished = arXiv:2512.14554v5`. We chose `year = 2025` on purpose: it is the v1 submission year (16 Dec 2025). arXiv's auto-generated BibTeX says 2026 (v5 date). Either is defensible; please don't silently "fix" it.
  - **"Recency blindness" is verified in the v5 body** (Level 3, Article/Clause Prediction). Models select outdated legislation over correct 2024–2025 instruments. Every evaluated model got the questions on the Road Traffic Order and Safety Law 2024, the Law on Organization of People's Courts 2024, and Decree 37/2025/ND-CP wrong. The term does not appear in the abstract.
- **HoH** exists: ACL 2025 long paper, 2025.acl-long.301 (Ouyang et al., USTC), arXiv 2503.04800. It is a dynamic benchmark of how *outdated documents in the retrieval corpus* hurt RAG. It is built with token-level diffs and LLM pipelines.
- **The Token Tax** exists: AfricaNLP 2026, 2026.africanlp-main.10 (Lundin et al.), arXiv 2509.05486. It uses AfriMMLU (16 African languages, 10 LLMs). Fertility predicts lower accuracy.
- **arXiv 2604.16270** is a single-author paper (Van-Truong Le). It evaluates GPT-4o, Claude 3 Opus, Gemini 1.5 Pro and Grok-1 on *legal text simplification*, using 60 articles and an error typology. It says nothing about recency. The arXiv comment says it was accepted at FJCAI 2026. We cite it as arXiv.

## One line per cited paper (key finding → how we differ)

### Temporal / outdated knowledge
- `dhingra2022time` (TACL 2022, TempLAMA): probes facts that change over time; time-aware LMs. → English Wikidata slices; no single real event, no control group.
- `zhang2021situatedqa` (EMNLP 2021): answers depend on temporal/geographic context; about 16.5% of NQ-Open is context-dependent. → We fix the context (after 1/7/2025) and test whether the model updated.
- `jang2022temporalwiki` (EMNLP 2022): lifelong benchmark built from consecutive English Wikipedia/Wikidata snapshot diffs. → Diffs mix unrelated changes; ours is one coherent event that entails all its changes.
- `liska2022streamingqa` (ICML 2022): QA over 14 years of time-stamped news; adapting semi-parametric and parametric models. → News-driven and English; we use a real administrative event in Vietnamese.
- `kasai2023realtime` (NeurIPS 2023 D&B): weekly questions about current events. → Rolling English news QA; no entailment structure.
- `vu2024freshllms` (Findings ACL 2024, FreshQA): fast-changing and false-premise questions; search augmentation. → General English; we isolate one structural change, with an `old_answer` label.
- `cheng2024dated` (COLM 2024): a model's effective knowledge cutoff can differ from its reported cutoff and varies by resource. → Motivates measuring whether models saw the 2025 reform at all (T0 headline items).
- `mousavi2024dyknow` (Findings EMNLP 2024): checks 24 LLMs against live Wikidata; outdatedness is widespread; editing methods help little. → Isolated time-sensitive triples; no event, no Vietnamese.
- `tang2025evowiki` (ACL 2025): stable/evolved/uncharted knowledge; models give outdated answers on evolved facts; RAG and continual learning are synergistic. → Auto-updated Wikipedia; not event-level.
- `zhu2025evolvebench` (ACL 2025): five temporal-competence dimensions; all 15 LLMs struggle with temporally misaligned context. → Same contrast.
- `ammarkhodja2024wikifactdiff` (LREC-COLING 2024): realistic (non-random) atomic fact updates from Wikidata diffs, labelled new/obsolete/static. → Atomic triples; we use entailed, hierarchical facts. (Its 327K size comes only from a search summary and is not used in the text.)
- `wallat2026when` (Findings ACL 2026, WikiRecentChanges): 2,380 mutable Wikidata facts with 2025 temporal qualifiers plus about 2,381 stable facts. Models often *verbalise* that a fact may have changed but rarely act on it. True and counterfactual contexts are **generated by Qwen-3-14B**. Updated relations are sports team, position held, awards, etc.; there is **no administrative/territorial relation** (checked in its Table 7). → Our items are entailed by one real event, the control is built in, and our contexts are real Wikipedia revisions.
- `ozer2025question` (arXiv 2506.07270): "Temporal Wiki" and "Unified Clark"; LLMs are misled when several versions of a fact appear in context. → Closest finding to our RQ3, but sports-biography-style facts in English.
- `wang2024lekube` (arXiv 2407.14192): legal knowledge-update benchmark using **synthetic** amendments to the Chinese Criminal and Civil Codes, written by law-school annotators. → Ours is a real, enacted change.
- `lyu2026kcbench` (arXiv 2609.03588): 238 multi-turn agent tasks, including multi-source temporal conflicts. → Agent setting; we use single-turn QA and RAG.

### Knowledge conflicts
- `longpre2021entity` (EMNLP 2021): entity-substitution conflicts; QA models over-rely on parametric memory. → Substituted (fake) contexts; ours are real.
- `xie2024adaptive` (ICLR 2024 spotlight): LLMs accept coherent counter-memory but show confirmation bias when the evidence partly agrees with memory. → Constructed counter-memory. Our mixed condition is a natural analogue, since the old passage agrees with memory.
- `su2024conflictbank` (NeurIPS 2024 D&B): large constructed benchmark of misinformation, temporal and semantic conflicts. → Constructed claims; ours come from one real event.
- `hou2024wikicontradict` (NeurIPS 2024 D&B): real contradictions between Wikipedia passages. → Real but static contradictions; ours are old-vs-new revisions of the *same* article.
- `xu2024knowledge` (EMNLP 2024): survey of context–memory, inter-context and intra-memory conflicts.
- `ouyang2025hoh` (ACL 2025): outdated documents in the RAG corpus distract models from correct information and can mislead them even when current information is available. → **Nearest RAG neighbour.** We differ in having a single coherent event, Vietnamese text, paired old/new revisions of the same article, a 2x2 changed/unchanged control, and the simple mitigations (date stamp, recency order, system date).

### Knowledge editing
- `cohen2024evaluating` (TACL 2024, RippleEdits): an edit should propagate to entailed facts. Besides counterfactual splits it has a **RECENT** split (2,000 triples recently inserted into Wikidata), checked in the PDF. → Those are still independent triples injected by editors; we observe ripple effects of a real-world "edit" in models without applying any edit.
- `zhong2023mquake` (EMNLP 2023): multi-hop questions to test whether edits propagate. Two parts: MQuAKE-CF (counterfactual) and **MQuAKE-T** (about 1.8K real-world temporal updates from a Wikidata 2021-04 vs 2023-04 diff, each tied to one fact change), checked in the PDF. → Real but independent changes injected by editors; our ward→province questions are 1–2-hop entailments of one event.
- `chen2025uniedit` (NeurIPS 2025 D&B; arXiv 2505.12345): open-domain editing benchmark covering 25 domains; NMCS sampling for ripple effects; text generated by an LLM. → Synthetic edits.
- `peng2024event` (arXiv 2402.13093, ELKEN): event-level editing, where one event updates many triples; 1,515 event edits. → The closest *conceptual* match to "event-level update", but its edits are constructed and injected. Ours is a real event, measured rather than edited. Venue not found; cited as arXiv.

### Vietnamese benchmarks
- `dao2023vnhsge` (arXiv 2305.12199): national high-school exam; 9 subjects including geography; ChatGPT and BingChat near human level on geography and history. → Static, pre-reform geography.
- `nguyen2024villm` (arXiv 2404.11086): ViLLM-Eval, from the VLSP 2023 Vietnamese LLM shared task. → Static knowledge.
- `bui2025vmlu` (ACL 2025): VMLU, four datasets (general knowledge, reading, reasoning, dialogue). → Static.
- `dang2025vmmu` (arXiv 2508.13680): Vietnamese multimodal reasoning, about 2.5k questions. → Different modality.
- `do2026how` (SIGUL 2026): commonsense and arithmetic reasoning in Vietnamese (PhoGPT, Vistral, VBD-Llama, Llama-2). → Reasoning, not temporal.
- `dong2025vlegal` (arXiv 2512.14554v5): 10,450 expert-annotated legal samples; **recency blindness** finding. → The only Vietnamese work we found that reports outdatedness, and only as an error-analysis finding. It is not a temporal-update benchmark.
- `le2026benchmarking` (arXiv 2604.16270): legal simplification across 4 LLMs. → Not temporal.

### Tokenization / diacritics
- `petrov2023language` (NeurIPS 2023): the same text can need up to 15x more tokens across languages. → Motivates our diacritics ablation.
- `ahia2023all` (EMNLP 2023): per-token API pricing is unfair across languages.
- `lundin2026token` (AfricaNLP 2026): token fertility predicts lower accuracy on AfriMMLU across all 10 models and 5 subjects (checked in the Anthology abstract). → Their evidence is for African languages; we test Vietnamese with and without diacritics.
- `naplava2018diacritics` (LREC 2018): neural diacritics restoration; Vietnamese has the most diacritics among the languages they study.
- `pham2017use` (arXiv 1709.07104; IALP 2017 per arXiv comment, proceedings not checked): MT-based Vietnamese diacritic restoration.
- `alqahtani2019efficient` (EMNLP-IJCNLP 2019): A-TCN diacritization for Arabic, Yoruba and Vietnamese.

## Verified but not cited (available if space allows)
- LocalBench, arXiv 2511.10459 (US county-level local knowledge; 14,782 QA over 526 counties; static). In bib as `gao2025localbench`.
- ChroKnowledge, arXiv 2410.09870 (ICLR 2025 per arXiv comment).
- LLMLagBench, arXiv 2511.12116 (finds training boundaries empirically).
- When Benchmarks Age, arXiv 2510.07238 (EACL 2026 per arXiv comment; finds that factuality benchmarks themselves go stale).
- Global-Liar, arXiv 2401.17839 (factuality across time and regions).
- EVEDIT, arXiv 2402.11324 (event-based knowledge editing).

## Left out because they could not be verified or did not fit
- **VLSP shared-task overview papers.** VLSP is cited only through ViLLM-Eval, which states it was part of VLSP 2023. A "VLSP 2025 challenge: Vietnamese Semantic Parsing" paper (VNU J. Sci.) appeared in OpenAlex but is off-topic and was not checked.
- **Vietnamese geography or culture QA benchmarks.** None found apart from the geography subject in VNHSGE. VIVID (arXiv 2608.03095, figurative language, LREC 2026) is off-topic.
- **Vietnamese address parsing or normalisation.** No academic paper found (arXiv, OpenAlex, web). There are non-academic resources, not cited:
  - the GitHub rule-based converter `tranngocminhhieu/vietnamadminunits` (old 63-province addresses → new 34-province addresses);
  - the HF dataset `tmquan/sapnhap-bando-vn` (CC BY-NC 4.0), a mirror of sapnhap.bando.com.vn under Resolution 202/2025/QH15. It could be useful **as an extra cross-check source**;
  - the HF dataset `trucmtnguyen/vietnam-address-collection` (pre-merger addresses).
- **Springer LNCS chapter** "A Small Language Model and Domain-Specific Resources for Vietnamese Public Services" (Van Thai Le, Anh-Cuong Le; MIWAI 2025; doi 10.1007/978-981-95-4960-3_2). Crossref shows no abstract and the Springer page is paywalled/redirected, so we **could not confirm** whether it touches the 2025 restructuring. The title suggests public-service QA. Low risk, but read it before submission if possible.
- **Semantic Scholar API** returned HTTP 429 on every query. Google Scholar was not queried directly. Coverage came from: WebSearch (EN/VI/ZH/JA), the arXiv API (fielded abstract queries), OpenAlex, the HF datasets API, and Crossref.

## Novelty risk assessment

**Verdict: LOW risk.** We found no paper that uses Vietnam's 2025 restructuring as an LLM benchmark. We also found none, in any country, that uses a natural administrative or territorial reorganisation (provincial or municipal mergers, renamed units) as an LLM test bed.

What we searched:
- arXiv API, abstract fields:
  - Vietnam/Vietnamese × administrative/province/address × LLM;
  - "administrative divisions/units", "municipal merger", "boundary changes", "administrative/territorial reform" × LLM;
  - province/prefecture/county × merger/restructuring × LLM;
  - renamed place/city/country × LLM;
  - outdated/temporal × geographic/toponym/gazetteer × LLM;
  - Vietnamese × temporal/outdated/knowledge cutoff × LLM.
  - Result: **no relevant hits**.
- WebSearch:
  - English: Vietnam 2025 reform × LLM benchmark/address conversion; administrative boundary changes × LLM.
  - Vietnamese: "sáp nhập tỉnh … mô hình ngôn ngữ lớn", "sắp xếp đơn vị hành chính", "ChatGPT trả lời sai tỉnh mới".
  - Chinese: 大模型 行政区划调整 撤县设区.
  - Japanese: 市町村合併 大規模言語モデル.
  - Korea/Japan/China/Indonesia administrative change × knowledge cutoff; renamed countries/capitals × LLM.
  - Result: only news about the reform, policy papers, and generic cutoff blogs.
- OpenAlex: "Vietnam administrative merger LLM", "sáp nhập tỉnh mô hình ngôn ngữ lớn", Vietnamese address parsing/normalization. Result: only social-science papers on the merger, e.g. a 2026 Aust. J. Public Admin. paper on public sentiment about the merger, which has no LLM content.
- HF datasets: "sap nhap", "vietnam address/province/ward", "34 tinh", "vietnamadminunits". Result: data mirrors only; no QA or LLM benchmark.

Nearest neighbours, and why they do not pre-empt us:
1. **WikiRecentChanges** (Wallat et al., Findings ACL 2026): https://aclanthology.org/2026.findings-acl.103/. Real 2025 changes plus a stable control, but isolated Wikidata triples, mostly sports and office roles, LLM-generated contexts, English, and no admin relations.
2. **HoH** (ACL 2025): https://aclanthology.org/2025.acl-long.301/. Outdated documents in RAG; general, not a single event, not Vietnamese.
3. **ELKEN / event-level editing** (arXiv 2402.13093): https://arxiv.org/abs/2402.13093. The event→many-triples idea, but with constructed edits.
4. **LeKUBE** (arXiv 2407.14192): https://arxiv.org/abs/2407.14192. Legal updates with synthetic amendments.
5. **VLegal-Bench / VietLegal** (arXiv 2512.14554v5): https://arxiv.org/abs/2512.14554. A Vietnamese benchmark that reports "recency blindness", but legal and static, with recency found only in error analysis.
6. **LocalBench** (arXiv 2511.10459): https://arxiv.org/abs/2511.10459. US county-level local knowledge; static, no change.
7. **Temporal Wiki / Unified Clark** (arXiv 2506.07270): https://arxiv.org/abs/2506.07270. Multiple fact versions in context.

Residual risks:
- (a) The reform is about 15 months old. A Vietnamese-venue paper (VLSP 2025/2026, KSE, SoICT, RIVF, MAPR, FAIR, or a Vietnamese-language journal) may exist without being indexed by arXiv or OpenAlex. Search those proceedings once more right before submission.
- (b) Semantic Scholar and Google Scholar were not queried.
- (c) The MIWAI 2025 public-services chapter is unread.

Recommended phrasing: keep "to our knowledge, the first Vietnamese benchmark built around a real-world temporal knowledge update". Do **not** claim to be the first benchmark using a natural event or to be the first temporal benchmark overall: WikiRecentChanges, HoH, EvoWiki and others use real changes. Our safe novelty is a *single event-level* administrative reform that entails thousands of facts, with an unchanged control, in Vietnamese, plus paired old/new revisions of real documents for RAG.
