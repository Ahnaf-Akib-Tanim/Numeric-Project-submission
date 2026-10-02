# CSE 402 — Simulating and Optimizing Emergency-Department Patient Flow

Numerical Analysis, Simulation and Modeling Sessional · Section C

Sudip Kumar Saha (2105152) · Ahnaf Akib Tanim (2105154) · Md. Shahjalal Rumman (2105165) ·
Md. Dulal Hossain (2105169) · Md. Shoaib Hossain (2105170)

---

## What is in this directory

| Path | What it is |
|---|---|
| **[`edsim/`](edsim/)** | **The project.** From-scratch discrete-event simulator, five work packages, all experiments, all results. **Start at [`edsim/README.md`](edsim/README.md).** |
| `healthcare-14-00099-v2.pdf` | The base paper — Lv, Liu, Yan & Wang (2026), *Healthcare* **14**(1), 99. |
| `Updated_Project_Proposal.md` | The approved proposal defining the five work packages. |
| `Project_Proposal.pdf` | The original proposal. |

## Run it

```bash
cd edsim
pip install -r requirements.txt

python tests/test_model.py          # 33 correctness checks   (~20 s)
python scripts/run_00_demo.py       # watch the simulator run (~15 s)
python scripts/run_all.py --quick   # whole study, fast pass  (~6 min)
python scripts/run_all.py           # whole study, full       (~35-50 min)
```

Outputs land in `edsim/results/` — tables, figures, per-replication data, and a provenance
log recording the exact command behind every file.

## Documentation

| Document | Answers |
|---|---|
| **[`edsim/docs/report/C_02.pdf`](edsim/docs/report/C_02.pdf)** | **The final report** (9 pages, ACM format). Full LaTeX source in `edsim/docs/report/`. |
| **[`edsim/docs/slides/C_02_slides.pdf`](edsim/docs/slides/C_02_slides.pdf)** | **The presentation** (14 slides, beamer 16:9). |
| [`edsim/docs/PROJECT_GUIDE.pdf`](edsim/docs/PROJECT_GUIDE.pdf) | **Start here.** A 31-page illustrated guide to the whole project: what the paper does, what we built, how every method works, which file does what, how to run it, the full results analysis, a paper-vs-ours comparison, and viva preparation. |
| [`edsim/README.md`](edsim/README.md) | What each Python file does, how to run everything, how the results are produced, what we had to decide ourselves, and how faithful the replication is. |
| [`edsim/docs/PAPER_MAPPING.md`](edsim/docs/PAPER_MAPPING.md) | Every equation, table and figure of the paper → the line of code that implements it; the ambiguities in the paper and how we resolved them. |
| [`edsim/docs/METHODS.md`](edsim/docs/METHODS.md) | The numerical methods written out in full: thinning, inverse-CDF sampling, the event loop, sample-average approximation, the penalty function, Nelder-Mead, common random numbers, the c·μ rule. |
| [`edsim/results/README.md`](edsim/results/README.md) | What is in the results folder and how to read it. |
| `edsim/results/RESULTS_SUMMARY.md` | *(generated)* The headline numbers. |
| `edsim/results/PROVENANCE.md` | *(generated)* Which command produced which file, when. |

## The five work packages

| WP | Owner | Contribution | Script |
|---|---|---|---|
| **WP1** | Ahnaf | Rebuild the paper's DES from scratch and validate it against every published KPI | `run_01_validate_paper.py` |
| **WP2** | Shoaib | Add the c·μ / WSEPT rule and the generalised c·μ rule — provably optimal queueing policies rather than heuristics | `run_03_wsept_policy.py` |
| **WP3** | Rumman | Replace brute-force grid search with a hand-implemented Nelder-Mead simplex plus a penalty function, and benchmark the simulation budget | `run_02_grid_search.py`, `run_04_nelder_mead.py` |
| **WP4** | Sudip | An explicit weekly cost model, and a joint search over integer physician rosters with the thresholds re-tuned inside each | `run_05_staffing_cost.py` |
| **WP5** | Dulal | Exact common random numbers, the variance reduction quantified, and the consolidated final comparison | `run_06_crn_variance.py`, `run_08_final_comparison.py` |
