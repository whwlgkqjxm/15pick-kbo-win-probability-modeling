# Portfolio and interview guide

## 30-second description

I built a multi-season KBO win-probability research pipeline to test whether role-specific player-performance indices add signal beyond team strength. The project covers official data collection, 65,554 player-game identities, strict-prior feature engineering, temporal CV, model and training-strategy comparison, ablation, calibration, bootstrap uncertainty, reproducibility, and prospective validation design.

## Strong technical stories

1. **Identity defect:** explain how side-specific coverage exposed the home/away starter-ID asymmetry and how 832/832 starter eligibility was recovered.
2. **Invalidated conclusion:** explain why the V5 ceiling claim was suspended after role contamination was discovered.
3. **Negative model result:** explain why 763 features and nine model families did not beat regulated logistic regression.
4. **Domain ambiguity:** explain why actual relief pitchers cannot be used pregame and why the tested pool average diluted signal.
5. **Scientific status:** explain the difference between within-row leakage control and repeated inspection of a development period.
6. **Reproducibility defect:** explain why a polished public script was insufficient until solver, deterministic ordering, bootstrap, and model replay matched the frozen evidence.

## Skills demonstrated

- data collection and provenance;
- entity resolution;
- feature engineering and temporal joins;
- probability modeling and calibration;
- temporal validation and clustered uncertainty;
- ablation and model-selection discipline;
- failure analysis and root-cause correction;
- software packaging, testing, CI, and artifact hashing;
- communication of limitations and valid claims.
